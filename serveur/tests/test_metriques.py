"""Tests des métriques de génération : calculs, puis route complète avec un faux Ollama."""

import json
import os
import re

import httpx
import pytest

os.environ.setdefault("OLLAMA_MODEL", "modele-de-test")  # requis à l'import de l'application

from fastapi.testclient import TestClient  # noqa: E402

import serveur.app as application  # noqa: E402
from serveur import metriques as mesures  # noqa: E402

NOM = application.REGLAGES.ollama_modele
CLES_TICKET = {"id", "theme", "nom", "service", "source", "objet", "canal", "demande", "reponses", "pointCle", "attendu"}


# --- Calculs ------------------------------------------------------------------------


def chat(total, chargement, entree, sortie, duree_sortie):
    return {"total_duration": total, "load_duration": chargement, "prompt_eval_count": entree,
            "eval_count": sortie, "eval_duration": duree_sortie}


def test_cumul_sur_plusieurs_tentatives():
    cumul = mesures.CumulOllama()
    cumul.ajouter(chat(10_000_000_000, 2_000_000_000, 3400, 450, 9_000_000_000))
    cumul.ajouter(chat(8_000_000_000, 0, 3450, 430, 7_000_000_000))
    assert cumul.totaux() == chat(18_000_000_000, 2_000_000_000, 6850, 880, 16_000_000_000)
    assert mesures.tokens_par_seconde(cumul.totaux()) == 55.0  # 880 tokens en 16 s


def test_champ_absent_dans_une_tentative_vaut_null():
    cumul = mesures.CumulOllama()
    cumul.ajouter(chat(1, 2, 3, 4, 5))
    cumul.ajouter({"total_duration": 1, "eval_count": 4})  # les autres champs manquent
    totaux = cumul.totaux()
    assert totaux["total_duration"] == 2 and totaux["eval_count"] == 8
    assert totaux["load_duration"] is None and totaux["eval_duration"] is None
    assert mesures.tokens_par_seconde(totaux) is None


@pytest.mark.parametrize("valeur", [None, "12", -1, True])
def test_valeur_mal_formee_vaut_null(valeur):
    cumul = mesures.CumulOllama()
    cumul.ajouter({**chat(1, 1, 1, 1, 1), "eval_count": valeur})
    assert cumul.totaux()["eval_count"] is None


def test_fiche_du_modele():
    show = {"details": {"parameter_size": "8.2B", "quantization_level": "Q4_K_M", "family": "qwen3"}}
    assert mesures.extraire_fiche(show) == {"taille": "8.2B", "quantification": "Q4_K_M", "famille": "qwen3"}
    assert mesures.extraire_fiche({}) == {"taille": None, "quantification": None, "famille": None}
    assert mesures.extraire_fiche("illisible") == {"taille": None, "quantification": None, "famille": None}


@pytest.mark.parametrize(
    "modeles, attendu",
    [
        ([{"name": "m:8b", "size": 6_600, "size_vram": 5_544}], 0.84),
        ([{"model": "m:8b", "size": 6_200, "size_vram": 6_200}], 1.0),
        ([{"name": "autre", "size": 1, "size_vram": 1}, {"name": "m:8b", "size": 100, "size_vram": 32}], 0.32),
        ([{"name": "autre", "size": 1, "size_vram": 1}], None),  # modèle non chargé
        ([{"name": "m:8b", "size": 0, "size_vram": 0}], None),
        ([{"name": "m:8b", "size": 100}], None),
    ],
)
def test_repartition_cpu_gpu(modeles, attendu):
    resultat = mesures.repartition({"models": modeles}, "m:8b")
    assert (resultat and resultat["part_gpu"]) == attendu
    if resultat:
        assert resultat["part_cpu"] == round(1 - attendu, 3)


def test_nom_sans_etiquette_equivaut_a_latest():
    assert mesures.repartition({"models": [{"name": "llama3:latest", "size": 10, "size_vram": 10}]}, "llama3")


# --- Route /api/generer-ticket avec un faux Ollama ------------------------------------


def ticket_valide(schema: dict, categorie: str = "Réseau") -> dict:
    """Ticket conforme au schéma reçu (nom, service, source, ordre des réponses imposés)."""
    p = schema["properties"]
    reponses = p["reponses"]["prefixItems"]
    textes = ["a" * 150, "b" * 150, "c" * 140, "d" * 130]  # bonne réponse la plus courte
    return {
        "theme": "Wi-Fi",
        "nom": p["nom"]["enum"][0],
        "service": p["service"]["enum"][0],
        "source": p["source"]["enum"][0],
        "objet": "Objet" if p["objet"].get("type") == "string" else None,
        "canal": "Chat" if p["canal"].get("type") == "string" else None,
        "demande": "Le Wi-Fi ne marche plus.",
        "reponses": [
            {"note": r["properties"]["note"]["enum"][0], "grossiere": r["properties"]["grossiere"]["enum"][0], "texte": t}
            for r, t in zip(reponses, textes)
        ],
        "pointCle": "vérifier d'abord si le problème est général.",
        "attendu": {"type": ["Incident"], "categorie": [categorie], "urgence": ["Haute"], "impact": ["Basse"]},
    }


class FauxOllama:
    """Répond à /api/chat, /api/show et /api/ps ; compte les appels."""

    def __init__(self, reponses_chat, show=None, ps=None):
        self.reponses_chat = list(reponses_chat)  # « rejet » ou dict de métriques
        self.show, self.ps = show, ps
        self.appels: list[str] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.appels.append(requete.url.path)
        if requete.url.path == "/api/chat":
            corps = json.loads(requete.content)
            suivante = self.reponses_chat.pop(0)
            if suivante == "rejet":  # réponse illisible : le serveur relance
                contenu, metriques = "pas du JSON", chat(1_000_000_000, 500_000_000, 3400, 20, 400_000_000)
            else:
                # La catégorie demandée figure dans la consigne : « catégorie principale : X (… ».
                consigne = corps["messages"][-1]["content"]
                categorie = re.search(r"catégorie principale : (.+?) \(", consigne).group(1)
                contenu, metriques = json.dumps(ticket_valide(corps["format"], categorie)), suivante
            return httpx.Response(200, json={"message": {"content": contenu}, **metriques})
        if requete.url.path == "/api/show":
            return httpx.Response(200, json=self.show) if self.show else httpx.Response(500, json={"error": "en panne"})
        if requete.url.path == "/api/ps":
            return httpx.Response(200, json=self.ps) if self.ps else httpx.Response(404, json={"error": "absent"})
        return httpx.Response(404)


@pytest.fixture
def generer(monkeypatch):
    monkeypatch.setattr(application, "_FICHES_MODELES", {})

    def lancer(faux: FauxOllama, nombre=1):
        client_ollama = httpx.AsyncClient(transport=httpx.MockTransport(faux), base_url="http://ollama.test")
        monkeypatch.setattr(application.app.state, "ollama", client_ollama, raising=False)
        client = TestClient(application.app, base_url="http://127.0.0.1")
        return [client.post("/api/generer-ticket", json={"categorie": "Réseau"}) for _ in range(nombre)]

    return lancer


SHOW = {"details": {"parameter_size": "8.2B", "quantization_level": "Q4_K_M", "family": "qwen3"}}
PS = {"models": [{"name": NOM, "model": NOM, "size": 6_600_000_000, "size_vram": 5_544_000_000}]}


def test_metriques_presentes_et_cumulees_sur_deux_tentatives(generer):
    faux = FauxOllama(["rejet", chat(9_000_000_000, 0, 3450, 440, 8_000_000_000)], show=SHOW, ps=PS)
    reponse = generer(faux)[0]
    assert reponse.status_code == 200
    corps = reponse.json()
    m = corps["metriques"]
    assert m["tentatives"] == corps["tentatives"] == 2
    assert m["modele"] == {"nom": NOM, "taille": "8.2B", "quantification": "Q4_K_M", "famille": "qwen3"}
    assert m["repartition"] == {"part_gpu": 0.84, "part_cpu": 0.16, "taille_octets": 6_600_000_000,
                                "vram_octets": 5_544_000_000}
    # Sommes des deux tentatives (la première a été rejetée).
    assert m["ollama"] == chat(10_000_000_000, 500_000_000, 6850, 460, 8_400_000_000)
    assert m["tokens_par_seconde"] == round(460 / 8.4, 1)
    assert isinstance(m["duree_serveur_s"], float) and m["duree_serveur_s"] >= 0
    # Le ticket reste au format de js/tickets.js, sans aucune métrique.
    assert set(corps["ticket"]) <= CLES_TICKET
    assert "metriques" not in json.dumps(corps["ticket"])


def test_metriques_absentes_null_sans_erreur(generer):
    faux = FauxOllama([{}])  # /api/chat sans métriques, /api/show en panne, /api/ps absent
    reponse = generer(faux)[0]
    assert reponse.status_code == 200
    m = reponse.json()["metriques"]
    assert m["modele"] == {"nom": NOM, "taille": None, "quantification": None, "famille": None}
    assert m["repartition"] is None
    assert m["ollama"] == dict.fromkeys(mesures.CHAMPS_OLLAMA)
    assert m["tokens_par_seconde"] is None
    assert m["duree_serveur_s"] is not None  # mesurée par le serveur, toujours disponible


def test_fiche_du_modele_mise_en_cache(generer):
    faux = FauxOllama([chat(1, 0, 1, 1, 1)] * 2, show=SHOW, ps=PS)
    reponses = generer(faux, nombre=2)
    assert all(r.json()["metriques"]["modele"]["taille"] == "8.2B" for r in reponses)
    assert faux.appels.count("/api/show") == 1
    assert faux.appels.count("/api/ps") == 2  # la répartition, elle, change : relevée à chaque fois


def test_fiche_en_echec_retentee_a_la_generation_suivante(generer):
    faux = FauxOllama([chat(1, 0, 1, 1, 1)] * 2)  # /api/show en panne
    generer(faux, nombre=2)
    assert faux.appels.count("/api/show") == 2


def test_erreur_inattendue_des_metriques_ne_fait_pas_echouer(generer, monkeypatch):
    def en_panne(*_):
        raise RuntimeError("bogue")

    monkeypatch.setattr(mesures, "repartition", en_panne)
    reponse = generer(FauxOllama([chat(1, 0, 1, 1, 1)], show=SHOW, ps=PS))[0]
    assert reponse.status_code == 200
    assert reponse.json()["metriques"]["repartition"] is None
    assert reponse.json()["metriques"]["modele"]["taille"] == "8.2B"

"""Tests des sous-thèmes : fichier de données, comparaison avec les thèmes déjà vus,
tirage, consigne, et route /api/generer-ticket (faux Ollama)."""

import json
import os
import random
import re

import httpx
import pytest

os.environ.setdefault("OLLAMA_MODEL", "modele-de-test")  # requis à l'import de l'application

from fastapi.testclient import TestClient  # noqa: E402

import serveur.app as application  # noqa: E402
from serveur.configuration import ErreurConfiguration, lire_categories, lire_profils, lire_sous_themes  # noqa: E402
from serveur.exemples import lire_exemples  # noqa: E402
from serveur.generateur import choisir_sous_theme, deja_vu, message_utilisateur, tirer_consigne  # noqa: E402
from test_metriques import SHOW, PS, FauxOllama, chat  # noqa: E402

CATEGORIES = lire_categories()
SOUS_THEMES = lire_sous_themes(CATEGORIES)


# --- Fichier de données --------------------------------------------------------------


def test_chaque_categorie_a_au_moins_8_sous_themes():
    assert tuple(SOUS_THEMES) == CATEGORIES
    assert all(len(liste) >= 8 for liste in SOUS_THEMES.values())


def test_aucun_sous_theme_d_impression_hors_de_la_categorie_impression():
    impression = re.compile(r"impri|toner|cartouche|bourrage|recto|scann|numéris", re.IGNORECASE)
    for categorie, liste in SOUS_THEMES.items():
        if categorie != "Impression":
            assert not [s for s in liste if impression.search(s)], categorie


def ecrire(tmp_path, donnees):
    fichier = tmp_path / "sous-themes.json"
    fichier.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    return fichier


HUIT = [f"sous-thème {i}" for i in range(8)]


@pytest.mark.parametrize(
    "donnees, message",
    [
        ({"A": HUIT}, "sans sous-thèmes : B"),
        ({"A": HUIT, "B": HUIT, "C": HUIT}, "absente(s) de js/config.js : C"),
        ({"A": HUIT, "B": HUIT[:7]}, "il en faut au moins 8"),
        ({"A": HUIT, "B": HUIT[:7] + ["SOUS-THÈME 0"]}, "en double"),
        ({"A": HUIT, "B": HUIT[:7] + [""]}, "textes non vides"),
    ],
)
def test_fichier_invalide_bloque_le_demarrage(tmp_path, donnees, message):
    with pytest.raises(ErreurConfiguration, match=re.escape(message)):
        lire_sous_themes(("A", "B"), ecrire(tmp_path, donnees))


# --- Thèmes déjà vus et tirage -----------------------------------------------------------


@pytest.mark.parametrize(
    "sous_theme, themes, attendu",
    [
        ("clavier", ["Clavier"], True),
        ("clavier", ["Claviers"], True),
        ("batterie de portable", ["Batterie"], True),
        ("Wi-Fi qui décroche", ["Wi-Fi"], True),
        ("écran externe", ["Écran noir"], False),  # un seul mot commun : pas le même cas
        ("mot de passe expiré", ["Mot de passe oublié"], False),
        ("souris", ["Clavier", "Webcam"], False),
        ("souris", [], False),
    ],
)
def test_deja_vu(sous_theme, themes, attendu):
    assert deja_vu(sous_theme, themes) is attendu


def test_le_tirage_evite_les_sous_themes_deja_vus():
    materiel = SOUS_THEMES["Matériel"]
    vus = ["Clavier", "Souris", "Webcam", "Batterie", "Port USB"]
    alea = random.Random(0)
    tires = {choisir_sous_theme(materiel, vus, alea) for _ in range(200)}
    assert tires.isdisjoint({"clavier", "souris", "webcam", "batterie de portable", "port USB"})
    assert len(tires) == len(materiel) - 5  # tous les autres finissent par sortir


def test_quand_tout_a_ete_vu_on_repart_de_la_liste_complete():
    materiel = SOUS_THEMES["Matériel"]
    assert choisir_sous_theme(materiel, list(materiel), random.Random(1)) in materiel


def test_consigne_impose_le_sous_theme_et_rappelle_les_regles():
    exemples, _ = lire_exemples(CATEGORIES)
    consigne = tirer_consigne("Matériel", "pas trop difficile", "Téléphone", lire_profils(), exemples,
                              random.Random(2), sous_themes=SOUS_THEMES["Matériel"])
    assert consigne.sous_theme in SOUS_THEMES["Matériel"]
    message = message_utilisateur(consigne)
    assert f"sous-thème imposé : « {consigne.sous_theme} »" in message
    assert "ne le lui propose à nouveau" in message
    assert "« Haute » seulement si l'utilisateur est bloqué" in message


# --- Route /api/generer-ticket ----------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """client(faux) : client de test dont les appels à Ollama vont au faux donné.
    app.state.ollama n'est remplacé qu'une fois ; un aiguillage choisit le faux."""
    monkeypatch.setattr(application, "_FICHES_MODELES", {})
    courant = {}
    ollama = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: courant["faux"](r)),
                               base_url="http://ollama.test")
    monkeypatch.setattr(application.app.state, "ollama", ollama, raising=False)
    client_test = TestClient(application.app, base_url="http://127.0.0.1")

    def avec(faux):
        courant["faux"] = faux
        return client_test

    return avec


def test_route_impose_le_seul_sous_theme_pas_encore_vu(client):
    materiel = list(SOUS_THEMES["Matériel"])
    faux = FauxOllama([chat(1, 0, 1, 1, 1)], show=SHOW, ps=PS)
    reponse = client(faux).post("/api/generer-ticket", json={
        # Envoyé par la page : tout sauf « webcam », sous forme de thèmes libres.
        "categorie": "Réseau", "themes_deja_vus": [s.capitalize() for s in materiel if s != "webcam"],
    })
    assert reponse.status_code == 200
    assert reponse.json()["consigne"]["sous_theme"] in SOUS_THEMES["Réseau"]  # catégorie demandée

    faux = FauxOllama([chat(1, 0, 1, 1, 1)], show=SHOW, ps=PS)
    reponse = client(faux).post("/api/generer-ticket", json={
        "categorie": "Matériel", "themes_deja_vus": [s.capitalize() for s in materiel if s != "webcam"],
    })
    assert reponse.json()["consigne"]["sous_theme"] == "webcam"
    # Le sous-thème est imposé dans la consigne envoyée au modèle, et le ticket garde son format.
    assert set(reponse.json()["ticket"]) <= {"id", "theme", "nom", "service", "source", "objet", "canal",
                                             "demande", "reponses", "pointCle", "attendu"}


def test_themes_deja_vus_bornes(client):
    faux = FauxOllama([])
    trop = client(faux).post("/api/generer-ticket", json={"categorie": "Matériel", "themes_deja_vus": ["x"] * 501})
    assert trop.status_code == 422
    long = client(faux).post("/api/generer-ticket", json={"categorie": "Matériel", "themes_deja_vus": ["x" * 201]})
    assert long.status_code == 422
    assert faux.appels == []  # refusé avant tout appel à Ollama

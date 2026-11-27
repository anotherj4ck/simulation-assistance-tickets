"""Tests du site apprenant dans un vrai navigateur (Playwright + Edge ou Chrome installé).

Le site est servi par un simple serveur de fichiers, sans l'API : c'est la
situation de GitHub Pages ou d'un serveur sans série publiée. Les réponses de
/api/serie sont simulées par Playwright quand un test en a besoin.

Ignorés (skip) si Playwright n'est pas installé ou si aucun navigateur n'est disponible.
"""

import copy
import functools
import json
import os
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from serveur.configuration import RACINE_SITE
from serveur.exemples import TICKETS_JS, _lire_brut

sync_api = pytest.importorskip("playwright.sync_api")

TICKETS = _lire_brut(TICKETS_JS)
SERIE = [TICKETS[i] for i in (29, 3, 17, 8, 22)]  # ordre choisi « par le formateur »


class _Silencieux(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _serveur_fichiers(adresse: str):
    gestionnaire = functools.partial(_Silencieux, directory=str(RACINE_SITE))
    serveur = ThreadingHTTPServer((adresse, 0), gestionnaire)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur


@pytest.fixture(scope="module")
def site():
    serveur = _serveur_fichiers("127.0.0.1")
    yield f"http://127.0.0.1:{serveur.server_address[1]}"
    serveur.shutdown()


@pytest.fixture(scope="module")
def navigateur():
    with sync_api.sync_playwright() as p:
        for canal in ("msedge", "chrome", None):
            try:
                nav = p.chromium.launch(channel=canal, headless=True) if canal else p.chromium.launch(headless=True)
                break
            except Exception:
                continue
        else:
            pytest.skip("aucun navigateur disponible pour Playwright (Edge, Chrome ou Chromium)")
        yield nav
        nav.close()


@pytest.fixture
def page(navigateur):
    contexte = navigateur.new_context(reduced_motion="reduce")  # pas d'animation : tests rapides
    page = contexte.new_page()
    page.requetes_serie = []
    page.on("request", lambda r: "api/serie" in r.url and page.requetes_serie.append(r.url))
    page.erreurs = []
    page.on("pageerror", lambda e: page.erreurs.append(str(e)))
    yield page
    contexte.close()


def commencer(page):
    page.fill("#nom", "Test")
    page.click("#form-nom button[type=submit]")
    page.click("#btn-commencer")
    sync_api.expect(page.locator("#ecran-simulation")).to_be_visible(timeout=10000)


def verifier_tirage_habituel(page):
    sync_api.expect(page.locator("#prog-total")).to_have_text("5")
    assert page.locator("#info-serie").is_hidden()
    assert page.locator("#erreur-chargement").is_hidden()
    assert page.erreurs == []


def test_api_absente_tirage_habituel(page, site):
    page.goto(f"{site}/index.html")  # serveur de fichiers : /api/serie répond 404
    commencer(page)
    verifier_tirage_habituel(page)
    assert page.requetes_serie, "la page servie en local doit demander la série"


def test_delai_depasse_tirage_habituel(page, site):
    page.route("**/api/serie", lambda route: None)  # requête jamais servie
    page.goto(f"{site}/index.html")
    page.fill("#nom", "Test")
    page.click("#form-nom button[type=submit]")
    debut = time.monotonic()
    page.click("#btn-commencer")
    sync_api.expect(page.locator("#ecran-simulation")).to_be_visible(timeout=10000)
    assert 1.5 < time.monotonic() - debut < 5, "abandon attendu après le délai de 2 s"
    verifier_tirage_habituel(page)


@pytest.mark.parametrize(
    "corps",
    [
        "pas du json",
        json.dumps({"tickets": SERIE[:4]}),                           # pas 5 tickets
        json.dumps({"tickets": SERIE[:4] + [{"id": "incomplet"}]}),  # ticket invalide
        json.dumps({"mode": "fixe", "tickets": TICKETS[:6]}),        # fixe : pas 5 tickets
        json.dumps({"mode": "tirage", "tickets": SERIE[:4]}),        # tirage : moins de 5
        json.dumps({"mode": "tirage", "tickets": SERIE + SERIE[:1]}),  # tirage : identifiant en double
        json.dumps({"mode": "aleatoire", "tickets": SERIE}),         # mode inconnu
    ],
)
def test_reponse_invalide_tirage_habituel(page, site, corps):
    page.route("**/api/serie", lambda route: route.fulfill(status=200, content_type="application/json", body=corps))
    page.goto(f"{site}/index.html")
    commencer(page)
    verifier_tirage_habituel(page)


def test_serie_valide_utilisee_dans_l_ordre_jusqu_au_rapport(page, site):
    corps = json.dumps({"publiee_le": "2026-11-26T10:00:00+01:00", "tickets": SERIE})
    page.route("**/api/serie", lambda route: route.fulfill(status=200, content_type="application/json", body=corps))
    page.goto(f"{site}/index.html")
    sync_api.expect(page.locator("#info-serie")).to_be_visible()
    assert page.locator("#info-serie").inner_text() == "Série préparée par votre formateur"
    commencer(page)

    for n, ticket in enumerate(SERIE):
        sync_api.expect(page.locator("#chat")).to_contain_text(ticket["demande"])
        page.locator("#choix .reponse").first.click()
        page.fill("#t-titre", f"Ticket {n + 1}")
        page.click("#btn-enregistrer")

    sync_api.expect(page.locator("#ecran-rapport")).to_be_visible()
    rapport = page.locator("#rapport-contenu").inner_text()
    positions = [rapport.index(f"Demande {n + 1} — {t['nom']}") for n, t in enumerate(SERIE)]
    assert positions == sorted(positions)
    assert page.erreurs == []


def test_hors_serveur_local_aucune_requete(page):
    # Comme sur GitHub Pages ou en double-cliquant sur index.html : la page ne
    # demande rien et se comporte exactement comme avant.
    page.goto((RACINE_SITE / "index.html").as_uri())
    commencer(page)
    verifier_tirage_habituel(page)
    assert page.requetes_serie == []


def test_nom_d_hote_non_local_aucune_requete(page):
    # Nom d'hôte différent de 127.0.0.1 / localhost, comme un site publié.
    try:
        serveur = _serveur_fichiers("127.0.0.2")
    except OSError:
        pytest.skip("adresse 127.0.0.2 indisponible sur ce poste")
    try:
        page.goto(f"http://127.0.0.2:{serveur.server_address[1]}/index.html")
        commencer(page)
        verifier_tirage_habituel(page)
        assert page.requetes_serie == []
    finally:
        serveur.shutdown()


# --- Page formateur : import d'un fichier, sur le vrai serveur (sans Ollama) -------


@pytest.fixture(scope="module")
def serveur_local(tmp_path_factory):
    """L'application FastAPI, lancée dans un thread sur un port libre. La série
    active est écrite dans un dossier temporaire. Ollama n'est pas appelé."""
    os.environ.setdefault("OLLAMA_MODEL", "modele-de-test")
    import uvicorn

    import serveur.app as application

    chemin_avant = application.CHEMIN_SERIE
    application.CHEMIN_SERIE = tmp_path_factory.mktemp("serie") / "serie-active.json"
    prise = socket.socket()
    prise.bind(("127.0.0.1", 0))
    serveur = uvicorn.Server(uvicorn.Config(application.app, log_level="warning"))
    fil = threading.Thread(target=serveur.run, kwargs={"sockets": [prise]}, daemon=True)
    fil.start()
    for _ in range(100):
        if serveur.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{prise.getsockname()[1]}"
    serveur.should_exit = True
    fil.join(5)
    application.CHEMIN_SERIE = chemin_avant


def fichier_json(tmp_path, nom, contenu):
    chemin = tmp_path / nom
    chemin.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    return str(chemin)


def ouvrir_formateur(page, serveur_local, liste_initiale=(), accepter_dialogues=True):
    page.add_init_script(
        f"localStorage.setItem('formateur.ticketsValides', {json.dumps(json.dumps(list(liste_initiale)))});"
    )
    if accepter_dialogues:
        page.on("dialog", lambda d: d.accept())
    page.goto(f"{serveur_local}/formateur.html")
    sync_api.expect(page.locator("#serie-etat")).not_to_have_text("Vérification…")


def test_import_doublons_refus_retrait_puis_publication(page, serveur_local, tmp_path):
    t = TICKETS
    invalide = copy.deepcopy(t[3])
    invalide["source"] = "Pigeon"
    contenu = [t[0], t[1], t[2], t[1], invalide, t[4], t[5]]  # t[0] déjà dans la liste, t[1] en double
    ouvrir_formateur(page, serveur_local, [t[0]])
    sync_api.expect(page.locator("#nb-valides")).to_have_text("1")

    page.set_input_files("#fichier-import", fichier_json(tmp_path, "export.json", contenu))
    compte_rendu = page.locator("#resultat-import")
    sync_api.expect(compte_rendu).to_contain_text("4 tickets importés, 2 ignorés (doublons), 1 refusé.")
    sync_api.expect(compte_rendu).to_contain_text(f"répété dans le fichier) : {t[0]['id']}, {t[1]['id']}.")
    sync_api.expect(compte_rendu).to_contain_text(f"Ticket n° 5 ({t[3]['id']}) : source : valeur non autorisée")
    sync_api.expect(page.locator("#nb-valides")).to_have_text("5")
    stocke = json.loads(page.evaluate("localStorage.getItem('formateur.ticketsValides')"))
    assert [x["id"] for x in stocke] == [t[i]["id"] for i in (0, 1, 2, 4, 5)]
    sync_api.expect(page.locator("#btn-publier")).to_be_enabled()

    # Un ticket importé se retire comme les autres…
    page.locator("#liste-valides li").nth(2).get_by_role("button", name="Retirer").click()
    sync_api.expect(page.locator("#nb-valides")).to_have_text("4")
    sync_api.expect(page.locator("#btn-publier")).to_be_disabled()

    # … et revient si on réimporte le fichier, sans créer de doublon.
    page.set_input_files("#fichier-import", fichier_json(tmp_path, "export.json", contenu))
    sync_api.expect(compte_rendu).to_contain_text("1 ticket importé, 5 ignorés (doublons), 1 refusé.")
    sync_api.expect(page.locator("#nb-valides")).to_have_text("5")

    # La série se publie comme d'habitude, dans l'ordre de la liste.
    page.click("#btn-publier")
    sync_api.expect(page.locator("#serie-etat")).to_contain_text("Série fixe, 5 tickets, publiée le")
    attendus = [f"{n + 1}. {t[i]['theme']}" for n, i in enumerate((0, 1, 4, 5, 2))]
    assert page.locator("#serie-tickets .titre").all_inner_texts() == attendus
    assert page.erreurs == []


@pytest.mark.parametrize(
    "contenu, message",
    [
        ("ceci n'est pas du JSON", "n'est pas un JSON valide"),
        ("[]", "aucun ticket (tableau vide)"),
        ('{"tickets": []}', "tableau de tickets"),
    ],
)
def test_import_fichier_refuse(page, serveur_local, tmp_path, contenu, message):
    ouvrir_formateur(page, serveur_local)
    page.set_input_files("#fichier-import", fichier_json(tmp_path, "mauvais.json", contenu))
    compte_rendu = page.locator("#resultat-import")
    sync_api.expect(compte_rendu).to_have_attribute("data-etat", "erreur")
    sync_api.expect(compte_rendu).to_contain_text("Import de « mauvais.json » impossible")
    sync_api.expect(compte_rendu).to_contain_text(message)
    sync_api.expect(page.locator("#nb-valides")).to_have_text("0")


def test_mention_liste_par_adresse_avec_infobulle(page, serveur_local):
    ouvrir_formateur(page, serveur_local)
    mention = page.locator(".f-memoire")
    sync_api.expect(mention).to_contain_text("Liste enregistrée dans ce navigateur, pour cette adresse")
    infobulle = page.locator("#infobulle-memoire")
    sync_api.expect(infobulle).to_be_hidden()
    mention.focus()  # au clavier comme à la souris
    sync_api.expect(infobulle).to_be_visible()
    sync_api.expect(infobulle).to_contain_text("localhost")
    sync_api.expect(infobulle).to_contain_text("127.0.0.1")


# --- Modes de publication : « tirage » côté apprenant ----------------------------

SELECTION = TICKETS[:12]  # sélection publiée en mode « tirage »


def jouer_session(page):
    """Joue une session complète ; renvoie les identifiants des tickets reçus, dans l'ordre."""
    recus = []
    for n in range(5):
        sync_api.expect(page.locator("#choix .reponse")).to_have_count(4)
        chat = page.locator("#chat").inner_text()
        trouves = [t["id"] for t in SELECTION if t["demande"] in chat]
        assert len(trouves) == 1, f"ticket {n + 1} introuvable dans la sélection"
        recus.append(trouves[0])
        page.locator("#choix .reponse").first.click()
        page.fill("#t-titre", f"Ticket {n + 1}")
        page.click("#btn-enregistrer")
    sync_api.expect(page.locator("#ecran-rapport")).to_be_visible()
    return recus


def test_tirage_n_tickets_distincts_de_la_selection_a_chaque_session(page, site):
    corps = json.dumps({"mode": "tirage", "publiee_le": "2026-11-26T10:00:00+01:00", "tickets": SELECTION})
    page.route("**/api/serie", lambda route: route.fulfill(status=200, content_type="application/json", body=corps))
    page.on("dialog", lambda d: d.accept())  # « Nouvelle session » sans avoir téléchargé le rapport
    page.goto(f"{site}/index.html")
    sync_api.expect(page.locator("#info-serie")).to_have_text("Tickets choisis par votre formateur")
    commencer(page)

    sessions = []
    for numero in range(3):
        recus = jouer_session(page)
        assert len(recus) == 5 and len(set(recus)) == 5, recus  # toujours 5, sans doublon
        sessions.append(recus)
        if numero < 2:
            page.click("#btn-recommencer")
            sync_api.expect(page.locator("#ecran-simulation")).to_be_visible()
    # Un nouveau tirage à chaque session : 3 sessions identiques (même sélection,
    # même ordre) n'arrivent qu'avec une chance sur 95 040².
    assert len({tuple(s) for s in sessions}) > 1, sessions
    assert page.erreurs == []


def test_serie_fixe_explicite_message_d_accueil(page, site):
    corps = json.dumps({"mode": "fixe", "publiee_le": "2026-11-26T10:00:00+01:00", "tickets": SERIE})
    page.route("**/api/serie", lambda route: route.fulfill(status=200, content_type="application/json", body=corps))
    page.goto(f"{site}/index.html")
    sync_api.expect(page.locator("#info-serie")).to_have_text("Série préparée par votre formateur")
    commencer(page)
    sync_api.expect(page.locator("#chat")).to_contain_text(SERIE[0]["demande"])


# --- Modes de publication : page formateur ------------------------------------------


def test_publier_selon_le_mode(page, serveur_local):
    ouvrir_formateur(page, serveur_local, TICKETS[:7])
    publier, aide = page.locator("#btn-publier"), page.locator("#aide-publier")

    sync_api.expect(page.locator("input[value=fixe]")).to_be_checked()
    sync_api.expect(publier).to_be_disabled()  # 7 tickets : pas une série fixe
    sync_api.expect(aide).to_have_text("Une série fixe demande exactement 5 tickets validés (actuellement 7).")

    page.check("input[value=tirage]")
    sync_api.expect(publier).to_be_enabled()
    sync_api.expect(aide).to_have_text("")
    sync_api.expect(page.locator(".f-modes")).to_contain_text("l'apprenant en reçoit 5, tirés au hasard")

    publier.click()
    sync_api.expect(page.locator("#serie-etat")).to_contain_text("Tirage dans la sélection, 7 tickets, publiée le")
    sync_api.expect(page.locator("#serie-etat")).to_contain_text("l'apprenant en reçoit 5, tirés au hasard")
    serie = page.request.get(f"{serveur_local}/api/serie").json()
    assert serie["mode"] == "tirage" and [t["id"] for t in serie["tickets"]] == [t["id"] for t in TICKETS[:7]]
    # En tirage, l'ordre ne compte pas : les tickets de l'encart ne sont pas numérotés.
    assert page.locator("#serie-tickets .titre").all_inner_texts() == [t["theme"] for t in TICKETS[:7]]

    # Moins de 5 tickets : aucun des deux modes ne permet de publier.
    for _ in range(3):
        page.locator("#liste-valides li").first.get_by_role("button", name="Retirer").click()
    sync_api.expect(publier).to_be_disabled()
    sync_api.expect(aide).to_have_text("Un tirage dans la sélection demande de 5 à 200 tickets validés (actuellement 4).")
    page.check("input[value=fixe]")
    sync_api.expect(publier).to_be_disabled()


def categorie_principale(t):
    c = t["attendu"]["categorie"]
    return c[0] if isinstance(c, list) else c


def tickets_de(*categories):
    """Un ticket différent par catégorie demandée (2e occurrence si la catégorie est répétée…)."""
    choisis = []
    for c in categories:
        choisis.append(next(t for t in TICKETS if categorie_principale(t) == c and t not in choisis))
    return choisis


@pytest.mark.parametrize(
    "categories, debut",
    [
        (("Sécurité", "Sécurité"), "securite"),
        (("Réseau", "Sécurité", "Réseau"), "reseau-securite"),
        (("Matériel", "Réseau", "Logiciel", "Impression"), "plusieurs-categories"),
    ],
)
def test_nom_d_export_propose(page, serveur_local, tmp_path, categories, debut):
    tickets = tickets_de(*categories)
    ouvrir_formateur(page, serveur_local, tickets, accepter_dialogues=False)
    proposes = []
    page.once("dialog", lambda d: (proposes.append(d.default_value), d.accept()))
    with page.expect_download() as telechargement:
        page.click("#btn-exporter")
    attendu = f"{debut}-{time.strftime('%Y-%m-%d')}"
    assert proposes == [attendu]
    assert telechargement.value.suggested_filename == attendu + ".json"
    exporte = json.loads(open(telechargement.value.path(), encoding="utf-8").read())
    assert [t["id"] for t in exporte] == [t["id"] for t in tickets]


@pytest.mark.parametrize(
    "saisie, fichier",
    [
        ("seance-1", "seance-1.json"),
        ("seance-1.json", "seance-1.json"),
        ("Séance 1 : réseau/sécurité ?", "Séance 1 - réseau-sécurité -.json"),
        ("   ", None),  # vide : le nom proposé est utilisé
    ],
)
def test_nom_d_export_saisi(page, serveur_local, saisie, fichier):
    ouvrir_formateur(page, serveur_local, tickets_de("Sécurité"), accepter_dialogues=False)
    page.once("dialog", lambda d: d.accept(saisie))
    with page.expect_download() as telechargement:
        page.click("#btn-exporter")
    assert telechargement.value.suggested_filename == (fichier or f"securite-{time.strftime('%Y-%m-%d')}.json")


def test_export_annule(page, serveur_local):
    ouvrir_formateur(page, serveur_local, tickets_de("Sécurité"), accepter_dialogues=False)
    telechargements = []
    page.on("download", lambda d: telechargements.append(d))
    page.once("dialog", lambda d: d.dismiss())
    page.click("#btn-exporter")
    page.wait_for_timeout(500)
    assert telechargements == []


# --- Métriques de génération dans la page formateur ----------------------------------

METRIQUES = {
    "modele": {"nom": "qwen3:8b", "taille": "8.2B", "quantification": "Q4_K_M", "famille": "qwen3"},
    "repartition": {"part_gpu": 0.84, "part_cpu": 0.16, "taille_octets": 6_600_000_000, "vram_octets": 5_544_000_000},
    "duree_serveur_s": 12.34,
    "ollama": {"total_duration": 12_100_000_000, "load_duration": 2_060_000_000, "prompt_eval_count": 7400,
               "eval_count": 441, "eval_duration": 10_970_000_000},
    "tokens_par_seconde": 40.2,
    "tentatives": 2,
}
METRIQUES_ABSENTES = {
    "modele": {"nom": "qwen3:8b", "taille": None, "quantification": None, "famille": None},
    "repartition": None,
    "duree_serveur_s": 0.94,
    "ollama": dict.fromkeys(["total_duration", "load_duration", "prompt_eval_count", "eval_count", "eval_duration"]),
    "tokens_par_seconde": None,
    "tentatives": 1,
}


def generer_simule(page, metriques):
    """Clique sur « Générer » ; la réponse du serveur est simulée (pas d'appel à Ollama)."""
    reponse = {"ticket": TICKETS[0], "alertes": [], "tentatives": 2, "modele": "qwen3:8b",
               "consigne": {"categorie": "Réseau", "source": "Direct", "difficulte": "pas trop difficile",
                            "avec_grossiere": True, "profil": {"ton": "calme et poli", "aisance": "à l'aise"},
                            "exemples": ["t13-vpn"]}}
    if metriques is not None:
        reponse["metriques"] = metriques
    page.route("**/api/generer-ticket", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(reponse)))
    page.click("#btn-generer")
    sync_api.expect(page.locator("#zone-ticket")).to_be_visible()
    return page.locator("#e-infos").inner_text()


def test_metriques_affichees_en_francais_et_jamais_exportees(page, serveur_local):
    ouvrir_formateur(page, serveur_local)
    infos = generer_simule(page, METRIQUES)
    assert "Tentatives : 2" in infos
    assert "Modèle : qwen3:8b (8,2B · Q4_K_M)" in infos
    assert "Mémoire : 16 % CPU / 84 % GPU" in infos
    assert "Durée : 12,3 s (dont chargement 2,1 s)" in infos
    assert "Génération : 441 tokens générés · 40,2 tokens/s" in infos

    page.click("#btn-valider")
    sync_api.expect(page.locator("#nb-valides")).to_have_text("1")
    with page.expect_download() as telechargement:
        page.click("#btn-exporter")
    texte = open(telechargement.value.path(), encoding="utf-8").read()
    stocke = page.evaluate("localStorage.getItem('formateur.ticketsValides')")
    for contenu in (texte, stocke):
        for cle in ("metriques", "duree_serveur_s", "eval_count", "part_gpu", "tokens_par_seconde", "Q4_K_M"):
            assert cle not in contenu
    exporte = json.loads(texte)
    assert set(exporte[0]) <= {"id", "theme", "nom", "service", "source", "objet", "canal",
                               "demande", "reponses", "pointCle", "attendu"}
    assert exporte[0]["id"] == TICKETS[0]["id"]


def test_metriques_absentes_n_affichent_rien_de_faux(page, serveur_local):
    ouvrir_formateur(page, serveur_local)
    infos = generer_simule(page, METRIQUES_ABSENTES)
    assert "Modèle : qwen3:8b · Durée : 0,9 s" in infos
    assert "Mémoire" not in infos and "Génération" not in infos and "chargement" not in infos
    for mot in ("null", "NaN", "undefined"):
        assert mot not in infos
    assert page.erreurs == []


def test_reponse_sans_metriques(page, serveur_local):
    ouvrir_formateur(page, serveur_local)
    infos = generer_simule(page, None)  # serveur plus ancien : pas de champ « metriques »
    assert "Modèle : qwen3:8b" in infos and "Durée" not in infos
    assert page.erreurs == []


def test_modele_entierement_sur_le_gpu(page, serveur_local):
    ouvrir_formateur(page, serveur_local)
    infos = generer_simule(page, {**METRIQUES, "repartition": {**METRIQUES["repartition"], "part_gpu": 1.0, "part_cpu": 0.0}})
    assert "Mémoire : 100 % GPU" in infos

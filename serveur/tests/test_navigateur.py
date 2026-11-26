"""Tests du site apprenant dans un vrai navigateur (Playwright + Edge ou Chrome installé).

Le site est servi par un simple serveur de fichiers, sans l'API : c'est la
situation de GitHub Pages ou d'un serveur sans série publiée. Les réponses de
/api/serie sont simulées par Playwright quand un test en a besoin.

Ignorés (skip) si Playwright n'est pas installé ou si aucun navigateur n'est disponible.
"""

import functools
import json
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

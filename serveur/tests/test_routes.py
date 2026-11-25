"""Tests des fichiers servis : site, page formateur, et rien d'autre.

Aucun appel à Ollama : seules les routes statiques sont testées.
"""

import os

import pytest

os.environ.setdefault("OLLAMA_MODEL", "modele-de-test")  # requis à l'import de l'application

from fastapi.testclient import TestClient  # noqa: E402

from serveur.app import app  # noqa: E402

client = TestClient(app, base_url="http://127.0.0.1")


@pytest.mark.parametrize(
    "chemin, contenu",
    [
        ("/", "Simulation d'assistance"),
        ("/formateur.html", "Mode formateur"),
        ("/formateur.js", "api/generer-ticket"),
        ("/formateur.css", "--alerte"),
        ("/js/config.js", "categories"),
        ("/css/style.css", "--accent"),
    ],
)
def test_fichiers_servis(chemin, contenu):
    reponse = client.get(chemin)
    assert reponse.status_code == 200
    assert contenu in reponse.text


@pytest.mark.parametrize(
    "chemin",
    [
        "/serveur/formateur/formateur.html",
        "/formateur/formateur.html",
        "/serveur/app.py",
        "/app.py",
        "/serveur/donnees/alertes.json",
        "/README.md",
        "/.git/HEAD",
        "/js/../serveur/app.py",
    ],
)
def test_rien_d_autre_n_est_servi(chemin):
    assert client.get(chemin).status_code == 404


def test_hote_non_local_refuse():
    assert TestClient(app, base_url="http://exemple.org").get("/").status_code == 400

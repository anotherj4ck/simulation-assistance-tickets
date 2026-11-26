"""Tests de /api/serie : publication, validation, lecture, retrait. Sans Ollama."""

import copy
import json
import os

import pytest

os.environ.setdefault("OLLAMA_MODEL", "modele-de-test")  # requis à l'import de l'application

from fastapi.testclient import TestClient  # noqa: E402

import serveur.app as application  # noqa: E402
from serveur.exemples import TICKETS_JS, _lire_brut  # noqa: E402

TICKETS = _lire_brut(TICKETS_JS)  # les 30 tickets du site, au format brut de js/tickets.js
SERIE = [TICKETS[i] for i in (4, 0, 12, 7, 20)]  # ordre volontairement non trié


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(application, "CHEMIN_SERIE", tmp_path / "serie-active.json")
    return TestClient(application.app, base_url="http://127.0.0.1")


def test_aucune_serie_au_depart(client):
    assert client.get("/api/serie").status_code == 404


def test_publication_valide_puis_lecture_dans_le_meme_ordre(client):
    reponse = client.post("/api/serie", json={"tickets": SERIE})
    assert reponse.status_code == 201
    lue = client.get("/api/serie").json()
    assert [t["id"] for t in lue["tickets"]] == [t["id"] for t in SERIE]
    assert lue["publiee_le"] == reponse.json()["publiee_le"]
    # Écriture atomique : seul le fichier final reste, sans fichier temporaire.
    assert [p.name for p in application.CHEMIN_SERIE.parent.iterdir()] == ["serie-active.json"]


def test_nouvelle_publication_remplace_la_precedente(client):
    client.post("/api/serie", json={"tickets": SERIE})
    autre = TICKETS[10:15]
    assert client.post("/api/serie", json={"tickets": autre}).status_code == 201
    assert [t["id"] for t in client.get("/api/serie").json()["tickets"]] == [t["id"] for t in autre]


@pytest.mark.parametrize("nombre", [4, 6])
def test_nombre_de_tickets_incorrect_refuse(client, nombre):
    reponse = client.post("/api/serie", json={"tickets": TICKETS[:nombre]})
    assert reponse.status_code == 422
    assert "exactement 5 tickets" in reponse.json()["detail"]
    assert client.get("/api/serie").status_code == 404


@pytest.mark.parametrize(
    "modifier, attendu",
    [
        (lambda t: t.update(source="Pigeon"), "ticket n° 3"),
        (lambda t: t["reponses"][0].update(grossière=True), "grossière"),
        (lambda t: t["attendu"].update(categorie="Plomberie"), "Plomberie"),
        (lambda t: t.update(id=SERIE[0]["id"]), "identifiant en double"),
    ],
)
def test_ticket_invalide_refuse(client, modifier, attendu):
    tickets = copy.deepcopy(SERIE)
    modifier(tickets[2])
    reponse = client.post("/api/serie", json={"tickets": tickets})
    assert reponse.status_code == 422
    assert attendu in reponse.json()["detail"]


def test_ticket_invalide_ne_remplace_pas_la_serie_en_cours(client):
    client.post("/api/serie", json={"tickets": SERIE})
    tickets = copy.deepcopy(SERIE)
    tickets[0]["source"] = "Pigeon"
    assert client.post("/api/serie", json={"tickets": tickets}).status_code == 422
    assert [t["id"] for t in client.get("/api/serie").json()["tickets"]] == [t["id"] for t in SERIE]


def test_retrait(client):
    client.post("/api/serie", json={"tickets": SERIE})
    assert client.delete("/api/serie").status_code == 204
    assert client.get("/api/serie").status_code == 404
    assert client.delete("/api/serie").status_code == 404


def test_fichier_modifie_a_la_main_signale(client):
    application.CHEMIN_SERIE.write_text(json.dumps({"publiee_le": "x", "tickets": SERIE[:3]}), encoding="utf-8")
    reponse = client.get("/api/serie")
    assert reponse.status_code == 500
    assert "exactement 5 tickets" in reponse.json()["detail"]


def test_ecriture_refusee_depuis_une_autre_page_web(client):
    corps = json.dumps({"tickets": SERIE})
    entetes = {"Content-Type": "application/json", "Origin": "https://site-malveillant.example"}
    assert client.post("/api/serie", content=corps, headers=entetes).status_code == 403
    assert client.delete("/api/serie", headers={"Origin": "https://site-malveillant.example"}).status_code == 403
    # Corps sans Content-Type JSON (requête « simple », qui échappe à CORS) : refusé aussi.
    assert client.post("/api/serie", content=corps).status_code == 415
    # Depuis une page de ce serveur : accepté.
    entetes["Origin"] = "http://127.0.0.1"
    assert client.post("/api/serie", content=corps, headers=entetes).status_code == 201

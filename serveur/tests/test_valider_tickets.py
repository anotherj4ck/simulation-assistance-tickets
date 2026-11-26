"""Tests de POST /api/valider-tickets (import d'un fichier exporté). Sans Ollama."""

import copy
import json
import os

import pytest

os.environ.setdefault("OLLAMA_MODEL", "modele-de-test")  # requis à l'import de l'application

from fastapi.testclient import TestClient  # noqa: E402

from serveur.app import app  # noqa: E402
from serveur.exemples import TICKETS_JS, _lire_brut  # noqa: E402

TICKETS = _lire_brut(TICKETS_JS)
client = TestClient(app, base_url="http://127.0.0.1")
JSON = {"Content-Type": "application/json"}


def importer(contenu: str | bytes):
    return client.post("/api/valider-tickets", content=contenu, headers=JSON)


def test_import_valide():
    fichier = json.dumps(TICKETS[:3], ensure_ascii=False, indent=2)
    reponse = importer(fichier)
    assert reponse.status_code == 200
    assert reponse.json() == {"valides": TICKETS[:3], "refuses": []}


def test_fichier_avec_bom_accepte():
    assert importer("﻿" + json.dumps(TICKETS[:1])).status_code == 200


@pytest.mark.parametrize(
    "contenu, message",
    [
        ("ceci n'est pas du JSON", "n'est pas un JSON valide (ligne 1"),
        ("[1, 2,", "n'est pas un JSON valide"),
        (json.dumps({"tickets": TICKETS[:2]}), "tableau de tickets"),
        ("[]", "aucun ticket (tableau vide)"),
        (b"\xff\xfe[]", "UTF-8"),
    ],
)
def test_fichier_illisible_refuse(contenu, message):
    reponse = importer(contenu)
    assert reponse.status_code == 422
    assert message in reponse.json()["detail"]


def test_tickets_invalides_refuses_avec_motif_et_champ():
    tickets = copy.deepcopy(TICKETS[:4])
    tickets[1]["source"] = "Pigeon"
    tickets[3]["reponses"][0]["grossière"] = True
    tickets[3]["attendu"]["categorie"] = "Plomberie"
    reponse = importer(json.dumps(tickets))
    assert reponse.status_code == 200
    resultat = reponse.json()
    assert [t["id"] for t in resultat["valides"]] == [tickets[0]["id"], tickets[2]["id"]]
    refuses = {r["position"]: r for r in resultat["refuses"]}
    assert set(refuses) == {2, 4}
    assert refuses[2]["id"] == tickets[1]["id"]
    assert refuses[2]["motifs"] == ["source : valeur non autorisée (attendu : 'Téléphone', 'Courriel', 'Direct', 'Helpdesk' ou 'Autre')"]
    assert "reponses.0.grossière : champ inconnu (faute de frappe ?)" in refuses[4]["motifs"]
    assert any("Plomberie" in m for m in refuses[4]["motifs"])


def test_element_qui_n_est_pas_un_ticket():
    resultat = importer(json.dumps([TICKETS[0], "texte", 42])).json()
    assert len(resultat["valides"]) == 1
    assert [r["motifs"] for r in resultat["refuses"]] == [["ticket : ce n'est pas un ticket { … }"]] * 2


def test_doublons_renvoyes_tels_quels():
    # Les doublons sont écartés par la page (elle seule connaît la liste du formateur) :
    # le serveur renvoie chaque ticket valide, même répété.
    resultat = importer(json.dumps([TICKETS[0], TICKETS[0]])).json()
    assert [t["id"] for t in resultat["valides"]] == [TICKETS[0]["id"]] * 2


def test_meme_protection_que_les_autres_post():
    corps = json.dumps(TICKETS[:1])
    assert client.post("/api/valider-tickets", content=corps).status_code == 415  # pas déclaré en JSON
    entetes = {**JSON, "Origin": "https://site-malveillant.example"}
    assert client.post("/api/valider-tickets", content=corps, headers=entetes).status_code == 403


def test_fichier_trop_gros():
    assert importer("[" + " " * (2 * 1024 * 1024) + "]").status_code == 413

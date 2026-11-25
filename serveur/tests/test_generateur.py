"""Tests du générateur : ordre imposé des réponses, mise au format, alertes."""

import json
import random

import pytest

from serveur.configuration import ErreurConfiguration, lire_categories, lire_mots_alertes, lire_profils
from serveur.exemples import lire_exemples, vers_format_genere
from serveur.generateur import (
    alertes_de_relecture,
    message_utilisateur,
    produire_ticket,
    schema_ticket,
    tirer_consigne,
)

CATEGORIES = lire_categories()
EXEMPLES, _ = lire_exemples(CATEGORIES)


def consigne(avec_grossiere: bool, graine: int = 0):
    # Cherche une graine qui donne la consigne voulue (le tirage est aléatoire).
    alea = random.Random(graine)
    while True:
        c = tirer_consigne("Réseau", "pas trop difficile", "Téléphone", lire_profils(), EXEMPLES, alea)
        if c.avec_grossiere == avec_grossiere:
            return c


def ordre_du_schema(c):
    items = schema_ticket(CATEGORIES, c)["properties"]["reponses"]["prefixItems"]
    return [(i["properties"]["note"]["enum"][0], i["properties"]["grossiere"]["enum"][0]) for i in items]


def test_schema_impose_fausse_fausse_partielle_bonne():
    assert ordre_du_schema(consigne(avec_grossiere=False)) == [(0, False), (0, False), (1, False), (2, False)]
    assert ordre_du_schema(consigne(avec_grossiere=True)) == [(0, False), (0, True), (1, False), (2, False)]


def test_exemples_dans_le_meme_ordre_que_le_schema():
    for exemple in EXEMPLES:
        assert [r["note"] for r in vers_format_genere(exemple)["reponses"]] == [0, 0, 1, 2]


def test_consigne_demande_en_phrases_et_rappelle_les_regles_metier():
    message = message_utilisateur(consigne(avec_grossiere=False))
    assert "2 phrases courtes au plus" in message
    assert "mot de passe" in message and "sans l'éteindre" in message


def ticket_genere(c, textes=("a" * 150, "b" * 150, "c" * 140, "d" * 130)):
    return json.dumps({
        "theme": "Wi-Fi", "nom": c.profil.nom, "service": c.profil.service, "source": c.source,
        "objet": None, "canal": None, "demande": "Le Wi-Fi ne marche plus.",
        "reponses": [
            {"note": n, "grossiere": g, "texte": t}
            for (n, g), t in zip(ordre_du_schema(c), textes)
        ],
        "pointCle": "Vérifier d'abord si le problème est général.",
        "attendu": {"type": ["Incident"], "categorie": ["Réseau"], "urgence": ["Haute"], "impact": ["Basse"]},
    })


def test_ticket_final_remis_dans_l_ordre_de_tickets_js():
    c = consigne(avec_grossiere=True)
    ticket = produire_ticket(ticket_genere(c), c, CATEGORIES)
    assert [(r["note"], r.get("grossiere", False)) for r in ticket["reponses"]] == [
        (2, False), (1, False), (0, False), (0, True)
    ]
    assert ticket["pointCle"].startswith("vérifier")


def test_alertes_sur_les_reponses_notees_2_et_1_seulement():
    ticket = {"reponses": [
        {"note": 2, "texte": "Ne me donnez surtout pas votre MOT DE PASSE."},
        {"note": 1, "texte": "Désactivez le Pare-Feu cinq minutes pour tester."},
        {"note": 0, "texte": "Donnez-moi votre mot de passe et votre identifiant."},
        {"note": 0, "texte": "Rien à signaler ici."},
    ]}
    alertes = alertes_de_relecture(ticket, lire_mots_alertes())
    assert len(alertes) == 2
    assert alertes[0].startswith("bonne réponse (note 2)") and "« mot de passe »" in alertes[0]
    assert "« désactiv »" in alertes[1] and "« pare-feu »" in alertes[1]


def test_pas_d_alerte_sans_mot_sensible():
    ticket = {"reponses": [{"note": 2, "texte": "Vos collègues ont-ils le même problème ?"}]}
    assert alertes_de_relecture(ticket, lire_mots_alertes()) == []


def test_alertes_json_mal_forme_bloque_le_demarrage(tmp_path):
    fichier = tmp_path / "alertes.json"
    fichier.write_text('{"mots": "mot de passe"}', encoding="utf-8")
    with pytest.raises(ErreurConfiguration, match="mots"):
        lire_mots_alertes(fichier)

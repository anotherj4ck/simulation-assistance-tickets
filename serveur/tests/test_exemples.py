"""Tests de la lecture de js/tickets.js et du choix des exemples (few-shot)."""

import json
import random

import pytest

from serveur.configuration import ErreurConfiguration, lire_categories, lire_profils
from serveur.exemples import (
    choisir_exemples,
    en_liste,
    lire_exemples,
    lire_tickets,
    vers_format_genere,
)
from serveur.generateur import message_utilisateur, tirer_consigne

CATEGORIES = lire_categories()

# Tickets dont la bonne réponse est la plus longue des 4 : ils sont écartés des
# exemples. À mettre à jour quand ces tickets seront corrigés dans js/tickets.js.
ECARTES_ATTENDUS = (
    "t14-nouvel-arrivant", "t15-panne-collective", "t17-micro-teams",
    "t19-ingenierie-sociale", "t20-double-ecran", "t21-dossier-supprime",
    "t24-demande-d-acces", "t25-mail-au-mauvais-destinataire",
    "t26-boite-mail-pleine", "t30-alerte-de-certificat",
)

TICKET_VALIDE = """{ id: "a", theme: "T", nom: "N", service: "s", source: "Direct", demande: "d",
  reponses: [ { note: 2, texte: "x" }, { note: 0, texte: "y" }, ],
  attendu: { type: "Incident", categorie: "Réseau", urgence: "Haute", impact: "Basse" } }"""


def ecrire(tmp_path, contenu):
    fichier = tmp_path / "tickets.js"
    fichier.write_text(contenu, encoding="utf-8")
    return fichier


def test_les_30_tickets_du_site_sont_lus():
    tickets = lire_tickets(CATEGORIES)
    assert len(tickets) == 30
    assert tickets[0].id == "t01-reseau"


def test_les_10_tickets_a_bonne_reponse_trop_longue_sont_ecartes():
    exemples, ecartes = lire_exemples(CATEGORIES)
    assert ecartes == ECARTES_ATTENDUS
    assert len(exemples) == 20


def test_format_js_accepte_commentaires_et_virgules_finales(tmp_path):
    fichier = ecrire(tmp_path, f"/* en-tête */\nwindow.TICKETS = [\n  // un ticket\n  {TICKET_VALIDE},\n];\n")
    assert [t.id for t in lire_tickets(CATEGORIES, fichier)] == ["a"]


@pytest.mark.parametrize(
    "contenu, message",
    [
        ("window.TICKETS = [ { id: 'a' } ];", "guillemets doubles"),
        ("window.TICKETS = [ { id: \"a\" ];", "syntaxe"),
        ("var autre = [];", "introuvable"),
        (f"window.TICKETS = [ {TICKET_VALIDE.replace('Direct', 'Pigeon')} ];", "source"),
        (f"window.TICKETS = [ {TICKET_VALIDE.replace('note: 0', 'note: 0, grossière: true')} ];", "grossière"),
        (f"window.TICKETS = [ {TICKET_VALIDE.replace('Réseau', 'Plomberie')} ];", "Plomberie"),
        (f"window.TICKETS = [ {TICKET_VALIDE}, {TICKET_VALIDE} ];", "double"),
    ],
)
def test_ticket_ou_syntaxe_invalide_bloque_le_demarrage(tmp_path, contenu, message):
    with pytest.raises(ErreurConfiguration, match=message):
        lire_tickets(CATEGORIES, ecrire(tmp_path, contenu))


def test_tickets_js_absent_bloque_le_demarrage(tmp_path):
    with pytest.raises(ErreurConfiguration, match="impossible de lire"):
        lire_tickets(CATEGORIES, tmp_path / "absent.js")


def test_exemples_pris_dans_la_categorie_si_possible():
    exemples, _ = lire_exemples(CATEGORIES)
    alea = random.Random(3)
    for _ in range(50):
        choix = choisir_exemples(exemples, "Sécurité", alea)
        assert len(choix) == 2 and len({t.id for t in choix}) == 2
        assert all("Sécurité" in en_liste(t.attendu.categorie) for t in choix)


def test_exemples_completes_quand_la_categorie_en_a_trop_peu():
    exemples, _ = lire_exemples(CATEGORIES)
    choix = choisir_exemples(exemples, "Impression", random.Random(0))
    assert len(choix) == 2
    assert sum("Impression" in en_liste(t.attendu.categorie) for t in choix) == 1


def test_exemple_au_format_genere():
    exemples, _ = lire_exemples(CATEGORIES)
    exemple = vers_format_genere(exemples[0])
    assert "id" not in exemple
    assert exemple["objet"] is None or exemple["source"] == "Courriel"
    assert all(isinstance(v, list) for v in exemple["attendu"].values())
    assert all(isinstance(r["grossiere"], bool) for r in exemple["reponses"])


def test_la_consigne_contient_les_deux_exemples():
    exemples, _ = lire_exemples(CATEGORIES)
    consigne = tirer_consigne("Réseau", "pas trop difficile", None, lire_profils(), exemples, random.Random(5))
    message = message_utilisateur(consigne)
    assert message.count('"reponses"') == 2
    assert "Ne recopie jamais leur scénario" in message
    for exemple in consigne.exemples:
        assert json.dumps(exemple.demande, ensure_ascii=False) in message

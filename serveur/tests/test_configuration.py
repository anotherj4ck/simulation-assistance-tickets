"""Tests de la lecture de configuration. Lancer depuis la racine du dépôt :

    python -m pytest serveur/tests
"""

import json
import random

import pytest

from serveur.configuration import (
    ErreurConfiguration,
    Profils,
    lire_categories,
    lire_profils,
    lire_reglages,
    lire_tickets_par_session,
)
from serveur.generateur import tirer_profil

CATEGORIES_DU_SITE = (
    "Matériel",
    "Poste de travail",
    "Réseau",
    "Logiciel",
    "Impression",
    "Messagerie et collaboratif",
    "Fichiers et partages",
    "Comptes et accès",
    "Sécurité",
)


def test_les_9_categories_de_config_js_sont_lues():
    assert lire_categories() == CATEGORIES_DU_SITE


def test_config_js_absent_bloque_le_demarrage(tmp_path):
    with pytest.raises(ErreurConfiguration, match="impossible de lire"):
        lire_categories(tmp_path / "absent.js")


def test_liste_vide_bloque_le_demarrage(tmp_path):
    fichier = tmp_path / "config.js"
    fichier.write_text("window.CONFIG = { categories: [ ] };", encoding="utf-8")
    with pytest.raises(ErreurConfiguration, match="vide"):
        lire_categories(fichier)


def test_ollama_model_absent_bloque_le_demarrage():
    with pytest.raises(ErreurConfiguration, match="OLLAMA_MODEL"):
        lire_reglages({})


def test_num_ctx_vaut_8192_par_defaut():
    assert lire_reglages({"OLLAMA_MODEL": "m"}).ollama_num_ctx == 8192


@pytest.mark.parametrize("valeur", ["abc", "8192.5", "1024", "4096"])
def test_num_ctx_invalide_bloque_le_demarrage(valeur):
    with pytest.raises(ErreurConfiguration, match="OLLAMA_NUM_CTX"):
        lire_reglages({"OLLAMA_MODEL": "m", "OLLAMA_NUM_CTX": valeur})


def test_profils_json_est_complet():
    profils = lire_profils()
    for cle in Profils.__dataclass_fields__:
        assert getattr(profils, cle), f"liste {cle} vide"


def test_profils_incomplet_bloque_le_demarrage(tmp_path):
    fichier = tmp_path / "profils.json"
    fichier.write_text(json.dumps({"services": ["accueil"]}), encoding="utf-8")
    with pytest.raises(ErreurConfiguration, match="absente ou vide"):
        lire_profils(fichier)


def test_tirage_du_profil_respecte_le_genre():
    profils = lire_profils()
    alea = random.Random(1)
    for _ in range(200):
        p = tirer_profil(profils, alea)
        prenoms = profils.prenoms_femmes if p.genre == "femme" else profils.prenoms_hommes
        civilite = "Mme " if p.genre == "femme" else "M. "
        assert p.nom in prenoms or (
            p.nom.startswith(civilite) and p.nom[len(civilite):] in profils.noms_de_famille
        )
        assert p.service in profils.services and p.ton in profils.tons and p.aisance in profils.aisances


def test_tickets_par_session_lu_dans_config_js():
    assert lire_tickets_par_session() == 5


def test_tickets_par_session_absent_vaut_5_comme_le_site(tmp_path):
    fichier = tmp_path / "config.js"
    fichier.write_text('window.CONFIG = { categories: ["A"] };', encoding="utf-8")
    assert lire_tickets_par_session(fichier) == 5


def test_tickets_par_session_invalide_bloque_le_demarrage(tmp_path):
    fichier = tmp_path / "config.js"
    fichier.write_text("window.CONFIG = { ticketsParSession: cinq };", encoding="utf-8")
    with pytest.raises(ErreurConfiguration, match="ticketsParSession"):
        lire_tickets_par_session(fichier)

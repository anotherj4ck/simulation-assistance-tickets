"""Configuration du serveur : variables d'environnement et données lues dans le site.

Toute erreur ici lève ErreurConfiguration : le serveur refuse alors de démarrer
plutôt que de tourner avec une configuration incomplète.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

# Racine du site (le dossier qui contient index.html, css/ et js/).
RACINE_SITE = Path(__file__).resolve().parent.parent
CONFIG_JS = RACINE_SITE / "js" / "config.js"

# Valeurs fixes du site : elles doivent rester identiques à NIVEAUX, TYPES et
# SOURCES dans js/app.js (le site rejette un ticket qui en sort).
Niveau = Literal["Très basse", "Basse", "Moyenne", "Haute", "Très haute"]
TypeTicket = Literal["Incident", "Demande"]
Source = Literal["Téléphone", "Courriel", "Direct", "Helpdesk", "Autre"]
Difficulte = Literal["facile", "pas trop difficile", "difficile"]

NIVEAUX: tuple[str, ...] = get_args(Niveau)
TYPES: tuple[str, ...] = get_args(TypeTicket)
SOURCES: tuple[str, ...] = get_args(Source)
DIFFICULTES: tuple[str, ...] = get_args(Difficulte)
DIFFICULTE_PAR_DEFAUT: Difficulte = "pas trop difficile"

OLLAMA_URL_PAR_DEFAUT = "http://127.0.0.1:11434"
OLLAMA_TIMEOUT_PAR_DEFAUT = 300.0  # secondes

# Taille du contexte demandée à Ollama (tokens). 8192 suffit largement
# (mesuré : prompt système + consigne avec 2 exemples ≈ 3 500 tokens, ticket ≈ 500) et limite la
# mémoire du cache, pour garder autant que possible le modèle en VRAM sur une
# carte de 8 Go (voir serveur/README.md).
OLLAMA_NUM_CTX_PAR_DEFAUT = 8192
OLLAMA_NUM_CTX_MINIMUM = 6144  # environ 4 000 tokens utilisés : en dessous, Ollama tronquerait le début du prompt

PROFILS_JSON = Path(__file__).resolve().parent / "donnees" / "profils.json"
ALERTES_JSON = Path(__file__).resolve().parent / "donnees" / "alertes.json"


class ErreurConfiguration(Exception):
    """Configuration absente ou invalide : le serveur ne doit pas démarrer."""


@dataclass(frozen=True)
class Reglages:
    ollama_url: str
    ollama_modele: str
    ollama_timeout: float
    ollama_num_ctx: int


def lire_reglages(env: Mapping[str, str] | None = None) -> Reglages:
    """Lit OLLAMA_URL, OLLAMA_MODEL (obligatoire), OLLAMA_TIMEOUT et OLLAMA_NUM_CTX."""
    env = os.environ if env is None else env

    # Pas de modèle par défaut dans le code : il est choisi par l'utilisateur.
    modele = env.get("OLLAMA_MODEL", "").strip()
    if not modele:
        raise ErreurConfiguration(
            "la variable d'environnement OLLAMA_MODEL n'est pas définie.\n"
            "  Indiquez le modèle Ollama à utiliser, par exemple (PowerShell) :\n"
            '    $env:OLLAMA_MODEL = "ministral-3:8b"\n'
            "  La commande « ollama list » affiche les modèles installés."
        )

    url = env.get("OLLAMA_URL", "").strip().rstrip("/") or OLLAMA_URL_PAR_DEFAUT
    if not url.startswith(("http://", "https://")):
        raise ErreurConfiguration(
            f"OLLAMA_URL doit commencer par http:// ou https:// (valeur actuelle : « {url} »)."
        )

    brut = env.get("OLLAMA_TIMEOUT", "").strip()
    if not brut:
        timeout = OLLAMA_TIMEOUT_PAR_DEFAUT
    else:
        try:
            timeout = float(brut.replace(",", "."))
        except ValueError:
            raise ErreurConfiguration(
                f"OLLAMA_TIMEOUT doit être un nombre de secondes (valeur actuelle : « {brut} »)."
            ) from None
        if timeout <= 0:
            raise ErreurConfiguration(f"OLLAMA_TIMEOUT doit être positif (valeur actuelle : {brut}).")

    brut = env.get("OLLAMA_NUM_CTX", "").strip()
    if not brut:
        num_ctx = OLLAMA_NUM_CTX_PAR_DEFAUT
    else:
        try:
            num_ctx = int(brut)
        except ValueError:
            raise ErreurConfiguration(
                f"OLLAMA_NUM_CTX doit être un nombre entier de tokens (valeur actuelle : « {brut} »)."
            ) from None
        if num_ctx < OLLAMA_NUM_CTX_MINIMUM:
            raise ErreurConfiguration(
                f"OLLAMA_NUM_CTX doit valoir au moins {OLLAMA_NUM_CTX_MINIMUM} "
                f"(valeur actuelle : {num_ctx}) : en dessous, le prompt et le ticket seraient tronqués."
            )

    return Reglages(ollama_url=url, ollama_modele=modele, ollama_timeout=timeout, ollama_num_ctx=num_ctx)


# --- Profils d'utilisateurs : serveur/donnees/profils.json --------------------


@dataclass(frozen=True)
class Profils:
    prenoms_femmes: tuple[str, ...]
    prenoms_hommes: tuple[str, ...]
    noms_de_famille: tuple[str, ...]
    services: tuple[str, ...]
    tons: tuple[str, ...]
    aisances: tuple[str, ...]


def lire_profils(chemin: Path = PROFILS_JSON) -> Profils:
    """Charge les listes de profils. Chaque liste doit exister et contenir au
    moins une chaîne non vide ; sinon ErreurConfiguration (pas de démarrage)."""
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as erreur:
        raise ErreurConfiguration(f"impossible de lire {chemin} ({erreur.strerror or erreur}).") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurConfiguration(f"{chemin} n'est pas un JSON valide en UTF-8 ({erreur}).") from None
    if not isinstance(donnees, dict):
        raise ErreurConfiguration(f"{chemin} doit contenir un objet JSON {{ ... }}.")

    listes: dict[str, tuple[str, ...]] = {}
    for cle in Profils.__dataclass_fields__:
        valeur = donnees.get(cle)
        if not isinstance(valeur, list) or not valeur:
            raise ErreurConfiguration(f"{chemin} : la liste « {cle} » est absente ou vide.")
        if not all(isinstance(v, str) and v.strip() for v in valeur):
            raise ErreurConfiguration(f"{chemin} : la liste « {cle} » ne doit contenir que des textes non vides.")
        listes[cle] = tuple(v.strip() for v in valeur)
    return Profils(**listes)


# --- Catégories : lues dans js/config.js, seule source de vérité -------------

_BLOC_CATEGORIES = re.compile(r"\bcategories\s*:\s*\[(.*?)\]", re.DOTALL)
_CHAINE = re.compile(r'"(?:[^"\\\n]|\\.)*"')
_COMMENTAIRE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def lire_categories(chemin: Path = CONFIG_JS) -> tuple[str, ...]:
    """Renvoie la liste `categories` de js/config.js.

    Lève ErreurConfiguration si le fichier est illisible ou si la liste est
    introuvable, vide ou dans un format non reconnu : jamais de liste vide
    silencieuse.
    """
    try:
        texte = chemin.read_text(encoding="utf-8")
    except OSError as erreur:
        raise ErreurConfiguration(
            f"impossible de lire {chemin} ({erreur.strerror or erreur}). "
            "Le serveur en a besoin pour connaître les catégories de tickets."
        ) from None
    except UnicodeDecodeError:
        raise ErreurConfiguration(f"{chemin} n'est pas encodé en UTF-8.") from None

    bloc = _BLOC_CATEGORIES.search(texte)
    if bloc is None:
        raise ErreurConfiguration(f"liste « categories: [ ... ] » introuvable dans {chemin}.")

    contenu = bloc.group(1)
    chaines = _CHAINE.findall(contenu)
    # Tout ce qui n'est ni une chaîne entre guillemets doubles, ni une virgule,
    # ni un commentaire, ni un espace est un format que l'on ne sait pas lire :
    # mieux vaut s'arrêter que de deviner.
    reste = _COMMENTAIRE.sub("", _CHAINE.sub("", contenu)).replace(",", "").strip()
    if reste:
        raise ErreurConfiguration(
            f"format non reconnu pour « categories » dans {chemin} : "
            f"seules des chaînes entre guillemets doubles sont attendues (trouvé : « {reste[:40]} »)."
        )

    categories = tuple(json.loads(c).strip() for c in chaines)
    if not categories:
        raise ErreurConfiguration(f"la liste « categories » de {chemin} est vide.")
    if any(not c for c in categories):
        raise ErreurConfiguration(f"la liste « categories » de {chemin} contient une catégorie vide.")
    if len(set(categories)) != len(categories):
        raise ErreurConfiguration(f"la liste « categories » de {chemin} contient des doublons.")
    return categories


# --- Mots sensibles pour les alertes de relecture : serveur/donnees/alertes.json


def lire_mots_alertes(chemin: Path = ALERTES_JSON) -> tuple[str, ...]:
    """Charge la liste « mots ». Fichier absent ou mal formé = ErreurConfiguration.
    Une liste vide est permise (alertes désactivées) ; le serveur l'affiche au démarrage."""
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except OSError as erreur:
        raise ErreurConfiguration(f"impossible de lire {chemin} ({erreur.strerror or erreur}).") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
        raise ErreurConfiguration(f"{chemin} n'est pas un JSON valide en UTF-8 ({erreur}).") from None
    mots = donnees.get("mots") if isinstance(donnees, dict) else None
    if not isinstance(mots, list):
        raise ErreurConfiguration(f"{chemin} : la liste « mots » est absente.")
    if not all(isinstance(m, str) and m.strip() for m in mots):
        raise ErreurConfiguration(f"{chemin} : la liste « mots » ne doit contenir que des textes non vides.")
    return tuple(m.strip() for m in mots)

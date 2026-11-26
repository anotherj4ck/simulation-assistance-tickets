"""Série de tickets publiée par le formateur, que les apprenants résolvent.

La série active est un fichier JSON (donnée d'exécution, ignorée par Git) :
    { "publiee_le": "2026-11-26T10:42:00+01:00", "tickets": [ ...5 tickets... ] }

Les tickets sont au format de js/tickets.js et validés par le même validateur
strict que lui. Le fichier est écrit de façon atomique : un fichier temporaire
dans le même dossier, puis un renommage. Un lecteur voit donc toujours soit
l'ancienne série, soit la nouvelle, jamais un fichier à moitié écrit.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from .exemples import valider_tickets

CHEMIN_SERIE = Path(__file__).resolve().parent / "donnees" / "serie-active.json"


class ErreurSerie(Exception):
    """Série refusée (publication) ou illisible (lecture) ; message en français."""


def valider_serie(tickets: object, categories: tuple[str, ...], nb_attendu: int) -> list:
    if not isinstance(tickets, list):
        raise ErreurSerie("« tickets » doit être une liste de tickets.")
    if len(tickets) != nb_attendu:
        raise ErreurSerie(
            f"une série contient exactement {nb_attendu} tickets (ticketsParSession dans js/config.js) ; "
            f"reçu : {len(tickets)}."
        )
    _, problemes = valider_tickets(tickets, categories)
    if problemes:
        reste = f" ; … et {len(problemes) - 10} autre(s)" if len(problemes) > 10 else ""
        raise ErreurSerie("tickets invalides : " + " ; ".join(problemes[:10]) + reste)
    return tickets


def ecrire_atomique(chemin: Path, texte: str) -> None:
    """Écrit dans un fichier temporaire du même dossier, puis le renomme.
    os.replace remplace la cible en une seule opération (Windows compris)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, prefix=f".{chemin.stem}-", suffix=".tmp")
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8", newline="\n") as fichier:
            fichier.write(texte)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(temporaire, chemin)
    except BaseException:
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


def publier_serie(tickets: list, categories: tuple[str, ...], nb_attendu: int, chemin: Path) -> dict:
    """Valide puis enregistre la série ; elle remplace la précédente."""
    valider_serie(tickets, categories, nb_attendu)
    serie = {"publiee_le": datetime.now().astimezone().isoformat(timespec="seconds"), "tickets": tickets}
    ecrire_atomique(chemin, json.dumps(serie, ensure_ascii=False, indent=2) + "\n")
    return serie


def lire_serie(categories: tuple[str, ...], nb_attendu: int, chemin: Path) -> dict | None:
    """Série active, ou None s'il n'y en a pas.

    Elle est revalidée à chaque lecture : si le fichier a été modifié à la main,
    ou si js/config.js a changé depuis la publication, l'erreur est signalée
    (ErreurSerie) au lieu d'envoyer aux apprenants une série devenue invalide.
    """
    try:
        texte = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as erreur:
        raise ErreurSerie(f"la série active est illisible ({erreur}).") from None
    try:
        serie = json.loads(texte)
    except json.JSONDecodeError as erreur:
        raise ErreurSerie(f"la série active n'est pas un JSON valide ({erreur.msg}).") from None
    if not isinstance(serie, dict) or not isinstance(serie.get("publiee_le"), str):
        raise ErreurSerie("la série active n'a pas le format attendu (publiee_le, tickets).")
    valider_serie(serie.get("tickets"), categories, nb_attendu)
    return {"publiee_le": serie["publiee_le"], "tickets": serie["tickets"]}


def retirer_serie(chemin: Path) -> bool:
    """Supprime la série active ; False s'il n'y en avait pas."""
    try:
        chemin.unlink()
    except FileNotFoundError:
        return False
    return True

"""Série de tickets publiée par le formateur, que les apprenants résolvent.

La série active est un fichier JSON (donnée d'exécution, ignorée par Git) :
    { "mode": "fixe" | "tirage", "publiee_le": "2026-11-26T10:42:00+01:00", "tickets": [ ... ] }

Deux modes (N = ticketsParSession de js/config.js, soit 5) :
- « fixe » : exactement N tickets ; chaque apprenant reçoit les mêmes, dans l'ordre publié ;
- « tirage » : de N à MAX_TICKETS_TIRAGE tickets ; à chaque session, le site apprenant
  en tire N au hasard, dans un ordre aléatoire. Le serveur ne garde aucun état par apprenant.
Un fichier à l'ancien format (sans « mode ») est lu comme « fixe ».

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

MODES = ("fixe", "tirage")
MODE_PAR_DEFAUT = "fixe"  # aussi celui d'un fichier à l'ancien format, sans « mode »
# Plafond du mode « tirage » : la sélection est envoyée à chaque apprenant à
# chaque session ; 200 tickets pèsent environ 300 Ko.
MAX_TICKETS_TIRAGE = 200


class ErreurSerie(Exception):
    """Série refusée (publication) ou illisible (lecture) ; message en français."""


def valider_serie(mode: object, tickets: object, categories: tuple[str, ...], nb_par_session: int) -> list:
    if mode not in MODES:
        raise ErreurSerie(f"mode inconnu : « {mode} » (valeurs possibles : {', '.join(MODES)}).")
    if not isinstance(tickets, list):
        raise ErreurSerie("« tickets » doit être une liste de tickets.")
    if mode == "fixe" and len(tickets) != nb_par_session:
        raise ErreurSerie(
            f"une série fixe contient exactement {nb_par_session} tickets (ticketsParSession dans js/config.js) ; "
            f"reçu : {len(tickets)}."
        )
    if mode == "tirage" and not nb_par_session <= len(tickets) <= MAX_TICKETS_TIRAGE:
        raise ErreurSerie(
            f"un tirage dans la sélection demande au moins {nb_par_session} tickets (ticketsParSession dans "
            f"js/config.js) et {MAX_TICKETS_TIRAGE} au plus ; reçu : {len(tickets)}."
        )
    # Le validateur refuse aussi les identifiants en double : le tirage ne peut
    # donc jamais donner deux fois le même ticket à un apprenant.
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


def publier_serie(mode: str, tickets: list, categories: tuple[str, ...], nb_par_session: int, chemin: Path) -> dict:
    """Valide puis enregistre la série ; elle remplace la précédente."""
    valider_serie(mode, tickets, categories, nb_par_session)
    serie = {
        "mode": mode,
        "publiee_le": datetime.now().astimezone().isoformat(timespec="seconds"),
        "tickets": tickets,
    }
    ecrire_atomique(chemin, json.dumps(serie, ensure_ascii=False, indent=2) + "\n")
    return serie


def lire_serie(categories: tuple[str, ...], nb_par_session: int, chemin: Path) -> dict | None:
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
        raise ErreurSerie("la série active n'a pas le format attendu (mode, publiee_le, tickets).")
    mode = serie.get("mode", MODE_PAR_DEFAUT)  # ancien format, sans mode : série fixe
    valider_serie(mode, serie.get("tickets"), categories, nb_par_session)
    return {"mode": mode, "publiee_le": serie["publiee_le"], "tickets": serie["tickets"]}


def retirer_serie(chemin: Path) -> bool:
    """Supprime la série active ; False s'il n'y en avait pas."""
    try:
        chemin.unlink()
    except FileNotFoundError:
        return False
    return True

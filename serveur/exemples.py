"""Tickets existants (js/tickets.js) utilisés comme exemples (few-shot).

La lecture est stricte, comme pour js/config.js : fichier illisible, syntaxe
non reconnue ou ticket invalide = ErreurConfiguration, le serveur ne démarre pas.
Le site, lui, se contente d'ignorer un ticket mal rempli ; le serveur préfère
signaler l'erreur tout de suite (ex. une clé « grossière » mal orthographiée,
que le site ignorerait sans rien dire).
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator, model_validator

from .configuration import RACINE_SITE, ErreurConfiguration, Niveau, Source, TypeTicket

TICKETS_JS = RACINE_SITE / "js" / "tickets.js"

NB_EXEMPLES = 2


# --- Lecture de js/tickets.js -----------------------------------------------

_IDENTIFIANT = re.compile(r"[A-Za-z_$][\w$]*")
_DEUX_POINTS = re.compile(r"\s*:")
_DEBUT = re.compile(r"\bwindow\.TICKETS\s*=\s*")


def _ligne(source: str, position: int) -> int:
    return source.count("\n", 0, position) + 1


def _js_vers_json(source: str, debut: int, chemin: Path) -> str:
    """Convertit le littéral JavaScript qui commence à `debut` en JSON :
    clés sans guillemets, commentaires et virgules finales. Tout le reste
    (guillemets simples, variables, expressions) est refusé."""

    def erreur(position: int, message: str) -> ErreurConfiguration:
        return ErreurConfiguration(f"{chemin}, ligne {_ligne(source, position)} : {message}")

    sortie: list[str] = []
    i, n = debut, len(source)
    while i < n:
        c = source[i]
        if c == '"':
            j = i + 1
            while j < n and source[j] != '"':
                if source[j] == "\n":
                    raise erreur(i, "chaîne non fermée (guillemet manquant)")
                j += 2 if source[j] == "\\" else 1
            if j >= n:
                raise erreur(i, "chaîne non fermée (guillemet manquant)")
            sortie.append(source[i : j + 1].replace("\\'", "'"))  # \' existe en JS, pas en JSON
            i = j + 1
        elif source.startswith("//", i):
            fin = source.find("\n", i)
            i = n if fin == -1 else fin
        elif source.startswith("/*", i):
            fin = source.find("*/", i + 2)
            if fin == -1:
                raise erreur(i, "commentaire /* non fermé")
            i = fin + 2
        elif c in "'`":
            raise erreur(i, "seules les chaînes entre guillemets doubles sont acceptées")
        elif c.isalpha() or c in "_$":
            mot = _IDENTIFIANT.match(source, i).group()
            i += len(mot)
            if _DEUX_POINTS.match(source, i):
                sortie.append(json.dumps(mot))  # clé : id -> "id"
            elif mot in ("true", "false", "null"):
                sortie.append(mot)
            else:
                raise erreur(i - len(mot), f"« {mot} » inattendu (seules des valeurs littérales sont acceptées)")
        elif c in "]}":
            # Virgule finale autorisée en JS, pas en JSON : on la retire.
            k = len(sortie) - 1
            while k >= 0 and sortie[k].isspace():
                k -= 1
            if k >= 0 and sortie[k] == ",":
                del sortie[k]
            sortie.append(c)
            i += 1
        else:
            sortie.append(c)
            i += 1
    return "".join(sortie)


def _lire_brut(chemin: Path) -> list:
    try:
        source = chemin.read_text(encoding="utf-8")
    except OSError as e:
        raise ErreurConfiguration(f"impossible de lire {chemin} ({e.strerror or e}).") from None
    except UnicodeDecodeError:
        raise ErreurConfiguration(f"{chemin} n'est pas encodé en UTF-8.") from None

    debut = _DEBUT.search(source)
    if debut is None:
        raise ErreurConfiguration(f"« window.TICKETS = [ ... ] » introuvable dans {chemin}.")
    texte = _js_vers_json(source, debut.end(), chemin)
    try:
        tickets, fin = json.JSONDecoder().raw_decode(texte)
    except json.JSONDecodeError as e:
        extrait = texte[max(0, e.pos - 40) : e.pos + 40].replace("\n", " ")
        raise ErreurConfiguration(f"erreur de syntaxe dans {chemin} ({e.msg}), près de : « {extrait} »") from None
    if texte[fin:].strip() not in ("", ";"):
        raise ErreurConfiguration(f"{chemin} : contenu inattendu après la liste des tickets.")
    if not isinstance(tickets, list):
        raise ErreurConfiguration(f"{chemin} : window.TICKETS doit être une liste [ ... ].")
    return tickets


# --- Validation : même format que js/tickets.js ------------------------------


class ReponseSite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Literal[0, 1, 2]
    grossiere: bool = False
    texte: str = Field(min_length=1)


class AttenduSite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TypeTicket | list[TypeTicket]
    categorie: str | list[str]
    urgence: Niveau | list[Niveau]
    impact: Niveau | list[Niveau]

    @field_validator("categorie")
    @classmethod
    def _categories_connues(cls, valeur: str | list[str], info: ValidationInfo) -> str | list[str]:
        connues = (info.context or {}).get("categories", ())
        inconnues = [v for v in en_liste(valeur) if v not in connues]
        if inconnues:
            raise ValueError(f"catégorie absente de js/config.js : {', '.join(inconnues)}")
        return valeur


class TicketSite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    theme: str | None = None
    nom: str = Field(min_length=1)
    service: str | None = None
    source: Source
    objet: str | None = None
    canal: str | None = None
    demande: str = Field(min_length=1)
    reponses: list[ReponseSite] = Field(min_length=2)
    pointCle: str | None = None
    attendu: AttenduSite

    @model_validator(mode="after")
    def _objet_si_courriel(self) -> "TicketSite":
        if self.source == "Courriel" and not self.objet:
            raise ValueError("objet obligatoire pour un courriel")
        if not any(r.note == 2 for r in self.reponses):
            raise ValueError("aucune bonne réponse (note 2)")
        return self


def en_liste(valeur: str | list[str]) -> list[str]:
    return valeur if isinstance(valeur, list) else [valeur]


def _message_fr(erreur: dict) -> str:
    """Message Pydantic traduit pour le formateur (les plus courants)."""
    type_ = erreur["type"]
    contexte = erreur.get("ctx") or {}
    if type_ == "missing":
        return "champ obligatoire manquant"
    if type_ == "extra_forbidden":
        return "champ inconnu (faute de frappe ?)"
    if type_ == "literal_error":
        attendu = str(contexte.get("expected", "?")).replace(" or ", " ou ")
        return f"valeur non autorisée (attendu : {attendu})"
    if type_ == "string_too_short":
        return "texte vide"
    if type_ == "too_short":
        return f"au moins {contexte.get('min_length', '?')} élément(s) attendu(s)"
    if type_ in ("model_type", "model_attributes_type"):
        return "ce n'est pas un ticket { … }"
    if type_ in ("string_type", "bool_type", "list_type"):
        attendu = {"string_type": "un texte", "bool_type": "true ou false", "list_type": "une liste [ … ]"}[type_]
        return f"type incorrect (attendu : {attendu})"
    if type_ == "value_error":
        return str(contexte.get("error", erreur["msg"]))
    return erreur["msg"]


@dataclass(frozen=True)
class ExamenTicket:
    """Résultat de la validation d'un ticket : `ticket` est None s'il est invalide."""

    position: int
    id: str
    ticket: TicketSite | None
    problemes: tuple[str, ...]  # « champ : message », vide si le ticket est valide


def examiner_tickets(bruts: list, categories: tuple[str, ...]) -> list[ExamenTicket]:
    """Valide chaque ticket séparément avec le validateur strict de js/tickets.js."""
    examens = []
    for n, brut in enumerate(bruts, 1):
        nom = str(brut.get("id") or "sans id") if isinstance(brut, dict) else "?"
        try:
            ticket = TicketSite.model_validate(brut, context={"categories": categories})
            examens.append(ExamenTicket(n, nom, ticket, ()))
        except ValidationError as e:
            problemes = tuple(
                f"{'.'.join(str(x) for x in err['loc']) or 'ticket'} : {_message_fr(err)}" for err in e.errors()
            )
            examens.append(ExamenTicket(n, nom, None, problemes))
    return examens


def valider_tickets(bruts: list, categories: tuple[str, ...]) -> tuple[list[TicketSite], list[str]]:
    """Validation stricte, commune à js/tickets.js et aux séries publiées par le
    formateur. Renvoie (tickets valides, problèmes) ; aucun problème = tout est valide."""
    problemes: list[str] = []
    tickets: list[TicketSite] = []
    for examen in examiner_tickets(bruts, categories):
        if examen.ticket is not None:
            tickets.append(examen.ticket)
        problemes += [f"ticket n° {examen.position} ({examen.id}) : {p}" for p in examen.problemes]
    ids = [t.id for t in tickets]
    problemes += [f"identifiant en double : {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    return tickets, problemes


def lire_tickets(categories: tuple[str, ...], chemin: Path = TICKETS_JS) -> tuple[TicketSite, ...]:
    """Lit et valide tous les tickets du site. Le moindre problème bloque le démarrage."""
    tickets, problemes = valider_tickets(_lire_brut(chemin), categories)
    if problemes:
        details = "\n  - ".join(problemes[:10])
        reste = f"\n  … et {len(problemes) - 10} autre(s)" if len(problemes) > 10 else ""
        raise ErreurConfiguration(f"{chemin} contient des tickets invalides :\n  - {details}{reste}")
    if not tickets:
        raise ErreurConfiguration(f"{chemin} ne contient aucun ticket.")
    return tuple(tickets)


# --- Choix et mise en forme des exemples ------------------------------------


def bonne_reponse_trop_longue(ticket: TicketSite) -> bool:
    """La bonne réponse est-elle strictement la plus longue ? (même règle que
    le contrôle des tickets générés)."""
    bonne = next(r for r in ticket.reponses if r.note == 2)
    autres = [len(r.texte) for r in ticket.reponses if r is not bonne]
    return bool(autres) and len(bonne.texte) > max(autres)


def peut_servir_d_exemple(ticket: TicketSite) -> bool:
    """Un exemple doit respecter les règles imposées au générateur, sinon il
    enseignerait au modèle le défaut que l'on rejette ensuite."""
    notes = [r.note for r in ticket.reponses]
    return (
        len(ticket.reponses) == 4
        and notes.count(2) == 1
        and notes.count(1) == 1
        and sum(r.grossiere for r in ticket.reponses) <= 1
        and bool(ticket.theme and ticket.service and ticket.pointCle)
        and not bonne_reponse_trop_longue(ticket)
    )


def lire_exemples(
    categories: tuple[str, ...], chemin: Path = TICKETS_JS
) -> tuple[tuple[TicketSite, ...], tuple[str, ...]]:
    """Renvoie (tickets utilisables comme exemples, identifiants écartés)."""
    tickets = lire_tickets(categories, chemin)
    exemples = tuple(t for t in tickets if peut_servir_d_exemple(t))
    ecartes = tuple(t.id for t in tickets if not peut_servir_d_exemple(t))
    if len(exemples) < NB_EXEMPLES:
        raise ErreurConfiguration(
            f"{chemin} : il faut au moins {NB_EXEMPLES} tickets utilisables comme exemples "
            f"(4 réponses, bonne réponse pas la plus longue…) ; trouvé : {len(exemples)}."
        )
    return exemples, ecartes


def choisir_exemples(
    exemples: tuple[TicketSite, ...], categorie: str, alea: random.Random, nb: int = NB_EXEMPLES
) -> tuple[TicketSite, ...]:
    """`nb` exemples au hasard, de préférence dans la catégorie demandée,
    complétés au besoin par des tickets d'autres catégories."""
    meme_categorie = [t for t in exemples if categorie in en_liste(t.attendu.categorie)]
    autres = [t for t in exemples if categorie not in en_liste(t.attendu.categorie)]
    choix = alea.sample(meme_categorie, min(nb, len(meme_categorie)))
    choix += alea.sample(autres, nb - len(choix))
    return tuple(choix)


def vers_format_genere(ticket: TicketSite) -> dict:
    """Le ticket au format JSON que le modèle doit produire (tableaux dans
    attendu, objet et canal toujours présents, grossiere toujours présent, sans id)."""
    return {
        "theme": ticket.theme,
        "nom": ticket.nom,
        "service": ticket.service,
        "source": ticket.source,
        "objet": ticket.objet if ticket.source == "Courriel" else None,
        "canal": ticket.canal if ticket.source == "Autre" else None,
        "demande": ticket.demande,
        # Même ordre que celui imposé par le schéma : fausse, fausse (la
        # grossière en second), en partie vraie, bonne.
        "reponses": [
            {"note": r.note, "grossiere": r.grossiere, "texte": r.texte}
            for r in sorted(ticket.reponses, key=lambda r: (r.note, r.grossiere))
        ],
        "pointCle": ticket.pointCle,
        "attendu": {
            "type": en_liste(ticket.attendu.type),
            "categorie": en_liste(ticket.attendu.categorie),
            "urgence": en_liste(ticket.attendu.urgence),
            "impact": en_liste(ticket.attendu.impact),
        },
    }

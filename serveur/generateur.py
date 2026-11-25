"""Génération d'un ticket : consigne, schéma JSON pour Ollama, validation,
contrôles de qualité et mise au format de js/tickets.js.

Ce module ne fait aucun appel réseau : il prépare la requête et juge la réponse.
"""

from __future__ import annotations

import json
import random
import re
import secrets
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
)

from .configuration import (
    NIVEAUX,
    SOURCES,
    TYPES,
    Difficulte,
    ErreurConfiguration,
    Niveau,
    Profils,
    Source,
    TypeTicket,
)
from .exemples import TicketSite, choisir_exemples, vers_format_genere

CHEMIN_PROMPT = Path(__file__).resolve().parent / "prompts" / "generateur_ticket.md"

# Probabilité (60 %) qu'un ticket contienne une réponse grossière (✗✗).
# Chaque ticket a 2 réponses fausses, dont au plus 1 grossière, donc en moyenne :
#   0,6 × 1 / 2 = 0,3, soit 30 % des réponses fausses sont grossières
# (même proportion que les tickets de js/tickets.js : 18 sur 60).
# Le serveur tire au sort et impose le résultat au modèle, puis le vérifie :
# un LLM respecte mal une proportion demandée en langage naturel.
PROBABILITE_TICKET_AVEC_GROSSIERE = 0.6

# Probabilité (90 %) que l'utilisateur soit nommé « M. » / « Mme » + nom de
# famille plutôt que par son prénom seul : 27 tickets sur 30 de js/tickets.js.
PROBABILITE_CIVILITE = 0.9

# Longueurs visées (caractères), mesurées sur js/tickets.js. Elles sont aussi
# écrites dans prompts/generateur_ticket.md : modifier les deux ensemble.
# (La demande, elle, est visée en phrases : voir LONGUEUR_DEMANDE_EN_PHRASES.)
CIBLE_REPONSE = (120, 190)
CIBLE_POINT_CLE = (80, 250)

# La demande est décrite au modèle en phrases : il compte mal les caractères.
# Le contrôle côté serveur, lui, reste en caractères (LONGUEUR_MAX_DEMANDE).
LONGUEUR_DEMANDE_EN_PHRASES = "2 phrases courtes au plus"

# Rappel court des règles métier (détaillées dans prompts/generateur_ticket.md).
RAPPEL_REGLES_METIER = (
    "ne jamais demander, dicter ni transmettre un mot de passe ; vérifier l'identité avant toute action"
    " sur un compte ; ne jamais désactiver l'antivirus ni le pare-feu ; ne jamais accorder de droits"
    " administrateur pour contourner une procédure ; ne jamais utiliser un réseau ou un compte tiers ;"
    " rançongiciel suspecté : isoler le poste du réseau sans l'éteindre"
)

# Rejet seulement si une longueur dépasse largement ces cibles.
LONGUEUR_MAX_DEMANDE = 250
LONGUEUR_MAX_REPONSE = 300
LONGUEUR_MAX_POINT_CLE = 400

_alea = random.Random()


def lire_prompt_systeme(chemin: Path = CHEMIN_PROMPT) -> str:
    try:
        texte = chemin.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as erreur:
        raise ErreurConfiguration(f"impossible de lire le prompt {chemin} ({erreur}).") from None
    if not texte:
        raise ErreurConfiguration(f"le prompt {chemin} est vide.")
    return texte


# --- Consigne : les paramètres d'une génération ------------------------------


@dataclass(frozen=True)
class Profil:
    """Utilisateur imposé au modèle : on ne compte pas sur lui pour varier."""

    nom: str
    genre: Literal["femme", "homme"]
    service: str
    ton: str
    aisance: str


def tirer_profil(profils: Profils, alea: random.Random = _alea) -> Profil:
    genre = alea.choice(("femme", "homme"))
    if alea.random() < PROBABILITE_CIVILITE:
        nom = ("Mme " if genre == "femme" else "M. ") + alea.choice(profils.noms_de_famille)
    else:
        nom = alea.choice(profils.prenoms_femmes if genre == "femme" else profils.prenoms_hommes)
    return Profil(
        nom=nom,
        genre=genre,
        service=alea.choice(profils.services),
        ton=alea.choice(profils.tons),
        aisance=alea.choice(profils.aisances),
    )


@dataclass(frozen=True)
class Consigne:
    categorie: str
    source: str
    difficulte: str
    avec_grossiere: bool
    profil: Profil
    exemples: tuple[TicketSite, ...]


def tirer_consigne(
    categorie: str,
    difficulte: str,
    source: str | None,
    profils: Profils,
    exemples: tuple[TicketSite, ...],
    alea: random.Random = _alea,
) -> Consigne:
    """Complète la demande : source tirée au sort si absente, réponse grossière
    ou non, profil de l'utilisateur, tickets d'exemple."""
    return Consigne(
        categorie=categorie,
        source=source or alea.choice(SOURCES),
        difficulte=difficulte,
        avec_grossiere=alea.random() < PROBABILITE_TICKET_AVEC_GROSSIERE,
        profil=tirer_profil(profils, alea),
        exemples=choisir_exemples(exemples, categorie, alea),
    )


def message_utilisateur(consigne: Consigne, motifs_precedents: list[str] | None = None) -> str:
    """Message envoyé au modèle après le prompt système."""
    if consigne.source == "Courriel":
        precision_source = "objet obligatoire, canal = null"
    elif consigne.source == "Autre":
        precision_source = "canal obligatoire, objet = null"
    else:
        precision_source = "objet = null, canal = null"

    if consigne.avec_grossiere:
        grossiere = "oui : exactement une des deux réponses fausses a grossiere = true."
    else:
        grossiere = "non : les deux réponses fausses sont plausibles, grossiere = false pour les quatre réponses."

    profil = consigne.profil
    lignes = [
        f"Voici {len(consigne.exemples)} tickets de référence, au format JSON attendu. Ils montrent le niveau,"
        " le ton et la longueur attendus. Ne recopie jamais leur scénario : ni leur problème, ni leurs"
        " phrases, ni leurs réponses. Invente un cas différent.",
    ]
    for n, exemple in enumerate(consigne.exemples, 1):
        lignes += ["", f"Exemple {n} :", json.dumps(vers_format_genere(exemple), ensure_ascii=False, indent=2)]
    lignes += [
        "",
        "Rédige un nouveau ticket, sur un cas concret, avec ces paramètres :",
        f"- un problème différent de ceux des exemples, mais qui relève bien de la catégorie {consigne.categorie}",
        f"- utilisateur : nom = « {profil.nom} », service = « {profil.service} » (recopie-les tels quels) ;"
        f" c'est {'une femme' if profil.genre == 'femme' else 'un homme'}, accorde les mots en conséquence",
        f"- ton de l'utilisateur : {profil.ton}",
        f"- aisance avec l'informatique : {profil.aisance}",
        f"- catégorie principale : {consigne.categorie} (elle doit figurer dans attendu.categorie)",
        f"- source : {consigne.source} ({precision_source})",
        f"- difficulté : {consigne.difficulte}",
        f"- réponse grossière : {grossiere}",
        f"- demande : {LONGUEUR_DEMANDE_EN_PHRASES}, quel que soit le ton : il se voit dans les mots"
        " choisis, pas dans la longueur",
        f"- réponses : chacune de {CIBLE_REPONSE[0]} à {CIBLE_REPONSE[1]} caractères, dans l'ordre imposé :"
        " les deux fausses, puis la réponse en partie vraie, puis la bonne en dernier ; la bonne doit être"
        " plus courte que la plus longue des trois autres",
        f"- règles métier, pour les réponses notées 2 et 1 : {RAPPEL_REGLES_METIER}",
    ]
    if motifs_precedents:
        lignes += ["", "Ta tentative précédente a été rejetée pour ces raisons :"]
        lignes += [f"- {motif}" for motif in motifs_precedents]
        lignes.append("Corrige ces points dans le nouveau ticket.")
    return "\n".join(lignes)


# --- Schéma JSON envoyé à Ollama (paramètre « format ») ----------------------


def schema_ticket(categories: tuple[str, ...], consigne: Consigne) -> dict:
    """Schéma du ticket, ajusté à la consigne.

    - Les champs de « attendu » sont toujours des tableaux (1 ou 2 valeurs) :
      les grammaires de sortie structurée gèrent mal « chaîne ou tableau ».
      Le serveur remet une chaîne quand il n'y a qu'une valeur.
    - « objet » et « canal » sont toujours présents : chaîne quand la source
      l'exige, null sinon (le serveur revérifie de toute façon).
    - « nom » et « service » ne peuvent prendre que la valeur tirée au sort.
    - Les 4 réponses sont imposées dans cet ordre : fausse, fausse (grossière
      si la consigne le demande), en partie vraie, bonne. Le modèle écrit
      ainsi la bonne réponse en dernier, en connaissant déjà la longueur des
      trois autres. L'ordre affiché importe peu : le site le mélange.
    """
    texte = {"type": "string"}

    def reponse(note: int, grossiere: bool) -> dict:
        return {
            "type": "object",
            "properties": {
                "note": {"type": "integer", "enum": [note]},
                "grossiere": {"type": "boolean", "enum": [grossiere]},
                "texte": texte,
            },
            "required": ["note", "grossiere", "texte"],
            "additionalProperties": False,
        }

    def liste(valeurs: tuple[str, ...]) -> dict:
        return {
            "type": "array",
            "items": {"type": "string", "enum": list(valeurs)},
            "minItems": 1,
            "maxItems": 2,
        }

    return {
        "type": "object",
        "properties": {
            "theme": texte,
            "nom": {"type": "string", "enum": [consigne.profil.nom]},
            "service": {"type": "string", "enum": [consigne.profil.service]},
            "source": {"type": "string", "enum": [consigne.source]},
            "objet": texte if consigne.source == "Courriel" else {"type": "null"},
            "canal": texte if consigne.source == "Autre" else {"type": "null"},
            "demande": texte,
            "reponses": {
                "type": "array",
                # « items: false » n'est pas accepté par Ollama ; minItems et
                # maxItems suffisent à limiter le tableau aux 4 réponses.
                "prefixItems": [
                    reponse(0, False),
                    reponse(0, consigne.avec_grossiere),
                    reponse(1, False),
                    reponse(2, False),
                ],
                "minItems": 4,
                "maxItems": 4,
            },
            "pointCle": texte,
            "attendu": {
                "type": "object",
                "properties": {
                    "type": liste(TYPES),
                    "categorie": liste(categories),
                    "urgence": liste(NIVEAUX),
                    "impact": liste(NIVEAUX),
                },
                "required": ["type", "categorie", "urgence", "impact"],
                "additionalProperties": False,
            },
        },
        "required": [
            "theme", "nom", "service", "source", "objet", "canal",
            "demande", "reponses", "pointCle", "attendu",
        ],
        "additionalProperties": False,
    }


# --- Validation Pydantic de la réponse du modèle -----------------------------

Texte = Annotated[str, StringConstraints(strip_whitespace=True)]


class ReponseGeneree(BaseModel):
    note: Literal[0, 1, 2]
    grossiere: bool = False
    texte: Texte


class AttenduGenere(BaseModel):
    type: list[TypeTicket] = Field(min_length=1, max_length=2)
    categorie: list[str] = Field(min_length=1, max_length=2)
    urgence: list[Niveau] = Field(min_length=1, max_length=2)
    impact: list[Niveau] = Field(min_length=1, max_length=2)

    @field_validator("categorie")
    @classmethod
    def _categories_connues(cls, valeurs: list[str], info: ValidationInfo) -> list[str]:
        connues = (info.context or {}).get("categories")
        if connues is None:
            raise ValueError("liste des catégories non fournie au validateur")
        inconnues = [v for v in valeurs if v not in connues]
        if inconnues:
            raise ValueError(f"catégorie inconnue : {', '.join(inconnues)}")
        return valeurs


class TicketGenere(BaseModel):
    theme: Texte
    nom: Texte
    service: Texte
    source: Source
    objet: Texte | None = None
    canal: Texte | None = None
    demande: Texte
    reponses: list[ReponseGeneree]
    pointCle: Texte
    attendu: AttenduGenere

    @field_validator("pointCle")
    @classmethod
    def _sans_prefixe(cls, valeur: str) -> str:
        # Le site affiche déjà « Point clé : » devant ce texte.
        return re.sub(r"^point\s+cl[ée]\s*:\s*", "", valeur, flags=re.IGNORECASE)


class TicketRejete(Exception):
    """Ticket refusé ; `motifs` explique pourquoi (en français)."""

    def __init__(self, motifs: list[str]):
        super().__init__(" ; ".join(motifs))
        self.motifs = motifs


def analyser(contenu: str, categories: tuple[str, ...]) -> TicketGenere:
    try:
        donnees = json.loads(contenu)
    except json.JSONDecodeError as erreur:
        raise TicketRejete(
            [f"la réponse du modèle n'est pas un JSON valide ({erreur.msg}, position {erreur.pos})"]
        ) from None
    try:
        return TicketGenere.model_validate(donnees, context={"categories": categories})
    except ValidationError as erreur:
        details = [
            f"{'.'.join(str(x) for x in e['loc']) or 'ticket'} : {e['msg']}"
            for e in erreur.errors()[:5]
        ]
        raise TicketRejete(["le ticket ne respecte pas le schéma (" + " ; ".join(details) + ")"]) from None


# --- Contrôles de qualité ----------------------------------------------------


def motifs_de_rejet(ticket: TicketGenere, consigne: Consigne) -> list[str]:
    """Liste des problèmes du ticket ; vide si le ticket est acceptable."""
    motifs: list[str] = []

    for champ in ("theme", "nom", "service", "demande", "pointCle"):
        if not getattr(ticket, champ):
            motifs.append(f"le champ {champ} est vide")
    for i, reponse in enumerate(ticket.reponses, 1):
        if not reponse.texte:
            motifs.append(f"la réponse {i} est vide")

    # 1. Exactement 4 réponses.
    if len(ticket.reponses) != 4:
        motifs.append(f"il faut exactement 4 réponses (reçu : {len(ticket.reponses)})")

    # 2. Exactement 1 bonne réponse et 1 réponse en partie vraie.
    notes = [r.note for r in ticket.reponses]
    if notes.count(2) != 1 or notes.count(1) != 1:
        motifs.append(
            "il faut exactement 1 bonne réponse (note 2) et 1 réponse en partie vraie (note 1) "
            f"(reçu : {notes.count(2)} note 2 et {notes.count(1)} note 1)"
        )
    else:
        # 3. La bonne réponse ne doit pas être strictement la plus longue.
        bonne = next(r for r in ticket.reponses if r.note == 2)
        autres = [len(r.texte) for r in ticket.reponses if r is not bonne]
        if autres and len(bonne.texte) > max(autres):
            motifs.append(
                f"la bonne réponse est la plus longue des 4 ({len(bonne.texte)} caractères, "
                f"la plus longue des autres en fait {max(autres)}) : allonge les réponses fausses"
            )

    # Réponse grossière : seulement sur une réponse fausse, et autant que demandé.
    for i, reponse in enumerate(ticket.reponses, 1):
        if reponse.grossiere and reponse.note != 0:
            motifs.append(f"la réponse {i} est marquée grossière alors que sa note est {reponse.note}")
    nb_grossieres = sum(1 for r in ticket.reponses if r.grossiere and r.note == 0)
    attendues = 1 if consigne.avec_grossiere else 0
    if nb_grossieres != attendues:
        motifs.append(f"il faut exactement {attendues} réponse grossière (reçu : {nb_grossieres})")

    # Cohérence avec la consigne et le canal.
    if ticket.nom != consigne.profil.nom or ticket.service != consigne.profil.service:
        motifs.append(
            f"nom et service doivent être « {consigne.profil.nom} » et « {consigne.profil.service} » "
            f"(reçu : « {ticket.nom} » et « {ticket.service} »)"
        )
    if ticket.source != consigne.source:
        motifs.append(f"la source doit être « {consigne.source} » (reçu : « {ticket.source} »)")
    if consigne.source == "Courriel" and not ticket.objet:
        motifs.append("objet obligatoire pour un courriel")
    if consigne.source == "Autre" and not ticket.canal:
        motifs.append("canal obligatoire pour la source « Autre » (ex. « Message Teams »)")
    if consigne.categorie not in ticket.attendu.categorie:
        motifs.append(f"la catégorie demandée « {consigne.categorie} » doit figurer dans attendu.categorie")

    # Longueurs très au-delà des cibles.
    # Le motif donne la cible, pas le seuil : le modèle vise ce qu'on lui montre.
    if len(ticket.demande) > LONGUEUR_MAX_DEMANDE:
        motifs.append(
            f"demande trop longue ({len(ticket.demande)} caractères, au-delà du maximum de "
            f"{LONGUEUR_MAX_DEMANDE}) : {LONGUEUR_DEMANDE_EN_PHRASES}"
        )
    for i, reponse in enumerate(ticket.reponses, 1):
        if len(reponse.texte) > LONGUEUR_MAX_REPONSE:
            motifs.append(
                f"réponse {i} trop longue ({len(reponse.texte)} caractères, au-delà du maximum de "
                f"{LONGUEUR_MAX_REPONSE}) : vise {CIBLE_REPONSE[0]} à {CIBLE_REPONSE[1]} caractères"
            )
    if len(ticket.pointCle) > LONGUEUR_MAX_POINT_CLE:
        motifs.append(
            f"point clé trop long ({len(ticket.pointCle)} caractères, au-delà du maximum de "
            f"{LONGUEUR_MAX_POINT_CLE}) : vise {CIBLE_POINT_CLE[0]} à {CIBLE_POINT_CLE[1]} caractères"
        )

    return motifs


# --- Mise au format de js/tickets.js ------------------------------------------


def _slug(texte: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:40].rstrip("-")
    return slug or "ticket"


def _une_ou_plusieurs(valeurs: list[str]) -> str | list[str]:
    """Une seule valeur -> chaîne ; plusieurs -> tableau (sans doublon)."""
    uniques = list(dict.fromkeys(valeurs))
    return uniques[0] if len(uniques) == 1 else uniques


def minuscule_initiale(texte: str) -> str:
    """Met en minuscule le premier caractère, sauf si le texte commence par un
    sigle (« VPN », « MFA ») qui perdrait son sens en minuscules."""
    premier_mot = texte.split(maxsplit=1)[0] if texte else ""
    lettres = [c for c in premier_mot if c.isalpha()]
    if len(lettres) >= 2 and all(c.isupper() for c in lettres):
        return texte
    return texte[:1].lower() + texte[1:]


def normaliser(ticket: TicketGenere, consigne: Consigne) -> dict:
    """Ticket au format de js/tickets.js (mêmes clés, même ordre)."""
    resultat: dict = {
        "id": f"ia-{_slug(ticket.theme)}-{secrets.token_hex(3)}",
        "theme": ticket.theme,
        "nom": consigne.profil.nom,
        "service": consigne.profil.service,
        "source": consigne.source,
    }
    if consigne.source == "Courriel":
        resultat["objet"] = ticket.objet
    if consigne.source == "Autre":
        resultat["canal"] = ticket.canal
    resultat["demande"] = ticket.demande
    # Ordre de js/tickets.js : bonne, en partie vraie, fausse, fausse grossière.
    # (Le modèle les écrit dans l'ordre inverse ; le site les mélange à l'affichage.)
    reponses = sorted(ticket.reponses, key=lambda r: (-r.note, r.grossiere))
    resultat["reponses"] = [
        {"note": r.note, **({"grossiere": True} if r.grossiere else {}), "texte": r.texte}
        for r in reponses
    ]
    resultat["pointCle"] = minuscule_initiale(ticket.pointCle)
    resultat["attendu"] = {
        champ: _une_ou_plusieurs(getattr(ticket.attendu, champ))
        for champ in ("type", "categorie", "urgence", "impact")
    }
    return resultat


# --- Alertes de relecture (non bloquantes) ------------------------------------


def _simplifier(texte: str) -> str:
    """Minuscules, sans accents, ponctuation et tirets remplacés par des espaces :
    « Pare-feu » et « pare feu », « désactivez » et « DESACTIVEZ » se retrouvent."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.casefold()).split())


def alertes_de_relecture(ticket: dict, mots_sensibles: tuple[str, ...]) -> list[str]:
    """Signale les réponses notées 2 ou 1 qui contiennent un mot sensible.

    Ce n'est pas un rejet : une bonne réponse peut très bien dire « ne donnez
    jamais votre mot de passe ». L'alerte attire seulement l'attention du
    formateur sur les passages à relire en priorité.
    """
    alertes = []
    for reponse in ticket["reponses"]:
        if reponse["note"] not in (1, 2):
            continue
        texte = _simplifier(reponse["texte"])
        trouves = [mot for mot in mots_sensibles if _simplifier(mot) in texte]
        if trouves:
            libelle = "bonne réponse (note 2)" if reponse["note"] == 2 else "réponse en partie vraie (note 1)"
            mots = ", ".join(f"« {mot} »" for mot in trouves)
            alertes.append(f"{libelle} : contient {mots}, à relire : « {reponse['texte']} »")
    return alertes


def produire_ticket(contenu: str, consigne: Consigne, categories: tuple[str, ...]) -> dict:
    """Réponse brute du modèle -> ticket prêt pour le site, ou TicketRejete."""
    ticket = analyser(contenu, categories)
    motifs = motifs_de_rejet(ticket, consigne)
    if motifs:
        raise TicketRejete(motifs)
    return normaliser(ticket, consigne)

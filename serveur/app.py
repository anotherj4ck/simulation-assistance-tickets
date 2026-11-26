"""Serveur local : sert le site et génère de nouveaux tickets avec un LLM local (Ollama).

Le site reste 100 % statique : sur GitHub Pages, il fonctionne sans ce serveur.

Lancement, depuis la racine du dépôt (voir serveur/README.md) :
    uvicorn serveur.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .configuration import (
    DIFFICULTE_PAR_DEFAUT,
    RACINE_SITE,
    Difficulte,
    ErreurConfiguration,
    Source,
    lire_categories,
    lire_mots_alertes,
    lire_profils,
    lire_reglages,
    lire_tickets_par_session,
)
from .exemples import lire_exemples
from . import serie as series
from .generateur import (
    TicketRejete,
    alertes_de_relecture,
    lire_prompt_systeme,
    message_utilisateur,
    produire_ticket,
    schema_ticket,
    tirer_consigne,
)

# Configuration lue une fois, au démarrage. Une erreur arrête le serveur avec
# un message explicite (pas de trace Python à déchiffrer).
try:
    REGLAGES = lire_reglages()
    CATEGORIES = lire_categories()
    PROFILS = lire_profils()
    # Tickets de js/tickets.js utilisables comme exemples (few-shot) ; ceux qui
    # ne respectent pas les règles du générateur sont écartés.
    EXEMPLES, EXEMPLES_ECARTES = lire_exemples(CATEGORIES)
    MOTS_ALERTES = lire_mots_alertes()
    PROMPT_SYSTEME = lire_prompt_systeme()
    # Taille d'une série publiée : celle d'une session du site.
    TICKETS_PAR_SESSION = lire_tickets_par_session()
except ErreurConfiguration as erreur:
    raise SystemExit(f"\n[serveur] Démarrage impossible : {erreur}\n") from None

# Série active publiée par le formateur (donnée d'exécution, ignorée par Git).
CHEMIN_SERIE = series.CHEMIN_SERIE
# Les routes /api/serie sont synchrones (exécutées en parallèle par FastAPI) :
# ce verrou évite qu'une lecture croise une publication ou un retrait.
VERROU_SERIE = threading.Lock()

# Après un ticket rejeté, on relance la génération jusqu'à 2 fois (3 essais au total).
NB_RELANCES = 2

# Seuls ces dossiers du site sont servis, en plus de index.html.
# serveur/, .git/, .venv/ et les fichiers de configuration ne sont jamais exposés.
DOSSIERS_DU_SITE = ("css", "js")

# Délai court pour /api/sante : la page de santé doit répondre vite.
TIMEOUT_SANTE = 10.0

log = logging.getLogger("uvicorn.error")


class ErreurOllama(Exception):
    """Ollama indisponible, trop lent ou modèle absent : renvoyé en 503."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    # trust_env=False : Ollama est local, on ignore un éventuel proxy système.
    app.state.ollama = httpx.AsyncClient(
        base_url=REGLAGES.ollama_url,
        timeout=httpx.Timeout(REGLAGES.ollama_timeout, connect=10.0),
        trust_env=False,
    )
    log.info(
        "Modèle Ollama : %s (%s), contexte %d tokens",
        REGLAGES.ollama_modele, REGLAGES.ollama_url, REGLAGES.ollama_num_ctx,
    )
    log.info(
        "Exemples : %d tickets de js/tickets.js ; écartés (bonne réponse la plus longue, etc.) : %s",
        len(EXEMPLES), ", ".join(EXEMPLES_ECARTES) or "aucun",
    )
    log.info(
        "Alertes de relecture : %s",
        f"{len(MOTS_ALERTES)} mots sensibles" if MOTS_ALERTES else "désactivées (liste vide dans alertes.json)",
    )
    try:
        yield
    finally:
        await app.state.ollama.aclose()


app = FastAPI(
    title="Simulation d'assistance : serveur local",
    description="Sert le site et génère des tickets avec Ollama.",
    lifespan=cycle_de_vie,
)

# Refuse les requêtes dont l'en-tête Host n'est pas local (protection contre
# le « DNS rebinding » : une page web externe ne peut pas piloter l'API).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.middleware("http")
async def _ecritures_depuis_ce_serveur_uniquement(request: Request, call_next):
    """Une page web ouverte ailleurs peut envoyer un POST à 127.0.0.1 sans
    passer par CORS (corps sans Content-Type). Les requêtes qui modifient
    quelque chose (/api/serie, /api/generer-ticket) doivent donc venir d'une
    page de ce serveur, et le POST être déclaré en JSON."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/"):
        origine = request.headers.get("origin")
        if origine is not None and urlsplit(origine).netloc != request.headers.get("host"):
            return JSONResponse(
                status_code=403,
                content={"detail": "Requête refusée : elle provient d'une page qui n'est pas servie par ce serveur."},
            )
        type_contenu = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if request.method == "POST" and type_contenu != "application/json":
            return JSONResponse(
                status_code=415,
                content={"detail": "Le corps de la requête doit être du JSON (Content-Type: application/json)."},
            )
    return await call_next(request)


@app.exception_handler(ErreurOllama)
async def _erreur_ollama(request: Request, erreur: ErreurOllama) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": erreur.message})


@app.exception_handler(RequestValidationError)
async def _requete_invalide(request: Request, erreur: RequestValidationError) -> JSONResponse:
    # Comme le gestionnaire par défaut de FastAPI (422), mais sans planter (500)
    # quand le corps reçu contient des octets qui ne sont pas de l'UTF-8.
    erreurs = jsonable_encoder(
        erreur.errors(), custom_encoder={bytes: lambda b: b.decode("utf-8", errors="replace")}
    )
    return JSONResponse(status_code=422, content={"detail": erreurs})


async def requete_ollama(
    client: httpx.AsyncClient, methode: str, chemin: str, *, timeout: float | None = None, **kwargs
) -> dict:
    """Appelle Ollama et traduit chaque échec en ErreurOllama (message en français)."""
    delai = timeout or REGLAGES.ollama_timeout
    try:
        reponse = await client.request(
            methode, chemin, timeout=httpx.Timeout(delai, connect=min(delai, 10.0)), **kwargs
        )
    except httpx.TimeoutException:
        raise ErreurOllama(
            f"Ollama n'a pas répondu dans le délai imparti ({delai:g} s). "
            "Le modèle est peut-être encore en cours de chargement : réessayez, "
            "ou augmentez OLLAMA_TIMEOUT."
        ) from None
    except httpx.HTTPError:
        raise ErreurOllama(
            f"Ollama est injoignable à l'adresse {REGLAGES.ollama_url}. "
            "Vérifiez qu'Ollama est lancé (application Ollama ou commande « ollama serve »)."
        ) from None

    if reponse.status_code == 404 and chemin == "/api/chat":
        raise ErreurOllama(
            f"Le modèle « {REGLAGES.ollama_modele} » n'est pas installé dans Ollama. "
            f"Installez-le avec « ollama pull {REGLAGES.ollama_modele} », "
            "ou changez la variable OLLAMA_MODEL."
        )
    if reponse.status_code != 200:
        try:
            detail = reponse.json().get("error", "")
        except ValueError:
            detail = reponse.text[:200]
        raise ErreurOllama(f"Ollama a renvoyé une erreur {reponse.status_code} : {detail}")
    try:
        return reponse.json()
    except ValueError:
        raise ErreurOllama("Ollama a renvoyé une réponse illisible (JSON attendu).") from None


def modele_installe(modele: str, noms: set[str]) -> bool:
    """« ministral-3:8b » doit figurer tel quel ; « llama3 » équivaut à « llama3:latest »."""
    return modele in noms or (":" not in modele and f"{modele}:latest" in noms)


# --- Routes /api (déclarées avant le montage des fichiers statiques) ----------


@app.get("/api/sante")
async def sante(request: Request) -> JSONResponse:
    """Ollama répond-il, et le modèle configuré est-il installé ? 200 si oui, 503 sinon."""
    etat = {
        "ollama": False,
        "url": REGLAGES.ollama_url,
        "modele": REGLAGES.ollama_modele,
        "modele_installe": False,
    }
    try:
        donnees = await requete_ollama(request.app.state.ollama, "GET", "/api/tags", timeout=TIMEOUT_SANTE)
    except ErreurOllama as erreur:
        return JSONResponse(status_code=503, content={**etat, "message": erreur.message})

    noms = {m.get(cle) for m in donnees.get("models", []) for cle in ("name", "model")}
    installe = modele_installe(REGLAGES.ollama_modele, noms)
    etat.update(ollama=True, modele_installe=installe)
    if installe:
        etat["message"] = f"Ollama répond et le modèle « {REGLAGES.ollama_modele} » est installé."
    else:
        etat["message"] = (
            f"Ollama répond, mais le modèle « {REGLAGES.ollama_modele} » n'est pas installé. "
            f"Installez-le avec « ollama pull {REGLAGES.ollama_modele} »."
        )
    return JSONResponse(status_code=200 if installe else 503, content=etat)


class DemandeTicket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categorie: str
    difficulte: Difficulte = DIFFICULTE_PAR_DEFAUT
    source: Source | None = None


@app.post("/api/generer-ticket")
async def generer_ticket(demande: DemandeTicket, request: Request) -> dict:
    if demande.categorie not in CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Catégorie inconnue : « {demande.categorie} ». Valeurs possibles : {', '.join(CATEGORIES)}.",
        )

    consigne = tirer_consigne(demande.categorie, demande.difficulte, demande.source, PROFILS, EXEMPLES)
    schema = schema_ticket(CATEGORIES, consigne)
    motifs: list[str] = []

    for tentative in range(1, NB_RELANCES + 2):
        corps = {
            "model": REGLAGES.ollama_modele,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEME},
                {"role": "user", "content": message_utilisateur(consigne, motifs)},
            ],
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"num_ctx": REGLAGES.ollama_num_ctx},
        }
        reponse = await requete_ollama(request.app.state.ollama, "POST", "/api/chat", json=corps)
        contenu = (reponse.get("message") or {}).get("content")
        if not isinstance(contenu, str):
            raise ErreurOllama("Ollama a renvoyé une réponse sans message.")
        # Utile pour régler OLLAMA_NUM_CTX : entrée + sortie doivent y tenir.
        log.info(
            "Tentative %d : %s tokens en entrée, %s en sortie (contexte %d), %.1f s",
            tentative, reponse.get("prompt_eval_count", "?"), reponse.get("eval_count", "?"),
            REGLAGES.ollama_num_ctx, reponse.get("total_duration", 0) / 1e9,
        )

        try:
            ticket = produire_ticket(contenu, consigne, CATEGORIES)
        except TicketRejete as rejet:
            motifs = rejet.motifs
            log.warning("Ticket rejeté (tentative %d) : %s", tentative, rejet)
            continue

        return {
            "ticket": ticket,
            # Non bloquant : passages à relire en priorité par le formateur.
            "alertes": alertes_de_relecture(ticket, MOTS_ALERTES),
            "tentatives": tentative,
            "modele": REGLAGES.ollama_modele,
            "consigne": {
                "categorie": consigne.categorie,
                "source": consigne.source,
                "difficulte": consigne.difficulte,
                "avec_grossiere": consigne.avec_grossiere,
                "profil": {
                    "nom": consigne.profil.nom,
                    "service": consigne.profil.service,
                    "ton": consigne.profil.ton,
                    "aisance": consigne.profil.aisance,
                },
                "exemples": [e.id for e in consigne.exemples],
            },
        }

    raise HTTPException(
        status_code=422,
        detail=(
            f"Le modèle n'a pas produit de ticket valable en {NB_RELANCES + 1} tentatives. "
            f"Dernier motif de rejet : {' ; '.join(motifs)}."
        ),
    )


# --- Série publiée par le formateur --------------------------------------------


class PublicationSerie(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Chaque ticket est validé ensuite par le validateur strict de js/tickets.js,
    # qui donne des messages précis (numéro du ticket, champ en cause).
    tickets: list[Any]


@app.get("/api/serie")
def serie_active() -> dict:
    """Série active (date de publication et tickets), ou 404 s'il n'y en a pas."""
    try:
        with VERROU_SERIE:
            serie = series.lire_serie(CATEGORIES, TICKETS_PAR_SESSION, CHEMIN_SERIE)
    except series.ErreurSerie as erreur:
        raise HTTPException(
            status_code=500,
            detail=f"Série active inutilisable : {erreur} Publiez une nouvelle série ou retirez celle-ci.",
        ) from None
    if serie is None:
        raise HTTPException(status_code=404, detail="Aucune série publiée.")
    return serie


@app.post("/api/serie", status_code=201)
def publier_serie(publication: PublicationSerie) -> dict:
    """Publie une série ; elle remplace la précédente."""
    try:
        with VERROU_SERIE:
            serie = series.publier_serie(publication.tickets, CATEGORIES, TICKETS_PAR_SESSION, CHEMIN_SERIE)
    except series.ErreurSerie as erreur:
        raise HTTPException(status_code=422, detail=f"Série refusée : {erreur}") from None
    log.info("Série publiée : %s", ", ".join(t.get("id", "?") for t in serie["tickets"]))
    return serie


@app.delete("/api/serie", status_code=204)
def retirer_serie() -> Response:
    with VERROU_SERIE:
        retiree = series.retirer_serie(CHEMIN_SERIE)
    if not retiree:
        raise HTTPException(status_code=404, detail="Aucune série publiée.")
    log.info("Série retirée.")
    return Response(status_code=204)


# --- Site statique : index.html et les seuls dossiers du site -----------------


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def accueil() -> FileResponse:
    return FileResponse(RACINE_SITE / "index.html")


# --- Mode formateur : 3 fichiers de serveur/formateur/, servis un par un ------
# Pas de montage de dossier : rien d'autre que ces trois fichiers n'est exposé.
# Le site publié (GitHub Pages) ne lie pas cette page et n'en dépend pas.

DOSSIER_FORMATEUR = Path(__file__).resolve().parent / "formateur"
FICHIERS_FORMATEUR = ("formateur.html", "formateur.js", "formateur.css")


def _route_formateur(nom: str):
    async def servir() -> FileResponse:
        return FileResponse(DOSSIER_FORMATEUR / nom)
    return servir


for _nom in FICHIERS_FORMATEUR:
    app.add_api_route(f"/{_nom}", _route_formateur(_nom), methods=["GET"], include_in_schema=False)


for _dossier in DOSSIERS_DU_SITE:
    app.mount(f"/{_dossier}", StaticFiles(directory=RACINE_SITE / _dossier), name=_dossier)

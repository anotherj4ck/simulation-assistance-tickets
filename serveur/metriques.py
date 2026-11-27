"""Métriques d'une génération, pour la page formateur.

Fonctions pures, sans appel réseau : app.py leur passe les réponses d'Ollama.
Une information absente ou mal formée vaut None (null en JSON) : les métriques
ne font jamais échouer une génération.

Elles sont renvoyées à part (« metriques » dans la réponse de /api/generer-ticket),
jamais dans le ticket : le format des tickets reste celui de js/tickets.js.
"""

from __future__ import annotations

# Champs renvoyés par /api/chat d'Ollama : durées en nanosecondes, compteurs en tokens.
CHAMPS_OLLAMA = ("total_duration", "load_duration", "prompt_eval_count", "eval_count", "eval_duration")


def _nombre(valeur: object) -> float | int | None:
    """Nombre positif ou nul, sinon None (bool exclu : True n'est pas une durée)."""
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and valeur >= 0:
        return valeur
    return None


class CumulOllama:
    """Additionne les métriques d'Ollama sur toutes les tentatives d'une génération.

    Un total n'est donné que si le champ figurait dans chaque tentative : une
    somme partielle sous-estimerait la durée ou les tokens sans le dire.
    """

    def __init__(self) -> None:
        self._totaux: dict[str, float | int | None] = dict.fromkeys(CHAMPS_OLLAMA, 0)

    def ajouter(self, reponse: dict) -> None:
        for champ in CHAMPS_OLLAMA:
            valeur = _nombre(reponse.get(champ))
            total = self._totaux[champ]
            self._totaux[champ] = None if valeur is None or total is None else total + valeur

    def totaux(self) -> dict[str, float | int | None]:
        return dict(self._totaux)


def tokens_par_seconde(totaux: dict) -> float | None:
    """Vitesse de génération : tokens produits / temps de production (eval_duration)."""
    tokens, duree = totaux.get("eval_count"), totaux.get("eval_duration")
    if tokens is None or not duree:
        return None
    return round(tokens / (duree / 1e9), 1)


def extraire_fiche(reponse_show: object) -> dict:
    """Taille, quantification et famille du modèle, depuis la réponse de /api/show."""
    details = reponse_show.get("details") if isinstance(reponse_show, dict) else None
    details = details if isinstance(details, dict) else {}

    def texte(cle: str) -> str | None:
        valeur = details.get(cle)
        return valeur if isinstance(valeur, str) and valeur.strip() else None

    return {
        "taille": texte("parameter_size"),
        "quantification": texte("quantization_level"),
        "famille": texte("family"),
    }


def _meme_modele(nom: str, modele: dict) -> bool:
    noms = {modele.get("name"), modele.get("model")}
    return nom in noms or (":" not in nom and f"{nom}:latest" in noms)


def repartition(reponse_ps: object, nom: str) -> dict | None:
    """Part du modèle en mémoire vidéo (GPU) et en mémoire vive (CPU), comme la
    colonne PROCESSOR de « ollama ps » : size_vram / size. None si le modèle
    n'est pas chargé ou si les tailles manquent."""
    modeles = reponse_ps.get("models") if isinstance(reponse_ps, dict) else None
    if not isinstance(modeles, list):
        return None
    for modele in modeles:
        if not isinstance(modele, dict) or not _meme_modele(nom, modele):
            continue
        taille, vram = _nombre(modele.get("size")), _nombre(modele.get("size_vram"))
        if not taille or vram is None:
            return None
        part_gpu = round(min(vram / taille, 1.0), 3)
        return {
            "part_gpu": part_gpu,
            "part_cpu": round(1 - part_gpu, 3),
            "taille_octets": taille,
            "vram_octets": vram,
        }
    return None


def assembler(
    nom_modele: str,
    fiche: dict | None,
    cumul: CumulOllama,
    duree_serveur_s: float | None,
    repartition_memoire: dict | None,
    tentatives: int,
) -> dict:
    """Objet « metriques » de la réponse de /api/generer-ticket."""
    totaux = cumul.totaux()
    fiche = fiche or {}
    return {
        "modele": {
            "nom": nom_modele,
            "taille": fiche.get("taille"),
            "quantification": fiche.get("quantification"),
            "famille": fiche.get("famille"),
        },
        "repartition": repartition_memoire,
        # Mesurée par le serveur (time.perf_counter), toutes tentatives comprises.
        "duree_serveur_s": None if duree_serveur_s is None else round(duree_serveur_s, 3),
        # Sommes sur toutes les tentatives, en nanosecondes et en tokens.
        "ollama": totaux,
        "tokens_par_seconde": tokens_par_seconde(totaux),
        "tentatives": tentatives,
    }

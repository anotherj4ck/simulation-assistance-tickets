# Serveur local : génération de tickets avec Ollama

Serveur **facultatif** qui :

- sert le site sur `http://127.0.0.1:8000/` ;
- expose une API qui génère de nouveaux tickets avec un LLM local, via [Ollama](https://ollama.com).

Le site lui-même ne change pas : sur GitHub Pages, ou en double-cliquant sur `index.html`, il fonctionne sans ce serveur.

## Prérequis

- Windows avec PowerShell.
- Python 3.10 ou plus récent (testé avec 3.12) : commande `py --version`.
- Ollama installé et lancé, avec un modèle téléchargé. Modèle conseillé : `ministral-3:8b`.

```powershell
ollama pull ministral-3:8b
ollama list
```

## Installation (une seule fois)

Depuis la racine du dépôt (le dossier qui contient `index.html`) :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r serveur\requirements.txt
```

Si PowerShell refuse d'exécuter `Activate.ps1` (« l'exécution de scripts est désactivée »), autorisez les scripts pour la session en cours, puis relancez l'activation :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Le dossier `.venv/` est ignoré par Git.

## Lancement

À chaque nouvelle fenêtre PowerShell, depuis la racine du dépôt :

```powershell
.\.venv\Scripts\Activate.ps1
$env:OLLAMA_MODEL = "ministral-3:8b"
uvicorn serveur.app:app --host 127.0.0.1 --port 8000
```

Ouvrez ensuite <http://127.0.0.1:8000/>. Arrêt : `Ctrl+C`.

Gardez `--host 127.0.0.1` : le serveur n'est alors accessible que depuis votre propre poste. Ne le remplacez pas par `0.0.0.0`.

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `OLLAMA_MODEL` | **aucun : obligatoire** | Modèle Ollama utilisé (ex. `ministral-3:8b`). Sans elle, le serveur refuse de démarrer et explique quoi faire. |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Adresse d'Ollama. |
| `OLLAMA_TIMEOUT` | `300` | Délai maximal de chaque appel à Ollama, en secondes (une génération fait jusqu'à 3 appels si des tickets sont rejetés). |
| `OLLAMA_NUM_CTX` | `8192` | Taille du contexte en tokens, envoyée à chaque génération (`"options": {"num_ctx": …}`). Entier, 4096 au minimum. |

`$env:NOM = "valeur"` ne vaut que pour la fenêtre PowerShell en cours. Pour enregistrer le modèle une fois pour toutes (il faut ensuite ouvrir une nouvelle fenêtre) :

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODEL", "ministral-3:8b", "User")
```

Le serveur lit aussi, au démarrage, `js/config.js` (catégories) et `serveur/donnees/profils.json` (profils d'utilisateurs). Si l'un d'eux est illisible ou incomplet, le serveur ne démarre pas.

### `OLLAMA_NUM_CTX` et la mémoire de la carte graphique

Objectif : garder le modèle entièrement en mémoire vidéo (VRAM) sur une carte de 8 Go. Ollama réserve de la mémoire pour tout le contexte demandé. Son réglage par défaut (16 384 tokens chez nous) fait déborder un modèle 8B sur le processeur, ce qui ralentit nettement la génération. Une génération utilise environ 2 800 tokens (prompt système et consigne ≈ 2 200, ticket ≈ 600), donc 8192 laisse une large marge.

Pour vérifier, pendant ou juste après une génération :

```powershell
ollama ps
```

La colonne `PROCESSOR` doit indiquer `100% GPU`. Si elle affiche un partage (`16%/84% CPU/GPU`), baissez la valeur, puis relancez le serveur :

```powershell
$env:OLLAMA_NUM_CTX = "4096"
```

Mesures avec `ministral-3:8b` sur une RTX 4060 Laptop (8 Go) :

| `OLLAMA_NUM_CTX` | Taille chargée | Répartition | Durée d'une génération |
|---|---|---|---|
| 16384 (défaut d'Ollama) | 7,8 Go | 30 % CPU / 70 % GPU | 25 à 50 s |
| 8192 | 6,6 Go | 16 % CPU / 84 % GPU | ≈ 30 s |
| 4096 | 6,0 Go | 8 % CPU / 92 % GPU | ≈ 21 s |

Sur cette carte, même 4096 ne suffit pas pour ce modèle : le reste vient du poids du modèle lui-même, environ 6 Go avec son module de vision, et de la mémoire déjà prise par Windows. Pour atteindre 100 % GPU, il faut un modèle plus léger, ou réduire le cache dans la configuration d'Ollama lui-même (variables `OLLAMA_FLASH_ATTENTION=1` et `OLLAMA_KV_CACHE_TYPE=q8_0`, à définir avant de lancer Ollama). Ces deux variables ne concernent pas ce serveur.

## API

### `GET /api/sante`

Indique si Ollama répond et si le modèle configuré est installé. Code 200 si tout va bien, 503 sinon. Le champ `message` dit quoi faire.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/sante
```

### `POST /api/generer-ticket`

Corps JSON :

| Champ | Obligatoire | Valeurs |
|---|---|---|
| `categorie` | oui | Une catégorie de `js/config.js` (ex. `"Réseau"`) |
| `difficulte` | non | `"facile"`, `"pas trop difficile"` (défaut), `"difficile"` |
| `source` | non | `"Téléphone"`, `"Courriel"`, `"Direct"`, `"Helpdesk"`, `"Autre"`. Si elle est absente, elle est tirée au sort. |

```powershell
$corps = @{ categorie = "Réseau"; difficulte = "pas trop difficile" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/generer-ticket `
       -ContentType "application/json; charset=utf-8" `
       -Body ([Text.Encoding]::UTF8.GetBytes($corps))
$r.ticket | ConvertTo-Json -Depth 5
```

L'encodage en UTF-8 (`GetBytes`) est nécessaire sous Windows PowerShell 5.1, sinon les accents arrivent mal.

Réponse :

```json
{
  "ticket": { "id": "ia-…", "theme": "…", "nom": "…", "source": "…", "reponses": [ … ], "attendu": { … } },
  "tentatives": 1,
  "modele": "ministral-3:8b",
  "consigne": {
    "categorie": "Réseau", "source": "Direct", "difficulte": "pas trop difficile", "avec_grossiere": true,
    "profil": { "nom": "Mme Brunet", "service": "RH", "ton": "pressé, il a une échéance proche", "aisance": "…" }
  }
}
```

`ticket` est au format de `js/tickets.js` : une valeur seule dans `attendu` devient une chaîne, plusieurs valeurs restent un tableau ; `objet` n'apparaît que pour un courriel, `canal` que pour la source « Autre » ; `grossiere: true` n'apparaît que sur la réponse concernée. L'identifiant commence par `ia-` pour ne jamais entrer en conflit avec `t01` à `t30`.

Une génération prend de quelques secondes à quelques minutes, selon le modèle et la machine. La documentation interactive de l'API est sur <http://127.0.0.1:8000/docs>.

### Codes d'erreur

| Code | Cause |
|---|---|
| 422 | Corps invalide (catégorie inconnue, difficulté inconnue…), ou ticket rejeté 3 fois de suite par les contrôles de qualité. Le message donne le dernier motif de rejet. |
| 503 | Ollama injoignable, délai dépassé (`OLLAMA_TIMEOUT`) ou modèle non installé. Le message dit quoi faire. |

## Ce que fait le générateur

Le prompt système est dans [`prompts/generateur_ticket.md`](prompts/generateur_ticket.md). Il fixe les règles d'écriture (utilisateur réaliste, canal respecté, 4 réponses, point clé, grille urgence/impact, difficulté). On peut le modifier sans toucher au code ; il est relu à chaque démarrage du serveur.

Ollama reçoit le schéma JSON du ticket (paramètre `format`), avec `stream=false` et `think=false`. La réponse est validée par un modèle Pydantic, puis le serveur la contrôle. Le ticket est **rejeté** si :

- il n'a pas exactement 4 réponses ;
- il n'a pas exactement 1 bonne réponse (note 2) et 1 réponse en partie vraie (note 1) ;
- la bonne réponse est strictement la plus longue des 4 ;
- un texte est vide, ou une longueur dépasse largement les cibles (demande > 250 caractères, réponse > 300, point clé > 400) ;
- `objet` manque pour un courriel, ou `canal` manque pour la source « Autre » ;
- le nom ou le service ne sont pas ceux du profil tiré au sort ;
- la catégorie demandée n'est pas dans `attendu.categorie` ;
- le nombre de réponses grossières ne correspond pas à la consigne.

En cas de rejet, la génération est relancée jusqu'à 2 fois ; le modèle reçoit alors les motifs du rejet précédent. Après 3 échecs : erreur 422.

**Réponses grossières (✗✗).** Le serveur décide lui-même, au hasard, si le ticket en contient une : la probabilité est de 0,6 (60 %), fixée par la constante `PROBABILITE_TICKET_AVEC_GROSSIERE` dans `generateur.py`. Comme chaque ticket a 2 réponses fausses, cela donne en moyenne 0,6 × 1 / 2 = 30 % de réponses fausses grossières, la même proportion que dans `js/tickets.js`.

**Profil de l'utilisateur.** Le serveur tire aussi au sort, dans [`donnees/profils.json`](donnees/profils.json) :

- le genre, puis le nom : « M. » / « Mme » et un nom de famille dans 90 % des cas (constante `PROBABILITE_CIVILITE`, comme 27 tickets sur 30 de `js/tickets.js`), sinon un prénom seul ;
- le service ;
- le ton (pressé, agacé, inquiet…) ;
- l'aisance avec l'informatique.

Le nom et le service sont imposés par le schéma : le modèle ne peut pas écrire autre chose. Le ton et l'aisance sont donnés dans la consigne ; ils ne peuvent pas être vérifiés automatiquement. Pour enrichir la variété, il suffit d'ajouter des lignes aux listes du fichier, puis de redémarrer le serveur. Chaque liste doit rester non vide, et les services restent sans accord de genre (« comptabilité », pas « comptable »).

**Corrections automatiques, sans rejet :** le premier caractère du point clé est mis en minuscule (sauf s'il commence par un sigle comme « VPN »), un éventuel préfixe « Point clé : » est retiré, et les espaces superflus sont supprimés.

Les contrôles garantissent la forme, pas la justesse pédagogique : **relisez chaque ticket généré** (bonne réponse vraiment la meilleure, réponse grossière vraiment inacceptable, qualification juste) avant de l'ajouter à `js/tickets.js`.

## Sécurité

- Écoute sur `127.0.0.1` uniquement, et les requêtes dont l'en-tête `Host` n'est pas `127.0.0.1` ou `localhost` sont refusées (protection contre le *DNS rebinding*).
- Seuls `index.html`, `css/` et `js/` sont servis. `serveur/`, `.git/`, `.venv/`, le README et les fichiers de configuration ne le sont jamais.
- Aucun secret : Ollama local n'a pas besoin de clé.

## Tests

```powershell
python -m pip install -r serveur\requirements-dev.txt
python -m pytest serveur\tests
```

## Fichiers

```
serveur/
  app.py                       Application FastAPI : routes, appels à Ollama, fichiers statiques
  configuration.py             Variables d'environnement, lecture des catégories et des profils
  generateur.py                Consigne (tirages au sort), schéma JSON, validation, contrôles, format final
  donnees/profils.json         Listes tirées au sort : prénoms, noms, services, tons, aisances
  prompts/generateur_ticket.md Prompt système du générateur
  requirements.txt             Dépendances (versions épinglées)
  requirements-dev.txt         Dépendances de test (pytest)
  tests/                       Tests unitaires
```

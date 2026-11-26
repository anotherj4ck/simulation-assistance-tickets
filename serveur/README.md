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

## Mode formateur (local)

Une fois le serveur lancé, ouvrez <http://127.0.0.1:8000/formateur.html>. Cette page sert à générer des tickets, les relire, les corriger et les exporter.

- **En-tête** : au chargement, la page interroge `/api/sante` et affiche le modèle utilisé (pastille verte). Si Ollama ou le modèle ne répond pas, un bandeau rouge explique quoi faire, avec un bouton « Revérifier ».
- **Génération** : choisissez la catégorie (liste de `js/config.js`), la difficulté et, si vous le souhaitez, la source (sinon elle est tirée au hasard), puis cliquez sur « Générer ». Un indicateur tourne pendant l'attente (comptez 20 à 60 s) et affiche le temps écoulé.
- **Alertes** : les passages sensibles des réponses notées ✓ ou ~ apparaissent dans un bandeau orange au-dessus du ticket (voir « Alertes de relecture » plus bas).
- **Relecture** : tous les textes sont modifiables (thème, nom, service, objet ou canal, demande, réponses, point clé). On peut aussi changer :
  - la note de chaque réponse : ✓ bonne, ~ en partie vraie, ✗ fausse, ✗✗ grossière ;
  - les valeurs attendues : cocher plusieurs valeurs les rend toutes acceptées.

  Un avertissement apparaît si la bonne réponse devient la plus longue des quatre.
- **Valider** ajoute le ticket à la liste du bas, s'il est complet : exactement une bonne réponse, aucun texte vide, objet présent pour un courriel, au moins une valeur cochée pour chaque critère. **Rejeter** l'abandonne.
- **Liste des tickets validés** : elle est gardée dans la mémoire du navigateur (`localStorage`) et survit donc à un rechargement de la page. Chaque ticket peut être retiré ; « Vider la liste » efface tout, après confirmation.
  - La liste est propre à ce navigateur et à l'adresse ouverte, ce que rappelle une mention discrète dans l'en-tête, avec une infobulle. Comme le navigateur sépare les données par adresse, `http://localhost:8000` et `http://127.0.0.1:8000` ont deux listes distinctes.
  - Pour passer de l'une à l'autre, ou d'un poste à un autre, utilisez « Exporter » puis « Importer ».
- **Exporter** télécharge `tickets-valides-AAAA-MM-JJ.json`, un tableau de tickets au format de `js/tickets.js`.
- **Importer** ouvre un fichier `.json` de ce format, par exemple un export précédent. Le serveur valide chaque ticket avec le validateur strict de `js/tickets.js`.
  - Les tickets valides s'ajoutent à la liste, sans doublon : un identifiant déjà présent, ou répété dans le fichier, n'est ajouté qu'une fois.
  - Un compte rendu indique les tickets importés, les doublons ignorés (avec leur identifiant) et les tickets refusés (avec le ticket, le champ et le motif, par exemple « source : valeur non autorisée »).
  - Un ticket importé se retire, se publie et s'exporte comme les autres.
- **Publier la série** n'est actif qu'avec exactement 5 tickets validés (`ticketsParSession` de `js/config.js`). Après confirmation, ces tickets deviennent la série que résolvent les apprenants, dans l'ordre de la liste. La confirmation rappelle que la série en cours sera remplacée.
- **Série active** : l'encart du bas indique s'il y a une série publiée, avec sa date de publication et les thèmes des 5 tickets. « Retirer la série » ramène les apprenants au tirage au hasard. « Ouvrir le mode apprenant » ouvre le site dans un nouvel onglet.

**Ajouter les tickets exportés au site.** Ouvrez le fichier JSON et copiez les blocs `{ ... }` (sans les crochets `[ ]` qui les entourent). Collez-les à la fin de la liste de `js/tickets.js`, avant le `];` final, en séparant chaque bloc du précédent par une virgule. Au démarrage suivant, le serveur relit `js/tickets.js` de façon stricte et signale toute erreur ; le site, lui, ignore un ticket invalide et le signale dans la console (F12).

**La page ne fait pas partie du site.** Ses fichiers sont dans `serveur/formateur/` et le serveur les sert un par un (`/formateur.html`, `/formateur.js`, `/formateur.css`). `index.html` ne la lie pas et le site n'en dépend pas. GitHub Pages publie tout de même l'ensemble du dépôt : ouverte de cette façon, sans serveur local, la page affiche seulement « Serveur local injoignable » et l'explication pour le lancer.

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `OLLAMA_MODEL` | **aucun : obligatoire** | Modèle Ollama utilisé (ex. `ministral-3:8b`). Sans elle, le serveur refuse de démarrer et explique quoi faire. |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Adresse d'Ollama. |
| `OLLAMA_TIMEOUT` | `300` | Délai maximal de chaque appel à Ollama, en secondes (une génération fait jusqu'à 3 appels si des tickets sont rejetés). |
| `OLLAMA_NUM_CTX` | `8192` | Taille du contexte en tokens, envoyée à chaque génération (`"options": {"num_ctx": …}`). Entier, 6144 au minimum. |

`$env:NOM = "valeur"` ne vaut que pour la fenêtre PowerShell en cours. Pour enregistrer le modèle une fois pour toutes (il faut ensuite ouvrir une nouvelle fenêtre) :

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODEL", "ministral-3:8b", "User")
```

Le serveur lit aussi, au démarrage :
- `js/config.js` (catégories) ;
- `js/tickets.js` (tickets d'exemple) ;
- `serveur/donnees/profils.json` (profils d'utilisateurs).

Si l'un d'eux est illisible ou incomplet, le serveur ne démarre pas. La lecture de `js/tickets.js` est plus stricte que celle du site, qui se contente d'ignorer un ticket mal rempli : le serveur refuse de démarrer et indique le ticket et le champ en cause. C'est le cas, par exemple, d'une clé mal orthographiée comme `grossière`, que le site ignorerait sans rien dire.

### `OLLAMA_NUM_CTX` et la mémoire de la carte graphique

Objectif : garder le modèle entièrement en mémoire vidéo (VRAM) sur une carte de 8 Go. Ollama réserve de la mémoire pour tout le contexte demandé. Son réglage par défaut (16 384 tokens chez nous) fait déborder un modèle 8B sur le processeur, ce qui ralentit nettement la génération. Une génération utilise environ 4 000 tokens (prompt système et consigne avec ses 2 exemples ≈ 3 500, ticket ≈ 500), donc 8192 laisse une marge confortable. Le serveur refuse les valeurs inférieures à 6144 : en dessous, Ollama tronquerait le début du prompt, c'est-à-dire les règles du générateur. Le journal du serveur affiche ces chiffres à chaque tentative (« Tentative 1 : 3420 tokens en entrée, 483 en sortie »).

Pour vérifier, pendant ou juste après une génération :

```powershell
ollama ps
```

La colonne `PROCESSOR` doit indiquer `100% GPU`. Si elle affiche un partage (`16%/84% CPU/GPU`), baissez la valeur, puis relancez le serveur :

```powershell
$env:OLLAMA_NUM_CTX = "6144"
```

Mesures avec `ministral-3:8b` sur une RTX 4060 Laptop (8 Go) :

| `OLLAMA_NUM_CTX` | Taille chargée | Répartition | Durée d'une génération |
|---|---|---|---|
| 16384 (défaut d'Ollama) | 7,8 Go | 30 % CPU / 70 % GPU | 25 à 50 s |
| 8192 | 6,6 Go | 16 % CPU / 84 % GPU | ≈ 30 s |
| 6144 | 6,3 Go | 13 % CPU / 87 % GPU | ≈ 28 s |
| 4096 (n'est plus accepté depuis l'ajout des exemples) | 6,0 Go | 8 % CPU / 92 % GPU | ≈ 21 s |

Ces mesures datent d'avant l'ajout des exemples dans la consigne. Sur cette carte, même 4096 ne suffisait pas pour ce modèle : le reste vient du poids du modèle lui-même, environ 6 Go avec son module de vision, et de la mémoire déjà prise par Windows. Pour atteindre 100 % GPU, il faut un modèle plus léger, ou réduire le cache dans la configuration d'Ollama lui-même (variables `OLLAMA_FLASH_ATTENTION=1` et `OLLAMA_KV_CACHE_TYPE=q8_0`, à définir avant de lancer Ollama). Ces deux variables ne concernent pas ce serveur.

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
  "alertes": [ "réponse en partie vraie (note 1) : contient « mot de passe », à relire : « … »" ],
  "tentatives": 1,
  "modele": "ministral-3:8b",
  "consigne": {
    "categorie": "Réseau", "source": "Direct", "difficulte": "pas trop difficile", "avec_grossiere": true,
    "profil": { "nom": "Mme Brunet", "service": "RH", "ton": "pressé, il a une échéance proche", "aisance": "…" },
    "exemples": ["t13-vpn", "t23-wi-fi-en-salle-de-reunion"]
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

### `POST /api/valider-tickets`

Valide le contenu d'un fichier de tickets ; c'est la route qu'utilise « Importer ». Le corps est le contenu brut du fichier, un tableau JSON au format de `js/tickets.js`, envoyé avec `Content-Type: application/json`.

- **200** : `{ "valides": [ …tickets valides, tels que reçus… ], "refuses": [ { "position": 5, "id": "t04-imprimante", "motifs": ["source : valeur non autorisée (…)"] } ] }`. Chaque ticket est validé séparément : un ticket refusé n'empêche pas les autres.
- **422** : le fichier n'est pas du JSON (la ligne et la colonne sont indiquées), n'est pas en UTF-8, n'est pas un tableau, ou est un tableau vide.
- **413** : fichier de plus de 2 Mo.

Les doublons ne sont pas écartés ici : seule la page formateur connaît la liste de tickets déjà validés.

### Série publiée pour les apprenants : `/api/serie`

Le formateur publie une série de tickets que les apprenants résolvent à la place du tirage au hasard. La série active est enregistrée dans `serveur/donnees/serie-active.json`. C'est une donnée d'exécution, ignorée par Git.

| Requête | Effet | Réponses |
|---|---|---|
| `GET /api/serie` | Série active : `{ "publiee_le": "2026-11-26T09:35:00+01:00", "tickets": [ … ] }` | 200 ; 404 s'il n'y en a pas ; 500 si le fichier est devenu invalide (modifié à la main, ou `js/config.js` changé depuis la publication) |
| `POST /api/serie` | Publie `{ "tickets": [ … ] }` ; elle remplace la série précédente | 201 ; 422 si le nombre de tickets est faux ou si un ticket est invalide (le message cite le ticket et le champ) |
| `DELETE /api/serie` | Retire la série active | 204 ; 404 s'il n'y en avait pas |

- Une série contient exactement `ticketsParSession` tickets, la valeur lue dans `js/config.js` (5).
- Chaque ticket est revalidé avec le même validateur strict que `js/tickets.js`, à la publication comme à chaque lecture.
- Le fichier est écrit de façon atomique (fichier temporaire, puis renommage) : un apprenant ne peut jamais lire une série à moitié écrite, et une publication refusée laisse la série précédente intacte.

**Côté site apprenant** (`js/app.js`) :
- **Quand la page est servie par ce serveur** (`127.0.0.1` ou `localhost`), elle demande la série au chargement et au début de chaque session, avec un délai de 2 s au plus.
  - Si elle reçoit une série valide, l'accueil affiche discrètement « Série préparée par votre formateur », et la session utilise exactement ces tickets, dans l'ordre du formateur. L'ordre des réponses reste mélangé.
  - Dans tous les autres cas (404, erreur, délai dépassé, réponse invalide), c'est le tirage au hasard habituel, sans message visible.
- **Sur GitHub Pages ou en ouvrant `index.html` directement**, la page ne fait aucune requête : le comportement est exactement celui d'avant.
- Le rapport final est le même dans les deux cas.

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

**Exemples (few-shot).** À chaque génération, le serveur choisit au hasard 2 tickets de `js/tickets.js`, de préférence dans la catégorie demandée, et complète avec d'autres catégories s'il n'y en a pas assez. Il les met dans la consigne, au format JSON attendu, avec une règle : ils montrent le niveau, le ton et la longueur attendus, mais leur scénario ne doit jamais être recopié.

Les tickets qui ne respectent pas les règles du générateur ne servent pas d'exemples, pour ne pas enseigner au modèle un défaut que le serveur rejette ensuite. Il s'agit surtout de ceux dont la bonne réponse est la plus longue : t14, t15, t17, t19, t20, t21, t24, t25, t26 et t30 (20 exemples sur 30 restent utilisables). Cette exclusion est calculée, pas écrite en dur : un ticket corrigé redevient automatiquement un exemple. La liste s'affiche au démarrage du serveur.

**Corrections automatiques, sans rejet :** le premier caractère du point clé est mis en minuscule (sauf s'il commence par un sigle comme « VPN »), un éventuel préfixe « Point clé : » est retiré, et les espaces superflus sont supprimés.

**Ordre des réponses.** Le schéma impose au modèle l'ordre fausse, fausse (la grossière en second, si elle est demandée), en partie vraie, bonne. Il écrit ainsi la bonne réponse en dernier, en connaissant déjà la longueur des trois autres. Le ticket renvoyé est remis dans l'ordre habituel de `js/tickets.js` (bonne réponse en premier), et le site mélange l'ordre à l'affichage. Les exemples de la consigne sont présentés dans le même ordre que le schéma.

**Longueur de la demande.** Elle est demandée au modèle en phrases (« 2 phrases courtes au plus »), parce qu'il compte mal les caractères. Le contrôle côté serveur reste en caractères (rejet au-delà de 250).

**Règles métier.** Le prompt contient une liste de fautes interdites dans les réponses notées 2 et 1, et la consigne la rappelle à chaque génération :
- demander, dicter ou transmettre un mot de passe ;
- agir sur un compte sans vérifier l'identité ;
- désactiver l'antivirus ou le pare-feu ;
- accorder des droits administrateur pour contourner une procédure ;
- utiliser un réseau ou un compte tiers ;
- face à un rançongiciel suspecté, éteindre le poste au lieu de l'isoler.

Ces fautes restent la matière des réponses grossières.

**Alertes de relecture (non bloquantes).** Quand une réponse notée 2 ou 1 contient un mot de [`donnees/alertes.json`](donnees/alertes.json) (mot de passe, désactiv, administrateur, pare-feu…), la réponse de l'API contient une alerte dans `alertes`. Le ticket n'est pas rejeté : une bonne réponse peut très bien dire « ne communiquez jamais votre mot de passe ». L'alerte signale seulement un passage à relire en priorité. La comparaison ignore majuscules, accents et tirets, et un début de mot suffit (« désactiv » trouve « désactivez »). On peut modifier la liste sans toucher au code, puis redémarrer le serveur ; une liste vide désactive les alertes.

Les contrôles garantissent la forme, pas la justesse pédagogique : **relisez chaque ticket généré** (bonne réponse vraiment la meilleure, réponse grossière vraiment inacceptable, qualification juste) avant de l'ajouter à `js/tickets.js`.

## Mesures

Le générateur a été mesuré sur les 6 mêmes requêtes (Réseau, Sécurité, Impression, Comptes et accès ; sources variées), avec `OLLAMA_NUM_CTX=8192`, sur un PC portable : RTX 4060 Laptop (8 Go de mémoire vidéo), Core i7-13620H, 23,6 Go de mémoire vive, en novembre 2026. Avec 6 générations par colonne, les chiffres sont indicatifs ; les écarts importants, eux, sont nets.

Trois versions du code, avec `ministral-3:8b` :

- **A, sans exemples** : prompt système, profils tirés au sort, contrôles et relances.
- **B, few-shot** : A + 2 tickets de `js/tickets.js` donnés en exemples à chaque génération.
- **C, few-shot + corrections** : B + ordre des réponses imposé par le schéma, demande limitée à « 2 phrases courtes au plus », règles métier dans le prompt.

Puis le code de C, inchangé, avec deux autres modèles :

- **D** : `qwen3:8b`.
- **E** : `qwen3:30b`, modèle MoE (*mixture of experts*) qui n'active qu'environ 3 milliards de paramètres sur 30 à chaque token.

| | A : sans exemples | B : few-shot | C : ministral-3:8b | D : qwen3:8b | E : qwen3:30b |
|---|---|---|---|---|---|
| Générations réussies | 6 / 6 | 4 / 6 | **6 / 6** | **6 / 6** | **6 / 6** |
| Tentatives rejetées | 2 / 8 (25 %) | 11 / 15 (73 %) | 1 / 7 (14 %) | 1 / 7 (14 %) | **0 / 6 (0 %)** |
| Rejets « bonne réponse la plus longue » | 1 | 7 | 1 | 1 | 0 |
| Rejets « demande trop longue » | 1 | 7 | 0 | 0 | 0 |
| Longueur moyenne des demandes (cible 60 à 150) | 217 car. | 217 car. | 184 car. | **107 car.** | **146 car.** |
| Réponses de plus de 190 car. | 11 / 24 | 3 / 16 | 8 / 24 | **0 / 24** | 3 / 24 |
| Utilisateur seul classé en impact Basse | 1 / 5 | 4 / 4 | 5 / 5 | 5 / 5 | 5 / 5 |
| Réponses ✗✗ vraiment inacceptables | 1 / 4 | 1 / 2 | 4 / 4 | 3 / 3 | 2 / 3 |
| Réponses ✓ ou ~ qui violent une règle métier | 0 | 3 | 1 | 1 (+ 1 ambiguë) | 1 |
| Notes mal attribuées ou bonne réponse fausse/faible | 3 | 2 | 2 | 4 | 3 |
| Durée moyenne par ticket (relances comprises) | 25 s | 51 s | 23 s | **14 s** (13 s hors chargement) | 21 s (17 s hors chargement) |
| Répartition relevée avec `ollama ps` | 16 % CPU / 84 % GPU, 6,6 Go | idem | idem | **100 % GPU, 6,2 Go** | 68 % CPU / 32 % GPU, 19 Go |

« Hors chargement » : le premier ticket de D et de E comprend le chargement du modèle en mémoire (environ 9 s et 28 s). La colonne « Répartition » est relevée toutes les 3 s pendant la série. Pour A, B et C (même modèle, même contexte), elle a été relevée après les générations.

**Défauts pédagogiques, série D (`qwen3:8b`).**
- Textes courts et plats : bonnes réponses de 92 et 93 caractères, sous la cible de 120.
- Une réponse ~ qui reprend mot pour mot la bonne réponse, en y ajoutant une question : elle vaut donc mieux qu'elle.
- Deux bonnes réponses faibles : « vérifiez que le serveur n'est pas en maintenance », « vérifiez le mot de passe de l'application ».
- Une réponse ~ qui active un accès sans vérifier l'identité.
- Sur le rançongiciel, la bonne réponse dit « débranchez votre ordinateur », ce qui peut se comprendre comme l'éteindre. Surtout, le point clé affirme qu'« un message de rançongiciel est une arnaque » : il enseigne donc une erreur.

**Défauts pédagogiques, série E (`qwen3:30b`).**
- Une réponse ~ envoie l'utilisateur sur le Wi-Fi de la boutique, un réseau tiers (l'alerte l'a signalé) ; dans le même ticket, la bonne réponse se limite à « redémarrez ».
- Une bonne réponse fausse sur le fond (« écran noir = le réseau ne détecte plus votre poste »).
- Une ✗✗ inoffensive (débrancher et rebrancher l'imprimante).
- Une réponse ~ incorrecte sur le fond plutôt que partielle (l'imprimante ne « traiterait pas les documents externes »).

En revanche, E produit les meilleurs tickets de sécurité et de compte : isoler le poste et prévenir la sécurité, impact Moyenne justifié par le risque de propagation, vérifier l'identité avant de déverrouiller. C'est aussi la série où le profil se lit le mieux dans la demande (« c'est sûrement le routeur, hier j'ai vu un technicien le configurer »).

**Ce qui a marché.** Les exemples seuls ont dégradé les résultats (B) : le modèle imitait le ton des tickets, mais pas leurs longueurs. Ce sont les contraintes structurelles qui ont fait la différence (C) :
- avec l'ordre imposé par le schéma, la bonne réponse s'écrit en dernier, une fois connue la longueur des trois autres ;
- une demande exprimée en phrases est mieux respectée qu'une demande exprimée en caractères, que le modèle compte mal ;
- les règles métier écrites noir sur blanc fournissent la matière des réponses grossières, qui deviennent toutes réellement inacceptables.

La règle d'impact explicite (« une seule personne = Basse, sauf propagation ») a corrigé l'erreur de qualification la plus fréquente.

**Ce qui reste à relire humainement.** Aucun des trois modèles testés n'est fiable sur le fond, 30B compris :
- notes mal attribuées (une réponse ✗ meilleure que la ~) ;
- bonne réponse parfois incohérente ;
- demandes parfois illogiques ;
- catégorie ou impact discutables sur les cas de sécurité ;
- ton imposé pas toujours perceptible.

Surtout, chaque série contient encore une réponse notée ~ qui viole une règle métier :
- C : « un accès temporaire via mon compte admin » ;
- D : un accès activé sans vérifier l'identité ;
- E : le Wi-Fi d'une boutique.

Le point clé peut lui aussi être faux (série D). Les règles du prompt réduisent ces fautes sans les éliminer.

**Pourquoi les alertes sont volontairement larges.** Elles ne bloquent rien et servent seulement à orienter la relecture. Une recherche de mots ne comprend pas la négation : « ne donnez jamais votre mot de passe » déclenche la même alerte que « donnez-moi votre mot de passe ». Il fallait donc choisir entre manquer une faute et signaler un passage sans problème. Une faute de sécurité notée ✓ ou ~ enseignerait un mauvais réflexe à l'apprenant, alors qu'une fausse alerte coûte quelques secondes de lecture : la liste préfère signaler trop. Dans la série C, 3 alertes sur 4 étaient sans objet ; la seule utile portait sur le cas « compte admin », trouvé grâce à « mot de passe ». « admin » a été ajouté ensuite pour le trouver directement.

Les séries D et E confirment ces limites dans les deux sens :
- en E, 1 alerte sur 5 était utile (le Wi-Fi de la boutique) ;
- en D, la seule alerte pointait une bonne réponse faible, mais l'accès activé sans vérifier l'identité ne contient aucun mot de la liste et n'a pas été signalé ;
- les alertes ne lisent pas le point clé, et n'ont donc pas vu « un rançongiciel est une arnaque ».

Elles orientent la relecture, elles ne la remplacent pas.

## Recommandation de modèle

- **Pour préparer des séries à l'avance (qualité prioritaire) : `qwen3:30b`.** Aucun rejet et des demandes proches de la cible. Ce sont aussi les meilleurs tickets de sécurité et de compte, et le profil de l'utilisateur s'y lit le mieux. Il reste rapide (environ 17 s par ticket) bien qu'il tourne aux deux tiers sur le processeur, grâce à son architecture MoE. Son coût est la mémoire : 19 Go chargés, sur les 23,6 Go de mémoire vive de la machine de test. Il faut fermer les applications lourdes pendant la génération. L'avance sur les modèles 8B reste modeste : relire chaque ticket reste indispensable.
- **Pour une génération rapide (démonstration, essai en direct) : `qwen3:8b`.** Il tient entièrement sur une carte de 8 Go et produit un ticket en 11 à 13 s. Ses textes sont plus courts et plus pauvres (réponses parfois en double, point clé faux une fois) : il demande davantage de corrections.
- **`ministral-3:8b`** n'a plus d'avantage dans ces mesures : il déborde sur le processeur, il est plus lent que `qwen3:8b`, et sa qualité est comparable.

Le modèle se choisit avec `OLLAMA_MODEL` ; le code n'a pas de modèle par défaut.

## Sécurité

- Écoute sur `127.0.0.1` uniquement, et les requêtes dont l'en-tête `Host` n'est pas `127.0.0.1` ou `localhost` sont refusées (protection contre le *DNS rebinding*).
- Les requêtes qui modifient quelque chose (`POST`, `DELETE` sur `/api/…`) doivent venir d'une page de ce serveur. Si l'en-tête `Origin` désigne un autre site, la réponse est 403 ; un `POST` doit en plus être déclaré en JSON, sinon la réponse est 415. Sans cela, une page web quelconque ouverte par le formateur pourrait publier une série ou lancer des générations, en envoyant une requête sans `Content-Type` qui échappe aux contrôles CORS du navigateur.
- Sont servis : `index.html`, `css/`, `js/` et les trois fichiers de la page formateur (`/formateur.html`, `/formateur.js`, `/formateur.css`), un par un, sans exposer le reste de `serveur/`. `serveur/`, `.git/`, `.venv/`, le README et les fichiers de configuration ne le sont jamais.
- Aucun secret : Ollama local n'a pas besoin de clé.

## Tests

```powershell
python -m pip install -r serveur\requirements-dev.txt
python -m pytest serveur\tests
```

Les tests n'appellent pas Ollama. Ils vérifient la configuration, la lecture des tickets, le générateur (schéma, format, alertes), les fichiers servis, l'API des séries et la validation des fichiers importés.

`test_navigateur.py` teste le site apprenant dans un vrai navigateur, avec Playwright et l'Edge ou le Chrome déjà installé (aucun téléchargement de navigateur) :
- avec une série valide, la session utilise les tickets dans l'ordre jusqu'au rapport ;
- avec une API absente, un délai dépassé ou une réponse invalide, la session revient au tirage habituel ;
- sur un nom d'hôte non local, ou avec la page ouverte comme fichier, aucune requête n'est faite.

Ce même fichier teste aussi la page formateur sur le vrai serveur, lancé dans le test, sans Ollama :
- import avec doublons et ticket refusé, retrait d'un ticket importé puis publication de la série ;
- fichier qui n'est pas du JSON, tableau vide ;
- infobulle de l'en-tête.

Sans navigateur disponible, ces tests sont ignorés.

## Fichiers

```
serveur/
  app.py                       Application FastAPI : routes, appels à Ollama, fichiers statiques
  configuration.py             Variables d'environnement ; lecture des catégories, de ticketsParSession et des profils
  generateur.py                Consigne (tirages au sort), schéma JSON, validation, contrôles, format final
  exemples.py                  Lecture et validation strictes des tickets, choix et mise en forme des exemples
  serie.py                     Série publiée pour les apprenants : validation, écriture atomique, lecture, retrait
  donnees/profils.json         Listes tirées au sort : prénoms, noms, services, tons, aisances
  donnees/alertes.json         Mots sensibles qui déclenchent une alerte de relecture
  donnees/serie-active.json    Série active (créée à la publication, ignorée par Git)
  formateur/                   Page formateur (HTML, JS, CSS) : servie par le serveur local uniquement
  prompts/generateur_ticket.md Prompt système du générateur
  requirements.txt             Dépendances (versions épinglées)
  requirements-dev.txt         Dépendances de test (pytest, Playwright)
  tests/                       Tests unitaires et tests dans le navigateur
```

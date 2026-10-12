# Simulation d'assistance informatique

Outil d'entraînement pour les formations de technicien d'assistance informatique : l'apprenant traite des demandes d'utilisateurs (téléphone, courriel, visite au bureau, portail, messagerie) et crée le ticket correspondant dans un outil de ticketing simulé, inspiré de la structure de GLPI.

## Fonctionnement

1. L'apprenant saisit son nom.
2. Cinq demandes sont tirées au hasard dans une réserve de 30 tickets. Chacune arrive par sa propre source, comme dans GLPI : Téléphone, Courriel, Direct, Helpdesk ou Autre.
3. Pour chaque demande, il choisit une réponse parmi quatre (ordre mélangé à chaque affichage) et remplit le ticket : type, source, catégorie, urgence, impact, priorité calculée, statut, attribution.
4. Un rapport s'affiche à la fin, avec les deux notes, les bonnes réponses et le détail de chaque ticket. Il se télécharge en HTML ou s'imprime (PDF possible).

## Barème : deux notes séparées

Les deux compétences sont notées à part, sans note fusionnée : une bonne relation avec l'utilisateur ne compense pas un ticket mal qualifié, et inversement.

**Réponses, sur 10** : bonne réponse 2 étoiles, réponse en partie juste 1 étoile, réponse fausse 0.

**Ticket, sur 10** : chaque ticket est noté sur 2, à partir de 5 critères :

| Critère | Comparé à |
|---|---|
| Type | `attendu.type` |
| Source | `source` du ticket (fait du scénario, comparaison exacte) |
| Catégorie | `attendu.categorie` |
| Urgence | `attendu.urgence` |
| Impact | `attendu.impact` |

Note du ticket = (critères justes / 5) × 2, soit 0,4 point par critère. Le total s'affiche avec une décimale (ex. « 8,4 / 10 »).

Les champs notés démarrent sur « — Choisir — » : un champ non renseigné vaut 0, un apprenant qui ne touche à rien n'a aucun point. Titre, description, statut et attribution ne sont pas notés : ils sont évalués par le formateur.

### Tolérance

Quand une qualification se discute, le ticket accepte plusieurs valeurs : un tableau au lieu d'une chaîne, par exemple `categorie: ["Fichiers et partages", "Messagerie et collaboratif"]` pour un problème OneDrive. Il n'y a pas de tolérance automatique : chaque valeur acceptée est écrite dans les données, ticket par ticket. La catégorie « Sécurité » reste stricte sur les tickets de sécurité : la reconnaître est justement ce qu'ils enseignent.

### Grille Urgence / Impact

Repères utilisés pour qualifier les tickets :

- **Urgence** : Très haute = chaque minute compte (sécurité, échéance imminente) ; Haute = utilisateur bloqué ; Moyenne = travail gêné ou contournement possible ; Basse = confort.
- **Impact** : Basse = une personne ; Moyenne = plusieurs personnes, ou un risque qui peut s'étendre ; Haute = tout un service ou au-delà.

La priorité est calculée à partir de l'urgence et de l'impact, avec la matrice proposée par défaut dans GLPI.

## Utilisation

- En ligne : via GitHub Pages.
- En local : double-cliquer sur `index.html`. Aucune installation nécessaire.

Aucun serveur, aucun compte, aucune donnée envoyée : tout se passe dans le navigateur.

## Structure

```
index.html        Structure de la page
css/style.css     Apparence (couleurs regroupées en variables en haut du fichier)
js/config.js      Nom de l'outil, nombre de tickets par session, catégories, groupes
js/tickets.js     Réserve de tickets
js/app.js         Logique de l'application
```

## Ajouter un ticket

Dans `js/tickets.js`, copier un bloc `{ ... }` complet, le coller à la fin de la liste (avant `];`), séparer les blocs par une virgule, puis modifier le texte :

```js
{
  id: "t31-exemple",
  theme: "Exemple",
  nom: "Mme Exemple",
  service: "comptabilité",
  source: "Courriel",
  objet: "Objet du courriel",
  demande: "Ce que dit l'utilisateur.",
  reponses: [
    { note: 2, texte: "La bonne réponse." },
    { note: 1, texte: "La réponse en partie juste." },
    { note: 0, texte: "Une réponse fausse mais plausible." },
    { note: 0, grossiere: true, texte: "Une réponse franchement mauvaise." }
  ],
  pointCle: "Ce que l'apprenant doit retenir.",
  attendu: {
    type: "Incident",
    categorie: ["Réseau", "Poste de travail"],
    urgence: "Moyenne",
    impact: "Basse"
  }
}
```

- `source` : `"Téléphone"`, `"Courriel"`, `"Direct"`, `"Helpdesk"` ou `"Autre"`. Le texte de la demande et des réponses doit coller au canal (on ne dit pas « dès que vous raccrochez » à quelqu'un qui a écrit un courriel).
- `objet` : obligatoire pour un courriel. `canal` : titre affiché pour la source `"Autre"` (ex. `"Message Teams"`).
- `attendu` : une chaîne pour une seule valeur acceptée, un tableau pour plusieurs. La catégorie doit faire partie de la liste de `config.js`.
- Les quatre réponses doivent avoir des longueurs proches : la bonne ne doit pas se reconnaître à sa taille.

Un ticket mal rempli (source inconnue, catégorie absente de `config.js`, niveau d'urgence mal écrit…) est ignoré et signalé dans la console du navigateur (F12), sans bloquer les autres.

## Licence

Le dépôt a deux licences :

- **Le code** (`index.html`, `css/`, `js/app.js`, `js/config.js`) est sous licence MIT : voir [LICENSE](LICENSE).
- **Les scénarios** de `js/tickets.js` (demandes, réponses, points clés, qualifications attendues) sont © 2026 anotherj4ck, tous droits réservés : voir [LICENCE-CONTENU.md](LICENCE-CONTENU.md).

Pour réutiliser les scénarios (copie, adaptation, formation dans un autre organisme, publication), ouvrez une « issue » sur ce dépôt : l'autorisation est accordée gratuitement, au cas par cas.

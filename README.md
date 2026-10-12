# Simulation d'assistance informatique

Outil d'entraînement pour les formations de technicien d'assistance informatique : l'apprenant répond à des appels d'utilisateurs et crée le ticket correspondant dans un outil de ticketing simulé, inspiré de la structure de GLPI.

## Fonctionnement

1. L'apprenant saisit son nom.
2. Cinq appels sont tirés au hasard dans une réserve de 30 tickets.
3. Pour chaque appel, il choisit une réponse parmi quatre (ordre mélangé à chaque affichage) et remplit le ticket : type, catégorie, urgence, impact, priorité calculée, statut, attribution.
4. Un rapport s'affiche à la fin, avec la note sur 10, les bonnes réponses et les tickets saisis. Il se télécharge en HTML ou s'imprime (PDF possible).

Barème : bonne réponse 2 étoiles, réponse en partie juste 1 étoile, réponse fausse 0. Les tickets ne sont pas notés : ils sont commentés par le formateur.

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
  demande: "Ce que dit l'utilisateur.",
  reponses: [
    { note: 2, texte: "La bonne réponse." },
    { note: 1, texte: "La réponse en partie juste." },
    { note: 0, texte: "Une réponse fausse mais plausible." },
    { note: 0, grossiere: true, texte: "Une réponse franchement mauvaise." }
  ],
  pointCle: "Ce que l'apprenant doit retenir.",
  attendu: { type: "Incident", categorie: "Réseau", urgence: "Moyenne", impact: "Basse" }
}
```

Un ticket mal rempli est ignoré et signalé dans la console du navigateur (F12), sans bloquer les autres.

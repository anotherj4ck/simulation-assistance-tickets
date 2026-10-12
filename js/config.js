/*
 * Réglages de l'outil : tout ce qui est modifiable sans toucher au code.
 * Changer un nom ici le change partout (en-tête, rapport, nom du fichier téléchargé).
 */
window.CONFIG = {
  nomOutil: "Simulation d'assistance informatique",
  sousTitre: "Entraînement à la relation utilisateur et à la création de tickets",
  nomTicketing: "Outil de ticketing",

  // Nombre de tickets tirés au hasard à chaque session (2 étoiles maximum par ticket)
  ticketsParSession: 5,

  // Liste déroulante « Catégorie » du ticket
  categories: [
    "Matériel",
    "Poste de travail",
    "Réseau",
    "Logiciel",
    "Impression",
    "Messagerie et collaboratif",
    "Fichiers et partages",
    "Comptes et accès",
    "Sécurité"
  ],

  // Liste déroulante « Attribué à » (l'apprenant est ajouté automatiquement en premier)
  groupes: [
    "Support niveau 2",
    "Équipe systèmes",
    "Équipe réseau",
    "Équipe sécurité"
  ]
};

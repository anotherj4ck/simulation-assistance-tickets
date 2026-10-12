/*
 * Contenu des scénarios © 2026 anotherj4ck, tous droits réservés (la licence MIT ne s'applique pas ici).
 * Toute réutilisation demande une autorisation : voir LICENCE-CONTENU.md.
 *
 * Réserve de tickets de la simulation.
 *
 * Pour ajouter un ticket : copiez un bloc { ... } complet, collez-le à la fin
 * (avant le ]; final), ajoutez une virgule entre les deux blocs, puis modifiez le texte.
 *
 * - source : "Téléphone", "Courriel", "Direct", "Helpdesk" ou "Autre"
 *     (le texte de la demande et des réponses doit coller à ce canal)
 * - objet : obligatoire si source vaut "Courriel" (objet du message)
 * - canal : pour la source "Autre", titre affiché (ex. "Message Teams")
 * - note : 2 = bonne réponse, 1 = en partie vraie, 0 = fausse
 * - grossiere: true  -> réponse signalée en rouge dans le rapport
 * - la bonne réponse peut rester en premier : l'outil mélange l'ordre à chaque affichage
 *
 * attendu : la qualification juste, qui sert à noter le ticket.
 * - type : "Incident" ou "Demande"
 * - categorie : une valeur de la liste categories de config.js
 * - urgence / impact : "Très basse", "Basse", "Moyenne", "Haute", "Très haute"
 * - une chaîne = une seule valeur acceptée ; un tableau = plusieurs valeurs
 *   acceptées, quand la qualification se discute. Ex. : urgence: ["Haute", "Très haute"]
 * - la source n'est pas dans attendu : c'est le champ source ci-dessus qui fait foi.
 */
window.TICKETS = [
  {
    id: "t01-reseau",
    theme: "Réseau",
    nom: "Karim",
    service: "logistique",
    source: "Direct",
    demande: "J'ai un petit globe barré en bas de l'écran. Plus rien ne marche, ni Internet ni le dossier partagé.",
    reponses: [
      { note: 2, texte: "Le globe barré signifie que votre poste n'est plus connecté au réseau. Vos collègues ont-ils le même problème ? Et vous êtes branché par câble ou en Wi-Fi ?" },
      { note: 1, texte: "Regardez derrière votre ordinateur en rentrant : débranchez le câble réseau, attendez quelques secondes, rebranchez-le à fond, puis revenez me dire si le globe a disparu." },
      { note: 0, texte: "Pas de souci, je prends la main sur votre poste à distance et je vous renouvelle l'adresse IP. Ne touchez à rien pendant quelques minutes, je m'occupe de tout." },
      { note: 0, texte: "Si le dossier partagé ne répond plus non plus, c'est forcément le serveur qui est tombé. Je préviens tout de suite l'équipe infrastructure, ils vont regarder ça en priorité." }
    ],
    pointCle: "un poste déconnecté n'est pas joignable à distance, et un seul poste touché ne veut pas dire panne serveur.",
    attendu: {
      type: "Incident",
      categorie: "Réseau",
      urgence: "Haute",
      impact: "Basse"
    }
  },
  {
    id: "t02-pc-lent",
    theme: "PC lent",
    nom: "M. Bernard",
    service: "directeur",
    source: "Courriel",
    objet: "PC très lent depuis lundi",
    demande: "Mon PC rame depuis lundi, c'est insupportable. Et je vous préviens, je n'ai pas le temps qu'on me le prenne une demi-journée.",
    reponses: [
      { note: 2, texte: "Je vais faire au plus court. C'est lent tout le temps ou sur un logiciel précis ? Si vous êtes d'accord, je prends la main à distance deux minutes." },
      { note: 1, texte: "Commencez par redémarrer complètement votre PC, ça règle une bonne partie des lenteurs. Si le problème continue cet après-midi, répondez-moi et je passerai le voir." },
      { note: 0, texte: "Ça peut être un virus, c'est souvent le cas quand un PC ralentit d'un coup. Je lance tout de suite une analyse antivirus complète à distance, laissez-la tourner jusqu'au bout." },
      { note: 0, texte: "Les lenteurs viennent presque toujours du navigateur. Vous avez sûrement trop d'onglets ouverts en même temps : fermez ceux qui ne servent pas et ça ira beaucoup mieux." }
    ],
    pointCle: "respecter la contrainte de l'utilisateur tout en diagnostiquant. Une analyse complète bloquerait son poste pendant des heures.",
    attendu: {
      type: "Incident",
      categorie: ["Poste de travail", "Matériel"],
      urgence: "Moyenne",
      impact: "Basse"
    }
  },
  {
    id: "t03-ecran-noir",
    theme: "Écran noir",
    nom: "Mme Petit",
    service: "accueil",
    source: "Téléphone",
    demande: "Mon écran est tout noir, j'ai rien fait je vous jure, j'ai juste allumé comme d'habitude.",
    reponses: [
      { note: 2, texte: "Ne vous inquiétez pas, ce n'est pas votre faute. Est-ce que vous voyez une petite lumière allumée sur l'écran ? Et sur l'ordinateur ?" },
      { note: 1, texte: "Regardez en bas de votre écran, il y a un petit bouton. Appuyez dessus une fois : l'écran est peut-être simplement éteint ou en veille." },
      { note: 0, texte: "On va forcer le redémarrage. Appuyez sur le bouton de l'ordinateur et gardez le doigt dessus une dizaine de secondes, jusqu'à ce que tout s'éteigne, puis rallumez-le." },
      { note: 0, grossiere: true, texte: "Un écran ne devient pas noir tout seul, ça arrive en général après une fausse manipulation. Réfléchissez bien : qu'est-ce que vous avez touché en arrivant ce matin ?" }
    ],
    pointCle: "rassurer, puis utiliser des repères visuels simples. Le vocabulaire s'adapte à l'utilisatrice.",
    attendu: {
      type: "Incident",
      categorie: ["Matériel", "Poste de travail"],
      urgence: "Haute",
      impact: ["Basse", "Moyenne"]
    }
  },
  {
    id: "t04-imprimante",
    theme: "Imprimante",
    nom: "Lucas",
    service: "stagiaire RH",
    source: "Courriel",
    objet: "L'imprimante n'imprime plus",
    demande: "L'imprimante ne sort rien. J'ai lancé mon document quatre fois.",
    reponses: [
      { note: 2, texte: "Est-ce que vos collègues arrivent à imprimer sur cette imprimante ? Et y a-t-il un message ou un voyant orange sur son petit écran ?" },
      { note: 1, texte: "Ouvrez la file d'attente de l'imprimante depuis les paramètres de Windows, supprimez vos quatre documents bloqués, puis relancez une seule impression pour voir." },
      { note: 0, texte: "C'est sûrement le pilote qui pose problème sur votre poste. Je prends la main à distance pour le désinstaller et le réinstaller proprement, ça prendra une dizaine de minutes." },
      { note: 0, grossiere: true, texte: "Relancez-le encore une fois. Les imprimantes réseau mettent parfois du temps à recevoir les documents, il faut un peu insister avant que ça parte." }
    ],
    pointCle: "savoir d'abord si c'est le poste ou l'imprimante, avant toute action lourde.",
    attendu: {
      type: "Incident",
      categorie: "Impression",
      urgence: "Moyenne",
      impact: "Basse"
    }
  },
  {
    id: "t05-onedrive",
    theme: "OneDrive",
    nom: "Mme Garnier",
    service: "cheffe de projet",
    source: "Courriel",
    objet: "Fichiers pas à jour au bureau",
    demande: "J'ai modifié mes fichiers hier soir chez moi, et au bureau ce matin ils ne sont pas à jour. Je les ai perdus ?",
    reponses: [
      { note: 2, texte: "Vos fichiers ne sont sûrement pas perdus. Voyez-vous l'icône de nuage OneDrive en bas à droite ? Y a-t-il une croix ou des flèches dessus ?" },
      { note: 1, texte: "Ouvrez votre navigateur et connectez-vous au site de OneDrive. Si vos fichiers modifiés y sont, c'est que le problème vient de la synchronisation de ce poste." },
      { note: 0, texte: "On va forcer la synchronisation : déconnectez votre compte OneDrive dans les paramètres, puis reconnectez-vous. Il va tout retélécharger depuis le cloud, ça devrait suffire." },
      { note: 0, texte: "Pour l'instant, je ne vois pas d'autre solution que d'attendre. À l'avenir, copiez vos fichiers importants sur une clé USB en plus, comme ça vous ne dépendrez plus de la synchronisation." }
    ],
    pointCle: "rassurer, puis vérifier l'état de la synchronisation. Le problème vient peut-être du PC de la maison, pas de celui du bureau.",
    attendu: {
      type: "Incident",
      categorie: ["Fichiers et partages", "Messagerie et collaboratif"],
      urgence: "Moyenne",
      impact: "Basse"
    }
  },
  {
    id: "t06-mail-suspect",
    theme: "Mail suspect",
    nom: "Thomas",
    service: "comptabilité",
    source: "Téléphone",
    demande: "J'ai reçu un mail de la banque qui demandait de confirmer mes identifiants… J'ai cliqué et j'ai tapé mon mot de passe. C'est grave ?",
    reponses: [
      { note: 2, texte: "Vous avez bien fait d'appeler tout de suite. On change votre mot de passe maintenant, et je signale le mail à la sécurité. Surtout, ne le supprimez pas." },
      { note: 1, texte: "Ce n'est pas dramatique si on agit vite. Changez votre mot de passe dès que vous raccrochez, puis supprimez ce mail pour ne pas recliquer dessus par erreur." },
      { note: 0, texte: "Votre antivirus est à jour et il n'a rien bloqué, donc le lien n'était probablement pas dangereux. Surveillez simplement votre messagerie et rappelez-moi si quelque chose de bizarre se passe." },
      { note: 0, grossiere: true, texte: "On fait pourtant des sensibilisations régulières là-dessus. Une banque ne demande jamais vos identifiants par mail, comment avez-vous pu tomber dedans ?" }
    ],
    pointCle: "ici, la bonne réponse est une action immédiate, pas une question. Culpabiliser l'utilisateur, c'est s'assurer qu'il ne signalera plus rien.",
    attendu: {
      type: "Incident",
      categorie: "Sécurité",
      urgence: "Très haute",
      impact: ["Moyenne", "Haute"]
    }
  },
  {
    id: "t07-compte-verrouille",
    theme: "Compte verrouillé",
    nom: "Mme N'Diaye",
    service: "RH",
    source: "Téléphone",
    demande: "Ça me dit que mon compte est verrouillé. J'ai essayé plusieurs fois, je suis sûre que mon mot de passe est bon.",
    reponses: [
      { note: 2, texte: "Je vérifie d'abord votre identité, puis je déverrouille votre compte. Au passage, la touche Verr. Maj était-elle activée quand vous avez tapé ?" },
      { note: 1, texte: "Pas de problème, je m'en occupe tout de suite. Donnez-moi votre identifiant de connexion et je vous déverrouille le compte dans la foulée." },
      { note: 0, texte: "Pour éviter que ça recommence, je vous réinitialise le mot de passe. Je vous dicte le nouveau par téléphone, notez-le bien et vous pourrez vous reconnecter tout de suite." },
      { note: 0, texte: "Le verrouillage est automatique après plusieurs erreurs, c'est une sécurité. Patientez une trentaine de minutes sans rien toucher, il se débloquera tout seul et vous pourrez réessayer." }
    ],
    pointCle: "vérifier l'identité avant toute action sur un compte. C'est la parade contre l'ingénierie sociale.",
    attendu: {
      type: "Incident",
      categorie: "Comptes et accès",
      urgence: "Haute",
      impact: "Basse"
    }
  },
  {
    id: "t08-logiciel",
    theme: "Logiciel",
    nom: "M. Roche",
    service: "communication",
    source: "Helpdesk",
    demande: "Il me faut Photoshop installé aujourd'hui, j'ai une plaquette à rendre demain.",
    reponses: [
      { note: 2, texte: "Je note votre demande. Un logiciel payant demande une validation et une licence : je la transmets au service concerné et je vous tiens informé." },
      { note: 1, texte: "Je n'ai pas le droit d'installer ce type de logiciel moi-même. Le mieux est d'en parler directement à votre responsable, c'est lui qui peut valider ce genre d'achat." },
      { note: 0, texte: "Vu l'urgence, je vous accorde temporairement les droits administrateur sur votre poste. Vous pourrez installer Photoshop vous-même, et je vous les retire demain matin." },
      { note: 0, grossiere: true, texte: "Une licence, ça va prendre des jours. En attendant, cherchez une version gratuite sur Internet, il y en a plein qui circulent, ça vous dépannera pour votre plaquette." }
    ],
    pointCle: "savoir escalader proprement au lieu de renvoyer l'utilisateur se débrouiller.",
    attendu: {
      type: "Demande",
      categorie: "Logiciel",
      urgence: "Moyenne",
      impact: "Basse"
    }
  },
  {
    id: "t09-panne-materielle",
    theme: "Panne matérielle",
    nom: "M. Lambert",
    service: "atelier",
    source: "Courriel",
    objet: "Bruit bizarre de mon PC",
    demande: "Mon PC fait un bruit de clic-clic depuis ce matin, et il met dix minutes à démarrer.",
    reponses: [
      { note: 2, texte: "Ce bruit peut venir du disque dur. Avez-vous des fichiers importants enregistrés seulement sur ce poste ? En attendant, évitez de l'éteindre." },
      { note: 1, texte: "D'après ce que vous décrivez, c'est très probablement le disque dur qui fatigue. Je lance la commande d'un disque de remplacement et je reviens vers vous pour l'intervention." },
      { note: 0, texte: "Un démarrage aussi long, c'est souvent un disque trop fragmenté. Lancez une défragmentation depuis les outils de Windows et laissez-la tourner, ça devrait accélérer nettement." },
      { note: 0, grossiere: true, texte: "Parfois une pièce est simplement mal enfoncée et fait du bruit. Tapotez doucement sur le côté du boîtier : si le clic s'arrête, c'est que ça s'est remis en place." }
    ],
    pointCle: "un disque qui claque, c'est d'abord des données à sauver. La défragmentation peut l'achever.",
    attendu: {
      type: "Incident",
      categorie: "Matériel",
      urgence: ["Haute", "Très haute"],
      impact: "Basse"
    }
  },
  {
    id: "t10-utilisateur-en-colere",
    theme: "Utilisateur en colère",
    nom: "M. Vasseur",
    service: "commercial",
    source: "Direct",
    demande: "C'est la troisième fois ce mois-ci qu'Outlook plante ! Vous servez à quoi, au service informatique ?",
    reponses: [
      { note: 2, texte: "Trois fois en un mois, je comprends que ce soit pénible. Je reprends l'historique de vos tickets. Que se passe-t-il exactement quand il plante ?" },
      { note: 1, texte: "Je suis désolé pour la gêne. Fermez Outlook, puis relancez-le en mode sans échec : si ça ne plante plus, on saura que le problème vient d'un complément." },
      { note: 0, texte: "Puisque ça revient sans arrêt, on va arrêter les rustines : je vous désinstalle et réinstalle toute la suite Office ce midi, comme ça on repart sur une base propre." },
      { note: 0, grossiere: true, texte: "Je comprends votre agacement, mais je ne continuerai pas cet échange si vous me parlez sur ce ton. Revenez me voir quand vous serez plus calme." }
    ],
    pointCle: "accueillir l'émotion, puis traiter la récurrence. Un incident qui revient demande de consulter l'historique, pas d'appliquer une nouvelle rustine.",
    attendu: {
      type: "Incident",
      categorie: ["Messagerie et collaboratif", "Logiciel"],
      urgence: "Moyenne",
      impact: "Basse"
    }
  },
  {
    id: "t11-rancongiciel",
    theme: "Rançongiciel",
    nom: "Mme Fabre",
    service: "secrétariat",
    source: "Téléphone",
    demande: "Tous mes fichiers ont une extension bizarre, \".locked\", et il y a un message qui demande de payer en bitcoins. Je fais quoi ?",
    reponses: [
      { note: 2, texte: "Ne touchez plus à rien et débranchez le câble réseau de votre PC, sans l'éteindre. Je préviens immédiatement l'équipe sécurité, restez près de votre poste." },
      { note: 1, texte: "Éteignez votre ordinateur tout de suite et ne le rallumez pas. Je préviens l'équipe sécurité, quelqu'un va venir récupérer le poste." },
      { note: 0, texte: "Ne paniquez pas, c'est peut-être un faux message. Avez-vous essayé d'ouvrir un fichier ? Je prends la main à distance pour vérifier s'ils sont vraiment chiffrés." },
      { note: 0, grossiere: true, texte: "Surtout, ne payez pas. Supprimez le message et les fichiers bizarres, puis restaurez ce que vous pouvez depuis la corbeille ou depuis votre clé USB." }
    ],
    pointCle: "isoler le poste du réseau pour stopper la propagation, sans l'éteindre (la mémoire sert à l'analyse), puis escalader.",
    attendu: {
      type: "Incident",
      categorie: "Sécurité",
      urgence: "Très haute",
      impact: ["Haute", "Très haute"]
    }
  },
  {
    id: "t12-accessibilite",
    theme: "Accessibilité",
    nom: "Mme Caron",
    service: "juridique",
    source: "Direct",
    demande: "Depuis la mise à jour d'hier, tout est écrit en tout petit. Avec ma vue, je n'arrive plus à lire mes dossiers.",
    reponses: [
      { note: 2, texte: "La mise à jour a sûrement remis l'affichage par défaut. Je vous accompagne à votre poste pour rétablir vos réglages, en vous expliquant chaque étape. Ça vous va ?" },
      { note: 1, texte: "Appuyez plusieurs fois sur Ctrl et la touche plus en même temps : le texte va grossir dans la fenêtre que vous utilisez." },
      { note: 0, texte: "Vous pouvez utiliser la loupe de Windows en attendant, avec la touche Windows et plus. Vous saviez qu'elle existait ? Elle agrandit tout l'écran, c'est très pratique." },
      { note: 0, texte: "Pour vous, le plus simple serait un écran plus grand. Je fais une demande de matériel, vous devriez le recevoir d'ici quelques semaines." }
    ],
    pointCle: "rétablir ses réglages d'accessibilité plutôt que de proposer un contournement, en expliquant et en demandant son accord.",
    attendu: {
      type: "Incident",
      categorie: "Poste de travail",
      urgence: ["Haute", "Moyenne"],
      impact: "Basse"
    }
  },
  {
    id: "t13-vpn",
    theme: "VPN",
    nom: "M. Girard",
    service: "comptabilité",
    source: "Téléphone",
    demande: "Je suis chez moi et le VPN refuse de se connecter. Il me met \"délai d'attente dépassé\".",
    reponses: [
      { note: 2, texte: "Est-ce que votre connexion Internet fonctionne normalement chez vous, sur un site web par exemple ? Et le VPN marchait-il encore la semaine dernière ?" },
      { note: 1, texte: "Redémarrez votre box et votre ordinateur, puis réessayez de vous connecter au VPN. Après une coupure, ça suffit souvent à rétablir la connexion." },
      { note: 0, texte: "Désactivez votre pare-feu et votre antivirus le temps de vous connecter. Ce sont souvent eux qui bloquent le VPN, vous les réactiverez juste après." },
      { note: 0, texte: "Un délai dépassé vient presque toujours du serveur VPN de l'entreprise. Je signale la panne à l'équipe réseau, et je vous rappelle dès que c'est rétabli." }
    ],
    pointCle: "vérifier d'abord la connexion de l'utilisateur avant d'accuser le serveur. Désactiver les protections n'est jamais un réflexe de dépannage.",
    attendu: {
      type: "Incident",
      categorie: "Réseau",
      urgence: ["Moyenne", "Haute"],
      impact: "Basse"
    }
  },
  {
    id: "t14-nouvel-arrivant",
    theme: "Nouvel arrivant",
    nom: "Mme Robin",
    service: "responsable logistique",
    source: "Courriel",
    objet: "Arrivée de Julien Martin lundi",
    demande: "J'ai quelqu'un qui arrive lundi. Vous pouvez lui créer un compte et préparer un PC ? Il s'appelle Julien Martin.",
    reponses: [
      { note: 2, texte: "Bien sûr. Pour lancer la création, il me faut la validation RH de son arrivée : la fiche a-t-elle été envoyée ? Je prépare ensuite son compte et son poste." },
      { note: 1, texte: "Je m'en occupe. Indiquez-moi son nom, son service et sa date d'arrivée, je crée son compte dès aujourd'hui et je lui prépare un poste." },
      { note: 0, texte: "Pas de problème, je lui crée un compte avec les mêmes droits que vous. Comme ça, il aura accès à tout ce dont votre équipe a besoin dès lundi." },
      { note: 0, grossiere: true, texte: "En attendant lundi, il peut utiliser votre session. Donnez-lui votre mot de passe, ce sera plus simple que de tout créer dans l'urgence." }
    ],
    pointCle: "une création de compte suit une procédure validée, avec seulement les droits nécessaires.",
    attendu: {
      type: "Demande",
      categorie: ["Comptes et accès", "Poste de travail"],
      urgence: "Moyenne",
      impact: "Basse"
    }
  },
  {
    id: "t15-panne-collective",
    theme: "Panne collective",
    nom: "M. Dubois",
    service: "chef d'équipe facturation",
    source: "Téléphone",
    demande: "Personne dans le service n'arrive à ouvrir le logiciel de facturation. On est huit à être bloqués.",
    reponses: [
      { note: 2, texte: "Huit personnes bloquées, je traite ça en priorité. Le message d'erreur est-il le même pour tout le monde ? J'ouvre un incident et je préviens l'équipe concernée." },
      { note: 1, texte: "Je prends la main sur votre poste pour regarder le message d'erreur, et je vous dirai ensuite si ça vient du logiciel ou de votre ordinateur." },
      { note: 0, texte: "Je vais passer sur chaque poste pour réinstaller le logiciel un par un. Vous pouvez demander à vos collègues de laisser leur session ouverte ?" },
      { note: 0, texte: "Ce logiciel est géré par l'éditeur, pas par nous. Appelez directement leur support, leur numéro doit être dans le manuel d'utilisation." }
    ],
    pointCle: "quand plusieurs personnes sont touchées, la cause est centrale. L'impact élevé fait monter la priorité.",
    attendu: {
      type: "Incident",
      categorie: "Logiciel",
      urgence: ["Haute", "Très haute"],
      impact: ["Haute", "Très haute"]
    }
  },
  {
    id: "t16-cle-usb-trouvee",
    theme: "Clé USB trouvée",
    nom: "Inès",
    service: "accueil",
    source: "Direct",
    demande: "J'ai trouvé cette clé USB sur le parking. Je l'ai branchée sur mon poste pour voir à qui elle était, mais il y a juste un fichier \"Salaires 2026\".",
    reponses: [
      { note: 2, texte: "Merci de me l'avoir apportée. Je la garde sans l'ouvrir. Avez-vous ouvert ce fichier ? Je viens avec vous faire vérifier votre poste." },
      { note: 1, texte: "Merci, je garde la clé et je la transmets à la sécurité. À l'avenir, ne branchez jamais une clé dont vous ne connaissez pas l'origine." },
      { note: 0, texte: "Si l'antivirus ne s'est pas déclenché quand vous l'avez branchée, c'est qu'elle est saine. Vous pouvez la déposer aux objets trouvés de l'accueil." },
      { note: 0, grossiere: true, texte: "Rebranchez-la et ouvrez le fichier, il y aura peut-être le nom du propriétaire dedans. Vous pourrez la lui rendre directement sans passer par nous." }
    ],
    pointCle: "une clé abandonnée est un mode d'attaque classique. On isole, on vérifie le poste, et on remercie l'utilisatrice d'avoir signalé.",
    attendu: {
      type: "Incident",
      categorie: "Sécurité",
      urgence: ["Haute", "Très haute"],
      impact: "Moyenne"
    }
  },
  {
    id: "t17-micro-teams",
    theme: "Micro Teams",
    nom: "Mme Leclerc",
    service: "RH",
    source: "Autre",
    canal: "Message Teams",
    demande: "Ma réunion Teams commence dans cinq minutes et personne ne m'entend ! Le micro marchait hier.",
    reponses: [
      { note: 2, texte: "On fait vite. Avez-vous un casque branché ? Dans Teams, cliquez sur les trois points, puis Paramètres de l'appareil : quel micro est sélectionné ?" },
      { note: 1, texte: "Quittez complètement Teams, puis relancez-le. Ça corrige souvent les problèmes de micro quand un appareil a été branché ou débranché." },
      { note: 0, texte: "Je mets à jour le pilote audio de votre poste à distance. Ça ne prend qu'un quart d'heure, vous pourrez rejoindre la réunion juste après." },
      { note: 0, texte: "Ce sont souvent les mises à jour de Windows qui cassent le son. Lancez Windows Update maintenant, puis redémarrez avant votre réunion." }
    ],
    pointCle: "avec cinq minutes devant soi, on vérifie d'abord le périphérique sélectionné, pas une intervention lourde.",
    attendu: {
      type: "Incident",
      categorie: ["Messagerie et collaboratif", "Matériel"],
      urgence: ["Haute", "Très haute"],
      impact: "Basse"
    }
  },
  {
    id: "t18-disque-plein",
    theme: "Disque plein",
    nom: "M. Henry",
    service: "bureau d'études",
    source: "Helpdesk",
    demande: "J'ai un message \"espace disque insuffisant\" et je ne peux plus enregistrer mes plans.",
    reponses: [
      { note: 2, texte: "Je regarde avec vous ce qui prend de la place. Vos plans sont-ils enregistrés sur le PC ou sur le réseau ? Je peux prendre la main ?" },
      { note: 1, texte: "Videz votre corbeille et supprimez les fichiers temporaires avec l'outil Nettoyage de disque. Ça libère souvent plusieurs gigaoctets en quelques minutes." },
      { note: 0, texte: "Supprimez les anciens plans dont vous n'avez plus besoin, et ceux en double. Vous savez lesquels sont sauvegardés ailleurs, ou je regarde avec vous ?" },
      { note: 0, grossiere: true, texte: "Allez sur le disque C et supprimez les dossiers que vous ne reconnaissez pas, comme Program Files : ce sont souvent des restes inutiles." }
    ],
    pointCle: "chercher ce qui occupe l'espace avant de supprimer quoi que ce soit. Les données de l'utilisateur ne se suppriment jamais à la légère.",
    attendu: {
      type: "Incident",
      categorie: ["Poste de travail", "Matériel"],
      urgence: ["Haute", "Moyenne"],
      impact: "Basse"
    }
  },
  {
    id: "t19-ingenierie-sociale",
    theme: "Ingénierie sociale",
    nom: "M. Vidal",
    service: "directeur financier",
    source: "Téléphone",
    demande: "Bonjour, ici M. Vidal, directeur financier. Ma secrétaire est bloquée : réinitialisez son mot de passe et donnez-le-moi, c'est urgent.",
    reponses: [
      { note: 2, texte: "Je comprends l'urgence. Pour des raisons de sécurité, je dois réinitialiser ce mot de passe avec votre secrétaire elle-même. Peut-elle m'appeler depuis son poste ?" },
      { note: 1, texte: "Je comprends, mais je ne peux pas vous donner son mot de passe. Votre secrétaire devra ouvrir un ticket elle-même quand elle le pourra." },
      { note: 0, texte: "Bien sûr, monsieur. Je lui mets un mot de passe temporaire et je vous l'envoie par mail. Elle devra le changer à sa première connexion." },
      { note: 0, grossiere: true, texte: "Pas de problème, vu que c'est vous. Je mets son mot de passe à « Bienvenue2026 », elle pourra se reconnecter immédiatement." }
    ],
    pointCle: "un mot de passe ne se transmet jamais à un tiers, même à un supérieur. L'autorité et l'urgence sont les deux leviers classiques de l'ingénierie sociale. La réponse ~ refuse à juste titre, mais laisse le problème en plan : la secrétaire, bloquée, ne peut pas ouvrir de ticket.",
    attendu: {
      type: ["Demande", "Incident"],
      categorie: ["Comptes et accès", "Sécurité"],
      urgence: ["Haute", "Moyenne"],
      impact: ["Basse", "Moyenne"]
    }
  },
  {
    id: "t20-double-ecran",
    theme: "Double écran",
    nom: "Mme Morin",
    service: "marketing",
    source: "Helpdesk",
    demande: "On a changé de bureau hier, et mon deuxième écran reste noir. Le premier marche très bien.",
    reponses: [
      { note: 2, texte: "Votre PC est-il branché sur une station d'accueil ? Pouvez-vous vérifier que le câble du deuxième écran est bien enfoncé des deux côtés et que l'écran est allumé ?" },
      { note: 1, texte: "Appuyez en même temps sur la touche Windows et P, puis choisissez « Étendre ». L'affichage est peut-être revenu sur un seul écran." },
      { note: 0, texte: "Le déménagement a dû abîmer l'écran. Je vous en commande un neuf, et en attendant vous pourrez travailler sur un seul écran quelques jours." },
      { note: 0, grossiere: true, texte: "Un double écran, c'est du confort, pas une priorité. Je regarderai quand j'aurai le temps, travaillez sur un seul écran en attendant." }
    ],
    pointCle: "après un déménagement, on vérifie d'abord le physique (câbles, station d'accueil, alimentation) avant de conclure à une panne.",
    attendu: {
      type: "Incident",
      categorie: ["Matériel", "Poste de travail"],
      urgence: ["Basse", "Très basse"],
      impact: ["Basse", "Très basse"]
    }
  },
  {
    id: "t21-dossier-supprime",
    theme: "Dossier supprimé",
    nom: "Mme Lemoine",
    service: "administration",
    source: "Direct",
    demande: "J'ai supprimé par erreur le dossier \"Contrats\" sur le partage commun. Il y avait tout le travail de l'équipe dedans !",
    reponses: [
      { note: 2, texte: "Pas de panique, le partage est sauvegardé. Vous souvenez-vous à peu près de l'heure de la suppression ? Je lance la restauration et je vous préviens dès que c'est fait." },
      { note: 1, texte: "Faites un clic droit dans le dossier parent, puis « Restaurer les versions précédentes ». Si la fonction est activée, vous pourrez récupérer le dossier vous-même." },
      { note: 0, texte: "Regardez dans votre corbeille Windows, le dossier doit y être. Faites un clic droit dessus, puis Restaurer, et il reviendra exactement à sa place." },
      { note: 0, grossiere: true, texte: "Ça arrive à tout le monde, mais là je ne peux plus rien faire. L'équipe devra refaire les documents à partir de ses mails et de ses brouillons." }
    ],
    pointCle: "ce qu'on supprime sur un partage réseau ne passe pas par la corbeille. On restaure depuis la sauvegarde.",
    attendu: {
      type: "Incident",
      categorie: "Fichiers et partages",
      urgence: ["Haute", "Très haute"],
      impact: ["Moyenne", "Haute"]
    }
  },
  {
    id: "t22-fichier-verrouille",
    theme: "Fichier verrouillé",
    nom: "M. Perrin",
    service: "comptabilité",
    source: "Courriel",
    objet: "Fichier budget verrouillé",
    demande: "Excel me dit que le fichier budget est \"verrouillé par un autre utilisateur\". Mais tout le monde dit qu'il ne l'a pas ouvert.",
    reponses: [
      { note: 2, texte: "Le verrou reste parfois après une fermeture brutale. Quel nom d'utilisateur Excel affiche-t-il ? Je vérifie avec cette personne avant de libérer le fichier." },
      { note: 1, texte: "Ouvrez-le en lecture seule pour l'instant, et enregistrez vos modifications sous un autre nom. On fusionnera les deux versions quand le verrou aura disparu." },
      { note: 0, texte: "Je redémarre le serveur de fichiers ce midi, ça libérera tous les verrous d'un coup. Vous pourrez retravailler sur le budget cet après-midi." },
      { note: 0, texte: "Copiez le fichier sur votre bureau, travaillez sur la copie, puis remettez-la sur le partage en remplaçant l'original quand vous aurez fini." }
    ],
    pointCle: "identifier qui tient le fichier avant d'agir. Redémarrer un serveur pour un seul fichier bloque tout le monde.",
    attendu: {
      type: "Incident",
      categorie: ["Logiciel", "Fichiers et partages"],
      urgence: "Moyenne",
      impact: ["Basse", "Moyenne"]
    }
  },
  {
    id: "t23-wi-fi-en-salle-de-reunion",
    theme: "Wi-Fi en salle de réunion",
    nom: "Mme Benali",
    service: "commerciale",
    source: "Téléphone",
    demande: "En salle de réunion, mon portable ne trouve pas le Wi-Fi. Au bureau, ça marche très bien.",
    reponses: [
      { note: 2, texte: "Dans la liste des réseaux, voyez-vous celui de l'entreprise ? Et le mode avion n'est-il pas activé, par hasard ? Il y a un petit avion en bas à droite." },
      { note: 1, texte: "En attendant, branchez-vous sur la prise réseau de la salle avec un câble. Je regarderai le Wi-Fi de cette salle plus tard dans la journée." },
      { note: 0, texte: "Il y a sûrement un problème avec la borne de cette salle. Je fais intervenir le prestataire réseau, ça peut prendre quelques jours. Vous avez un autre endroit pour travailler ?" },
      { note: 0, texte: "Oubliez le réseau Wi-Fi dans les paramètres, puis redémarrez votre portable. Ensuite, reconnectez-vous en saisissant à nouveau la clé du réseau." }
    ],
    pointCle: "vérifier les causes simples côté poste avant de mettre en cause l'infrastructure.",
    attendu: {
      type: "Incident",
      categorie: "Réseau",
      urgence: ["Moyenne", "Haute"],
      impact: "Basse"
    }
  },
  {
    id: "t24-demande-d-acces",
    theme: "Demande d'accès",
    nom: "M. Fontaine",
    service: "chargé de mission",
    source: "Helpdesk",
    demande: "J'ai besoin d'accéder au dossier partagé de la direction pour un projet. Vous pouvez me donner les droits ?",
    reponses: [
      { note: 2, texte: "Je prends votre demande. L'accès à ce dossier doit être validé par son responsable : je lui transmets, et je vous ouvre les droits dès qu'il a donné son accord." },
      { note: 1, texte: "Pour ce dossier, il faut l'accord de la direction. Demandez à votre responsable d'envoyer un mail au service informatique, et on s'en occupera." },
      { note: 0, texte: "Je vous ajoute au groupe Direction, comme ça vous aurez accès au dossier. C'est le plus rapide, et vous verrez aussi les autres ressources de l'équipe." },
      { note: 0, grossiere: true, texte: "Demandez à un collègue de la direction de vous prêter ses identifiants le temps du projet, ce sera bien plus simple que toute une procédure." }
    ],
    pointCle: "un droit d'accès se valide par le propriétaire de la ressource, et on ne donne que ce qui est nécessaire.",
    attendu: {
      type: "Demande",
      categorie: ["Comptes et accès", "Fichiers et partages"],
      urgence: ["Basse", "Moyenne"],
      impact: "Basse"
    }
  },
  {
    id: "t25-mail-au-mauvais-destinataire",
    theme: "Mail au mauvais destinataire",
    nom: "Mme Gauthier",
    service: "RH",
    source: "Téléphone",
    demande: "J'ai envoyé un tableau avec les salaires de l'équipe au mauvais destinataire, quelqu'un d'extérieur. Je fais quoi ?",
    reponses: [
      { note: 2, texte: "Vous avez bien fait d'appeler vite. Essayez de rappeler le message si c'est possible, et je signale l'incident à la sécurité et au référent données personnelles." },
      { note: 1, texte: "Utilisez la fonction de rappel du message dans Outlook. Si le destinataire ne l'a pas encore ouvert, il sera supprimé de sa boîte." },
      { note: 0, texte: "Envoyez un mail à cette personne pour lui demander de supprimer le message sans l'ouvrir. En général, les gens jouent le jeu, et ça règle le problème." },
      { note: 0, grossiere: true, texte: "Le mail est parti, on ne peut plus rien y faire. Le mieux est de ne pas en parler, ça évitera d'inquiéter l'équipe pour rien." }
    ],
    pointCle: "une fuite de données personnelles doit être signalée. Le RGPD impose de prévenir la CNIL sous 72 heures dans la plupart des cas.",
    attendu: {
      type: "Incident",
      categorie: "Sécurité",
      urgence: ["Haute", "Très haute"],
      impact: ["Moyenne", "Haute"]
    }
  },
  {
    id: "t26-boite-mail-pleine",
    theme: "Boîte mail pleine",
    nom: "M. Charpentier",
    service: "achats",
    source: "Helpdesk",
    demande: "Outlook me dit que ma boîte aux lettres est pleine, je ne peux plus envoyer de mails.",
    reponses: [
      { note: 2, texte: "Je vais regarder avec vous ce qui prend le plus de place. Vous gardez beaucoup de mails avec des pièces jointes ? On peut aussi archiver les plus anciens." },
      { note: 1, texte: "Videz le dossier Éléments supprimés et le Courrier indésirable. Ça libère souvent un peu de place, et vous pourrez de nouveau envoyer." },
      { note: 0, texte: "Je vais augmenter la taille de votre boîte aux lettres, comme ça vous serez tranquille. Vous voulez que je fasse pareil pour vos collègues ?" },
      { note: 0, texte: "Triez vos mails par date et supprimez d'un coup tous ceux de plus d'un an. Vous n'en aurez plus besoin, et votre boîte sera presque vide." }
    ],
    pointCle: "comprendre ce qui remplit la boîte et archiver, plutôt que tout supprimer ou repousser la limite sans règle.",
    attendu: {
      type: "Incident",
      categorie: "Messagerie et collaboratif",
      urgence: ["Moyenne", "Haute"],
      impact: "Basse"
    }
  },
  {
    id: "t27-mise-a-jour-bloquee",
    theme: "Mise à jour bloquée",
    nom: "Mme Barbier",
    service: "accueil",
    source: "Téléphone",
    demande: "Mon PC affiche \"Ne pas éteindre l'ordinateur, mise à jour en cours\" depuis une heure. Je peux l'éteindre ?",
    reponses: [
      { note: 2, texte: "Non, surtout pas pour l'instant. Le pourcentage avance-t-il, même lentement ? Et le petit voyant du disque clignote-t-il sur l'ordinateur ?" },
      { note: 1, texte: "Laissez-le tranquille, certaines mises à jour sont très longues. Si rien n'a bougé dans une heure, rappelez-moi et je passerai le voir." },
      { note: 0, texte: "Débranchez le câble réseau, la mise à jour est peut-être bloquée en plein téléchargement. Ça devrait la forcer à terminer avec ce qu'elle a déjà." },
      { note: 0, grossiere: true, texte: "Une heure, c'est qu'elle est plantée. Appuyez longtemps sur le bouton d'alimentation pour l'éteindre, puis rallumez-le : ça repartira normalement." }
    ],
    pointCle: "couper une mise à jour en cours peut rendre le système inutilisable. On vérifie d'abord si elle avance.",
    attendu: {
      type: "Incident",
      categorie: ["Poste de travail", "Logiciel"],
      urgence: ["Moyenne", "Haute"],
      impact: ["Basse", "Moyenne"]
    }
  },
  {
    id: "t28-videoprojecteur",
    theme: "Vidéoprojecteur",
    nom: "M. Lefèvre",
    service: "directeur commercial",
    source: "Téléphone",
    demande: "Le vidéoprojecteur de la salle affiche \"Aucun signal\", et mes clients arrivent dans dix minutes !",
    reponses: [
      { note: 2, texte: "Dix minutes, c'est jouable. Votre portable est-il branché au câble HDMI de la salle ? Appuyez sur Windows et P, puis choisissez « Dupliquer »." },
      { note: 1, texte: "Vérifiez que le vidéoprojecteur est sur la bonne entrée, avec le bouton Source ou Input de la télécommande. Il cherche peut-être sur une autre entrée." },
      { note: 0, texte: "Je vous apporte un autre vidéoprojecteur du stock. Il me faut une vingtaine de minutes pour l'installer, vous pouvez retarder un peu le début ?" },
      { note: 0, texte: "Redémarrez votre portable avec le câble déjà branché. Windows ne détecte pas toujours un écran branché après le démarrage, ça règle souvent tout." }
    ],
    pointCle: "sous pression, on teste dans l'ordre les causes rapides (câble, mode d'affichage, source) avant toute solution lourde.",
    attendu: {
      type: "Incident",
      categorie: "Matériel",
      urgence: "Très haute",
      impact: ["Basse", "Moyenne"]
    }
  },
  {
    id: "t29-clavier",
    theme: "Clavier",
    nom: "Mme Rousseau",
    service: "comptable",
    source: "Direct",
    demande: "Mon clavier ne tape plus rien. La souris marche, mais le clavier, plus rien du tout.",
    reponses: [
      { note: 2, texte: "On va vérifier ensemble. Votre clavier a-t-il un fil, ou est-il sans fil ? S'il est sans fil, les piles sont peut-être simplement à changer." },
      { note: 1, texte: "Débranchez le petit boîtier USB du clavier, attendez quelques secondes, puis rebranchez-le sur une autre prise USB de l'ordinateur." },
      { note: 0, texte: "Je prends la main à distance pour réinstaller le pilote du clavier. Pendant ce temps, ne touchez pas à la souris, sinon ça risque de couper." },
      { note: 0, grossiere: true, texte: "Un clavier, ça ne coûte rien. Je vous en commande un neuf, et en attendant, tapez avec le clavier virtuel de Windows, il est dans les paramètres." }
    ],
    pointCle: "partir du plus simple, avec des mots que l'utilisatrice comprend. Le « petit boîtier USB » parle plus que « le dongle ».",
    attendu: {
      type: "Incident",
      categorie: "Matériel",
      urgence: ["Moyenne", "Haute"],
      impact: "Basse"
    }
  },
  {
    id: "t30-alerte-de-certificat",
    theme: "Alerte de certificat",
    nom: "M. Marchand",
    service: "achats",
    source: "Courriel",
    objet: "Alerte sur le site du fournisseur",
    demande: "Quand je vais sur le site de notre fournisseur, le navigateur affiche \"Votre connexion n'est pas privée\". Je peux continuer quand même ?",
    reponses: [
      { note: 2, texte: "Non, ne continuez pas pour l'instant et ne saisissez rien sur ce site. Vous y êtes allé par un lien reçu par mail, ou par vos favoris habituels ?" },
      { note: 1, texte: "Évitez ce site pour le moment. Ce message signale un problème de certificat : prévenez le fournisseur par téléphone pour le lui signaler." },
      { note: 0, texte: "Cliquez sur Paramètres avancés, puis sur Continuer vers le site. Si c'est bien l'adresse habituelle du fournisseur, il n'y a aucun risque." },
      { note: 0, grossiere: true, texte: "Ces messages sont presque toujours de fausses alertes. Changez de navigateur, essayez Firefox par exemple, il bloque beaucoup moins." }
    ],
    pointCle: "une alerte de certificat peut signaler un faux site. On s'arrête, on vérifie l'origine du lien, on ne contourne pas.",
    attendu: {
      type: "Incident",
      categorie: "Sécurité",
      urgence: "Moyenne",
      impact: "Basse"
    }
  }
];

/*
 * Simulation d'assistance informatique — logique de l'application.
 * Tout tourne dans le navigateur : pas de serveur, pas de compte, aucune donnée envoyée.
 */
(function () {
  "use strict";

  /* ======================= Constantes ======================= */

  var CFG = window.CONFIG || {};
  var NB_PAR_SESSION = CFG.ticketsParSession || 5;
  var CATEGORIES = CFG.categories || [];
  var GROUPES = CFG.groupes || [];

  var NIVEAUX = ["Très basse", "Basse", "Moyenne", "Haute", "Très haute"]; // 1 à 5
  var TYPES = ["Incident", "Demande"];
  var SOURCES = ["Téléphone", "Courriel", "Direct", "Helpdesk", "Autre"];
  var STATUTS = ["Nouveau", "En cours (attribué)", "En cours (planifié)", "En attente", "Résolu", "Clos"];

  // Titre du panneau de gauche selon la source de la demande.
  // Pour « Autre », le titre vient du champ canal du ticket (ex. « Message Teams »).
  var TITRES_SOURCE = {
    "Téléphone": "Appel entrant",
    "Courriel": "Courriel reçu",
    "Direct": "Visite au bureau",
    "Helpdesk": "Demande via le portail",
    "Autre": "Autre canal"
  };

  // Priorité = f(urgence, impact). Reprend la matrice proposée par défaut dans GLPI
  // (Configuration > Générale > Assistance) : MATRICE[urgence][impact], valeurs de 1 à 5.
  var MATRICE = {
    1: { 1: 1, 2: 1, 3: 2, 4: 2, 5: 2 },
    2: { 1: 1, 2: 2, 3: 2, 4: 3, 5: 3 },
    3: { 1: 2, 2: 2, 3: 3, 4: 4, 5: 4 },
    4: { 1: 2, 2: 3, 3: 4, 4: 4, 5: 5 },
    5: { 1: 2, 2: 3, 3: 4, 4: 5, 5: 5 }
  };

  /* ======================= Outils ======================= */

  var $ = function (id) { return document.getElementById(id); };

  // Échappe le texte avant de l'insérer dans du HTML (évite l'injection de code,
  // par exemple via le nom saisi par l'apprenant).
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Mélange de Fisher-Yates : chaque ordre a la même probabilité.
  function melanger(liste) {
    var a = liste.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function initiales(nom) {
    var mots = String(nom).replace(/\b(M\.|Mme|Mlle)\s+/g, "").split(/\s+/).filter(Boolean);
    return (mots[0] || "?").charAt(0).toUpperCase() + (mots[1] ? mots[1].charAt(0).toUpperCase() : "");
  }

  function slug(s) {
    return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "")
      .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "apprenant";
  }

  function remplirSelect(select, options, valeurParDefaut) {
    select.innerHTML = "";
    options.forEach(function (o) {
      var opt = document.createElement("option");
      opt.value = o.value != null ? o.value : o;
      opt.textContent = o.label != null ? o.label : o;
      select.appendChild(opt);
    });
    if (valeurParDefaut != null) select.value = valeurParDefaut;
  }

  var attendre = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var animationsReduites = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ======================= Chargement des tickets ======================= */

  // Vérifie un ticket ; renvoie la liste des problèmes (vide si tout va bien).
  function problemesTicket(t) {
    var p = [];
    if (!t || typeof t !== "object") return ["ce n'est pas un bloc { ... }"];
    if (!t.id) p.push("id manquant");
    if (!t.nom) p.push("nom manquant");
    if (!t.demande) p.push("demande manquante");
    if (SOURCES.indexOf(t.source) === -1) p.push("source invalide (valeurs possibles : " + SOURCES.join(", ") + ")");
    if (t.source === "Courriel" && !t.objet) p.push("objet manquant (obligatoire pour un courriel)");
    if (!Array.isArray(t.reponses) || t.reponses.length < 2) {
      p.push("il faut au moins 2 réponses");
    } else {
      t.reponses.forEach(function (r, i) {
        if (!r || !r.texte) p.push("réponse " + (i + 1) + " sans texte");
        if (!r || [0, 1, 2].indexOf(r.note) === -1) p.push("réponse " + (i + 1) + " : note doit valoir 0, 1 ou 2");
      });
      if (!t.reponses.some(function (r) { return r && r.note === 2; })) p.push("aucune bonne réponse (note: 2)");
    }
    return p;
  }

  function chargerTickets() {
    if (!Array.isArray(window.TICKETS)) return null; // fichier absent ou erreur de syntaxe
    return window.TICKETS.filter(function (t, i) {
      var p = problemesTicket(t);
      if (p.length) console.warn("Ticket ignoré (position " + (i + 1) + ", id « " + (t && t.id) + " ») : " + p.join(" ; "));
      return p.length === 0;
    });
  }

  /* ======================= État ======================= */

  var etat = {
    apprenant: "",
    debut: null,
    fin: null,
    session: [],     // [{ ticket, ordre, choix, saisie, numero }]
    index: 0,
    enCours: false,
    rapportTelecharge: false
  };
  var reserve = [];

  /* ======================= Navigation ======================= */

  function afficherEcran(id) {
    ["ecran-accueil", "ecran-consigne", "ecran-simulation", "ecran-rapport"].forEach(function (e) {
      $(e).hidden = e !== id;
    });
    window.scrollTo(0, 0);
  }

  /* ======================= Thème ======================= */

  function themeActuel() {
    var t = document.documentElement.dataset.theme;
    if (t) return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function majBoutonTheme() {
    var sombre = themeActuel() === "dark";
    $("btn-theme").textContent = sombre ? "☀️" : "🌙";
    $("btn-theme").setAttribute("aria-label", sombre ? "Passer en thème clair" : "Passer en thème sombre");
  }

  $("btn-theme").addEventListener("click", function () {
    var nouveau = themeActuel() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nouveau;
    try { localStorage.setItem("theme", nouveau); } catch (e) { /* stockage indisponible : sans gravité */ }
    majBoutonTheme();
  });

  /* ======================= Accueil ======================= */

  function initialiser() {
    // Textes issus de config.js
    document.querySelectorAll("[data-config]").forEach(function (el) {
      var v = CFG[el.getAttribute("data-config")];
      if (v) el.textContent = v;
    });
    if (CFG.nomOutil) document.title = CFG.nomOutil;
    majBoutonTheme();

    reserve = chargerTickets();
    if (reserve === null || reserve.length === 0) {
      $("erreur-chargement").hidden = false;
      $("erreur-chargement").textContent = reserve === null
        ? "Impossible de charger les tickets : le fichier js/tickets.js est absent ou contient une erreur (virgule ou guillemet oublié ?). Ouvrez la console (F12) pour voir la ligne en cause."
        : "Aucun ticket valide dans js/tickets.js. Ouvrez la console (F12) pour voir les problèmes détectés.";
      $("form-nom").hidden = true;
      return;
    }
    $("nb-tickets").textContent = Math.min(NB_PAR_SESSION, reserve.length);
    $("nom").focus();
  }

  $("form-nom").addEventListener("submit", function (e) {
    e.preventDefault();
    var nom = $("nom").value.trim();
    if (!nom) {
      $("aide-nom").textContent = "Indiquez votre nom ou prénom pour commencer.";
      $("nom").focus();
      return;
    }
    $("aide-nom").textContent = "";
    etat.apprenant = nom;
    $("info-apprenant").textContent = "Technicien : " + nom;
    afficherEcran("ecran-consigne");
    $("btn-commencer").focus();
  });

  $("btn-commencer").addEventListener("click", demarrerSession);

  /* ======================= Session ======================= */

  function demarrerSession() {
    var tirage = melanger(reserve).slice(0, Math.min(NB_PAR_SESSION, reserve.length));
    var annee = new Date().getFullYear();
    etat.session = tirage.map(function (t) {
      return {
        ticket: t,
        ordre: melanger(t.reponses.map(function (_, i) { return i; })), // ordre d'affichage des réponses
        choix: null,
        saisie: null,
        numero: "#" + annee + "-" + String(Math.floor(1000 + Math.random() * 9000))
      };
    });
    etat.index = 0;
    etat.debut = new Date();
    etat.enCours = true;
    etat.rapportTelecharge = false;

    $("prog-total").textContent = etat.session.length;
    $("progression").hidden = false;
    afficherEcran("ecran-simulation");
    preparerFormulaireFixe();
    afficherTicket();
  }

  function preparerFormulaireFixe() {
    remplirSelect($("t-type"), TYPES);
    remplirSelect($("t-source"), SOURCES);
    remplirSelect($("t-categorie"), [{ value: "", label: "— Choisir —" }].concat(CATEGORIES));
    remplirSelect($("t-statut"), STATUTS);
    var niveaux = NIVEAUX.map(function (n, i) { return { value: i + 1, label: n }; });
    remplirSelect($("t-urgence"), niveaux);
    remplirSelect($("t-impact"), niveaux);
    remplirSelect($("t-attribue"), [etat.apprenant + " (moi)"].concat(GROUPES));
  }

  function reinitialiserTicket(s) {
    var t = s.ticket;
    $("form-ticket").reset();
    $("t-type").value = "Incident";
    $("t-source").value = "Téléphone";
    $("t-categorie").value = "";
    $("t-statut").value = "Nouveau";
    $("t-urgence").value = 3;
    $("t-impact").value = 3;
    $("t-demandeur").value = t.nom + (t.service ? " (" + t.service + ")" : "");
    $("t-attribue").selectedIndex = 0;
    $("ticket-id").textContent = s.numero;
    $("ticket-date").textContent = new Date().toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
    majPriorite();
  }

  function majPriorite() {
    var p = MATRICE[$("t-urgence").value][$("t-impact").value];
    $("t-priorite").textContent = NIVEAUX[p - 1];
    $("t-priorite").setAttribute("data-niveau", p);
  }
  $("t-urgence").addEventListener("change", majPriorite);
  $("t-impact").addEventListener("change", majPriorite);

  /* ---------- Chat ---------- */

  function ajouterMessage(type, texte, meta, avatar) {
    var msg = document.createElement("div");
    msg.className = "msg " + type;
    if (type !== "systeme") {
      var av = document.createElement("div");
      av.className = "avatar";
      av.textContent = avatar;
      av.setAttribute("aria-hidden", "true");
      msg.appendChild(av);
    }
    var bloc = document.createElement("div");
    if (meta) {
      var m = document.createElement("div");
      m.className = "meta";
      m.textContent = meta;
      bloc.appendChild(m);
    }
    var bulle = document.createElement("div");
    bulle.className = type === "systeme" ? "" : "bulle";
    bulle.textContent = texte;
    bloc.appendChild(bulle);
    msg.appendChild(bloc);
    $("chat").appendChild(msg);
    return msg;
  }

  function indicateurEcriture(avatar) {
    var msg = document.createElement("div");
    msg.className = "msg user";
    msg.setAttribute("aria-hidden", "true");
    msg.innerHTML = '<div class="avatar">' + esc(avatar) + '</div><div class="bulle ecrit"><i></i><i></i><i></i></div>';
    $("chat").appendChild(msg);
    return msg;
  }

  // Affiche un message écrit (courriel, demande du portail) : un en-tête
  // (De, Objet…) puis le texte. entetes = [["De", "Mme X"], ["Objet", "…"]].
  function ajouterFiche(entetes, corps) {
    var html = '<div class="fiche-entete">';
    entetes.forEach(function (e) {
      html += "<div><span>" + esc(e[0]) + " :</span> " + esc(e[1]) + "</div>";
    });
    html += '</div><div class="fiche-corps">' + esc(corps) + "</div>";
    var fiche = document.createElement("div");
    fiche.className = "fiche";
    fiche.innerHTML = html;
    $("chat").appendChild(fiche);
  }

  // Présente la demande de l'utilisateur selon sa source.
  async function afficherDemande(t) {
    var qui = t.nom + (t.service ? " · " + t.service : "");
    if (t.source === "Courriel") {
      await attendre(animationsReduites ? 0 : 300);
      ajouterFiche([["De", qui], ["Objet", t.objet]], t.demande);
      return;
    }
    if (t.source === "Helpdesk") {
      await attendre(animationsReduites ? 0 : 300);
      ajouterFiche([["Demandeur", qui]], t.demande);
      return;
    }
    // Téléphone, Direct, Autre (messagerie instantanée) : l'utilisateur « parle »
    // ou « écrit », puis son message apparaît dans une bulle.
    if (t.source === "Direct") ajouterMessage("systeme", t.nom + " passe à votre bureau.");
    var ecrit = indicateurEcriture(initiales(t.nom));
    await attendre(animationsReduites ? 0 : 900);
    ecrit.remove();
    ajouterMessage("user", t.demande, qui, initiales(t.nom));
  }

  async function afficherTicket() {
    var s = etat.session[etat.index];
    var t = s.ticket;
    var dernier = etat.index === etat.session.length - 1;

    $("prog-num").textContent = etat.index + 1;
    $("jauge").style.width = (etat.index / etat.session.length * 100) + "%";
    $("chat").innerHTML = "";
    $("choix").innerHTML = "";
    $("choix-titre").hidden = true;
    $("btn-enregistrer").textContent = dernier ? "Enregistrer et voir le rapport" : "Enregistrer le ticket";
    reinitialiserTicket(s);
    majBoutonEnregistrer();

    // Le panneau de gauche s'adapte à la source : titre et pastille.
    $("titre-chat").textContent = t.source === "Autre" && t.canal ? t.canal : TITRES_SOURCE[t.source];
    $("pastille-source").textContent = t.source;

    // La demande apparaît, puis les réponses possibles.
    await afficherDemande(t);
    await attendre(animationsReduites ? 0 : 300);
    afficherReponses(s);
  }

  function afficherReponses(s) {
    $("choix-titre").hidden = false;
    var lettres = "ABCDEFGH";
    s.ordre.forEach(function (indexReponse, position) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "reponse";
      b.style.animationDelay = (position * 60) + "ms";
      var l = document.createElement("span");
      l.className = "lettre";
      l.textContent = lettres.charAt(position);
      l.setAttribute("aria-hidden", "true");
      var txt = document.createElement("span");
      txt.textContent = s.ticket.reponses[indexReponse].texte;
      b.appendChild(l);
      b.appendChild(txt);
      b.addEventListener("click", function () { choisirReponse(s, indexReponse, b); });
      $("choix").appendChild(b);
    });
    // Pas de focus automatique sur une réponse : le contour la ferait passer pour présélectionnée.
  }

  function choisirReponse(s, indexReponse, bouton) {
    if (s.choix !== null) return;
    s.choix = indexReponse;
    document.querySelectorAll("#choix .reponse").forEach(function (b) { b.disabled = true; });
    bouton.classList.add("choisie");
    bouton.setAttribute("aria-pressed", "true");
    ajouterMessage("tech", s.ticket.reponses[indexReponse].texte, "Vous", initiales(etat.apprenant));
    ajouterMessage("systeme", "Réponse enregistrée. Complétez le ticket, puis enregistrez-le pour passer à la suite.");
    majBoutonEnregistrer();
    $("t-titre").focus({ preventScroll: true });
  }

  /* ---------- Enregistrement du ticket ---------- */

  function majBoutonEnregistrer() {
    var s = etat.session[etat.index];
    if (!s) return;
    var manque = [];
    if (s.choix === null) manque.push("choisissez une réponse dans l'échange");
    if (!$("t-titre").value.trim()) manque.push("donnez un titre au ticket");
    $("btn-enregistrer").disabled = manque.length > 0;
    $("aide-enregistrer").textContent = manque.length
      ? "Pour enregistrer : " + manque.join(" et ") + "."
      : "";
  }
  $("t-titre").addEventListener("input", majBoutonEnregistrer);

  $("form-ticket").addEventListener("submit", function (e) {
    e.preventDefault();
    majBoutonEnregistrer();
    if ($("btn-enregistrer").disabled) return;

    var s = etat.session[etat.index];
    var urg = Number($("t-urgence").value), imp = Number($("t-impact").value);
    s.saisie = {
      titre: $("t-titre").value.trim(),
      description: $("t-description").value.trim(),
      type: $("t-type").value,
      source: $("t-source").value,
      categorie: $("t-categorie").value || "(non renseignée)",
      statut: $("t-statut").value,
      urgence: NIVEAUX[urg - 1],
      impact: NIVEAUX[imp - 1],
      priorite: NIVEAUX[MATRICE[urg][imp] - 1],
      demandeur: $("t-demandeur").value.trim(),
      attribue: $("t-attribue").value
    };

    etat.index++;
    if (etat.index < etat.session.length) {
      afficherTicket();
      window.scrollTo({ top: 0, behavior: animationsReduites ? "auto" : "smooth" });
    } else {
      terminerSession();
    }
  });

  /* ======================= Rapport ======================= */

  function score() {
    return etat.session.reduce(function (total, s) { return total + s.ticket.reponses[s.choix].note; }, 0);
  }

  function etoiles(note) { return "★".repeat(note) + "☆".repeat(2 - note); }

  // Construit le contenu du rapport (utilisé à l'écran, à l'impression et dans le fichier téléchargé).
  function contenuRapport() {
    var max = etat.session.length * 2;
    var duree = Math.max(1, Math.round((etat.fin - etat.debut) / 60000));
    var html = '<div class="r-entete"><div>' +
      "<h1>Rapport — " + esc(CFG.nomOutil || "Simulation") + "</h1>" +
      "<p><strong>Apprenant :</strong> " + esc(etat.apprenant) + "</p>" +
      "<p><strong>Date :</strong> " + esc(etat.debut.toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" })) +
      " · <strong>Durée :</strong> " + duree + " min</p>" +
      '<p class="r-legende">★★ bonne réponse · ★☆ en partie juste · ☆☆ fausse. Les tickets saisis ne sont pas notés : ils sont à commenter par le formateur.</p>' +
      "</div>" +
      '<div class="r-note">Note<strong>' + score() + " / " + max + "</strong></div></div>";

    etat.session.forEach(function (s, i) {
      var t = s.ticket, rep = t.reponses[s.choix], bonne = t.reponses.filter(function (r) { return r.note === 2; })[0];
      var g = s.saisie, a = t.attendu || {};
      var icone = rep.note === 2 ? "✓" : rep.note === 1 ? "~" : "✗";

      html += '<article class="r-ticket">' +
        '<div class="r-tete"><h3>Demande ' + (i + 1) + " — " + esc(t.nom) + (t.service ? ", " + esc(t.service) : "") +
          " · " + esc(t.source === "Autre" && t.canal ? t.canal : t.source) + "</h3>" +
        '<span class="r-etoiles" aria-label="' + rep.note + ' étoile(s) sur 2">' + etoiles(rep.note) + "</span></div>" +
        '<p class="r-demande">« ' + esc(t.demande) + " »</p>" +
        '<p class="r-rep r-n' + rep.note + '"><strong>' + icone + " Réponse choisie :</strong> " + esc(rep.texte) +
        (rep.grossiere ? ' <span class="r-grossiere-label">— Réponse grossière</span>' : "") + "</p>";
      if (rep.note < 2 && bonne) {
        html += '<p class="r-rep r-n2"><strong>✓ Bonne réponse :</strong> ' + esc(bonne.texte) + "</p>";
      }
      if (t.pointCle) html += '<p class="r-cle"><strong>Point clé :</strong> ' + esc(t.pointCle) + "</p>";

      html += '<div class="r-glpi"><h4>Ticket saisi ' + esc(s.numero) + "</h4>" +
        "<p><strong>" + esc(g.titre) + "</strong></p>" +
        "<p>" + [g.type, g.categorie, "Urgence " + g.urgence.toLowerCase(), "Impact " + g.impact.toLowerCase(),
          "Priorité " + g.priorite.toLowerCase(), g.statut, "Source : " + g.source, "Attribué à : " + g.attribue].map(esc).join(" · ") + "</p>" +
        "<p>" + (g.description ? esc(g.description) : "<em>(pas de description)</em>") + "</p>";
      if (a.type) {
        html += '<p class="r-attendu"><strong>Repère attendu :</strong> ' +
          esc([a.type, a.categorie, "Urgence " + String(a.urgence).toLowerCase(), "Impact " + String(a.impact).toLowerCase()].join(" · ")) + "</p>";
      }
      html += "</div></article>";
    });
    return html;
  }

  function terminerSession() {
    etat.fin = new Date();
    etat.enCours = false;
    $("jauge").style.width = "100%";
    $("rapport-contenu").innerHTML = contenuRapport();
    afficherEcran("ecran-rapport");
    $("btn-telecharger").focus();
  }

  // Styles intégrés au fichier téléchargé : il s'ouvre seul, sans les fichiers du site.
  var CSS_RAPPORT =
    "body{font-family:'Segoe UI',Ubuntu,system-ui,sans-serif;color:#2E2A24;background:#FAF8F3;margin:0;padding:32px 16px;line-height:1.5}" +
    ".page{max-width:860px;margin:0 auto;background:#fff;border-radius:18px;padding:32px;box-shadow:0 10px 40px rgba(120,100,60,.12)}" +
    ".r-entete{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1.5px solid #E6DECF;padding-bottom:16px}" +
    ".r-entete h1{font-size:1.4rem;margin:0 0 6px}.r-entete p{margin:2px 0;color:#6B6358}.r-legende{font-size:.82rem}" +
    ".r-note{text-align:center;padding:10px 18px;border-radius:16px;background:#FFF4CF}.r-note strong{display:block;font-size:1.8rem}" +
    ".r-ticket{padding:18px 0;border-bottom:1px solid #E6DECF;break-inside:avoid}.r-ticket:last-child{border-bottom:none}" +
    ".r-tete{display:flex;justify-content:space-between;gap:10px;align-items:baseline}.r-tete h3{font-size:1.05rem;margin:0}" +
    ".r-etoiles{color:#C9971C;font-size:1.1rem;letter-spacing:2px;white-space:nowrap}" +
    ".r-demande{margin:8px 0 12px;padding:8px 14px;border-left:4px solid #E6DECF;font-style:italic}" +
    ".r-rep{margin:6px 0;padding:10px 12px;border-radius:10px}" +
    ".r-n2{background:#E6F0E6;border-left:4px solid #4F7D52}.r-n1{background:#E6ECF6;border-left:4px solid #4D6FA3}.r-n0{background:#F7E6E1;border-left:4px solid #B4553C}" +
    ".r-grossiere-label{color:#B4553C;font-weight:800}" +
    ".r-glpi{margin-top:12px;padding:12px 14px;border-radius:12px;border:1.5px solid #E6DECF}" +
    ".r-glpi h4{margin:0 0 6px;font-size:.8rem;text-transform:uppercase;letter-spacing:.5px;color:#6B6358}.r-glpi p{margin:4px 0}" +
    ".r-attendu{color:#6B6358;font-size:.9rem}" +
    "@media print{body{background:#fff;padding:0}.page{box-shadow:none;padding:0}}";

  function nomFichier() {
    var d = etat.debut;
    var date = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    return "rapport-" + slug(etat.apprenant) + "-" + date + ".html";
  }

  $("btn-telecharger").addEventListener("click", function () {
    var doc = "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
      "<title>Rapport — " + esc(etat.apprenant) + "</title><style>" + CSS_RAPPORT + "</style></head>" +
      "<body><div class=\"page\">" + contenuRapport() + "</div></body></html>";
    var url = URL.createObjectURL(new Blob([doc], { type: "text/html;charset=utf-8" }));
    var a = document.createElement("a");
    a.href = url;
    a.download = nomFichier();
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    etat.rapportTelecharge = true;
  });

  $("btn-imprimer").addEventListener("click", function () { window.print(); });

  $("btn-recommencer").addEventListener("click", function () {
    if (!etat.rapportTelecharge && !confirm("Le rapport n'a pas été téléchargé. Commencer une nouvelle session quand même ?")) return;
    etat.rapportTelecharge = true;
    demarrerSession();
  });

  /* ======================= Protection contre la fermeture ======================= */

  // Rien n'est sauvegardé : on prévient si l'apprenant quitte en cours de session
  // ou avant d'avoir téléchargé son rapport.
  window.addEventListener("beforeunload", function (e) {
    var rapportNonSauve = !$("ecran-rapport").hidden && !etat.rapportTelecharge;
    if (etat.enCours || rapportNonSauve) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  initialiser();
})();

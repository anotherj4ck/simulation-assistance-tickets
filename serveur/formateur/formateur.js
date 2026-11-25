/*
 * Mode formateur : génère un ticket avec le serveur local (/api/generer-ticket),
 * le fait relire et corriger, puis exporte les tickets validés au format de js/tickets.js.
 *
 * Page servie uniquement par le serveur local (serveur/app.py) : le site publié
 * ne la lie pas et n'en dépend pas. Tout le texte venu du modèle est inséré avec
 * textContent ou value, jamais comme du HTML.
 */
(function () {
  "use strict";

  // Valeurs fixes du site : doivent rester identiques à js/app.js.
  var NIVEAUX = ["Très basse", "Basse", "Moyenne", "Haute", "Très haute"];
  var TYPES = ["Incident", "Demande"];
  var SOURCES = ["Téléphone", "Courriel", "Direct", "Helpdesk", "Autre"];
  var CATEGORIES = window.CONFIG && Array.isArray(window.CONFIG.categories) ? window.CONFIG.categories : [];

  // Notes affichées : la grossière est une note 0 avec grossiere: true.
  var NOTES = [
    { valeur: "2", libelle: "✓ Bonne réponse", classe: "r-n2" },
    { valeur: "1", libelle: "~ En partie vraie", classe: "r-n1" },
    { valeur: "0", libelle: "✗ Fausse", classe: "r-n0" },
    { valeur: "g", libelle: "✗✗ Grossière", classe: "r-n0" }
  ];
  var GROUPES_ATTENDU = [
    { cle: "type", titre: "Type", valeurs: TYPES },
    { cle: "categorie", titre: "Catégorie", valeurs: CATEGORIES },
    { cle: "urgence", titre: "Urgence", valeurs: NIVEAUX },
    { cle: "impact", titre: "Impact", valeurs: NIVEAUX }
  ];
  var CLE_STOCKAGE = "formateur.ticketsValides";

  var $ = function (id) { return document.getElementById(id); };
  var courant = null;   // réponse de l'API pour le ticket affiché (null : aucun)
  var blocs = [];       // { note: <select>, texte: <textarea> } pour chaque réponse
  var valides = [];     // tickets validés, au format de js/tickets.js
  var minuteur = null;

  function element(balise, classe, texte) {
    var el = document.createElement(balise);
    if (classe) el.className = classe;
    if (texte != null) el.textContent = texte;
    return el;
  }
  function enListe(v) { return Array.isArray(v) ? v : [v]; }
  function uneOuPlusieurs(liste) { return liste.length === 1 ? liste[0] : liste; }

  /* ======================= Thème (même comportement que le site) ======================= */

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
    try { localStorage.setItem("theme", nouveau); } catch (e) { /* sans gravité */ }
    majBoutonTheme();
  });

  /* ======================= État d'Ollama ======================= */

  function panne(message) {
    $("panne").hidden = !message;
    $("panne-message").textContent = message || "";
  }

  function verifierSante() {
    var etat = $("etat-modele");
    etat.dataset.etat = "attente";
    etat.textContent = "Vérification d'Ollama…";
    return fetch("api/sante", { cache: "no-store" })
      .then(function (r) {
        return r.json().catch(function () { return null; }).then(function (d) { return { ok: r.ok, d: d }; });
      })
      .then(function (res) {
        var d = res.d;
        if (!d || typeof d.ollama !== "boolean") throw new Error("réponse inattendue");
        if (res.ok) {
          etat.dataset.etat = "ok";
          etat.textContent = "Modèle : " + d.modele;
          panne(null);
        } else {
          etat.dataset.etat = "ko";
          etat.textContent = d.ollama ? "Modèle absent : " + d.modele : "Ollama ne répond pas";
          panne(d.message);
        }
      })
      .catch(function () {
        etat.dataset.etat = "ko";
        etat.textContent = "Serveur local injoignable";
        panne("Cette page fonctionne uniquement avec le serveur local. Depuis la racine du dépôt : " +
          "uvicorn serveur.app:app --host 127.0.0.1 --port 8000, puis ouvrez http://127.0.0.1:8000/formateur.html.");
      });
  }
  $("btn-reverifier").addEventListener("click", verifierSante);

  /* ======================= Génération ======================= */

  function remplirSelect(select, options) {
    options.forEach(function (o) {
      var opt = element("option", null, o.libelle);
      opt.value = o.valeur;
      select.appendChild(opt);
    });
  }

  function erreurGeneration(message) {
    $("erreur-generation").hidden = !message;
    $("erreur-generation").textContent = message || "";
  }

  function messageErreur(res) {
    var d = res.d && res.d.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return "Requête refusée : " + d.map(function (e) { return (e.loc || []).join(".") + " : " + e.msg; }).join(" ; ");
    }
    return "Le serveur a répondu par une erreur " + res.statut + ".";
  }

  function attente(oui) {
    $("attente").hidden = !oui;
    $("btn-generer").disabled = oui;
    $("btn-generer").textContent = oui ? "Génération…" : "Générer";
    ["g-categorie", "g-difficulte", "g-source"].forEach(function (id) { $(id).disabled = oui; });
    clearInterval(minuteur);
    if (oui) {
      var debut = Date.now();
      $("chrono").textContent = "(0 s)";
      minuteur = setInterval(function () {
        $("chrono").textContent = "(" + Math.round((Date.now() - debut) / 1000) + " s)";
      }, 1000);
    }
  }

  $("form-generation").addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (courant && !window.confirm("Le ticket affiché n'a été ni validé ni rejeté. Le remplacer par un nouveau ?")) return;
    var corps = { categorie: $("g-categorie").value, difficulte: $("g-difficulte").value };
    if ($("g-source").value) corps.source = $("g-source").value;

    erreurGeneration(null);
    $("message-statut").textContent = "";
    attente(true);
    fetch("api/generer-ticket", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps)
    })
      .then(function (r) {
        return r.json().catch(function () { return null; }).then(function (d) { return { ok: r.ok, statut: r.status, d: d }; });
      })
      .then(function (res) {
        if (res.ok && res.d && res.d.ticket) {
          afficherTicket(res.d);
        } else {
          erreurGeneration(messageErreur(res));
          if (res.statut === 503) verifierSante();
        }
      })
      .catch(function () {
        erreurGeneration("Le serveur local ne répond pas. Est-il toujours lancé ?");
        verifierSante();
      })
      .then(function () { attente(false); });
  });

  /* ======================= Ticket modifiable ======================= */

  function classeNote(valeur) {
    for (var i = 0; i < NOTES.length; i++) if (NOTES[i].valeur === valeur) return NOTES[i].classe;
    return "r-n0";
  }

  function blocReponse(reponse, n) {
    var bloc = element("div", "f-reponse r-rep");
    var tete = element("div", "f-reponse-tete");
    var note = document.createElement("select");
    note.setAttribute("aria-label", "Note de la réponse " + n);
    remplirSelect(note, NOTES);
    note.value = reponse.note === 0 && reponse.grossiere ? "g" : String(reponse.note);
    var compte = element("span", "f-compte");
    var texte = document.createElement("textarea");
    texte.rows = 3;
    texte.value = reponse.texte;
    texte.setAttribute("aria-label", "Texte de la réponse " + n);

    function maj() {
      bloc.className = "f-reponse r-rep " + classeNote(note.value);
      compte.textContent = texte.value.trim().length + " caractères";
      verifierLongueurs();
    }
    note.addEventListener("change", maj);
    texte.addEventListener("input", maj);

    tete.appendChild(note);
    tete.appendChild(compte);
    bloc.appendChild(tete);
    bloc.appendChild(texte);
    blocs.push({ note: note, texte: texte, maj: maj });
    return bloc;
  }

  // Même règle que le serveur : la bonne réponse ne doit pas être strictement la plus longue.
  function verifierLongueurs() {
    var bonnes = blocs.filter(function (b) { return b.note.value === "2"; });
    var trop = false;
    if (bonnes.length === 1) {
      var lg = bonnes[0].texte.value.trim().length;
      var autres = blocs.filter(function (b) { return b !== bonnes[0]; })
        .map(function (b) { return b.texte.value.trim().length; });
      trop = autres.length > 0 && lg > Math.max.apply(null, autres);
    }
    $("avert-longueur").hidden = !trop;
  }

  function groupeAttendu(groupe, valeursTicket) {
    var fieldset = element("fieldset");
    fieldset.appendChild(element("legend", null, groupe.titre));
    var puces = element("div", "f-puces");
    var possibles = groupe.valeurs.slice();
    valeursTicket.forEach(function (v) { if (possibles.indexOf(v) === -1) possibles.push(v); });
    possibles.forEach(function (v) {
      var label = element("label", "f-puce");
      var case_ = document.createElement("input");
      case_.type = "checkbox";
      case_.name = "a-" + groupe.cle;
      case_.value = v;
      case_.checked = valeursTicket.indexOf(v) !== -1;
      label.appendChild(case_);
      label.appendChild(element("span", null, v));
      puces.appendChild(label);
    });
    fieldset.appendChild(puces);
    return fieldset;
  }

  function afficherInfos(reponse) {
    var c = reponse.consigne || {};
    var p = c.profil || {};
    var infos = $("e-infos");
    infos.textContent = "";
    function ajouter(etiquette, valeur) {
      if (!valeur) return;
      if (infos.childNodes.length) infos.appendChild(document.createTextNode(" · "));
      infos.appendChild(element("b", null, etiquette + " : "));
      infos.appendChild(document.createTextNode(valeur));
    }
    ajouter("Profil imposé", [p.ton, p.aisance].filter(Boolean).join(" ; "));
    ajouter("Difficulté", c.difficulte);
    ajouter("Tentatives", String(reponse.tentatives || 1));
    ajouter("Exemples", (c.exemples || []).join(", "));
    ajouter("Modèle", reponse.modele);
  }

  function afficherAlertes(alertes) {
    var liste = $("liste-alertes");
    liste.textContent = "";
    (alertes || []).forEach(function (a) { liste.appendChild(element("li", null, a)); });
    $("alertes").hidden = !(alertes && alertes.length);
  }

  function afficherTicket(reponse) {
    var t = reponse.ticket;
    courant = reponse;
    $("e-id").textContent = t.id;
    $("e-theme").value = t.theme || "";
    $("e-source").value = t.source;
    $("e-nom").value = t.nom || "";
    $("e-service").value = t.service || "";
    $("e-objet").value = t.objet || "";
    $("e-canal").value = t.canal || "";
    $("champ-objet").hidden = t.source !== "Courriel";
    $("champ-canal").hidden = t.source !== "Autre";
    $("e-demande").value = t.demande || "";
    $("e-pointcle").value = t.pointCle || "";
    afficherInfos(reponse);
    afficherAlertes(reponse.alertes);

    blocs = [];
    var zone = $("e-reponses");
    zone.textContent = "";
    t.reponses.forEach(function (r, i) { zone.appendChild(blocReponse(r, i + 1)); });
    blocs.forEach(function (b) { b.maj(); });

    var attendu = $("e-attendu");
    attendu.textContent = "";
    GROUPES_ATTENDU.forEach(function (g) {
      attendu.appendChild(groupeAttendu(g, enListe(t.attendu[g.cle])));
    });

    erreursTicket(null);
    $("zone-ticket").hidden = false;
    $("zone-ticket").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function erreursTicket(erreurs) {
    var zone = $("erreurs-ticket");
    zone.textContent = "";
    zone.hidden = !(erreurs && erreurs.length);
    if (zone.hidden) return;
    zone.appendChild(element("span", null, "Impossible de valider :"));
    var ul = element("ul");
    erreurs.forEach(function (e) { ul.appendChild(element("li", null, e)); });
    zone.appendChild(ul);
  }

  // Ticket tel que modifié par le formateur, au format de js/tickets.js.
  function lireTicket() {
    var t = courant.ticket;
    var erreurs = [];
    function texte(id) { return $(id).value.trim(); }

    var res = { id: t.id, theme: texte("e-theme"), nom: texte("e-nom"), service: texte("e-service"), source: t.source };
    if (t.source === "Courriel") res.objet = texte("e-objet");
    if (t.source === "Autre" && texte("e-canal")) res.canal = texte("e-canal");
    res.demande = texte("e-demande");
    res.reponses = blocs.map(function (b) {
      var r = { note: b.note.value === "g" ? 0 : Number(b.note.value) };
      if (b.note.value === "g") r.grossiere = true;
      r.texte = b.texte.value.trim();
      return r;
    });
    res.pointCle = texte("e-pointcle");
    res.attendu = {};
    GROUPES_ATTENDU.forEach(function (g) {
      var coches = Array.prototype.map.call(
        document.querySelectorAll('input[name="a-' + g.cle + '"]:checked'),
        function (c) { return c.value; }
      );
      if (!coches.length) erreurs.push(g.titre + " attendu(e) : cochez au moins une valeur.");
      res.attendu[g.cle] = uneOuPlusieurs(coches);
    });

    if (!res.theme) erreurs.push("Le thème est vide.");
    if (!res.nom) erreurs.push("Le nom est vide.");
    if (t.source === "Courriel" && !res.objet) erreurs.push("L'objet est obligatoire pour un courriel.");
    if (!res.demande) erreurs.push("La demande est vide.");
    res.reponses.forEach(function (r, i) { if (!r.texte) erreurs.push("La réponse " + (i + 1) + " est vide."); });
    var nbBonnes = res.reponses.filter(function (r) { return r.note === 2; }).length;
    if (nbBonnes !== 1) erreurs.push("Il faut exactement une bonne réponse (✓) ; il y en a " + nbBonnes + ".");
    if (!res.pointCle) erreurs.push("Le point clé est vide.");
    return { ticket: res, erreurs: erreurs };
  }

  function fermerTicket() {
    courant = null;
    blocs = [];
    $("zone-ticket").hidden = true;
  }

  $("form-ticket").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var lu = lireTicket();
    if (lu.erreurs.length) { erreursTicket(lu.erreurs); return; }
    valides.push(lu.ticket);
    enregistrerValides();
    afficherValides();
    fermerTicket();
    $("message-statut").textContent = "✓ Ticket « " + lu.ticket.theme + " » validé et ajouté à la liste.";
  });

  $("btn-rejeter").addEventListener("click", function () {
    var theme = $("e-theme").value.trim();
    fermerTicket();
    $("message-statut").textContent = "Ticket « " + theme + " » rejeté.";
  });

  // Prévient avant de fermer la page si un ticket affiché n'a pas été traité.
  window.addEventListener("beforeunload", function (ev) {
    if (courant) { ev.preventDefault(); ev.returnValue = ""; }
  });

  /* ======================= Tickets validés ======================= */

  function chargerValides() {
    try {
      var brut = localStorage.getItem(CLE_STOCKAGE);
      var liste = brut ? JSON.parse(brut) : [];
      return Array.isArray(liste) ? liste : [];
    } catch (e) {
      $("note-stockage").hidden = false;
      return [];
    }
  }

  function enregistrerValides() {
    try {
      localStorage.setItem(CLE_STOCKAGE, JSON.stringify(valides));
      $("note-stockage").hidden = true;
    } catch (e) {
      $("note-stockage").hidden = false;
    }
  }

  function afficherValides() {
    var liste = $("liste-valides");
    liste.textContent = "";
    $("nb-valides").textContent = valides.length;
    $("liste-vide").hidden = valides.length > 0;
    $("btn-exporter").disabled = $("btn-vider").disabled = valides.length === 0;

    valides.forEach(function (t, i) {
      var li = element("li");
      var corps = element("div");
      corps.appendChild(element("div", "titre", (t.theme || "Sans thème") + " — " + t.nom + (t.service ? ", " + t.service : "")));
      var a = t.attendu || {};
      corps.appendChild(element("div", "detail",
        [t.source, enListe(a.categorie || []).join(" / "), "urgence " + enListe(a.urgence || []).join(" / "),
          "impact " + enListe(a.impact || []).join(" / "), t.id].join(" · ")));
      corps.appendChild(element("div", "demande", "« " + t.demande + " »"));
      var retirer = element("button", "btn secondaire petit", "Retirer");
      retirer.type = "button";
      retirer.setAttribute("aria-label", "Retirer le ticket « " + (t.theme || t.id) + " »");
      retirer.addEventListener("click", function () {
        valides.splice(i, 1);
        enregistrerValides();
        afficherValides();
      });
      li.appendChild(corps);
      li.appendChild(retirer);
      liste.appendChild(li);
    });
  }

  $("btn-exporter").addEventListener("click", function () {
    var blob = new Blob([JSON.stringify(valides, null, 2) + "\n"], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var lien = document.createElement("a");
    lien.href = url;
    lien.download = "tickets-valides-" + new Date().toISOString().slice(0, 10) + ".json";
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });

  $("btn-vider").addEventListener("click", function () {
    if (!window.confirm("Vider la liste des " + valides.length + " tickets validés ? Pensez à exporter avant.")) return;
    valides = [];
    enregistrerValides();
    afficherValides();
  });

  /* ======================= Démarrage ======================= */

  majBoutonTheme();
  remplirSelect($("g-categorie"), CATEGORIES.map(function (c) { return { valeur: c, libelle: c }; }));
  remplirSelect($("g-source"), [{ valeur: "", libelle: "Au hasard" }].concat(
    SOURCES.map(function (s) { return { valeur: s, libelle: s }; })));
  if (!CATEGORIES.length) {
    erreurGeneration("Liste des catégories introuvable : js/config.js n'a pas été chargé.");
    $("btn-generer").disabled = true;
  }
  valides = chargerValides();
  afficherValides();
  verifierSante();
})();

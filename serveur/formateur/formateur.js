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
  // Une série publiée compte autant de tickets qu'une session du site (js/config.js).
  var NB_SERIE = (window.CONFIG && window.CONFIG.ticketsParSession) || 5;
  // Plafond du mode « tirage » : même valeur que MAX_TICKETS_TIRAGE dans serveur/serie.py.
  var MAX_TIRAGE = 200;
  var LIBELLES_MODE = { fixe: "Série fixe", tirage: "Tirage dans la sélection" };

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
    var m = reponse.metriques || {};
    ajouter("Modèle", texteModele(m.modele) || reponse.modele);
    ajouter("Mémoire", texteRepartition(m.repartition));
    ajouter("Durée", texteDuree(m));
    ajouter("Génération", texteTokens(m));
  }

  /* ---------- Métriques de génération (jamais copiées dans le ticket) ---------- */

  function estNombre(v) { return typeof v === "number" && isFinite(v); }

  // Format français : virgule décimale, espace pour les milliers.
  function nombreFr(valeur, decimales) {
    return valeur.toLocaleString("fr-FR", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
  }

  // « qwen3:8b (8,2B · Q4_K_M) » ; le nom seul si la fiche du modèle manque.
  function texteModele(modele) {
    if (!modele || !modele.nom) return "";
    var details = [modele.taille && modele.taille.replace(/(\d)\.(\d)/g, "$1,$2"), modele.quantification].filter(Boolean);
    return modele.nom + (details.length ? " (" + details.join(" · ") + ")" : "");
  }

  // Comme la colonne PROCESSOR de « ollama ps » : « 100 % GPU » ou « 16 % CPU / 84 % GPU ».
  function texteRepartition(repartition) {
    if (!repartition || !estNombre(repartition.part_gpu)) return "";
    var gpu = Math.round(repartition.part_gpu * 100);
    if (gpu >= 100) return "100 % GPU";
    if (gpu <= 0) return "100 % CPU";
    return (100 - gpu) + " % CPU / " + gpu + " % GPU";
  }

  // Durée mesurée par le serveur (relances comprises), dont le chargement du modèle.
  function texteDuree(m) {
    var ollama = m.ollama || {};
    var total = estNombre(m.duree_serveur_s) ? m.duree_serveur_s
      : estNombre(ollama.total_duration) ? ollama.total_duration / 1e9 : null;
    if (total === null) return "";
    var texte = nombreFr(total, 1) + " s";
    if (estNombre(ollama.load_duration)) texte += " (dont chargement " + nombreFr(ollama.load_duration / 1e9, 1) + " s)";
    return texte;
  }

  function texteTokens(m) {
    var produits = (m.ollama || {}).eval_count;
    if (!estNombre(produits)) return "";
    return nombreFr(produits, 0) + " tokens générés" +
      (estNombre(m.tokens_par_seconde) ? " · " + nombreFr(m.tokens_par_seconde, 1) + " tokens/s" : "");
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
    majPublier();

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

  function slug(texte) {
    return String(texte).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }

  // Date locale du jour (et non UTC : un export à 23 h 30 garde la date du jour).
  function dateDuJour() {
    var d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }

  // Nom proposé : la catégorie principale de chaque ticket (3 au plus, sinon
  // « plusieurs-categories »), puis la date. Ex. : « securite-2026-11-26 ».
  function nomExportPropose(tickets) {
    var categories = [];
    tickets.forEach(function (t) {
      var principale = slug(enListe((t.attendu || {}).categorie || [])[0] || "");
      if (principale && categories.indexOf(principale) === -1) categories.push(principale);
    });
    var debut = !categories.length ? "tickets" : categories.length <= 3 ? categories.join("-") : "plusieurs-categories";
    return debut + "-" + dateDuJour();
  }

  // Nom saisi : caractères interdits dans un nom de fichier remplacés, une seule
  // extension .json. Vide : chaîne vide (le nom proposé est alors utilisé).
  function nomFichierPropre(saisie) {
    var nom = String(saisie).trim()
      .replace(/[\\/:*?"<>|\u0000-\u001f]+/g, "-")
      .replace(/\.json$/i, "")
      .replace(/^[.\s-]+|[.\s]+$/g, "");
    return nom ? nom + ".json" : "";
  }

  $("btn-exporter").addEventListener("click", function () {
    var propose = nomExportPropose(valides);
    var saisie = window.prompt("Nom du fichier à enregistrer (l'extension .json est ajoutée) :", propose);
    if (saisie === null) return; // export annulé
    var blob = new Blob([JSON.stringify(valides, null, 2) + "\n"], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var lien = document.createElement("a");
    lien.href = url;
    lien.download = nomFichierPropre(saisie) || propose + ".json";
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  });

  /* ---------- Import d'un fichier exporté ---------- */

  function pluriel(n, mot) { return n + " " + mot + (n > 1 ? "s" : ""); }

  function compteRenduImport(etat, lignes) {
    var zone = $("resultat-import");
    zone.textContent = "";
    zone.dataset.etat = etat;
    lignes.forEach(function (l) { zone.appendChild(l); });
    zone.hidden = false;
  }

  // Ajoute les tickets valides renvoyés par le serveur, sans doublon d'identifiant
  // (ni avec la liste existante, ni à l'intérieur du fichier).
  function ajouterImportes(nomFichier, resultat) {
    var connus = {};
    valides.forEach(function (t) { connus[t.id] = true; });
    var importes = [], doublons = [];
    resultat.valides.forEach(function (t) {
      if (connus[t.id]) { doublons.push(t.id); return; }
      connus[t.id] = true;
      importes.push(t);
    });
    if (importes.length) {
      valides = valides.concat(importes);
      enregistrerValides();
      afficherValides();
    }

    var refuses = resultat.refuses || [];
    var lignes = [element("p", null, "Import de « " + nomFichier + " » : " +
      pluriel(importes.length, "ticket") + " importé" + (importes.length > 1 ? "s" : "") + ", " +
      doublons.length + " ignoré" + (doublons.length > 1 ? "s" : "") + " (doublons), " +
      refuses.length + " refusé" + (refuses.length > 1 ? "s" : "") + ".")];
    if (doublons.length) {
      lignes.push(element("p", null, "Doublons non ajoutés (identifiant déjà dans la liste ou répété dans le fichier) : " +
        doublons.join(", ") + "."));
    }
    if (refuses.length) {
      var ul = element("ul", "refus");
      refuses.forEach(function (r) {
        ul.appendChild(element("li", null, "Ticket n° " + r.position + " (" + r.id + ") : " + r.motifs.join(" ; ")));
      });
      lignes.push(element("p", "refus", "Refusés par le validateur :"));
      lignes.push(ul);
    }
    compteRenduImport(refuses.length && !importes.length ? "erreur" : "ok", lignes);
  }

  $("btn-importer").addEventListener("click", function () { $("fichier-import").click(); });

  $("fichier-import").addEventListener("change", function () {
    var fichier = this.files && this.files[0];
    this.value = ""; // permet de réimporter le même fichier
    if (!fichier) return;
    var bouton = $("btn-importer");
    bouton.disabled = true;
    fichier.text()
      .then(function (contenu) {
        // Le contenu brut est envoyé tel quel : le serveur le lit et le valide.
        return fetch("api/valider-tickets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: contenu
        });
      })
      .then(lireReponse)
      .then(function (res) {
        if (res.ok && res.d && Array.isArray(res.d.valides)) {
          ajouterImportes(fichier.name, res.d);
        } else {
          compteRenduImport("erreur", [element("p", null, "Import de « " + fichier.name + " » impossible : " + messageErreur(res))]);
        }
      })
      .catch(function () {
        compteRenduImport("erreur", [element("p", null, "Import impossible : le serveur local ne répond pas.")]);
      })
      .then(function () { bouton.disabled = false; });
  });

  $("btn-vider").addEventListener("click", function () {
    if (!window.confirm("Vider la liste des " + valides.length + " tickets validés ? Pensez à exporter avant.")) return;
    valides = [];
    enregistrerValides();
    afficherValides();
  });

  /* ======================= Série publiée pour les apprenants ======================= */

  var serieActive = null;

  function dateLisible(iso) {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" });
  }

  function erreurSerie(message) {
    $("erreur-serie").hidden = !message;
    $("erreur-serie").textContent = message || "";
  }

  function afficherSerie(serie) {
    serieActive = serie;
    var liste = $("serie-tickets");
    liste.textContent = "";
    $("btn-retirer-serie").hidden = !serie;
    if (!serie) {
      $("serie-etat").textContent = "Aucune série publiée : les apprenants ont le tirage au hasard habituel.";
      return;
    }
    var mode = serie.mode || "fixe";
    $("serie-etat").textContent = LIBELLES_MODE[mode] + ", " + serie.tickets.length + " tickets, publiée le " +
      dateLisible(serie.publiee_le) + ". " + (mode === "tirage"
        ? "À chaque session, l'apprenant en reçoit " + NB_SERIE + ", tirés au hasard, dans un ordre aléatoire."
        : "Tous les apprenants reçoivent ces " + serie.tickets.length + " tickets, dans cet ordre.");
    serie.tickets.forEach(function (t, i) {
      var li = element("li");
      var corps = element("div");
      // Numéros seulement pour une série fixe : en tirage, l'ordre de la liste ne compte pas.
      corps.appendChild(element("div", "titre", (mode === "fixe" ? (i + 1) + ". " : "") + (t.theme || t.id)));
      corps.appendChild(element("div", "detail",
        [t.nom + (t.service ? ", " + t.service : ""), t.source, enListe(t.attendu.categorie).join(" / "), t.id].join(" · ")));
      li.appendChild(corps);
      liste.appendChild(li);
    });
  }

  function lireReponse(r) {
    return r.json().catch(function () { return null; }).then(function (d) { return { ok: r.ok, statut: r.status, d: d }; });
  }

  function chargerSerieActive() {
    return fetch("api/serie", { cache: "no-store" })
      .then(lireReponse)
      .then(function (res) {
        if (res.statut === 200 && res.d && Array.isArray(res.d.tickets)) {
          erreurSerie(null);
          afficherSerie(res.d);
        } else if (res.statut === 404) {
          erreurSerie(null);
          afficherSerie(null);
        } else {
          afficherSerie(null);
          erreurSerie(messageErreur(res));
        }
      })
      .catch(function () {
        $("serie-etat").textContent = "État inconnu : le serveur local ne répond pas.";
      });
  }

  function modeChoisi() {
    return document.querySelector('input[name="mode-serie"]:checked').value;
  }

  // « Publier » s'active selon le mode : exactement NB_SERIE tickets pour une
  // série fixe ; de NB_SERIE à MAX_TIRAGE pour un tirage dans la sélection.
  function publicationPossible() {
    var n = valides.length;
    return modeChoisi() === "fixe" ? n === NB_SERIE : n >= NB_SERIE && n <= MAX_TIRAGE;
  }

  function majPublier() {
    var n = valides.length;
    $("btn-publier").disabled = !publicationPossible();
    $("aide-publier").textContent = publicationPossible() ? ""
      : modeChoisi() === "fixe"
        ? "Une série fixe demande exactement " + NB_SERIE + " tickets validés (actuellement " + n + ")."
        : "Un tirage dans la sélection demande de " + NB_SERIE + " à " + MAX_TIRAGE + " tickets validés (actuellement " + n + ").";
  }

  Array.prototype.forEach.call(document.querySelectorAll('input[name="mode-serie"]'), function (radio) {
    radio.addEventListener("change", majPublier);
  });

  $("btn-publier").addEventListener("click", function () {
    var mode = modeChoisi();
    var question = "Publier ces " + valides.length + " tickets pour les apprenants, en mode « " + LIBELLES_MODE[mode] + " » ?\n\n" +
      (mode === "tirage"
        ? "À chaque session, chaque apprenant en recevra " + NB_SERIE + ", tirés au hasard.\n"
        : "Tous les apprenants recevront ces " + NB_SERIE + " tickets, dans l'ordre de la liste.\n") +
      (serieActive
        ? "Elle remplacera la série en cours, publiée le " + dateLisible(serieActive.publiee_le) + "."
        : "Elle remplacera la série en cours s'il y en a une (aucune pour l'instant).");
    if (!window.confirm(question)) return;
    var bouton = $("btn-publier");
    bouton.disabled = true;
    erreurSerie(null);
    fetch("api/serie", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: mode, tickets: valides })
    })
      .then(lireReponse)
      .then(function (res) {
        if (res.ok && res.d) {
          afficherSerie(res.d);
          $("message-statut").textContent = "✓ Série publiée : les apprenants la recevront au début de leur prochaine session.";
        } else {
          erreurSerie(messageErreur(res));
        }
      })
      .catch(function () { erreurSerie("Le serveur local ne répond pas : la série n'a pas été publiée."); })
      .then(majPublier);
  });

  $("btn-retirer-serie").addEventListener("click", function () {
    if (!window.confirm("Retirer la série active ? Les apprenants reviendront au tirage au hasard habituel.")) return;
    fetch("api/serie", { method: "DELETE" })
      .then(function (r) {
        if (r.status === 204 || r.status === 404) { erreurSerie(null); afficherSerie(null); return; }
        return lireReponse(r).then(function (res) { erreurSerie(messageErreur(res)); });
      })
      .catch(function () { erreurSerie("Le serveur local ne répond pas : la série n'a pas été retirée."); });
  });

  /* ======================= Démarrage ======================= */

  majBoutonTheme();
  // Explications des modes : nombres issus de js/config.js et du plafond du tirage.
  Array.prototype.forEach.call(document.querySelectorAll(".nb-session"), function (el) { el.textContent = NB_SERIE; });
  Array.prototype.forEach.call(document.querySelectorAll(".max-tirage"), function (el) { el.textContent = MAX_TIRAGE; });
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
  chargerSerieActive();
})();

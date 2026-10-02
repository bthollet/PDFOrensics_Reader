/* Fragment 40 - le lecteur: la phrase, la sous-barre, la fiche, l'ouverture d'une piece. */
/* Tant que les pages se lisent encore, un compte n'est que celui des pages deja lues: la phrase le dit. */
function avancement() { return enCours(P) ? " Lecture en cours : " + P.lues + " pages lues sur " + P.pages.length + "." : ""; }
function phrase() {
  var v = P.versions[E.version - 1];
  switch (E.regard) {
    case "fiche":
      return "Ce que contient le fichier, relevé à la lecture." + avancement();
    case "caches":
      return s(R.caches.length, "zone recouverte", "zones recouvertes") + ". Faites disparaître ce qui est posé sur la page pour voir dessous." + avancement();
    case "calques":
      return s(R.eteints.length, "calque éteint", "calques éteints") + " à l'ouverture : " + R.eteints.map(function (c) { return c.nom; }).join(", ") + ".";
    case "versions":
      return "Fichier enregistré " + R.versions + " fois. Version " + v.n + (v.date ? " du " + v.date : "") + (v.n > 1 ? ", comparée à la version " + (v.n - 1) + " : " + (v.resume || "aucune différence relevée") + "." : ", la première.");
    case "composition":
      return [s(R.textes.length, "ligne de texte", "lignes de texte"), s(R.invisibles.length, "ligne de texte invisible", "lignes de texte invisible"), s(R.images.length, "image"), s(R.traces.length, "tracé"), s(R.annotations.length, "annotation")].join(", ") + "." + avancement();
    case "ordre":
      return (P.balise ? "Ce fichier décrit son ordre de lecture, que cet écran ne dessine pas encore." : "Ce fichier ne décrit pas son ordre de lecture.") + " Les numéros suivent l'ordre où il écrit ses blocs de texte." + avancement();
    default:
      return "La page telle qu'un lecteur PDF l'affiche.";
  }
}
function legende(lignes) {
  var liste = el("ul", "legende");
  lignes.forEach(function (l) {
    var li = el("li");
    li.append(el("span", "pastille g-" + l[0]), document.createTextNode(l[1]));
    liste.appendChild(li);
  });
  return liste;
}
function sousBarre() {
  var barre = $("sous-barre");
  barre.textContent = "";
  if (E.regard === "versions" && R.versions > 1) {
    var frise = el("ol", "frise");
    P.versions.forEach(function (v) {
      var li = el("li"), b = el("button");
      b.type = "button";
      b.setAttribute("aria-pressed", String(v.n === E.version));
      b.append(el("b", "", "Version " + v.n), document.createTextNode((v.date || "date non inscrite") + " · " + v.taille));
      b.addEventListener("click", function () { E.version = v.n; E.choix = null; rendre(); });
      li.appendChild(b);
      frise.appendChild(li);
    });
    barre.appendChild(frise);
    if (E.version > 1) {
      var reglage = el("label", "rideau-reglage", "Rideau avant / après ");
      var curseur = el("input");
      curseur.type = "range"; curseur.id = "curseur-rideau"; curseur.min = 0; curseur.max = 100; curseur.value = Math.round(E.rideau);
      curseur.addEventListener("input", function () { regler(Number(curseur.value)); });
      reglage.appendChild(curseur);
      barre.appendChild(reglage);
    }
  } else if (E.regard === "caches") {
    /* Voir dessous: on coche ce qu'on veut faire disparaitre, le curseur l'efface peu a peu. Le texte de la page reste. */
    [["a", "Annotations"], ["i", "Images"], ["t", "Aplats et tracés"]].forEach(function (f) {
      var bouton = el("button", "bascule", f[1]);
      bouton.type = "button";
      bouton.dataset.famille = f[0];
      bouton.setAttribute("role", "switch");
      bouton.setAttribute("aria-checked", String(E.pele[f[0]]));
      bouton.addEventListener("click", function () { E.pele[f[0]] = !E.pele[f[0]]; E.peleChoisi = true; rendre(); });
      barre.appendChild(bouton);
    });
    var effacer = el("label", "rideau-reglage", "Faire disparaître ");
    var dose = el("input");
    dose.type = "range"; dose.id = "curseur-voile"; dose.min = 0; dose.max = 100; dose.value = E.voile;
    dose.addEventListener("input", function () { voiler(Number(dose.value)); });
    effacer.appendChild(dose);
    barre.appendChild(effacer);
  } else if (E.regard === "calques" && R.eteints.length) {
    var b = el("button", "bascule", "Afficher le contenu des calques éteints");
    b.type = "button";
    b.setAttribute("role", "switch");
    b.setAttribute("aria-checked", String(E.calques));
    b.addEventListener("click", function () { E.calques = !E.calques; E.choix = null; rendre(); });
    barre.appendChild(b);
  } else if (E.regard === "composition") {
    barre.appendChild(legende([["texte", "texte"], ["invisible", "texte invisible"], ["image", "image"], ["trace", "tracé"], ["annot", "annotation"]]));
  }
  barre.hidden = !barre.childNodes.length;
}

function fiche() {
  var racine = $("fiche");
  racine.textContent = "";
  var dl = el("dl");
  P.fiche.forEach(function (ligne) { dl.append(el("dt", "", ligne[0]), el("dd", "", ligne[1])); });
  racine.appendChild(dl);
  rubriques(P).forEach(function (rub) {
    var h = el("h2", "", rub.titre), ul = el("ul");
    h.appendChild(el("span", "compte" + (rub.compte ? "" : " zero"), rub.compte));
    rub.lignes.forEach(function (l) {
      var li = el("li", "", l.texte);
      if (l.cible) {
        var voir = el("button", "lien", "Voir sur la page");
        voir.type = "button";
        voir.addEventListener("click", function () { aller(l.cible, l.regard); });
        li.appendChild(voir);
      }
      ul.appendChild(li);
    });
    racine.append(h, ul);
  });
}
function aller(cible, regard) {
  if (cible.indexOf("version-") === 0) { E.version = Number(cible.slice(8)); cible = null; }
  E.regard = regard;
  E.calques = true;
  E.choix = null;
  rendre();
  var trouve = null;
  P.pages.forEach(function (p, i) {
    traces(p, i).forEach(function (t) { if (!trouve && (!cible || t.id === cible)) { trouve = { t: t, i: i }; } });
  });
  if (!trouve) { return; }
  var cadre = pages.children[trouve.i].firstChild.getBoundingClientRect();
  doc.scrollTop = Math.max(0, cadre.top - doc.getBoundingClientRect().top + doc.scrollTop + hautAffiche(trouve.t.bbox) * cadre.height - doc.clientHeight / 3);
  if (cible) { choisir(trouve.t); }
}

function carte(titre, texte, refus) {
  $("carte").hidden = false;
  $("carte").className = "carte" + (refus ? " refus" : "");
  $("carte-titre").textContent = titre;
  $("carte-texte").textContent = texte;
  pages.hidden = true;
  $("fiche").hidden = true;
  $("phrase").hidden = $("sous-barre").hidden = $("pied").hidden = $("outils").hidden = true;
  $("regards").hidden = true;
  $("marques").textContent = "";
}
/* Les comptes des regards, et ceux qui n'ont pas d'objet: redit a chaque tranche de pages lue. */
function compter() {
  if (!E.peleChoisi) {
    /* Ce qu'on fait disparaitre par defaut: ce qui recouvre dans CETTE piece; a defaut, les annotations seules.
       Retirer les traces d'une page dont les lettres sont dessinees en contours l'effacerait tout entiere. */
    E.pele = { a: !R.caches.length || R.caches.some(function (c) { return c.nature === "annotation"; }),
      i: R.caches.some(function (c) { return c.nature === "image"; }),
      t: R.caches.some(function (c) { return c.nature !== "annotation" && c.nature !== "image"; }) };
  }
  Array.prototype.forEach.call($("regards").children, function (b, i) {
    var compte = b.querySelector(".compte"), n = REGARDS[i].compte && REGARDS[i].compte(R);
    if (compte) { compte.textContent = n; compte.className = "compte" + (n ? "" : " zero"); }
    /* Un regard sans objet pour ce fichier ne se choisit pas, et dit pourquoi au survol. */
    var pourquoi = REGARDS[i].vide ? REGARDS[i].vide(P, R) : "";
    if (pourquoi && REGARDS[i].pages && enCours(P)) { pourquoi = "lecture en cours, " + P.lues + " pages lues sur " + P.pages.length; }
    b.setAttribute("aria-disabled", String(!!pourquoi));
    b.dataset.pourquoi = pourquoi;
    expliquer(b, REGARDS[i].nom, pourquoi || REGARDS[i].dit);
    if (pourquoi && E.regard === REGARDS[i].cle) { E.regard = "page"; }
  });
  $("sous-titre").textContent = s(P.pages.length, "page") + " · " + (R.versions > 1 ? "enregistré " + R.versions + " fois" : "enregistré une fois") + " · " + champ(P, "Taille")
    + (enCours(P) ? " · lecture des pages : " + P.lues + " sur " + P.pages.length : "");
}
/* Le contenu des pages arrive par tranches: l'ecran se met a jour sans attendre la fin. */
function suivre(piece) {
  if (P !== piece || !enCours(piece)) { return Promise.resolve(); }
  return api.pages(piece.chemin, piece.lues).then(function (t) {
    if (P !== piece) { return; }
    if (!t.ok) {
      piece.lues = piece.pages.length;
      R = releve(P);
      compter();
      $("phrase").textContent = "La lecture des pages s'est arrêtée : " + t.raison;
      return;
    }
    integrer(piece, t);
    R = releve(P);
    compter();
    $("phrase").textContent = phrase();
    if (E.regard !== "fiche") { t.pages.forEach(function (pg) { if (visibles[pg.n - 1]) { montrer(pg.n - 1); } }); }
    if (!enCours(piece)) {
      E.lus[piece.chemin] = faits(piece);
      dessiner("src");
      rendre();
    } else if (!E.marquesTard) {
      E.marquesTard = setTimeout(function () { E.marquesTard = 0; if (P === piece) { marquer(); if (!E.choix) { detail(); } } }, 900);
    }
    return suivre(piece);
  });
}
function ouvrirPiece(chemin, nom) {
  E.jeton += 1;
  var jeton = E.jeton;
  P = null;
  $("titre").textContent = nom;
  $("sous-titre").textContent = "Lecture en cours.";
  carte("Lecture en cours", "Le fichier est lu sur ce poste.", false);
  marquerOuverte(chemin);
  return api.lire(chemin).then(function (r) {
    if (jeton !== E.jeton) { return; }
    if (!r.ok) {
      $("sous-titre").textContent = "Ce fichier n'est pas lu.";
      carte("Ce fichier ne se lit pas", r.raison, true);
      return;
    }
    P = preparer(r.piece);
    R = releve(P);
    DITS = {};
    E.version = R.versions;
    E.choix = null;
    E.pivot = 0;
    E.peleChoisi = false;
    E.voile = 0;
    $("carte").hidden = true;
    $("regards").hidden = false;
    $("phrase").hidden = false;
    construire();
    $("sur-combien").textContent = "sur " + P.pages.length;
    $("saisie-page").max = P.pages.length;
    $("saisie-page").value = 1;
    compter();
    doc.scrollTop = 0;
    rendre();
    return suivre(P);
  });
}
function rendre() {
  Array.prototype.forEach.call($("regards").children, function (b) { b.setAttribute("aria-pressed", String(b.dataset.regard === E.regard)); });
  $("phrase").textContent = phrase();
  if (E.regard === "fiche") { fiche(); }
  sousBarre();
  peindre();
  detail();
}

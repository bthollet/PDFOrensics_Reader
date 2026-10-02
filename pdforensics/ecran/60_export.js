/* Fragment 60 - l'export groupe: ce qu'il ecrit, ou il a le droit de l'ecrire, le dossier neuf. */
var COLONNES = [
  ["Pièce", function (p) { return p.nom; }], ["Dossier", function (p) { return p.dossier; }],
  ["Format", function (p) { return champ(p, "Format"); }], ["Logiciel d'origine", function (p) { return champ(p, "Logiciel d'origine"); }],
  ["Logiciel qui a produit le PDF", function (p) { return champ(p, "Logiciel qui a produit le PDF"); }],
  ["Créé le", function (p) { return champ(p, "Créé le"); }], ["Modifié le", function (p) { return champ(p, "Modifié le"); }],
  ["Taille", function (p) { return champ(p, "Taille"); }], ["Pages", function (p) { return p.pages.length; }],
  ["Versions enregistrées", function (p) { return releve(p).versions; }], ["Zones recouvertes", function (p) { return releve(p).caches.length; }],
  ["Calques éteints", function (p) { return releve(p).eteints.length; }], ["Lignes de texte affichées", function (p) { return releve(p).textes.length; }],
  ["Lignes de texte invisible", function (p) { return releve(p).invisibles.length; }], ["Images", function (p) { return releve(p).images.length; }],
  ["Annotations", function (p) { return releve(p).annotations.length; }], ["Métadonnées XMP", function (p) { return p.xmp.length ? "oui" : "non"; }],
  ["Fichiers joints", function (p) { return p.joints.length; }], ["Ordre de lecture décrit", function (p) { return p.balise ? "oui" : "non"; }]
];
function ficheDe(p) {
  return { nom: p.nom, identite: p.fiche, rubriques: rubriques(p).map(function (r) { return { titre: r.titre, compte: r.compte, lignes: r.lignes.map(function (l) { return l.texte; }) }; }) };
}
/* Ce que le dossier affiche accepte: la phrase vient de l'outil, l'ecran ne juge pas. */
function verdict() {
  if (!api || !E.exp) { return; }
  var chemins = Object.keys(E.coches), jeton = (E.verdict += 1);
  api.examiner(E.exp.chemin, chemins).then(function (x) {
    if (jeton !== E.verdict) { return; }
    var refusees = chemins.filter(function (c) { return x.pieces[c]; }).length;
    if (x.destination) { dire("verdict", x.destination, "refus"); }
    else if (refusees) { dire("verdict", "L'export peut s'écrire dans ce dossier. " + s(refusees, "pièce sélectionnée est", "pièces sélectionnées sont") + " dans un dossier protégé : " + (refusees > 1 ? "leurs fiches ne s'exportent pas." : "sa fiche ne s'exporte pas."), "refus"); }
    else { dire("verdict", "L'export peut s'écrire dans ce dossier.", "accord"); }
  });
}
function nouveauDossier(ouvrir) {
  $("nouveau-dossier-saisie").hidden = !ouvrir;
  if (ouvrir) {
    $("nouveau-dossier-nom").value = "Fiches des fichiers";
    $("nouveau-dossier-nom").focus();
    $("nouveau-dossier-nom").select();
  }
}
function creerDossier() {
  var nom = $("nouveau-dossier-nom").value;
  api.creer_dossier(E.exp.chemin, nom, Object.keys(E.coches)).then(function (r) {
    if (!r.ok) { dire("etat-export", r.raison, "refus"); return; }
    nouveauDossier(false);
    dire("etat-export", "Dossier créé.", "accord");
    ouvrirDossier("exp", r.chemin);
  });
}
function exporter() {
  var chemins = Object.keys(E.coches);
  if (E.export) { return; }
  if (!chemins.length) { dire("etat-export", "Sélectionnez au moins une pièce dans l'explorateur des pièces.", "refus"); return; }
  E.export = true;
  api.examiner(E.exp.chemin, chemins).then(function (x) {
    if (x.destination) { throw x.destination; }
    var bonnes = chemins.filter(function (c) { return !x.pieces[c]; }), fiches = [], lignes = [], lues = [], illisibles = 0;
    if (!bonnes.length) { throw "Aucune pièce exportable : les pièces sélectionnées sont dans un dossier protégé."; }
    var suite = Promise.resolve();
    bonnes.forEach(function (chemin, i) {
      suite = suite.then(function () {
        dire("etat-export", "Lecture " + (i + 1) + " sur " + bonnes.length + ".");
        return lireTout(chemin).then(function (r) {
          if (!r.ok) { illisibles += 1; return; }
          E.lus[chemin] = faits(r.piece);
          fiches.push(ficheDe(r.piece));
          lignes.push(COLONNES.map(function (c) { return c[1](r.piece); }));
          lues.push(chemin);
        });
      });
    });
    return suite.then(function () {
      if (!fiches.length) { throw "Aucune des pièces sélectionnées ne se lit."; }
      dire("etat-export", "Écriture.");
      return api.exporter(E.genre, E.exp.chemin, fiches, { colonnes: COLONNES.map(function (c) { return c[0]; }), lignes: lignes }, lues);
    }).then(function (r) {
      if (!r.ok) { throw r.raison; }
      var etat = $("etat-export"), restes = [];
      if (chemins.length - bonnes.length) { restes.push(s(chemins.length - bonnes.length, "pièce d'un dossier protégé non exportée", "pièces d'un dossier protégé non exportées")); }
      if (illisibles) { restes.push(s(illisibles, "fichier illisible", "fichiers illisibles")); }
      etat.className = "accord";
      etat.textContent = "Export écrit : " + r.quoi + ", pour " + s(fiches.length, "pièce") + (restes.length ? " (" + restes.join(", ") + ")" : "") + ". ";
      var ouvrir = el("button", "lien", "Ouvrir le dossier");
      ouvrir.type = "button";
      ouvrir.addEventListener("click", function () { api.montrer_export(); });
      etat.appendChild(ouvrir);
      dessiner("src");
      ouvrirDossier("exp", E.exp.chemin);
    });
  }).catch(function (raison) { dire("etat-export", typeof raison === "string" ? raison : "L'export a échoué.", "refus"); })
    .then(function () { E.export = false; });
}

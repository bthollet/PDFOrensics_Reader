/* Fragment 20 - ce que la lecture d'une piece a releve, et ce que chaque trace en dit. */
var NOMS = { texte: "Texte", invisible: "Texte invisible", image: "Image", trace: "Tracé", annotation: "Annotation", page: "Page" };
var GENRE = { texte: "texte", invisible: "invisible", image: "image", trace: "trace", annotation: "annot" };
var CAUSES = { "mode invisible": "écrit en mode invisible", "transparent": "écrit sans aucune opacité", "hors de la page": "placé hors de la page", "couleur du fond": "écrit de la couleur du fond" };
var ZOOMS = [0.4, 0.6, 0.8, 1, 1.25, 1.5, 2, 3, 4];
/* `pages`: ce regard depend du contenu des pages, qui se lit par tranches apres l'ouverture. */
var REGARDS = [
  { cle: "page", nom: "La page", dit: "telle qu'un lecteur PDF l'affiche" },
  { cle: "fiche", nom: "Fiche du fichier", dit: "ses métadonnées, ses versions, et tout ce que la lecture relève" },
  { cle: "caches", nom: "Voir dessous", dit: "les zones recouvertes, et de quoi faire disparaître annotations, images et tracés pour voir ce qu'ils recouvrent", pages: true,
    compte: function (r) { return r.caches.length; },
    vide: function (p, r) { return r.caches.length + r.annotations.length + r.images.length + r.traces.length ? "" : "rien n'est posé sur les pages de ce fichier"; } },
  { cle: "calques", nom: "Contenu non affiché", dit: "les calques éteints à l'ouverture", compte: function (r) { return r.eteints.length; },
    vide: function (p, r) {
      if (r.eteints.length) { return ""; }
      return p.calques.length ? "aucun calque éteint, " + s(p.calques.length, "calque affiché", "calques affichés") + " à l'ouverture" : "aucun calque dans ce fichier";
    } },
  { cle: "versions", nom: "Versions enregistrées", dit: "chaque enregistrement du fichier, comparé au précédent", compte: function (r) { return r.versions; },
    vide: function (p, r) { return r.versions > 1 ? "" : "une seule version, ce fichier a été enregistré une fois"; } },
  { cle: "composition", nom: "De quoi la page est faite", dit: "texte, texte invisible, images, tracés, annotations", pages: true,
    vide: function (p, r) { return r.textes.length + r.invisibles.length + r.images.length + r.traces.length + r.annotations.length ? "" : "aucun élément dans ce fichier"; } },
  { cle: "ordre", nom: "Ordre de lecture", dit: "l'ordre où le fichier écrit ses blocs de texte", pages: true,
    vide: function (p) { return p.pages.some(function (pg) { return pg.blocs.length; }) ? "" : "aucun bloc de texte dans ce fichier"; } }
];

/* Une piece arrive d'abord sans le contenu de ses pages; il suit par tranches. */
function preparer(p) {
  p.lues = 0;
  p.pages.forEach(function (pg) { pg.caches = []; pg.calques = []; pg.elements = []; pg.blocs = []; });
  p.r = null;
  return p;
}
function integrer(p, tranche) {
  tranche.pages.forEach(function (pg) { p.pages[pg.n - 1] = pg; });
  p.lues = tranche.suite === null ? p.pages.length : tranche.suite;
  p.r = null;
}
function enCours(p) { return p.lues < p.pages.length; }
/* Toute la piece, en-tete puis pages: pour l'export, qui ne montre rien avant d'avoir tout lu. */
function lireTout(chemin) {
  return api.lire(chemin).then(function (r) {
    if (!r.ok) { return r; }
    var piece = preparer(r.piece);
    function encore() {
      if (!enCours(piece)) { return { ok: true, piece: piece }; }
      return api.pages(chemin, piece.lues).then(function (t) {
        if (!t.ok) { return t; }
        integrer(piece, t);
        return encore();
      });
    }
    return encore();
  });
}

function releve(p) {
  if (p.r) { return p.r; }
  function tous(cle) {
    var liste = [];
    p.pages.forEach(function (pg) { pg[cle].forEach(function (x) { x.page = pg.n; liste.push(x); }); });
    return liste;
  }
  var elements = tous("elements");
  function de(n) { return elements.filter(function (e) { return e.nature === n; }); }
  p.r = { caches: tous("caches"), hors: tous("calques"), eteints: p.calques.filter(function (c) { return !c.allume; }),
    textes: de("texte"), invisibles: de("invisible"), images: de("image"), traces: de("trace"), annotations: de("annotation"),
    versions: p.versions.length };
  return p.r;
}
function champ(p, nom) {
  var ligne = p.fiche.filter(function (l) { return l[0] === nom; })[0];
  return ligne ? ligne[1] : "";
}
function faits(p) {
  var r = releve(p), mots = [s(r.versions, "version")];
  if (r.caches.length) { mots.push(s(r.caches.length, "zone recouverte", "zones recouvertes")); }
  if (r.eteints.length) { mots.push(s(r.eteints.length, "calque éteint", "calques éteints")); }
  if (r.invisibles.length) { mots.push("texte invisible"); }
  if (!r.textes.length && !r.invisibles.length) { mots.push(sansTexte(r)); }
  if (r.annotations.length) { mots.push(s(r.annotations.length, "annotation")); }
  return mots.join(" · ");
}
/* Une piece sans texte n'est pas toujours une image: ses lettres peuvent etre dessinees en contours. */
function sansTexte(r) {
  if (r.traces.length) { return "sans texte, faite de " + s(r.traces.length, "tracé") + (r.images.length ? " et de " + s(r.images.length, "image") : ""); }
  return r.images.length ? "image seule, sans texte" : "sans texte";
}
/* Ce qui est pose sur la page et cache: un aplat et sa couleur, une image, un degrade, une annotation. */
function pose(c) {
  if (c.nature === "annotation") { return "annotation (" + c.genre + ")" + (c.couleur ? ", " + c.couleur : ""); }
  return c.nature === "image" ? "image" : c.nature === "dégradé" ? "dégradé" : "aplat " + c.couleur;
}
/* Les familles qu'on fait disparaitre pour voir dessous, dans l'ordre que le pont attend. */
function familles() { return ["a", "i", "t"].filter(function (f) { return E.pele[f]; }).join(""); }
function rubriques(p) {
  var r = releve(p);
  function ou(lignes, vide) { return lignes.length ? lignes : [{ texte: vide }]; }
  var texte = [];
  if (r.textes.length) { texte.push({ texte: s(r.textes.length, "ligne de texte affichée", "lignes de texte affichées") + " par les pages." }); }
  p.pages.forEach(function (pg) {
    var parCause = {};
    pg.elements.forEach(function (e) { if (e.nature === "invisible") { (parCause[e.cause || "mode invisible"] = parCause[e.cause || "mode invisible"] || []).push(e); } });
    Object.keys(parCause).forEach(function (cause) {
      texte.push({ texte: "Page " + pg.n + " : " + s(parCause[cause].length, "ligne") + " de texte invisible, " + CAUSES[cause] + ".", cible: parCause[cause][0].id, regard: "composition" });
    });
  });
  return [
    { titre: "Second jeu de métadonnées (XMP)", compte: p.xmp.length, lignes: ou(p.xmp.map(function (x) { return { texte: x[0] + " : " + x[1] }; }), "Aucun.") },
    { titre: "Versions enregistrées", compte: r.versions, lignes: p.versions.map(function (v) {
      return { texte: "Version " + v.n + " : " + (v.date || "date non inscrite") + ", " + v.taille + "." + (v.resume ? " " + maj(v.resume) + "." : ""),
        cible: v.zones.some(function (z) { return z.length; }) ? "version-" + v.n : null, regard: "versions" };
    }) },
    { titre: "Zones recouvertes", compte: r.caches.length, lignes: ou(r.caches.map(function (c) {
      var texte = c.dessous.map(function (d) { return d.texte; }).join(" ");
      return { texte: "Page " + c.page + ", zone " + c.numero + " : " + pose(c) + (c.version ? ", version " + c.version : "")
        + (texte ? ", texte dessous « " + court(texte, 400) + " »" : "")
        + (c.dessus.length ? ", texte écrit par-dessus « " + court(c.dessus.join(" "), 400) + " »." : "."), cible: c.id, regard: "caches" };
    }), "Aucune.") },
    { titre: "Calques éteints à l'ouverture", compte: r.eteints.length, lignes: ou(r.eteints.map(function (c) {
      var contenu = r.hors.filter(function (k) { return k.nom === c.nom; });
      return { texte: c.nom + " : " + s(contenu.length, "élément") + ".", cible: contenu.length ? contenu[0].id : null, regard: "calques" };
    }), p.calques.length ? "Aucun. " + s(p.calques.length, "calque affiché", "calques affichés") + " à l'ouverture : " + p.calques.map(function (c) { return c.nom; }).join(", ") + "." : "Aucun calque dans ce fichier.") },
    { titre: "Texte", compte: r.textes.length + r.invisibles.length, lignes: ou(texte, "Aucun texte : pièce " + sansTexte(r) + ".") },
    { titre: "Images", compte: r.images.length, lignes: ou(r.images.map(function (i) { return { texte: "Page " + i.page + " : image de " + i.texte + ".", cible: i.id, regard: "composition" }; }), "Aucune.") },
    { titre: "Annotations", compte: r.annotations.length, lignes: ou(r.annotations.map(function (a) { return { texte: "Page " + a.page + " : " + a.texte + ".", cible: a.id, regard: "composition" }; }), "Aucune.") },
    { titre: "Fichiers joints dans le PDF", compte: p.joints.length, lignes: ou(p.joints.map(function (j) { return { texte: j }; }), "Aucun.") },
    { titre: "Ordre de lecture", compte: p.balise ? 1 : 0, lignes: [{ texte: p.balise ? "Décrit par le fichier." : "Non décrit par le fichier." }] }
  ];
}

/* ---------- ce que chaque trace dit quand on le clique ---------- */
function dateDe(v) { var d = P.versions[v - 1].date; return d ? " (" + d + ")" : ""; }
function ditCache(c) {
  var quand = !c.version ? "" : c.version === 1 ? " présent dès le premier enregistrement" : " posé à la version " + c.version + dateDe(c.version);
  var texte = c.dessous.map(function (d) { return d.texte; }).join(" ");
  return { id: c.id, genre: "cache", bbox: c.bbox, numero: c.numero, marque: true, mots: c.nature === "annotation" ? [] : c.dessous,
    titre: "Zone recouverte " + c.numero + ", page " + c.page,
    detail: [maj(pose(c)) + quand + "." + (texte ? " Texte resté dessous :" : " Faites-la disparaître pour voir dessous."), texte]
      .concat(c.dessus.length ? ["Texte écrit par-dessus :", c.dessus.join(" ")] : []) };
}
function ditCalque(k) {
  return { id: k.id, genre: "calque", bbox: k.bbox, marque: true, titre: "Calque « " + k.nom + " », éteint à l'ouverture, page " + k.page, detail: ["Contenu :", k.texte] };
}
function ditZone(z, v, rang) {
  var detail = [];
  z.quoi.forEach(function (q) {
    var sens = q.sens === "ajout" ? "Ajouté : " : "Retiré : ";
    if (q.nature === "texte" || q.nature === "invisible") { detail.push(sens + NOMS[q.nature].toLowerCase(), q.texte); } else { detail.push(sens + q.texte, ""); }
  });
  return { id: z.id, genre: "change", bbox: z.bbox, numero: rang, marque: true, titre: "Zone modifiée à la version " + v + dateDe(v),
    detail: detail.length ? detail : ["L'image de la page diffère ici de la version précédente."] };
}
function ditElement(e) {
  var texte = e.nature === "texte" || e.nature === "invisible";
  return { id: e.id, genre: GENRE[e.nature], bbox: e.bbox, marque: e.nature === "invisible" || e.nature === "annotation",
    titre: NOMS[e.nature] + ", page " + e.page,
    detail: texte ? [e.nature === "invisible" ? maj(CAUSES[e.cause || "mode invisible"]) + " :" : "", e.texte] : [maj(e.texte) + "."] };
}
function ditBloc(b) { return { id: b.id, genre: "bloc", bbox: b.bbox, numero: b.n, titre: "Bloc " + b.n + " dans l'ordre du fichier", detail: ["", b.texte] }; }
function traces(page, index) {
  if (E.regard === "caches") { return page.caches.map(ditCache); }
  if (E.regard === "calques") { return E.calques ? page.calques.map(ditCalque) : []; }
  if (E.regard === "versions") { return (P.versions[E.version - 1].zones[index] || []).map(function (z, i) { return ditZone(z, E.version, i + 1); }); }
  if (E.regard === "composition") { return page.elements.map(ditElement); }
  if (E.regard === "ordre") { return page.blocs.map(ditBloc); }
  return [];
}

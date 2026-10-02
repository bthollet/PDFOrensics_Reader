/* Fragment 90 - le branchement: chaque geste a son bouton, puis le depart. */
REGARDS.forEach(function (r) {
  var b = el("button");
  b.type = "button";
  b.dataset.regard = r.cle;
  b.appendChild(icone(r.cle));
  if (r.compte) { b.appendChild(el("span", "compte")); }
  expliquer(b, r.nom, r.dit);
  b.addEventListener("click", function () {
    if (!P) { return; }
    /* Un regard sans objet dit aussi pourquoi quand on le clique: en mots, pas au seul survol. */
    if (b.getAttribute("aria-disabled") === "true") { $("phrase").textContent = r.nom + " : " + b.dataset.pourquoi + "."; return; }
    E.regard = r.cle; E.choix = null; rendre();
  });
  $("regards").appendChild(b);
});
$("regards").hidden = true;

$("pivoter").appendChild(icone("pivoter"));
expliquer($("pivoter"), "Faire pivoter", "tourne l'affichage d'un quart de tour, le fichier n'est pas modifié");
$("pivoter").addEventListener("click", function () { if (P) { pivoter(); } });
$("nouveau-dossier").appendChild(icone("nouveau"));
expliquer($("nouveau-dossier"), "Créer un nouveau dossier", "dans le dossier affiché, pour y écrire l'export");
$("nouveau-dossier").addEventListener("click", function () { nouveauDossier($("nouveau-dossier-saisie").hidden); });
$("nouveau-dossier-annuler").addEventListener("click", function () { nouveauDossier(false); });
$("nouveau-dossier-saisie").addEventListener("submit", function (ev) { ev.preventDefault(); creerDossier(); });
$("onglet-src").prepend(icone("dossier"));
$("onglet-exp").prepend(icone("exporter"));
["src", "exp"].forEach(function (quel) {
  $("onglet-" + quel).addEventListener("click", function () { montrerVolet(quel); });
  $("chemin-" + quel).addEventListener("keydown", function (ev) { if (ev.key === "Enter") { ouvrirDossier(quel, $("chemin-" + quel).value); } });
  $("parcourir-" + quel).addEventListener("click", function () { api.choisir_dossier().then(function (c) { if (c) { ouvrirDossier(quel, c); } }); });
});
montrerVolet("src");
$("replier").addEventListener("click", function () { replier(!coque.classList.contains("replie")); });
$("tout").addEventListener("click", function () {
  var ici = E.src ? E.src.pdfs : [], toutes = ici.length > 0 && ici.every(function (f) { return E.coches[f.chemin]; });
  ici.forEach(function (f) { if (toutes) { delete E.coches[f.chemin]; } else { E.coches[f.chemin] = f.nom; } });
  dessiner("src");
});
$("vider").addEventListener("click", function () { E.coches = {}; dessiner("src"); });
Array.prototype.forEach.call($("genres").children, function (b) {
  b.setAttribute("aria-pressed", String(b.dataset.genre === E.genre));
  b.addEventListener("click", function () {
    E.genre = b.dataset.genre;
    Array.prototype.forEach.call($("genres").children, function (x) { x.setAttribute("aria-pressed", String(x === b)); });
  });
});
$("exporter").addEventListener("click", exporter);
$("saisie-page").addEventListener("change", function () {
  var cible = $("page-" + Math.max(1, Math.min(P.pages.length, Number($("saisie-page").value) || 1)));
  doc.scrollTop = cible.offsetTop - pages.offsetTop;
});
doc.addEventListener("scroll", function () {
  if (!P || pages.hidden) { return; }
  var repere = doc.scrollTop + doc.clientHeight / 3, courante = 1;
  Array.prototype.forEach.call(pages.children, function (f, i) { if (f.offsetTop - pages.offsetTop <= repere) { courante = i + 1; } });
  if (document.activeElement !== $("saisie-page")) { $("saisie-page").value = courante; }
});
/* Le zoom garde sous le pointeur le point de la page qui s'y trouvait; les images nettes suivent, une fois le geste fini. */
function appliquerZoom(zoom, ancre) {
  var avant = E.zoom, cadre = doc.getBoundingClientRect();
  E.zoom = Math.max(ZOOMS[0], Math.min(ZOOMS[ZOOMS.length - 1], zoom));
  var x = ancre ? ancre.x - cadre.left : doc.clientWidth / 2, y = ancre ? ancre.y - cadre.top : doc.clientHeight / 3;
  var gauche = (doc.scrollLeft + x) * E.zoom / avant - x, haut = (doc.scrollTop + y) * E.zoom / avant - y;
  pages.style.setProperty("--zoom", E.zoom);
  doc.scrollLeft = gauche;
  doc.scrollTop = haut;
  $("zoom-largeur").textContent = Math.abs(E.zoom - 1) < 0.005 ? "Largeur" : Math.round(E.zoom * 100) + " %";
  clearTimeout(E.zoomTard);
  E.zoomTard = setTimeout(function () { if (P) { peindre(); } }, 170);
}
function zoomer(sens) {
  var plus = ZOOMS.filter(function (z) { return z > E.zoom + 0.01; })[0], moins = ZOOMS.filter(function (z) { return z < E.zoom - 0.01; }).pop();
  appliquerZoom(sens === 0 ? 1 : (sens > 0 ? plus : moins) || E.zoom);
}
$("zoom-moins").addEventListener("click", function () { zoomer(-1); });
$("zoom-plus").addEventListener("click", function () { zoomer(1); });
$("zoom-largeur").addEventListener("click", function () { zoomer(0); });
/* Pincer sur un pave tactile, ou tourner la molette en tenant Ctrl: le navigateur l'annonce comme une molette avec Ctrl. */
doc.addEventListener("wheel", function (ev) {
  if (!ev.ctrlKey || !P || pages.hidden) { return; }
  ev.preventDefault();
  appliquerZoom(E.zoom * Math.exp(Math.max(-0.25, Math.min(0.25, -ev.deltaY * 0.01))), { x: ev.clientX, y: ev.clientY });
}, { passive: false });
window.addEventListener("resize", function () { if (P) { marquer(); mesurerDetail(); } });

$("bas-fermer").appendChild(icone("fermer"));
expliquer($("bas-fermer"), "Masquer le détail", "le tracé reste sur la page, recliquez-le pour le relire");
$("bas-fermer").addEventListener("click", fermerDetail);
$("bas-taille").addEventListener("click", function () { E.detailLong = !E.detailLong; mesurerDetail(); });

function demarrer() {
  api = window.pywebview.api;
  api.depart().then(function (d) {
    E.dialogues = d.dialogues !== false;
    ["src", "exp"].forEach(function (quel) {
      $("parcourir-" + quel).hidden = !E.dialogues;
      d.raccourcis.forEach(function (r) {
        var b = el("button", "", r.nom);
        b.type = "button";
        b.title = r.chemin;
        b.addEventListener("click", function () { ouvrirDossier(quel, r.chemin); });
        $("raccourcis-" + quel).appendChild(b);
      });
    });
    return ouvrirDossier("src", d.dossier).then(function () { return ouvrirDossier("exp", d.export); });
  }).then(function () { window.lecteur.pret = true; });
}
/* Ce que les essais pilotent: les memes gestes que l'utilisateur, par leurs noms. */
window.lecteur = { pret: false, ouvrirDossier: ouvrirDossier, ouvrirPiece: ouvrirPiece, etat: function () { return E; }, piece: function () { return P; },
  complet: function () { return !!P && !enCours(P); }, zoomer: appliquerZoom };
if (window.pywebview && window.pywebview.api) { demarrer(); } else { window.addEventListener("pywebviewready", demarrer); }

/* Fragment 30 - les pages: images et traces a la demande, a l'approche de la vue; le pivot de l'affichage. */
/* `sans`: ce qu'on retire de la page pour voir dessous (a: annotations, i: images, t: traces); vide pour la page telle quelle. */
function image(version, page, calques, sans) {
  var echelle = E.zoom >= 2.6 ? 4.5 : E.zoom >= 1.5 ? 3 : 1.6, cle = [P.chemin, version, page, calques, echelle, sans || ""].join("|");
  if (IMAGES[cle]) { return Promise.resolve(IMAGES[cle]); }
  return api.image(P.chemin, version, page, calques, echelle, sans || "").then(function (r) {
    if (!r.ok) { return ""; }
    if (!IMAGES[cle]) { ORDRE.push(cle); POIDS += r.src.length; }
    IMAGES[cle] = r.src;
    /* Les images gardees se comptent aussi au poids: une page fortement agrandie pese plusieurs millions de signes. */
    while (ORDRE.length > 40 || (POIDS > 150e6 && ORDRE.length > 3)) { var vieille = ORDRE.shift(); POIDS -= IMAGES[vieille].length; delete IMAGES[vieille]; }
    return r.src;
  });
}
/* Le voile: la page telle quelle, posee sur la page pelee; plus on efface, plus le dessous se voit. */
function voiler(x) {
  E.voile = Math.max(0, Math.min(100, x));
  pages.style.setProperty("--voile", (1 - E.voile / 100).toFixed(3));
  pages.dataset.pele = E.voile > 0 ? "1" : "0";
}
function regler(x) {
  E.rideau = Math.max(0, Math.min(100, x));
  pages.style.setProperty("--rideau", E.rideau.toFixed(1) + "%");
  var curseur = $("curseur-rideau");
  if (curseur) { curseur.value = Math.round(E.rideau); }
}
/* Ou, dans la hauteur du cadre affiche, tombe le haut d'une zone de la page: depend du pivot. */
function hautAffiche(b) { return [b[1], b[0], 1 - b[3], 1 - b[2]][E.pivot / 90]; }
function cadrer() {
  P.pages.forEach(function (p, i) {
    pages.children[i].firstChild.style.aspectRatio = E.pivot % 180 ? p.h + " / " + p.l : p.l + " / " + p.h;
  });
  pages.dataset.pivot = E.pivot;
}
function construire() {
  if (observateur) { observateur.disconnect(); }
  visibles = {};
  pages.textContent = "";
  P.pages.forEach(function (p, i) {
    var feuille = el("figure", "feuille");
    feuille.id = "page-" + p.n;
    feuille.dataset.index = i;
    var tourne = el("div", "tourne"), pile = el("div", "pile");
    var fond = el("img", "fond");
    fond.alt = "Page " + p.n + " sur " + P.pages.length;
    var avant = el("img", "avant");
    avant.alt = "";
    var rideau = el("div", "rideau");
    rideau.appendChild(el("span", "", "‹›"));
    rideau.addEventListener("pointerdown", function (ev) {
      rideau.setPointerCapture(ev.pointerId);
      ev.preventDefault();
      function bouger(e) {
        /* Le rideau suit l'axe horizontal DE LA PAGE, qui n'est plus celui de l'ecran quand elle a pivote. */
        var c = tourne.getBoundingClientRect(), x = (e.clientX - c.left) / c.width, y = (e.clientY - c.top) / c.height;
        regler(100 * [x, y, 1 - x, 1 - y][E.pivot / 90]);
      }
      function fin() { rideau.removeEventListener("pointermove", bouger); rideau.removeEventListener("pointerup", fin); rideau.removeEventListener("pointercancel", fin); }
      rideau.addEventListener("pointermove", bouger);
      rideau.addEventListener("pointerup", fin);
      rideau.addEventListener("pointercancel", fin);
    });
    pile.append(fond, avant, el("span", "etiquette avant-nom"), el("span", "etiquette apres-nom"), rideau, el("div", "sur"));
    tourne.appendChild(pile);
    feuille.append(tourne, el("figcaption", "folio", p.n + " / " + P.pages.length));
    pages.appendChild(feuille);
  });
  cadrer();
  observateur = new IntersectionObserver(function (entrees) {
    entrees.forEach(function (x) {
      var i = Number(x.target.dataset.index);
      visibles[i] = x.isIntersecting;
      if (x.isIntersecting) { montrer(i); } else { cacher(i); }
    });
  }, { root: doc, rootMargin: "700px 0px" });
  Array.prototype.forEach.call(pages.children, function (f) { observateur.observe(f); });
}
function pile(i) { return pages.children[i].firstChild.firstChild; }
function cacher(i) {
  var p = pile(i);
  p.querySelector(".sur").textContent = "";
  p.querySelector(".fond").removeAttribute("src");
  p.querySelector(".avant").removeAttribute("src");
}
function montrer(i) {
  var p = P.pages[i], boite = pile(i), jeton = E.jeton;
  var compare = E.regard === "versions" && E.version > 1 && i < P.versions[E.version - 2].pages;
  var version = E.regard === "versions" ? E.version : R.versions;
  var fond = boite.querySelector(".fond"), avant = boite.querySelector(".avant");
  var peler = E.regard === "caches";
  /* Pour voir dessous: la page pelee au fond, la page telle quelle par-dessus, que le curseur efface. */
  image(version, p.n, E.regard === "calques" && E.calques, peler ? familles() : "").then(function (src) { if (jeton === E.jeton && visibles[i] && src) { fond.src = src; } });
  avant.hidden = !compare && !peler;
  if (compare) { image(E.version - 1, p.n, false).then(function (src) { if (jeton === E.jeton && visibles[i] && src) { avant.src = src; } }); }
  if (peler) { image(version, p.n, false, "").then(function (src) { if (jeton === E.jeton && visibles[i] && src) { avant.src = src; } }); }
  boite.querySelector(".rideau").hidden = !compare;
  var noms = boite.querySelectorAll(".etiquette");
  noms[0].hidden = noms[1].hidden = !compare;
  noms[0].textContent = "version " + (E.version - 1);
  noms[1].textContent = "version " + E.version;
  var sur = boite.querySelector(".sur");
  sur.textContent = "";
  /* Hors de la page, rien ne se dessine - sauf le texte que le fichier y a place: une marque au bord le signale. */
  traces(p, i).filter(function (t) { return t.genre === "invisible" || !horsPage(t.bbox); }).sort(function (a, b) { return aire(b.bbox) - aire(a.bbox); }).forEach(function (t) {
    var b = el("button", "trace g-" + t.genre + (E.choix === t.id ? " choisi" : ""));
    b.type = "button";
    b.dataset.id = t.id;
    b.style.left = pct(t.bbox[0]); b.style.top = pct(t.bbox[1]);
    b.style.width = pct(t.bbox[2] - t.bbox[0]); b.style.height = pct(t.bbox[3] - t.bbox[1]);
    b.setAttribute("aria-label", t.titre);
    if (t.numero) { b.appendChild(el("span", "numero", t.numero)); }
    b.addEventListener("click", function () { choisir(t); });
    sur.appendChild(b);
    (t.mots || []).filter(function (m) { return m.texte.indexOf("(illisible") !== 0; }).forEach(function (m) {   /* un texte illisible ne se pose pas sur la page */
      /* Le mot part du debut de sa ligne de base, tourne comme la page du fichier, puis s'ajuste a sa longueur d'origine. */
      var mot = el("span", "mot", m.texte);
      mot.style.left = pct((m.x - t.bbox[0]) / (t.bbox[2] - t.bbox[0]));
      mot.style.top = "calc(" + pct((m.y - t.bbox[1]) / (t.bbox[3] - t.bbox[1])) + " - 0.85em)";
      mot.style.fontSize = (m.taille / p.l * 100).toFixed(3) + "cqw";
      b.appendChild(mot);
      /* Largeurs de MISE EN PAGE: elles ne changent pas quand l'affichage pivote. */
      var voulue = m.long / p.l * boite.clientWidth, mesuree = mot.offsetWidth;
      mot.style.transform = "rotate(" + m.angle + "deg)" + (voulue > 0 && mesuree > 0 ? " scaleX(" + (voulue / mesuree).toFixed(4) + ")" : "");
    });
  });
}
function peindre() {
  E.jeton += 1;
  var nombre = E.regard === "versions" ? P.versions[E.version - 1].pages : P.pages.length;
  pages.hidden = E.regard === "fiche";
  pages.dataset.mode = E.regard === "caches" ? "voile" : "";
  voiler(E.voile);
  $("fiche").hidden = !pages.hidden;
  $("outils").hidden = pages.hidden;
  /* Ce qui est a portee de vue se mesure ici meme: l'observateur ne previent qu'apres coup. */
  var vue = doc.getBoundingClientRect();
  Array.prototype.forEach.call(pages.children, function (f, i) {
    f.hidden = i >= nombre;
    var cadre = f.getBoundingClientRect();
    visibles[i] = !pages.hidden && !f.hidden && cadre.bottom > vue.top - 700 && cadre.top < vue.bottom + 700;
    if (visibles[i]) { montrer(i); } else { cacher(i); }
  });
  marquer();
}
function pivoter() {
  E.pivot = (E.pivot + 90) % 360;
  cadrer();
  peindre();
}
function choisir(t) {
  E.choix = t.id;
  DITS[t.id] = t;
  Array.prototype.forEach.call(pages.querySelectorAll(".trace"), function (b) { b.classList.toggle("choisi", b.dataset.id === t.id); });
  detail();
}
/* Le detail d'un trace tient en quelques lignes; un long texte se deroule, s'ouvre en grand, ou se masque. */
function detail() {
  var bas = $("bas"), pied = $("pied"), t = E.choix && DITS[E.choix];
  bas.textContent = "";
  $("bas-fermer").hidden = !t;
  if (!t) {
    var rien = E.regard === "page" || E.regard === "fiche" || !P.pages.some(function (p, i) { return traces(p, i).length; });
    bas.textContent = rien ? "" : "Cliquez un tracé sur la page pour lire le détail.";
    pied.hidden = rien;
    $("bas-taille").hidden = true;
    return;
  }
  pied.hidden = false;
  bas.appendChild(el("b", "", t.titre + "."));
  for (var i = 0; i < t.detail.length; i += 2) {
    if (t.detail[i]) { bas.appendChild(document.createTextNode((i ? " · " : " ") + t.detail[i] + " ")); }
    if (t.detail[i + 1]) { bas.appendChild(el("q", "", t.detail[i + 1])); }
  }
  bas.scrollTop = 0;
  mesurerDetail();
}
function mesurerDetail() {
  var bas = $("bas"), pied = $("pied");
  pied.classList.remove("long");
  var deborde = bas.scrollHeight > bas.clientHeight + 2;
  pied.classList.toggle("long", deborde && E.detailLong);
  $("bas-taille").hidden = !deborde;
  $("bas-taille").textContent = deborde && E.detailLong ? "Réduire" : "Tout lire";
}
function fermerDetail() {
  E.choix = null;
  Array.prototype.forEach.call(pages.querySelectorAll(".trace.choisi"), function (b) { b.classList.remove("choisi"); });
  detail();
}
/* Une marque par page et par genre de trace: une piece de cent pages ne pose pas mille marques. */
function marquer() {
  var marques = $("marques");
  marques.textContent = "";
  if (!P || pages.hidden || doc.scrollHeight <= doc.clientHeight) { return; }
  var haut = doc.getBoundingClientRect().top - doc.scrollTop, couleurs = getComputedStyle(document.documentElement);
  var teinte = { cache: "--c-cache", calque: "--c-calque", change: "--c-change", invisible: "--c-invisible", annot: "--c-annot" };
  P.pages.forEach(function (p, i) {
    var feuille = pages.children[i], vus = {};
    if (feuille.hidden) { return; }
    var cadre = feuille.firstChild.getBoundingClientRect();
    traces(p, i).forEach(function (t) {
      if (!t.marque || vus[t.genre]) { return; }
      vus[t.genre] = true;
      var y = cadre.top - haut + hautAffiche(t.bbox) * cadre.height, m = el("button");
      m.type = "button";
      m.tabIndex = -1;
      m.title = t.titre;
      m.style.setProperty("--k", couleurs.getPropertyValue(teinte[t.genre] || "--c-change"));
      m.style.top = (y / doc.scrollHeight * 100).toFixed(2) + "%";
      m.addEventListener("click", function () { doc.scrollTop = Math.max(0, y - doc.clientHeight / 3); choisir(t); });
      marques.appendChild(m);
    });
  });
}

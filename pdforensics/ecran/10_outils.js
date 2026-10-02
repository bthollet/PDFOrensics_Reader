/* Fragment 10 - les outils communs, les icones, l'etat de l'ecran. */
var api = null;
function $(id) { return document.getElementById(id); }
function el(balise, classe, texte) {
  var e = document.createElement(balise);
  if (classe) { e.className = classe; }
  if (texte !== undefined) { e.textContent = texte; }
  return e;
}
function pct(v) { return (v * 100).toFixed(3) + "%"; }
function s(n, mot, pluriel) { return n + " " + (n > 1 ? (pluriel || mot + "s") : mot); }
function maj(t) { return t.charAt(0).toUpperCase() + t.slice(1); }
function aire(b) { return Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]); }
/* Une zone bornee a la page et reduite a rien sur un de ses bords: elle est hors de la page, rien ne s'y dessine. */
function horsPage(b) { return (b[0] === b[2] && (b[0] === 0 || b[0] === 1)) || (b[1] === b[3] && (b[1] === 0 || b[1] === 1)); }
function court(t, n) { return t.length > n ? t.slice(0, n).replace(/\s+\S*$/, "") + " […]" : t; }
function dire(id, texte, classe) { $(id).textContent = texte; $(id).className = classe || ""; }

/* Les icones sont dessinees ici: l'ecran ne charge rien de l'exterieur. */
var ICONES = {
  page: '<path d="M6 3h6l4 4v10H6z"/><path d="M12 3v4h4"/>',
  fiche: '<circle cx="10" cy="10" r="7"/><path d="M10 9.2v4.6"/><circle cx="10" cy="6.4" r=".7" fill="currentColor" stroke="none"/>',
  caches: '<path d="M3 5.5h14M3 14.5h14M3 10h3.5"/><rect x="8" y="7.8" width="9" height="4.4" rx=".6" fill="currentColor" stroke="none"/>',
  calques: '<path d="M10 3l7 3.6-7 3.6-7-3.6z"/><path d="M3 10.4l7 3.6 7-3.6" stroke-dasharray="2 2.2"/><path d="M3 14l7 3.6 7-3.6" stroke-dasharray="2 2.2"/>',
  versions: '<path d="M4.3 10.2a5.9 5.9 0 1 0 1.9-4.5"/><path d="M4 3.6v3h3"/><path d="M10 7v3.4l2.4 1.5"/>',
  composition: '<rect x="3" y="3" width="6" height="6" rx=".8"/><circle cx="14" cy="6" r="3"/><path d="M3 12.5h6M3 15.5h6"/><path d="M11.2 17l2.8-5 2.8 5z"/>',
  ordre: '<path d="M4 5h12L4 15h12"/><path d="M13.6 12.6L16 15l-2.4 2.4"/>',
  pivoter: '<path d="M15.8 10.4a5.9 5.9 0 1 1-1.9-4.6"/><path d="M16 3.6v3.2h-3.2"/>',
  dossier: '<path d="M3 6.5V15a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1h-6L8.6 5H4a1 1 0 0 0-1 1.5z"/>',
  nouveau: '<path d="M3 6.5V15a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1h-6L8.6 5H4a1 1 0 0 0-1 1.5z"/><path d="M10 9.5v4M8 11.5h4"/>',
  exporter: '<path d="M10 12.5V3.5"/><path d="M6.6 6.8L10 3.4l3.4 3.4"/><path d="M4 11.5V16h12v-4.5"/>',
  fermer: '<path d="M5.5 5.5l9 9M14.5 5.5l-9 9"/>'
};
function icone(nom) {
  var boite = el("span", "icone");
  boite.innerHTML = '<svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONES[nom] + "</svg>";
  return boite;
}
/* Un bouton qui ne porte qu'une icone dit son nom aux lecteurs d'ecran, et s'explique au survol. */
function expliquer(bouton, nom, explication) {
  bouton.setAttribute("aria-label", explication ? nom + ". " + explication : nom);
  bouton.dataset.bulle = explication ? nom + " : " + explication : nom;
}

var E = { regard: "page", version: 1, calques: true, choix: null, zoom: 1, rideau: 50, pivot: 0, coches: {}, genre: "fiches",
  src: null, exp: null, lus: {}, jeton: 0, verdict: 0, export: false, dialogues: true, detailLong: false, zoomTard: 0, marquesTard: 0,
  /* Voir dessous: ce qu'on fait disparaitre (a: annotations, i: images, t: traces), et de combien (0 a 100). */
  pele: { a: true, i: true, t: true }, voile: 0 };
var P = null, R = null, DITS = {}, IMAGES = {}, ORDRE = [], POIDS = 0, observateur = null, visibles = {};
var pages = $("pages"), doc = $("doc"), coque = $("coque");

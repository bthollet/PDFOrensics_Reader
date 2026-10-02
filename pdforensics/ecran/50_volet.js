/* Fragment 50 - le volet: deux explorateurs, un seul montre a la fois, un petit menu pour passer de l'un a l'autre. */
function ouvrirDossier(quel, chemin) {
  return api.lister(chemin).then(function (l) {
    E[quel] = l;
    dessiner(quel);
    if (quel === "exp") { verdict(); }
    return l;
  });
}
function marquerOuverte(chemin) {
  Array.prototype.forEach.call(document.querySelectorAll("#liste-src .piece button"), function (b) { b.setAttribute("aria-current", String(b.dataset.chemin === chemin)); });
}
function dessiner(quel) {
  var l = E[quel], liste = $("liste-" + quel);
  if (!l) { return; }
  var champDuChemin = $("chemin-" + quel), descente = liste.dataset.chemin === l.chemin ? liste.scrollTop : 0;
  champDuChemin.value = l.chemin;
  champDuChemin.scrollLeft = champDuChemin.scrollWidth;   /* un long chemin montre sa fin: le dossier ou l'on est */
  liste.dataset.chemin = l.chemin;
  liste.textContent = "";
  if (l.refus) { liste.appendChild(el("p", "", l.refus)); }
  function rang(classe, marque, texte, agir) {
    var ligne = el("div", "rang " + classe), bouton = el("button", "", texte);
    bouton.type = "button";
    bouton.addEventListener("click", agir);
    ligne.append(marque, bouton);
    liste.appendChild(ligne);
    return bouton;
  }
  if (l.parent) { rang("dossier", el("span", "", "↑"), "Dossier parent", function () { ouvrirDossier(quel, l.parent); }); }
  l.dossiers.forEach(function (d) { rang("dossier", el("span", "", "▸"), d.nom, function () { ouvrirDossier(quel, d.chemin); }); });
  if (quel === "src") {
    l.pdfs.forEach(function (f) {
      var coche = el("input");
      coche.type = "checkbox";
      coche.checked = !!E.coches[f.chemin];
      coche.setAttribute("aria-label", "Sélectionner " + f.nom);
      coche.addEventListener("change", function () { if (coche.checked) { E.coches[f.chemin] = f.nom; } else { delete E.coches[f.chemin]; } selection(); });
      var bouton = rang("piece", coche, f.nom, function () { ouvrirPiece(f.chemin, f.nom.replace(/\.pdf$/i, "")); });
      bouton.dataset.chemin = f.chemin;
      bouton.setAttribute("aria-current", String(!!P && P.chemin === f.chemin));
      bouton.appendChild(el("small", "", E.lus[f.chemin] || f.taille));
    });
    if (!l.refus && !l.dossiers.length && !l.pdfs.length) { liste.appendChild(el("p", "", "Aucun dossier ni PDF ici.")); }
    else if (!l.refus && !l.pdfs.length) { liste.appendChild(el("p", "", "Aucun PDF dans ce dossier.")); }
  } else if (!l.refus && !l.dossiers.length) { liste.appendChild(el("p", "", "Aucun sous-dossier.")); }
  if (l.tronque) { liste.appendChild(el("p", "", "Et " + l.tronque + " autres, non affichés.")); }
  liste.scrollTop = descente;
  if (quel === "src") { selection(); }
}
function selection() {
  var n = Object.keys(E.coches).length, ici = E.src ? E.src.pdfs : [];
  var toutes = ici.length > 0 && ici.every(function (f) { return E.coches[f.chemin]; });
  $("tout").textContent = toutes ? "Tout désélectionner" : "Tout sélectionner";
  $("selection").textContent = n ? s(n, "pièce sélectionnée", "pièces sélectionnées") : "Aucune pièce sélectionnée";
  $("vider").hidden = !n;
  ["exporter-compte", "onglet-compte"].forEach(function (id) {
    $(id).textContent = n;
    $(id).className = "compte" + (n ? "" : " zero");
  });
  verdict();
}
/* Le volet montre l'un OU l'autre explorateur; celui qui est hors de vue ne recoit ni clic ni tabulation. */
function montrerVolet(quel) {
  coque.dataset.volet = quel;
  $("onglet-src").setAttribute("aria-pressed", String(quel === "src"));
  $("onglet-exp").setAttribute("aria-pressed", String(quel === "exp"));
  $("exp-pieces").inert = quel !== "src";
  $("exp-export").inert = quel !== "exp";
}
function replier(oui) {
  coque.classList.toggle("replie", oui);
  var bouton = $("replier"), libelle = oui ? "Déplier le volet" : "Replier le volet";
  bouton.textContent = oui ? "»" : "«";
  bouton.setAttribute("aria-expanded", String(!oui));
  bouton.setAttribute("aria-label", libelle);
  bouton.title = libelle;
  if (P) { peindre(); }
}

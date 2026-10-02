# -*- coding: utf-8 -*-
"""Les essais de l'export OpenDocument, sur des donnees fabriquees et sur elles seules.

  python -B essais/essais_exports.py    structure des archives, contenu relu, cas tordus

Chaque essai imprime « OK » ou « ECHEC »; le script sort sur un code non nul s'il y a un echec.
Tout s'ecrit dans un dossier temporaire, supprime a la fin.

CE QUE CES ESSAIS NE FONT PAS: ouvrir les fichiers avec LibreOffice. La verification s'arrete a la
structure de l'archive et au contenu relu; elle ne dit pas comment un traitement de texte met le
document en pages. L'ouverture reelle est un essai a part, qui ne se lance que volontairement:
essais_exports_ouverture.py.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # meme lance sans -B, rien ne s'ecrit a cote des sources
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # le paquet est a cote du dossier des essais

from pdforensics import exports_odf  # noqa: E402

GENERATEUR = "PDForensics"  # ce que le fichier doit dire de lui-meme, ecrit ici sans rien emprunter a l'export
TITRE_ODT, TITRE_ODS, SOUS_TITRE = "Fiches des fichiers", "Tableau des fiches", "Relevé du 1er janvier 2000 : 2 pièces."
VUE = ["Pièce", "Pages", "Versions enregistrées", "Zones recouvertes", "Calques éteints", "Lignes de texte invisible", "Images", "Annotations"]
ENTREES = ["mimetype", "content.xml", "styles.xml", "meta.xml", "META-INF/manifest.xml"]
MANIFESTE = ENTREES[-1]
SIGNATURE = bytes([0x50, 0x4B, 0x03, 0x04])  # les quatre premiers octets d'une archive ZIP
OASIS = "urn:oasis:names:tc:opendocument:xmlns:"
ESPACES = {"office": OASIS + "office:1.0", "style": OASIS + "style:1.0", "text": OASIS + "text:1.0", "table": OASIS + "table:1.0",
           "fo": OASIS + "xsl-fo-compatible:1.0", "meta": OASIS + "meta:1.0", "manifest": OASIS + "manifest:1.0",
           "dc": "http://purl.org/dc/elements/1.1/"}
ESPACE, TABULATION, RETOUR = chr(0xE000), chr(0xE001), chr(0xE002)  # ce que posent les balises: a ne pas fondre avec les blancs
ABSENT = "Pièce absente du relevé"  # le temoin: une chaine qu'aucun fichier ne porte
ECHECS: list[str] = []
PRODUITS: list[tuple[Path, list[str]]] = []  # chaque fichier ecrit, et ce qu'un lecteur doit y lire

# Deux fiches et leur tableau, ecrits a la main: des libelles qui disent ce qu'ils sont, des dates et des tailles rondes.
FICHES = [
    {"nom": "Document d'essai à trois enregistrements",
     "identite": [["Format", "PDF 1.7"], ["Titre inscrit dans le fichier", "Document d'essai n° 1"], ["Auteur inscrit dans le fichier", "aucun"],
                  ["Logiciel d'origine", "Logiciel de saisie (essai)"], ["Logiciel qui a produit le PDF", "Export PDF (essai)"],
                  ["Créé le", "1er janvier 2000 à 12 h 00"], ["Modifié le", "1er mars 2000 à 12 h 00"], ["Taille", "100 Ko"], ["Pages", "2, de 210 × 297 mm"]],
     "rubriques": [
         {"titre": "Versions enregistrées", "compte": 3, "lignes": [
             "Version 1 : 1er janvier 2000 à 12 h 00, 100 Ko.",
             "Version 2 : 1er février 2000 à 12 h 00, 100 Ko. Page 1 : 1 texte ajouté, 1 aplat blanc ajouté, 1 annotation ajoutée.",
             "Version 3 : 1er mars 2000 à 12 h 00, 100 Ko. Page 1 : 1 texte ajouté, 1 aplat noir ajouté."]},
         {"titre": "Zones recouvertes", "compte": 2, "lignes": [
             "Page 1, zone 1 : aplat blanc, version 2, texte dessous « Mot écrit à l'origine », texte écrit par-dessus « Mot remplacé ».",
             "Page 1, zone 2 : aplat noir, version 3, texte dessous « texte resté sous le cache. »."]},
         {"titre": "Calques éteints à l'ouverture", "compte": 1, "lignes": ["Brouillon : 2 éléments."]},
         {"titre": "Annotations", "compte": 1, "lignes": ["Page 1 : note « À vérifier »."]},
         {"titre": "Ordre de lecture", "compte": 0, "lignes": ["Non décrit par le fichier."]}]},
    {"nom": "Document d'essai sans rien à relever",
     "identite": [["Format", "PDF 1.7"], ["Logiciel d'origine", "Logiciel de saisie (essai)"], ["Créé le", "1er avril 2000 à 12 h 00"], ["Taille", "10 Ko"], ["Pages", "2, de 210 × 297 mm"]],
     "rubriques": [
         {"titre": "Versions enregistrées", "compte": 1, "lignes": ["Version 1 : 1er avril 2000 à 12 h 00, 10 Ko."]},
         {"titre": "Zones recouvertes", "compte": 0, "lignes": ["Aucune."]}]},
]
TABLEAU = {"colonnes": ["Pièce", "Dossier", "Format", "Logiciel d'origine", "Créé le", "Modifié le", "Taille", "Pages", "Versions enregistrées",
                        "Zones recouvertes", "Calques éteints", "Textes affichés", "Lignes de texte invisible", "Images", "Annotations", "Ordre de lecture décrit"],
           "lignes": [["Document d'essai à trois enregistrements", "Essais - couches", "PDF 1.7", "Logiciel de saisie (essai)", "1er janvier 2000 à 12 h 00", "1er mars 2000 à 12 h 00", "100 Ko", 2, 3, 2, 1, 20, 5, 1, 1, "non"],
                      ["Document d'essai sans rien à relever", "Essais - texte", "PDF 1.7", "Logiciel de saisie (essai)", "1er avril 2000 à 12 h 00", "1er avril 2000 à 12 h 00", "10 Ko", 2, 1, 0, 0, 40, 0, 0, 0, "non"]]}

# Le cas des signes: ce qui entre, puis ce qui doit se relire. Les caracteres speciaux se construisent, ils ne se tapent pas.
SIGNES = "<&>" + chr(34) + chr(39)  # chevrons, esperluette, guillemet droit, apostrophe
CLOCHE = chr(7)
LIGNES_SIGNES = [
    ("Signes " + SIGNES + " et cloche" + CLOCHE + " retirée", "Signes " + SIGNES + " et cloche retirée"),
    ("Insécable" + chr(0xA0) + "« gardée »", "Insécable" + chr(0xA0) + "« gardée »"),
    (" Deux  espaces, une\ttabulation, des bords ", " Deux  espaces, une\ttabulation, des bords "),
    ("Première ligne\r\nseconde ligne", "Première ligne\nseconde ligne"),
    ("Nul" + chr(0) + ", échappement" + chr(0x1B) + ", demi-code" + chr(0xD800) + ", hors plan" + chr(0xFFFE) + ".", "Nul, échappement, demi-code, hors plan."),
    ("", ""),
    (100, "100"),
]
NOM_SIGNES = "Pièce " + SIGNES


def fiche_signes(relue: bool) -> dict:
    """La fiche du cas des signes, telle qu'elle entre ou telle qu'elle doit se relire."""
    sale = "" if relue else CLOCHE
    return {"nom": NOM_SIGNES + sale, "identite": [["Titre " + SIGNES, "Valeur " + SIGNES + sale], ["Vide", ""]],
            "rubriques": [{"titre": "Rubrique " + SIGNES, "compte": 7, "lignes": [paire[relue] for paire in LIGNES_SIGNES]},
                          {"titre": "Rubrique sans ligne", "compte": 0, "lignes": []}]}


def tableau_signes(relu: bool) -> dict:
    sale = "" if relu else CLOCHE
    return {"colonnes": ["Pièce", "Pages", "Remarque " + SIGNES], "lignes": [[NOM_SIGNES + sale, 3, "a" + sale + "b"]]}


# --------------------------------------------------------------- instruments

def essai(nom: str, defauts: list[str], precision: str = "") -> None:
    """Imprime le verdict d'un essai: OK s'il ne releve aucun defaut, ECHEC et ses defauts sinon."""
    if defauts:
        ECHECS.append(nom)
        print(f"ECHEC {nom} : " + " ; ".join(defauts))
    else:
        print(f"OK    {nom}" + (f" ({precision})" if precision else ""))


def q(nom: str) -> str:
    """« prefixe:local » en nom qualifie, comme xml.etree les ecrit."""
    prefixe, local = nom.split(":")
    return "{" + ESPACES[prefixe] + "}" + local


def brut_de(element: ET.Element) -> str:
    morceaux = [element.text or ""]
    for enfant in element:
        if enfant.tag == q("text:s"):
            morceaux.append(ESPACE * int(enfant.get(q("text:c"), "1")))
        elif enfant.tag == q("text:tab"):
            morceaux.append(TABULATION)
        elif enfant.tag == q("text:line-break"):
            morceaux.append(RETOUR)
        else:
            morceaux.append(brut_de(enfant))
        morceaux.append(enfant.tail or "")
    return "".join(morceaux)


def texte_de(element: ET.Element) -> str:
    """Le texte d'un paragraphe comme un lecteur OpenDocument le rend.

    Les blancs ecrits tels quels se fondent en une seule espace et tombent aux bords; seuls ceux
    que posent les balises sont gardes. Un export qui ecrirait deux espaces a la suite se verrait.
    """
    fondu = re.sub("[ \t\r\n]+", " ", brut_de(element)).strip(" ")
    return fondu.replace(ESPACE, " ").replace(TABULATION, "\t").replace(RETOUR, "\n")


def case_de(cellule: ET.Element) -> str:
    return "\n".join(texte_de(paragraphe) for paragraphe in cellule.findall(q("text:p")))


def lire(chemin: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(chemin) as archive:
        return {entree.filename: archive.read(entree) for entree in archive.infolist()}


def ecarts(nom: str, lu: list, attendu: list) -> list[str]:
    """Le premier ecart entre ce qui est relu et ce qui etait attendu; aucune ligne s'ils sont egaux."""
    if lu == attendu:
        return []
    for rang, (ici, la) in enumerate(zip(lu, attendu), 1):
        if ici != la:
            return [f"{nom}, élément {rang} : lu {ici!r:.160}, attendu {la!r:.160}"]
    return [f"{nom} : {len(lu)} éléments lus, {len(attendu)} attendus"]


def styles_orphelins(arbres: list[ET.Element]) -> list[str]:
    """Les styles, polices et pages cites quelque part et que le fichier ne declare pas."""
    declares, cites = set(), set()
    for racine in arbres:
        for element in racine.iter():
            for attribut, valeur in element.attrib.items():
                local = attribut.rsplit("}", 1)[-1]
                if attribut == q("style:name"):
                    declares.add(valeur)
                elif local.endswith("-name") and local != "display-name":
                    cites.add(valeur)
    return sorted(cites - declares)


# ----------------------------------------------------------------- structure

def structure(chemin: Path, mime: str) -> list[str]:
    """Les defauts de structure d'une archive OpenDocument; aucune ligne si elle est saine."""
    defauts: list[str] = []
    brut, type_attendu = chemin.read_bytes(), mime.encode("ascii")
    with zipfile.ZipFile(chemin) as archive:
        entrees = archive.infolist()
        contenus = {entree.filename: archive.read(entree) for entree in entrees}
        if archive.testzip() is not None:
            defauts.append("une entrée de l'archive est abîmée")
    if [entree.filename for entree in entrees] != ENTREES:
        defauts.append("entrées inattendues : " + ", ".join(entree.filename for entree in entrees))
    premiere = entrees[0]
    if premiere.filename != "mimetype" or contenus.get("mimetype") != type_attendu:
        defauts.append("la première entrée n'est pas le type attendu")
    if premiere.compress_type != zipfile.ZIP_STORED:
        defauts.append("mimetype est compressé")
    champ = struct.unpack("<H", brut[28:30])[0]  # longueur du champ supplementaire, dans l'en-tete local
    if brut[:4] != SIGNATURE or champ or premiere.extra or brut[30:38] != b"mimetype" or brut[38:38 + len(type_attendu)] != type_attendu:
        defauts.append("mimetype porte un champ supplémentaire, ou le type ne se lit pas à l'octet 38")
    arbres: dict[str, ET.Element] = {}
    for nom, octets in contenus.items():
        if nom.endswith(".xml"):
            try:
                arbres[nom] = ET.fromstring(octets)
            except ET.ParseError as erreur:
                defauts.append(f"{nom} ne se lit pas ({erreur})")
            if any(octet < 32 and octet not in (9, 10, 13) for octet in octets):
                defauts.append(f"{nom} porte un caractère de contrôle")
    if MANIFESTE in arbres:  # la norme veut que ni mimetype ni le manifeste ne s'y listent
        declares = {e.get(q("manifest:full-path")): e.get(q("manifest:media-type")) for e in arbres[MANIFESTE]}
        attendus = {"/": mime, **{nom: "text/xml" for nom in contenus if nom not in ("mimetype", MANIFESTE)}}
        if declares != attendus:
            defauts.append(f"le manifeste ne liste pas les fichiers de l'archive : {sorted(declares)}")
    orphelins = styles_orphelins([arbres[nom] for nom in ("content.xml", "styles.xml") if nom in arbres])
    return defauts + ([f"styles cités sans être déclarés : {orphelins}"] if orphelins else [])


def defauts_meta(chemin: Path) -> list[str]:
    """Ce que le fichier dit de lui-meme: un generateur neutre, une date de creation, et rien de plus."""
    defauts: list[str] = []
    contenus = lire(chemin)
    meta = ET.fromstring(contenus["meta.xml"])
    if meta.findtext(f".//{q('meta:generator')}") != GENERATEUR:
        defauts.append("générateur inattendu")
    try:
        age = (datetime.now() - datetime.fromisoformat(meta.findtext(f".//{q('meta:creation-date')}") or "")).total_seconds()
    except ValueError:
        age = -1.0
    if not 0 <= age < 600:
        defauts.append("date de création absente ou fausse")
    permis = {q("office:document-meta"), q("office:meta"), q("meta:generator"), q("dc:title"), q("meta:creation-date")}
    autres = sorted(element.tag.rsplit("}", 1)[-1] for element in meta.iter() if element.tag not in permis)
    if autres:
        defauts.append(f"meta.xml porte autre chose : {autres}")
    # Le nom d'utilisateur et le nom du poste ne s'impriment jamais: on dit seulement s'ils y sont.
    poste = {os.environ.get("USERNAME", ""), os.environ.get("COMPUTERNAME", ""), platform.node(), Path.home().name}
    tout = b"".join(contenus.values()).decode("utf-8", "replace").casefold()
    if any(len(nom) >= 3 and nom.casefold() in tout for nom in poste):
        defauts.append("un nom d'utilisateur ou de poste figure dans l'archive")
    return defauts


# ------------------------------------------------------------ document Writer

def releve_odt(chemin: Path) -> list[tuple[str, object]]:
    """Ce que dit le document, dans l'ordre: paragraphes, titres, tableaux et listes."""
    corps = ET.fromstring(lire(chemin)["content.xml"]).find(f"{q('office:body')}/{q('office:text')}")
    releve: list[tuple[str, object]] = []
    for bloc in corps:
        if bloc.tag == q("text:h"):
            releve.append((f"titre {bloc.get(q('text:outline-level'))}", texte_de(bloc)))
        elif bloc.tag == q("text:p"):
            releve.append(("paragraphe", texte_de(bloc)))
        elif bloc.tag == q("text:list"):
            releve.append(("liste", [texte_de(paragraphe) for paragraphe in bloc.iter(q("text:p"))]))
        elif bloc.tag == q("table:table"):
            releve.append(("tableau", [[case_de(c) for c in rangee] for rangee in bloc.iter(q("table:table-row"))]))
        else:
            releve.append(("inconnu", bloc.tag))
    return releve


def attendu_odt(fiches: list[dict], tableau: dict) -> list[tuple[str, object]]:
    """Ce que le document doit dire, calcule ici sans rien emprunter a l'export."""
    attendu: list[tuple[str, object]] = [("paragraphe", TITRE_ODT), ("paragraphe", SOUS_TITRE)]
    rangs = [tableau["colonnes"].index(nom) for nom in VUE if nom in tableau["colonnes"]]
    if rangs and tableau["lignes"]:
        vue = [[tableau["colonnes"][rang] for rang in rangs]] + [[str(ligne[rang]) for rang in rangs] for ligne in tableau["lignes"]]
        attendu += [("titre 1", "Vue d'ensemble"), ("tableau", vue)]
    elif not fiches:
        attendu.append(("paragraphe", "Aucune pièce."))
    for fiche in fiches:
        attendu.append(("titre 1", fiche["nom"]))
        if fiche["identite"]:
            attendu.append(("tableau", [list(paire) for paire in fiche["identite"]]))
        for rubrique in fiche["rubriques"]:
            attendu.append(("titre 2", f"{rubrique['titre']} ({rubrique['compte']})"))
            if rubrique["lignes"]:
                attendu.append(("liste", list(rubrique["lignes"])))
    return attendu


def forme_odt(chemin: Path) -> list[str]:
    """La mise en forme promise, lue dans les styles que le fichier declare."""
    contenus = lire(chemin)
    styles, contenu = ET.fromstring(contenus["styles.xml"]), ET.fromstring(contenus["content.xml"])
    par_nom = {style.get(q("style:name")): style for racine in (styles, contenu) for style in racine.iter(q("style:style"))}

    def propriete(style: str | None, bloc: str, attribut: str) -> str:
        proprietes = par_nom[style].find(q(bloc)) if style in par_nom else None
        return (proprietes.get(q(attribut)) if proprietes is not None else None) or ""

    defauts: list[str] = []
    page = styles.find(f".//{q('style:page-layout-properties')}")
    format_page = tuple(page.get(q(nom)) for nom in ("fo:page-width", "fo:page-height", "style:print-orientation")) if page is not None else ()
    if format_page != ("21cm", "29.7cm", "portrait"):
        defauts.append(f"la page n'est pas un A4 en portrait : {format_page}")
    if styles.find(f".//{q('style:footer')}//{q('text:page-number')}") is None:
        defauts.append("pas de numéro de page en pied de page")
    police = styles.find(f".//{q('style:default-style')}/{q('style:text-properties')}")
    if police is None or police.get(q("style:font-name")) != "Liberation Sans":
        defauts.append("la police par défaut n'est pas Liberation Sans")
    defauts += [f"{titre} n'est pas en gras" for titre in ("Title", "Heading_20_1", "Heading_20_2")
                if propriete(titre, "style:text-properties", "fo:font-weight") != "bold"]
    cases = list(contenu.iter(q("table:table-cell")))
    if not cases or any(not propriete(c.get(q("table:style-name")), "style:table-cell-properties", "fo:border").startswith("0.5pt solid") for c in cases):
        defauts.append("une case de tableau n'a pas sa bordure fine")
    entetes = [c for rangees in contenu.iter(q("table:table-header-rows")) for c in rangees.iter(q("table:table-cell"))]
    if not entetes or any(not propriete(c.get(q("table:style-name")), "style:table-cell-properties", "fo:background-color") for c in entetes):
        defauts.append("les en-têtes de tableau ne sont pas grisés")
    fiches = [titre for titre in contenu.iter(q("text:h")) if titre.get(q("text:outline-level")) == "1" and texte_de(titre) != "Vue d'ensemble"]
    if not fiches or any(propriete(t.get(q("text:style-name")), "style:paragraph-properties", "fo:break-before") != "page" for t in fiches):
        defauts.append("une fiche ne commence pas sur une page neuve")
    return defauts


def contenu_odt(chemin: Path, fiches: list[dict], tableau: dict) -> tuple[list[str], str]:
    """Les defauts du contenu relu, et le decompte de ce qui a ete relu."""
    releve = releve_odt(chemin)
    tableaux = [contenu for genre, contenu in releve if genre == "tableau"]
    noms = [texte for genre, texte in releve if genre == "titre 1" and texte != "Vue d'ensemble"]
    libelles = [rangee[0] for table in tableaux[1:] for rangee in table]
    lignes = [ligne for genre, contenu in releve if genre == "liste" for ligne in contenu]
    defauts = ecarts(chemin.name, releve, attendu_odt(fiches, tableau)) + forme_odt(chemin)
    # Les trois retrouvailles demandees, dites une a une: chaque nom, chaque libelle, chaque ligne.
    defauts += [f"nom absent : {fiche['nom']}" for fiche in fiches if fiche["nom"] not in noms]
    defauts += [f"libellé absent : {paire[0]}" for fiche in fiches for paire in fiche["identite"] if paire[0] not in libelles]
    defauts += [f"ligne absente : {ligne}" for fiche in fiches for r in fiche["rubriques"] for ligne in r["lignes"] if ligne not in lignes]
    if ABSENT in noms + libelles + lignes:
        defauts.append("le témoin absent est retrouvé")
    return defauts, f"{len(noms)} noms, {len(libelles)} libellés, {len(lignes)} lignes de rubrique"


# -------------------------------------------------------------- tableau Calc

def cellule_ods(cellule: ET.Element) -> tuple[str | None, object]:
    """Le type et la valeur d'une cellule; un nombre doit aussi s'afficher comme l'entier qu'il porte."""
    genre, texte = cellule.get(q("office:value-type")), case_de(cellule)
    if genre != "float":
        return genre, texte
    valeur = float(cellule.get(q("office:value"), "nan"))
    return (genre, valeur) if texte == f"{valeur:.0f}" else ("nombre mal affiché", texte)


def attendu_ods(fiches: list[dict], tableau: dict) -> dict[str, list]:
    """Les deux feuilles attendues, calculees ici sans rien emprunter a l'export."""
    def case(valeur: object) -> tuple[str | None, object]:
        if isinstance(valeur, int):
            return "float", float(valeur)
        return ("string", valeur) if valeur != "" else (None, "")

    largeur = max([len(tableau["colonnes"]), 1] + [len(ligne) for ligne in tableau["lignes"]])
    feuille = [[case(v) for v in list(ligne) + [""] * (largeur - len(ligne))] for ligne in [tableau["colonnes"], *tableau["lignes"]]]
    detail = [["Pièce", "Rubrique", "Ligne"]]
    for fiche in fiches:
        detail += [[fiche["nom"], "Identité", " : ".join(part for part in paire if part)] for paire in fiche["identite"]]
        for rubrique in fiche["rubriques"]:
            detail += [[fiche["nom"], rubrique["titre"], ligne] for ligne in rubrique["lignes"]]
    return {"Tableau": feuille, "Détail": [[case(v) for v in ligne] for ligne in detail]}


def forme_ods(racine: ET.Element) -> list[str]:
    """En-tetes en gras et largeurs de colonnes raisonnables, lus dans les styles declares."""
    par_nom = {style.get(q("style:name")): style for style in racine.iter(q("style:style"))}
    defauts: list[str] = []
    for table in racine.iter(q("table:table")):
        nom = table.get(q("table:name"))
        for cellule in table.find(q("table:table-header-rows")).iter(q("table:table-cell")):
            police = par_nom[cellule.get(q("table:style-name"))].find(q("style:text-properties"))
            if police is None or police.get(q("fo:font-weight")) != "bold":
                defauts.append(f"feuille {nom} : un en-tête n'est pas en gras")
        for colonne in table.findall(q("table:table-column")):
            largeur = par_nom[colonne.get(q("table:style-name"))].find(q("style:table-column-properties")).get(q("style:column-width"))
            if not 1.5 <= float(largeur.removesuffix("cm")) <= 15:
                defauts.append(f"feuille {nom} : colonne large de {largeur}")
    return defauts


def contenu_ods(chemin: Path, fiches: list[dict], tableau: dict) -> tuple[list[str], str]:
    """Les defauts du contenu relu, et le decompte de ce qui a ete relu."""
    racine = ET.fromstring(lire(chemin)["content.xml"])
    feuilles = {table.get(q("table:name")): [[cellule_ods(c) for c in rangee.findall(q("table:table-cell"))]
                                             for rangee in table.iter(q("table:table-row"))] for table in racine.iter(q("table:table"))}
    attendu = attendu_ods(fiches, tableau)
    defauts = [] if list(feuilles) == ["Tableau", "Détail"] else [f"feuilles : {list(feuilles)}"]
    for nom, rangees in attendu.items():
        defauts += ecarts(f"{chemin.name}, feuille {nom}", feuilles.get(nom, []), rangees)
    lignes = len(feuilles.get("Tableau", []))
    if lignes != len(tableau["lignes"]) + 1:
        defauts.append(f"la feuille Tableau a {lignes} lignes pour {len(tableau['lignes'])} pièces")
    nombres = sum(1 for rangee in feuilles.get("Tableau", []) for genre, _ in rangee if genre == "float")
    entiers = sum(1 for ligne in tableau["lignes"] for valeur in ligne if isinstance(valeur, int))
    if nombres != entiers:
        defauts.append(f"{nombres} cellules numériques pour {entiers} entiers")
    precision = f"{lignes} lignes au Tableau, {nombres} entiers numériques, {len(feuilles.get('Détail', []))} lignes au Détail"
    return defauts + forme_ods(racine), precision


# ---------------------------------------------------------------- cas tordus

def ecrire(dossier: Path, base: str, fiches: list, tableau: dict, noms: list[str]) -> tuple[Path, Path]:
    """Ecrit le document et le tableau d'un cas, sous deux noms distincts, et note ce qu'un lecteur doit y lire."""
    odt, ods = dossier / f"{base}_document.odt", dossier / f"{base}_tableau.ods"
    exports_odf.ecrire_odt(odt, TITRE_ODT, SOUS_TITRE, fiches, tableau)
    exports_odf.ecrire_ods(ods, TITRE_ODS, SOUS_TITRE, fiches, tableau)
    PRODUITS.extend([(odt, [TITRE_ODT, SOUS_TITRE, *noms]), (ods, [TITRE_ODS, SOUS_TITRE, *noms])])
    return odt, ods


def cas(dossier: Path, base: str, fiches: list, tableau: dict, relues: list | None = None, relu: dict | None = None) -> list[str]:
    """Ecrit les deux fichiers d'un cas tordu; rend leurs defauts de structure et de contenu relu."""
    relues, relu = (fiches if relues is None else relues), (relu or tableau)
    odt, ods = ecrire(dossier, base, fiches, tableau, [fiche["nom"] for fiche in relues])
    return (structure(odt, exports_odf.MIME_ODT) + structure(ods, exports_odf.MIME_ODS)
            + ecarts(odt.name, releve_odt(odt), attendu_odt(relues, relu)) + contenu_ods(ods, relues, relu)[0])


def temoins(dossier: Path) -> list[str]:
    """Les instruments, sur des cas dont la reponse est connue: ils doivent savoir dire non."""
    defauts: list[str] = []
    for mauvais in ("<a>&</a>", "<a>" + CLOCHE + "</a>"):
        try:
            ET.fromstring(mauvais)
            defauts.append("un XML mal formé est accepté")
        except ET.ParseError:
            pass
    orphelin = ET.fromstring(f'<a xmlns:text="{ESPACES["text"]}" text:style-name="Absent"/>')
    if styles_orphelins([orphelin]) != ["Absent"]:
        defauts.append("un style non déclaré n'est pas vu")
    fondu = ET.fromstring(f'<p xmlns:text="{ESPACES["text"]}"> a  b<text:s text:c="2"/>c </p>')
    if texte_de(fondu) != "a b  c":
        defauts.append("la relecture ne fond pas les blancs comme un lecteur OpenDocument")
    faux = dossier / "temoin_mal_range.odt"
    with zipfile.ZipFile(faux, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", "<a/>")
        archive.writestr("mimetype", exports_odf.MIME_ODT)
    if len(structure(faux, exports_odf.MIME_ODT)) < 3:
        defauts.append("une archive mal rangée passe pour saine")
    return defauts


def refus(dossier: Path, odt: Path, ods: Path) -> list[str]:
    """Ecrire sur un fichier qui existe: l'erreur attendue, le fichier intact, aucun provisoire laisse."""
    defauts, avant = [], (odt.read_bytes(), ods.read_bytes())
    for ecrire_un, chemin in ((exports_odf.ecrire_odt, odt), (exports_odf.ecrire_ods, ods)):
        try:
            ecrire_un(chemin, "Autre titre", SOUS_TITRE, [], {"colonnes": [], "lignes": []})
            defauts.append(f"{chemin.suffix} : aucun refus")
        except FileExistsError:
            pass
    if (odt.read_bytes(), ods.read_bytes()) != avant:
        defauts.append("le fichier qui existait a changé")
    return defauts + [f"provisoire laissé : {reste.name}" for reste in dossier.iterdir() if reste.name.endswith(".partiel")]


def panne(dossier: Path) -> list[str]:
    """Une ecriture qui echoue au dernier geste ne laisse ni fichier ni provisoire."""
    defauts: list[str] = []
    vrai = exports_odf._nommer

    def en_panne(provisoire: Path, chemin: Path) -> None:
        if not provisoire.is_file() or provisoire.parent != chemin.parent or not zipfile.is_zipfile(provisoire):
            defauts.append("le provisoire n'était pas écrit en entier, à côté du fichier")
        raise OSError("panne simulee")

    exports_odf._nommer = en_panne
    try:
        for ecrire_un, nom in ((exports_odf.ecrire_odt, "panne.odt"), (exports_odf.ecrire_ods, "panne.ods")):
            try:
                ecrire_un(dossier / nom, TITRE_ODT, SOUS_TITRE, FICHES, TABLEAU)
                defauts.append(f"{nom} : la panne n'a pas été levée")
            except OSError:
                pass
    finally:
        exports_odf._nommer = vrai
    return defauts + [f"reste : {reste.name}" for reste in dossier.iterdir() if reste.name.startswith("panne")]


def cas_tordus(dossier: Path, odt: Path, ods: Path) -> None:
    vide = {"colonnes": [], "lignes": []}
    seule = {"nom": "Pièce sans rubrique", "identite": [["Format", "PDF 1.4"]], "rubriques": []}
    essai("cas tordu : fiche sans rubrique", cas(dossier, "sans_rubrique", [seule], {"colonnes": ["Pièce", "Pages"], "lignes": [[seule["nom"], 1]]}))
    essai("cas tordu : signes et caractère de contrôle",
          cas(dossier, "signes", [fiche_signes(False)], tableau_signes(False), [fiche_signes(True)], tableau_signes(True)))
    essai("cas tordu : tableau vide", cas(dossier, "tableau_vide", FICHES, vide))
    essai("cas tordu : aucune fiche", cas(dossier, "aucune_fiche", [], {"colonnes": TABLEAU["colonnes"], "lignes": []})
          + cas(dossier, "rien_du_tout", [], vide))
    long = ("Document d'essai " * 12)[:200]
    longue = {"nom": long, "identite": [["Format", "PDF 1.7"]], "rubriques": [{"titre": "Versions enregistrées", "compte": 1, "lignes": ["Version 1."]}]}
    essai("cas tordu : nom de 200 caractères", ([] if len(long) == 200 else [f"le nom d'essai fait {len(long)} caractères"])
          + cas(dossier, "nom_long", [longue], {"colonnes": ["Pièce", "Pages"], "lignes": [[long, 1]]}))
    essai("cas tordu : refus d'écraser", refus(dossier, odt, ods))
    essai("cas tordu : panne sans reste", panne(dossier))


def jouer(dossier: Path) -> None:
    """Tous les essais, dans ce dossier. Chaque fichier ecrit reste note dans PRODUITS, avec ce qu'un lecteur doit y lire."""
    essai("témoins des instruments", temoins(dossier))
    odt, ods = ecrire(dossier, "nominal", FICHES, TABLEAU, [fiche["nom"] for fiche in FICHES])
    essai("structure du .odt", structure(odt, exports_odf.MIME_ODT))
    essai("structure du .ods", structure(ods, exports_odf.MIME_ODS))
    essai("méta sans auteur ni poste", defauts_meta(odt) + defauts_meta(ods))
    essai("contenu relu du .odt", *contenu_odt(odt, FICHES, TABLEAU))
    essai("contenu relu du .ods", *contenu_ods(ods, FICHES, TABLEAU))
    cas_tordus(dossier, odt, ods)


def principal() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # un signe que la console ne sait pas ecrire ne fait pas tomber le script
    dossier = Path(tempfile.mkdtemp(prefix="pdforensics-exports-"))
    try:
        jouer(dossier)
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    print("NON FAIT ouverture par LibreOffice : elle ne se fait que sur demande, par essais_exports_ouverture.py.")
    print("VERDICT :", "tout passe (1 non fait)" if not ECHECS else f"{len(ECHECS)} échec(s) : " + " ; ".join(ECHECS))
    return 1 if ECHECS else 0


if __name__ == "__main__":
    sys.exit(principal())

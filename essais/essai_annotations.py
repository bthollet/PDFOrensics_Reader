# -*- coding: utf-8 -*-
"""Decrire les annotations de pieces REELLES, en ne rendant que des NOMBRES.

Meme regle que essai_pieces_reelles.py: lecture en place, en memoire, rien
d'ecrit, et une sortie faite d'entiers, de mesures en points et d'un
vocabulaire ferme (les genres et les modes de melange sont ceux de la norme
PDF). Jamais un nom de fichier, un chemin, le texte d'une annotation, son
auteur, une date, ni le message d'une erreur.

  python -B essais/essai_annotations.py --liste FICHIER
  python -B essais/essai_annotations.py --dossier D --combien 12 [--graine 7]

Une ligne par annotation. Ce qu'elle dit:
- genre, drapeaux, largeur et hauteur de son cadre (en points);
- dessin_propre: l'annotation porte-t-elle son propre dessin (0 non, 1 oui,
  2 plusieurs etats). Sans dessin propre, chaque lecteur invente le sien;
- boite: largeur et hauteur de ce dessin; matrice: 1 s'il est transforme;
- quads: nombre de quadrilateres, taille de leur reunion, ordre de leurs coins;
- traits et points d'un trace a main levee; epaisseur; opacite; melange;
- operateurs du dessin: courbes, rectangles, remplissages, contours;
- couleur declaree (trois composantes, en centiemes);
- teinte: part du cadre que l'annotation change sur l'image de la page, et le
  rectangle touche, en centiemes du cadre (gauche, haut, droite, bas);
- refait: part du cadre qui change si la bibliotheque redessine elle-meme
  l'annotation. 0 = le dessin du fichier et celui de la bibliotheque se valent.
"""
from __future__ import annotations

import argparse
import re
import sys

import numpy as np
import pymupdf

from essai_pieces_reelles import canal_garde, pieces

GENRES = ("Text", "FreeText", "Highlight", "Underline", "Squiggly", "StrikeOut", "Stamp", "Square", "Circle", "Line",
          "Polygon", "PolyLine", "Ink", "Redact", "FileAttachment", "Link", "Widget", "Popup", "Caret", "Sound", "Watermark")
MELANGES = ("Normal", "Compatible", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "ColorDodge", "ColorBurn",
            "HardLight", "SoftLight", "Difference", "Exclusion", "Hue", "Saturation", "Color", "Luminosity")
COLONNES = ("page", "genre", "drapeaux", "cadre_l", "cadre_h", "dessin_propre", "boite_l", "boite_h", "matrice",
            "quads", "quads_l", "quads_h", "ordre", "traits", "points", "epaisseur", "opacite", "melange",
            "courbes", "rectangles", "remplissages", "contours", "couleur", "teinte", "touche", "refait")


def nombres(texte: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", texte or "")]


def cle(doc, xref: int, nom: str) -> str:
    genre, valeur = doc.xref_get_key(xref, nom)
    return "" if genre == "null" else valeur


def ordre_des_coins(q: list[float]) -> str:
    """Comment les quatre coins du premier quadrilatere sont ranges (repere du fichier, y vers le haut)."""
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = [(q[i], q[i + 1]) for i in range(0, 8, 2)]
    haut12, haut34 = (y1 + y2) / 2, (y3 + y4) / 2
    if abs(y1 - y2) < 0.5 and abs(y3 - y4) < 0.5:
        if haut12 > haut34:
            return "haut puis bas" + (", croise" if (x1 < x2) != (x3 < x4) else "")
        return "bas puis haut" + (", croise" if (x1 < x2) != (x3 < x4) else "")
    if abs(x1 - x2) < 0.5 and abs(x3 - x4) < 0.5:
        return "par colonnes"
    return "incline"


def dessin(doc, xref: int) -> dict:
    """Ce que le dessin propre de l'annotation contient, sans jamais le citer."""
    rendu = {"dessin_propre": 0}
    genre, valeur = doc.xref_get_key(xref, "AP/N")
    if genre == "null":
        return rendu
    if genre != "xref":
        rendu["dessin_propre"] = 2
        return rendu
    flux = int(valeur.split()[0])
    rendu["dessin_propre"] = 1
    boite = nombres(cle(doc, flux, "BBox"))
    if len(boite) == 4:
        rendu["boite_l"], rendu["boite_h"] = round(abs(boite[2] - boite[0]), 1), round(abs(boite[3] - boite[1]), 1)
    matrice = nombres(cle(doc, flux, "Matrix"))
    rendu["matrice"] = int(len(matrice) == 6 and [round(v, 3) for v in matrice] != [1, 0, 0, 1, 0, 0])
    try:
        contenu = (doc.xref_stream(flux) or b"").decode("latin-1")
    except Exception:  # noqa: BLE001
        contenu = ""
    sans_chaines = re.sub(r"\((?:\\.|[^\\)])*\)", "()", contenu)
    mots = sans_chaines.split()
    rendu["courbes"] = sum(1 for m in mots if m in ("c", "v", "y"))
    rendu["rectangles"] = mots.count("re")
    rendu["remplissages"] = sum(1 for m in mots if m in ("f", "F", "f*", "B", "B*", "b", "b*"))
    rendu["contours"] = sum(1 for m in mots if m in ("S", "s", "B", "B*", "b", "b*"))
    objet = doc.xref_object(flux, compressed=True)
    ressources = cle(doc, flux, "Resources")
    if ressources.endswith(" 0 R"):
        objet += doc.xref_object(int(ressources.split()[0]), compressed=True)
    for reference in re.findall(r"(\d+) 0 R", objet)[:12]:
        try:
            objet += doc.xref_object(int(reference), compressed=True)
        except Exception:  # noqa: BLE001
            continue
    melanges = sorted({m for m in re.findall(r"/BM\s*/(\w+)", objet) if m in MELANGES})
    rendu["melange"] = "+".join(melanges) or "aucun"
    return rendu


def gris(page) -> np.ndarray:
    image = page.get_pixmap(colorspace=pymupdf.csRGB, alpha=False)
    return np.frombuffer(image.samples, np.uint8).reshape(image.height, image.width, 3).astype(np.int16)


def part_changee(avant: np.ndarray, apres: np.ndarray, cadre, page) -> tuple[float, str]:
    """Part du cadre qui change, et le rectangle touche en centiemes du cadre."""
    r = (pymupdf.Rect(cadre) * page.rotation_matrix).normalize() & page.rect
    x0, y0, x1, y1 = (max(0, int(r.x0)), max(0, int(r.y0)), int(r.x1 + 0.999), int(r.y1 + 0.999))
    if avant.shape != apres.shape or x1 <= x0 or y1 <= y0:
        return 0.0, ""
    change = (np.abs(avant[y0:y1, x0:x1] - apres[y0:y1, x0:x1]).max(axis=2) > 10)
    if not change.any():
        return 0.0, ""
    lignes_, colonnes = np.nonzero(change)
    haut, large = change.shape
    touche = "/".join(str(round(100 * v)) for v in (colonnes.min() / large, lignes_.min() / haut,
                                                    (colonnes.max() + 1) / large, (lignes_.max() + 1) / haut))
    return round(float(change.mean()), 3), touche


def decrire(chemin) -> list[dict]:
    octets = chemin.read_bytes()
    doc = pymupdf.open(stream=octets, filetype="pdf")
    if doc.needs_pass:
        return [{"genre": "refus : mot de passe"}]
    lignes = []
    for n in range(doc.page_count):
        page = doc[n]
        xrefs = [a.xref for a in page.annots() or []]
        if not xrefs:
            continue
        avec = gris(page)
        for xref in xrefs:
            ligne = {"page": n + 1}
            sous_type = cle(doc, xref, "Subtype").lstrip("/")
            ligne["genre"] = sous_type if sous_type in GENRES else "autre"
            ligne["drapeaux"] = int((nombres(cle(doc, xref, "F")) or [0])[0])
            cadre = nombres(cle(doc, xref, "Rect"))
            if len(cadre) == 4:
                ligne["cadre_l"], ligne["cadre_h"] = round(abs(cadre[2] - cadre[0]), 1), round(abs(cadre[3] - cadre[1]), 1)
            ligne.update(dessin(doc, xref))
            quads = nombres(cle(doc, xref, "QuadPoints"))
            ligne["quads"] = len(quads) // 8
            if len(quads) >= 8:
                xs, ys = quads[0::2], quads[1::2]
                ligne["quads_l"], ligne["quads_h"] = round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)
                ligne["ordre"] = ordre_des_coins(quads[:8])
            encre = cle(doc, xref, "InkList")
            if encre:
                ligne["traits"] = encre.count("[") - 1
                ligne["points"] = len(nombres(encre)) // 2
            epaisseur = nombres(cle(doc, xref, "BS/W")) or nombres(cle(doc, xref, "Border"))[2:3]
            ligne["epaisseur"] = round(epaisseur[0], 2) if epaisseur else ""
            opacite = nombres(cle(doc, xref, "CA"))
            ligne["opacite"] = round(opacite[0], 2) if opacite else ""
            ligne["couleur"] = "/".join(str(round(100 * v)) for v in nombres(cle(doc, xref, "C"))[:4])
            # ce que l'annotation change sur l'image, puis ce que la bibliotheque dessinerait a sa place
            seul = pymupdf.open(stream=octets, filetype="pdf")
            feuille = seul[n]
            cible = None
            for annotation in list(feuille.annots() or []):
                if annotation.xref == xref:
                    cible = annotation
            if cible is not None:
                zone = pymupdf.Rect(cible.rect)
                refaite = pymupdf.open(stream=octets, filetype="pdf")
                for annotation in refaite[n].annots() or []:
                    if annotation.xref == xref:
                        try:
                            refaite.xref_set_key(xref, "AP", "null")
                            annotation.update()
                            zone |= annotation.rect
                        except Exception:  # noqa: BLE001
                            pass
                feuille.delete_annot(cible)
                sans = gris(feuille)
                ligne["teinte"], ligne["touche"] = part_changee(sans, avec, zone, page)
                ligne["refait"] = part_changee(avec, gris(refaite[n]), zone, page)[0]
            lignes.append(ligne)
    return lignes


def main() -> int:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("--liste")
    lecteur.add_argument("--dossier")
    lecteur.add_argument("--combien", type=int, default=0)
    lecteur.add_argument("--graine", type=int, default=7)
    arguments = lecteur.parse_args()
    if not arguments.liste and not arguments.dossier:
        lecteur.error("--liste ou --dossier")
    canal = canal_garde()

    def dire(texte: str) -> None:
        canal.write(texte + "\n")
        canal.flush()

    try:
        a_lire = pieces(arguments)
    except Exception as erreur:  # noqa: BLE001
        dire("ARRET : la liste des pièces ne s'établit pas (" + type(erreur).__name__ + ").")
        return 2
    dire(" | ".join(["piece", "annotation"] + list(COLONNES)))
    total = 0
    for rang, chemin in enumerate(a_lire, 1):
        try:
            lignes = decrire(chemin)
        except BaseException as erreur:  # noqa: BLE001
            dire(f"{rang} | PANNE : {type(erreur).__name__}")
            continue
        for numero, ligne in enumerate(lignes, 1):
            total += 1
            dire(" | ".join([str(rang), str(numero)] + [str(ligne.get(colonne, "")) for colonne in COLONNES]))
    dire(f"BILAN : {len(a_lire)} pièces, {total} annotations décrites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Les annotations d'une page, et celles que le fichier laisse SANS dessin propre.

Une annotation peut etre decrite par le fichier sans y etre dessinee: chaque
lecteur PDF invente alors son dessin. La bibliotheque imite un lecteur du
commerce et arrondit les bouts d'un surlignage; sur un grand quadrilatere,
cela donne un tonneau qui deborde de ce que le fichier declare. La lecture
dessine donc elle-meme, et au plus sobre: les quadrilateres tels qu'ils sont
ecrits, dans la couleur declaree - et elle dit que l'annotation n'avait pas
de dessin propre.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pymupdf

from .lecture_page import ECHELLE_ENCRE, POINTS_MAX, Repere, milieu, nom_de_couleur, noyau_uni, propre, texte_dessous

GENRES = {"Text": "note", "FreeText": "texte libre", "Highlight": "surlignage", "Underline": "soulignement",
          "StrikeOut": "barré", "Squiggly": "soulignement ondulé", "Stamp": "tampon", "Square": "rectangle",
          "Circle": "ellipse", "Line": "trait", "Polygon": "polygone", "PolyLine": "ligne brisée",
          "Ink": "tracé à main levée", "Redact": "zone de biffage non appliquée", "FileAttachment": "pièce jointe",
          "Link": "lien", "Widget": "champ de formulaire", "Popup": "bulle", "Caret": "marque d'insertion"}
SANS_DESSIN_ATTENDU = ("/Popup", "/Link", "/Widget")   # ces genres n'ont d'ordinaire pas de dessin propre


def nombres(texte: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", texte or "")]


def annotations(page, sans_dessin: set[int]) -> list[dict]:
    rendu = []
    for annotation in page.annots() or []:
        info = annotation.info
        genre = GENRES.get(annotation.type[1], annotation.type[1])
        if annotation.xref in sans_dessin:
            genre += " sans dessin propre"
        rendu.append({"bbox": tuple(annotation.rect), "genre": genre, "contenu": propre(info.get("content") or "")})
    return rendu


def _image(page, echelle: float, annotations_: bool) -> np.ndarray:
    rendu = page.get_pixmap(matrix=pymupdf.Matrix(echelle, echelle), colorspace=pymupdf.csRGB, alpha=False, annots=annotations_)
    return np.frombuffer(rendu.samples, np.uint8).reshape(rendu.height, rendu.width, 3).astype(np.int16)


def zones_sous_annotation(page, rep: Repere, ecrits: list[dict], dessins: list[dict], images: list[dict]) -> list[dict]:
    """Chaque annotation, ou champ, sous lequel la page porte de l'encre que son image ne montre plus.

    Une annotation se pose par-dessus la page et s'en retire: ce qu'elle cache
    n'a pas disparu du fichier. Le constat ne depend ni du genre de
    l'annotation ni de ce qu'il y a dessous - texte, traces, image: la page
    est dessinee avec ses annotations et sans elles. Il y a masque quand, dans
    le cadre de l'annotation, de l'encre presente sans elle se trouve sous une
    teinte unie avec elle. Un surlignage laisse voir le texte: ce n'est pas un
    masque. Un carre plein pose sur du vide ne cache rien: ce n'en est pas un.
    """
    posees = [{"rect": tuple(a.rect), "genre": GENRES.get(a.type[1], a.type[1])} for a in page.annots() or []]
    posees += [{"rect": tuple(c.rect), "genre": "champ de formulaire"} for c in page.widgets() or []]
    if not posees:
        return []
    echelle = min(ECHELLE_ENCRE, (POINTS_MAX / max(rep.large * rep.haut, 1)) ** 0.5)
    try:
        avec, sans = _image(page, echelle, True), _image(page, echelle, False)
    except Exception:  # noqa: BLE001 - une page qui ne se dessine pas ne dit aucune zone
        return []
    if avec.shape != sans.shape:
        return []
    haut, large = avec.shape[:2]
    zones = []
    for posee in posees:
        x0, y0, x1, y1 = (v * echelle for v in rep.vue(posee["rect"]))
        gx, gy, hx, hy = max(0, int(x0)), max(0, int(y0)), min(large, int(x1) + 1), min(haut, int(y1) + 1)
        if hx - gx < 2 or hy - gy < 2:
            continue
        dessus, dessous = avec[gy:hy, gx:hx], sans[gy:hy, gx:hx]
        encre = np.abs(dessous - np.median(dessous.reshape(-1, 3), axis=0)).max(axis=2) > 30        # ce que la page porte la, sans l'annotation
        teinte = np.median(dessus.reshape(-1, 3), axis=0)
        cachee = encre & (np.abs(dessus - teinte).max(axis=2) <= 30) & (np.abs(dessus - dessous).max(axis=2) > 12)
        if int(cachee.sum()) < 40 or cachee.sum() < 0.5 * encre.sum():
            continue
        cadre = posee["rect"]

        def dedans(boite, cadre=cadre) -> bool:
            x, y = milieu(boite)
            return cadre[0] <= x <= cadre[2] and cadre[1] <= y <= cadre[3]

        textes = []
        for ecrit in ecrits:
            prises = [l for l in ecrit["lettres"] if dedans(l[3]) and noyau_uni(avec, rep.vue(l[3]), echelle)]
            if prises:
                textes.append(texte_dessous(rep, ecrit, prises))
        zones.append({"rect": tuple(round(v, 1) for v in cadre), "bbox": rep.fraction(cadre),
                      "couleur": nom_de_couleur(tuple(float(v) / 255 for v in teinte)), "nature": "annotation", "genre": posee["genre"],
                      "dessous": textes, "dessus": [], "traces": sum(1 for d in dessins if dedans(d["bbox"])),
                      "images": sum(1 for i in images if dedans(i["bbox"]))})
    return zones


def dessins_litteraux(doc) -> set[int]:
    """Rend les annotations que le fichier laisse sans dessin propre, et dessine les surlignages a la lettre.

    A appeler AVANT tout chargement de page: une page chargee recoit de la
    bibliotheque un dessin invente, qui ne se distingue plus d'un dessin propre.
    """
    sans = set()
    for n in range(doc.page_count):
        try:
            genre, valeur = doc.xref_get_key(doc.page_xref(n), "Annots")
            if genre == "xref":
                valeur = doc.xref_object(int(valeur.split()[0]), compressed=True)
            elif genre != "array":
                continue
            for reference in re.findall(r"(\d+) 0 R", valeur):
                xref = int(reference)
                if doc.xref_get_key(xref, "AP")[0] != "null":
                    continue
                sous_type = doc.xref_get_key(xref, "Subtype")[1]
                if sous_type in SANS_DESSIN_ATTENDU:
                    continue
                sans.add(xref)
                if sous_type == "/Highlight":
                    _surlignage_litteral(doc, xref)
        except Exception:  # noqa: BLE001 - une page dont les annotations ne se lisent pas garde le dessin de la bibliotheque
            continue
    return sans


def _surlignage_litteral(doc, xref: int) -> None:
    quads = nombres(doc.xref_get_key(xref, "QuadPoints")[1])
    genre, valeur = doc.xref_get_key(xref, "C")
    couleur = [1.0, 1.0, 0.0] if genre == "null" else nombres(valeur)
    operateur = {1: "g", 3: "rg", 4: "k"}.get(len(couleur))
    if len(quads) < 8 or not operateur:
        return
    opacite = (nombres(doc.xref_get_key(xref, "CA")[1]) or [1.0])[0]
    chemins = []
    for i in range(0, len(quads) - 7, 8):
        coins = [(quads[i + j], quads[i + j + 1]) for j in range(0, 8, 2)]
        cx, cy = sum(c[0] for c in coins) / 4, sum(c[1] for c in coins) / 4
        coins.sort(key=lambda c: math.atan2(c[1] - cy, c[0] - cx))      # quel que soit l'ordre ou le fichier range les coins
        chemins.append(" ".join(f"{x:.3f} {y:.3f} {'m' if j == 0 else 'l'}" for j, (x, y) in enumerate(coins)) + " h")
    cadre = nombres(doc.xref_get_key(xref, "Rect")[1])
    xs, ys = quads[0::2] + cadre[0::2][:2], quads[1::2] + cadre[1::2][:2]
    boite = f"[{min(xs):.3f} {min(ys):.3f} {max(xs):.3f} {max(ys):.3f}]"
    flux = doc.get_new_xref()
    doc.update_object(flux, f"<</Type/XObject/Subtype/Form/FormType 1/BBox{boite}/Matrix[1 0 0 1 0 0]"
                            f"/Resources<</ExtGState<</H<</Type/ExtGState/BM/Multiply/CA {opacite:.3f}/ca {opacite:.3f}>>>>>>>>")
    doc.update_stream(flux, ("/H gs " + " ".join(f"{v:.4f}" for v in couleur) + f" {operateur} " + " ".join(chemins) + " f").encode())
    doc.xref_set_key(xref, "Rect", boite)
    doc.xref_set_key(xref, "AP", f"<</N {flux} 0 R>>")

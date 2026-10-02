# -*- coding: utf-8 -*-
"""Ce que la page ne montre pas: une piece fabriquee par MECANISME, a reponse connue.

L'axe eprouve: la maniere dont un fichier peut poser quelque chose sur un
texte. Ce qui doit rester vrai le long de l'axe: une zone n'est dite
« recouverte » que si l'image de la page ne montre plus le texte. Chaque cas
est donc double - ce qui cache, et ce qui y ressemble sans rien cacher:

  ne cache pas            aplat rogne ailleurs, aplat en mode de melange, aplat
                          transparent, filets d'un tableau traces d'un seul
                          geste, coin du rectangle d'une ellipse
  cache                   aplat franc, image, ellipse pleine, aplat sous un
                          texte reecrit
  ne se montre pas        mode invisible, couleur du fond, hors de la page

S'y ajoutent: le sens d'ecriture (un tableau couche sur une page tournee), les
espaces d'une ligne ecrite sans espaces, le surlignage sans dessin propre, et
la page qui n'a pas besoin d'etre comparee a son image.

  python -B essais/essais_caches.py

Tout est fabrique dans un dossier temporaire, puis supprime.
"""
from __future__ import annotations

import base64
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pymupdf

sys.dont_write_bytecode = True  # meme lance sans -B, rien ne s'ecrit a cote des sources
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # le paquet est a cote du dossier des essais

from pdforensics import lecture_page, lecture_pdf  # noqa: E402

ECHECS: list[str] = []
HAUT = 842
TRAVAIL: Path = Path(".")
RANG = [0]


def essai(nom: str, vrai: bool, detail: object = "") -> None:
    print(("OK    " if vrai else "ECHEC ") + nom + (f" : {detail}" if detail != "" else ""))
    if not vrai:
        ECHECS.append(nom)


def page_neuve(texte: str = "Ligne fabriquee sous ce qui est pose", **options):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=HAUT)
    page.insert_text((60, 200), texte, fontsize=12, **options)
    return doc, page


def zone_du_texte(page) -> pymupdf.Rect:
    span = page.get_texttrace()[0]
    return pymupdf.Rect(span["bbox"]) + (-2, -2, 2, 2)


DEGRADE = ("<</ShadingType 2/ColorSpace/DeviceRGB/Coords[0 0 595 0]/Function<</FunctionType 2/Domain[0 1]"
           "/C0[1 1 0.8]/C1[0.8 0.9 1]/N 1>>/Extend[true true]>>")
MELANGE = "<</Type/ExtGState/BM/Multiply>>"


def brut(doc, page, operateurs: str, etat: str = "", degrade: str = "") -> None:
    """Ajoute des operateurs PDF a la fin de la page; `etat` est l'etat graphique /GX, `degrade` le degrade /Sh0."""
    flux = doc.get_new_xref()
    doc.update_object(flux, "<<>>")
    doc.update_stream(flux, operateurs.encode())
    doc.xref_set_key(page.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in page.get_contents() + [flux]) + "]")
    for nom, objet in (("ExtGState/GX", etat), ("Shading/Sh0", degrade)):
        if objet:
            neuf = doc.get_new_xref()
            doc.update_object(neuf, objet)
            genre, valeur = doc.xref_get_key(page.xref, "Resources")
            cible = int(valeur.split()[0]) if genre == "xref" else page.xref
            doc.xref_set_key(cible, ("" if genre == "xref" else "Resources/") + nom, f"{neuf} 0 R")


def re(zone: pymupdf.Rect) -> str:
    """Un rectangle de la page (y vers le bas) en operateur du fichier (y vers le haut)."""
    return f"{zone.x0:.2f} {HAUT - zone.y1:.2f} {zone.width:.2f} {zone.height:.2f} re"


def lire(doc) -> tuple[lecture_pdf.Lecture, dict]:
    RANG[0] += 1
    chemin = TRAVAIL / f"cas {RANG[0]}.pdf"
    doc.save(chemin)
    lecture = lecture_pdf.Lecture(chemin)
    return lecture, lecture.faits()["pages"][0]


def natures(page: dict) -> list[tuple]:
    return [(e["nature"], e.get("cause", "")) for e in page["elements"] if e["nature"] in ("texte", "invisible")]


def ne_cache_pas() -> None:
    doc, page = page_neuve()
    brut(doc, page, f"q 400 700 30 30 re W n 1 0 0 rg 0 0 595 {HAUT} re f Q")
    lecture, lue = lire(doc)
    trace = [e for e in lue["elements"] if e["nature"] == "trace"]
    essai("un aplat pleine page rogné ailleurs ne recouvre rien", lue["caches"] == [] and natures(lue) == [("texte", "")], lue["caches"])
    essai("son tracé est ramené à ce que la découpe en laisse voir", len(trace) == 1 and trace[0]["bbox"][2] - trace[0]["bbox"][0] < 0.06, trace)

    doc, page = page_neuve()
    brut(doc, page, f"q /GX gs 1 1 0 rg {re(zone_du_texte(page))} f Q", "<</Type/ExtGState/BM/Multiply>>")
    essai("un aplat en mode de mélange ne recouvre rien", lire(doc)[1]["caches"] == [])

    doc, page = page_neuve()
    brut(doc, page, f"q /GX gs 0 0 0 rg {re(zone_du_texte(page))} f Q", "<</Type/ExtGState/ca 0.35>>")
    essai("un aplat transparent ne recouvre rien", lire(doc)[1]["caches"] == [])

    # Un aplat que rien, dans sa description, ne distingue d'un aplat franc - mais qu'un masque efface.
    # Seule l'image le sait: c'est le cas qui tombe si la lecture s'en remet a la geometrie.
    doc, page = page_neuve()
    masque = doc.get_new_xref()
    doc.update_object(masque, f"<</Type/XObject/Subtype/Form/BBox[0 0 595 {HAUT}]/Group<</S/Transparency/CS/DeviceGray>>>>")
    doc.update_stream(masque, f"0 g 0 0 595 {HAUT} re f".encode())
    brut(doc, page, f"q /GX gs 0 0 0 rg {re(zone_du_texte(page))} f Q", f"<</Type/ExtGState/SMask<</Type/Mask/S/Luminosity/G {masque} 0 R>>>>")
    lecture, lue = lire(doc)
    essai("un aplat qu'un masque efface ne recouvre rien : l'image le dit, la géométrie ne le sait pas",
          lue["caches"] == [] and natures(lue) == [("texte", "")] and lecture.analyse(1, 0)["comparee"] is True, lue["caches"])

    def filets(z: pymupdf.Rect) -> str:
        cadre = [pymupdf.Rect(z.x0, z.y0 - 1, z.x1, z.y0), pymupdf.Rect(z.x0, z.y1, z.x1, z.y1 + 1),
                 pymupdf.Rect(z.x0 - 1, z.y0 - 1, z.x0, z.y1 + 1), pymupdf.Rect(z.x1, z.y0 - 1, z.x1 + 1, z.y1 + 1)]
        return "0 0 0 rg " + " ".join(re(f) for f in cadre) + " f"

    doc, page = page_neuve()
    brut(doc, page, filets(zone_du_texte(page)))
    lecture, lue = lire(doc)
    essai("les filets d'un tableau, tracés d'un seul geste autour du texte, ne recouvrent rien",
          lue["caches"] == [] and natures(lue) == [("texte", "")], lue["caches"])

    doc, page = page_neuve("Coin")          # dans le rectangle de l'ellipse, loin de sa forme
    page.insert_text((250, 320), "au milieu de l'ellipse", fontsize=12)
    page.draw_oval(pymupdf.Rect(56, 180, 560, 460), color=(0, 0, 0), fill=(0, 0, 0))
    lecture, lue = lire(doc)
    dessous = [d["texte"] for c in lue["caches"] for d in c["dessous"]]
    essai("une ellipse pleine recouvre ce qui est sous sa forme, pas ce qui est au coin de son rectangle",
          dessous == ["au milieu de l'ellipse"], dessous)

    # La ou l'image ne peut pas trancher, la geometrie tranche seule: elle doit donc etre juste.
    # 1. Un texte deja invisible: rien ne change a l'image, qu'il soit recouvert ou non.
    doc, page = page_neuve("Coin", render_mode=3)
    page.draw_oval(pymupdf.Rect(56, 180, 560, 460), color=(0, 0, 0), fill=(0, 0, 0))
    essai("un texte invisible au coin du rectangle d'une ellipse n'est pas dit recouvert", lire(doc)[1]["caches"] == [])
    # 2. Un autre texte ecrit au meme endroit: l'image change a cause du second, et ne dit rien du premier.
    faux = {
        "rogné ailleurs": (lambda z: f"q 400 700 30 30 re W n 1 0 0 rg 0 0 595 {HAUT} re f Q", ""),
        "en mode de mélange": (lambda z: f"q /GX gs 1 1 0 rg {re(z)} f Q", "<</Type/ExtGState/BM/Multiply>>"),
        "transparent": (lambda z: f"q /GX gs 0 0 0 rg {re(z)} f Q", "<</Type/ExtGState/ca 0.35>>"),
        "fait de filets": (filets, ""),
    }
    for nom, (operateurs, etat) in faux.items():
        doc, page = page_neuve("Libelle ancien")
        brut(doc, page, operateurs(zone_du_texte(page)), etat)
        page = doc[0]
        page.insert_text((60.3, 200), "Mention neuve", fontsize=12)
        lue = lire(doc)[1]
        essai(f"un aplat {nom}, entre un texte et un autre écrit au même endroit, ne recouvre rien",
              lue["caches"] == [] and len([e for e in lue["elements"] if e["nature"] == "trace"]) == 1, lue["caches"])


def cache() -> None:
    doc, page = page_neuve()
    page.draw_rect(zone_du_texte(page), color=(0, 0, 0), fill=(0, 0, 0))
    lecture, lue = lire(doc)
    zones = lue["caches"]
    essai("un aplat franc recouvre, et dit sa nature", len(zones) == 1 and (zones[0]["nature"], zones[0]["couleur"]) == ("aplat", "noir")
          and zones[0]["dessous"][0]["texte"] == "Ligne fabriquee sous ce qui est pose", zones)
    essai("cette page-là a été comparée à son image", lecture.analyse(1, 0)["comparee"] is True)

    doc, page = page_neuve()
    teinte = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), False)
    teinte.set_rect(teinte.irect, (110, 150, 200))
    page.insert_image(zone_du_texte(page), pixmap=teinte, keep_proportion=False)
    zones = lire(doc)[1]["caches"]
    essai("une image posée sur du texte le recouvre", len(zones) == 1 and zones[0]["nature"] == "image"
          and zones[0]["dessous"][0]["texte"] == "Ligne fabriquee sous ce qui est pose", zones)

    doc, page = page_neuve("Ancien montant")
    page.draw_rect(zone_du_texte(page) + (0, 0, 30, 0), color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((60, 200), "Nouveau montant", fontsize=12)
    zones = lire(doc)[1]["caches"]
    essai("un texte réécrit sur un aplat blanc : l'ancien dessous, le nouveau par-dessus",
          len(zones) == 1 and zones[0]["dessous"][0]["texte"] == "Ancien montant" and zones[0]["dessus"] == ["Nouveau montant"], zones)

    # Un titre ecrit sous un bandeau puis redessine par-dessus, comme le font les logiciels de mise en page:
    # le texte du dessous est bien sous l'aplat, mais la page montre le meme titre. Rien n'est cache au lecteur.
    doc, page = page_neuve("Titre du bandeau")
    page.draw_rect(zone_du_texte(page) + (0, 0, 30, 0), color=(0.2, 0.3, 0.5), fill=(0.2, 0.3, 0.5))
    page.insert_text((60, 200), "Titre du bandeau", fontsize=12, color=(1, 1, 1))
    lecture, lue = lire(doc)
    essai("un titre écrit sous un bandeau puis redessiné par-dessus n'est pas dit recouvert",
          lue["caches"] == [] and lecture.analyse(1, 0)["redessinees"] == 14, (lue["caches"], lecture.analyse(1, 0)["redessinees"]))

    doc, page = page_neuve("Total : 1 250,00")
    page.draw_rect(zone_du_texte(page) + (0, 0, 30, 0), color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((60, 200), "Total : 1 950,00", fontsize=12)
    zones = lire(doc)[1]["caches"]
    essai("un montant dont un seul chiffre change se relit en entier, dessous comme dessus",
          len(zones) == 1 and zones[0]["dessous"][0]["texte"] == "Total : 1 250,00" and zones[0]["dessus"] == ["Total : 1 950,00"], zones)


def faux_semblants() -> None:
    """Ce qui est pose sur une lettre peut la redessiner, ou ne rien cacher du tout: releve sur de vraies pieces."""
    # 1. Ce qui recouvre montre la meme lettre: un texte converti en traces, un scan du meme mot.
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=HAUT)
    page.insert_text((60, 200), "I", fontsize=40)
    image = page.get_pixmap(matrix=pymupdf.Matrix(4, 4), colorspace=pymupdf.csGRAY, alpha=False)
    gris = np.frombuffer(image.samples, np.uint8).reshape(image.height, image.width)
    lignes_, colonnes = np.nonzero(gris < 128)
    fut = pymupdf.Rect(colonnes.min() / 4, lignes_.min() / 4, (colonnes.max() + 1) / 4, (lignes_.max() + 1) / 4)
    page.draw_rect(fut, color=(0, 0, 0), fill=(0, 0, 0), width=0)
    lecture, lue = lire(doc)
    essai("un tracé noir qui redessine la lettre sur elle-même ne la recouvre pas",
          lue["caches"] == [] and natures(lue) == [("texte", "")], lue["caches"])

    doc, page = page_neuve()
    zone = zone_du_texte(page)
    page.insert_image(zone, pixmap=page.get_pixmap(matrix=pymupdf.Matrix(3, 3), clip=zone), keep_proportion=False)
    essai("une image qui montre le même texte, posée sur lui, ne le recouvre pas", lire(doc)[1]["caches"] == [])

    doc, page = page_neuve("aaaa")
    lettres = page.get_texttrace()[0]["chars"]
    barre = pymupdf.Rect(lettres[0][3][0] - 1, 200 - 7.5, lettres[-1][3][2] + 1, 200 + 1.5)       # plus basse que la ligne: de la ligne de base a la hauteur d'x
    page.draw_rect(barre, color=(0, 0, 0), fill=(0, 0, 0))
    zones = lire(doc)[1]["caches"]
    essai("une barre noire plus basse que la ligne, mais qui couvre toute l'encre, recouvre",
          len(zones) == 1 and zones[0]["dessous"][0]["texte"] == "aaaa", zones)

    # 2. Un signe sans dessin, d'une police qui ne dit pas ses lettres, n'est pas une lettre cachee.
    doc, page = page_neuve("amorce")
    brut(doc, page, f"BT /helv 12 Tf 60 {HAUT - 300} Td (\\001\\037\\001\\037) Tj ET 0 0 0 rg 56 {HAUT - 304} 60 16 re f")
    lecture, lue = lire(doc)
    vides = [e["texte"] for e in lue["elements"] if "illisible" in e["texte"]]
    essai("des signes sans dessin sous un aplat ne font pas une zone recouverte", lue["caches"] == [], lue["caches"])
    essai("un texte dont la police ne dit pas les lettres se dit illisible", len(vides) == 1 and vides[0].startswith("(illisible : 4 signes"), vides)

    # 3. Un degrade pleine page pose en dernier, a travers lequel tout reste lisible.
    doc, page = page_neuve()
    brut(doc, page, "q /GX gs /Sh0 sh Q", MELANGE, DEGRADE)
    lecture, lue = lire(doc)
    essai("un dégradé pleine page à travers lequel le texte se lit ne recouvre rien", lue["caches"] == [] and natures(lue) == [("texte", "")],
          lue["caches"])

    doc, page = page_neuve("Ancien montant")
    page.draw_rect(zone_du_texte(page) + (0, 0, 30, 0), color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((60, 200), "Nouveau montant", fontsize=12)
    page = doc[0]
    brut(doc, page, "q /GX gs /Sh0 sh Q", MELANGE, DEGRADE)
    zones = lire(doc)[1]["caches"]
    essai("sous un dégradé posé en dernier, c'est l'aplat qui cache, pas le dégradé",
          len(zones) == 1 and (zones[0]["nature"], zones[0]["couleur"]) == ("aplat", "blanc") and zones[0]["dessus"] == ["Nouveau montant"], zones)

    # 4. Une opacite declaree nulle n'est un fait que si l'image le confirme.
    doc, page = page_neuve("amorce")
    brut(doc, page, f"q /GX gs BT /helv 12 Tf 60 {HAUT - 300} Td (Texte sans opacite) Tj ET Q", "<</Type/ExtGState/ca 0/CA 0>>")
    essai("un texte sans aucune opacité est dit transparent", ("invisible", "transparent") in natures(lire(doc)[1]), natures(lire(doc)[1]))

    # 5. Du texte reellement place au-dela du bord droit de la page.
    doc, page = page_neuve()
    page.insert_text((640, 300), "Colonne hors de la feuille", fontsize=12)
    lecture, lue = lire(doc)
    hors = [e for e in lue["elements"] if e.get("cause") == "hors de la page"]
    essai("un texte placé au-delà du bord droit est dit hors de la page", len(hors) == 1 and hors[0]["texte"] == "Colonne hors de la feuille", natures(lue))
    # ... mais seulement si les DEUX releves de la bibliotheque l'y placent: ici le second est rendu muet.
    vrai = lecture_page.lettres_hors_page_selon_les_lignes
    lecture_page.lettres_hors_page_selon_les_lignes = lambda page, rep: []
    try:
        lecture, lue = lire(doc)
        analyse = lecture.analyse(1, 0)
    finally:
        lecture_page.lettres_hors_page_selon_les_lignes = vrai
    essai("si le relevé par lignes ne le voit pas dehors, le texte n'est pas dit hors de la page, et il est compté",
          not any(e.get("cause") for e in lue["elements"]) and analyse["douteuses"] == 1, (natures(lue), analyse["douteuses"]))

    # 6. Quand l'image ne peut pas etre comparee, la lecture ne dit aucune zone plutot que de s'en remettre a la geometrie.
    doc, page = page_neuve()
    page.draw_rect(zone_du_texte(page), color=(0, 0, 0), fill=(0, 0, 0))
    vraie = lecture_pdf.Lecture._encre
    lecture_pdf.Lecture._encre = lambda self, version, n: (None, None, None, 1.0)
    try:
        lecture, lue = lire(doc)
        analyse = lecture.analyse(1, 0)
    finally:
        lecture_pdf.Lecture._encre = vraie
    essai("sans comparaison possible, aucune zone n'est dite, et la page se compte comme non comparée",
          lue["caches"] == [] and analyse["ratee"] is True and analyse["non_comparees"] > 0, (lue["caches"], analyse["ratee"], analyse["non_comparees"]))


def annotations_qui_masquent() -> None:
    """Une annotation opaque posee sur la page: ce qu'elle cache se constate sur l'image, quel que soit ce qu'il y a dessous."""
    def carre_blanc(page, zone, teinte=(1, 1, 1)):
        annotation = page.add_rect_annot(zone)
        annotation.set_colors(stroke=teinte, fill=teinte)
        annotation.update()

    # Une page SANS texte: des lettres dessinees en contours et une image, masquees par un carre blanc.
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=HAUT)
    for rang in range(6):
        page.draw_rect(pymupdf.Rect(80 + rang * 40, 200, 100 + rang * 40, 260), color=(0, 0, 0), fill=(0, 0, 0))
    couleur = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 16, 16), False)
    couleur.set_rect(couleur.irect, (200, 60, 60))
    page.insert_image(pymupdf.Rect(80, 300, 200, 380), pixmap=couleur, keep_proportion=False)
    carre_blanc(page, pymupdf.Rect(60, 180, 360, 400))
    lecture, lue = lire(doc)
    zones = lue["caches"]
    essai("un carré blanc en annotation sur une page sans texte est une zone recouverte, dite en nombres",
          len(zones) == 1 and (zones[0]["nature"], zones[0]["genre"], zones[0]["couleur"], zones[0]["traces"], zones[0]["images"], zones[0]["dessous"])
          == ("annotation", "rectangle", "blanc", 6, 1, []), zones)
    essai("la page se dessine aussi sans ses annotations, pour montrer ce qui est dessous",
          lecture.image(1, 1, False, 1.6, "a") != lecture.image(1, 1, False, 1.6))

    doc, page = page_neuve()
    carre_blanc(page, zone_du_texte(page) + (-10, -10, 10, 10))
    zones = lire(doc)[1]["caches"]
    essai("le même carré sur du texte rend ce texte",
          len(zones) == 1 and zones[0]["nature"] == "annotation" and [d["texte"] for d in zones[0]["dessous"]] == ["Ligne fabriquee sous ce qui est pose"], zones)

    doc, page = page_neuve()
    page.add_highlight_annot(zone_du_texte(page).quad)
    essai("un surlignage laisse voir le texte : ce n'est pas une zone recouverte", lire(doc)[1]["caches"] == [])

    doc, page = page_neuve()
    carre_blanc(page, pymupdf.Rect(300, 500, 420, 600), teinte=(1, 0.9, 0.1))
    essai("un carré plein posé sur du vide ne cache rien", lire(doc)[1]["caches"] == [])


def sombre(lecture: lecture_pdf.Lecture, sans: str, zone) -> float:
    """Part de points sombres dans une zone de la page 1, dessinee sans les familles nommees."""
    image = pymupdf.Pixmap(base64.b64decode(lecture.image(1, 1, False, 1.6, sans).split(",", 1)[1]))
    gris = pymupdf.Pixmap(pymupdf.csGRAY, image)
    points = np.frombuffer(gris.samples, np.uint8).reshape(gris.height, gris.width)
    x0, y0, x1, y1 = (int(v * 1.6) for v in zone)
    return float((points[y0:y1, x0:x1] < 128).mean())


def voir_dessous() -> None:
    """Faire disparaitre ce qui est pose sur la page - annotations, images, traces - pour voir dessous. Le texte reste."""
    doc, page = page_neuve()
    zone = zone_du_texte(page)
    page.draw_rect(zone, color=(0, 0, 0), fill=(0, 0, 0))
    lecture, _ = lire(doc)
    avec, sans = sombre(lecture, "", zone), sombre(lecture, "t", zone)
    essai("sans ses tracés, la page montre le texte qu'un aplat noir recouvrait", avec > 0.9 and 0.02 < sans < 0.5, (round(avec, 2), round(sans, 2)))

    doc, page = page_neuve()
    zone = zone_du_texte(page)
    nuit = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), False)
    nuit.set_rect(nuit.irect, (30, 30, 30))
    page.insert_image(zone, pixmap=nuit, keep_proportion=False)
    lecture, _ = lire(doc)
    avec, sans = sombre(lecture, "", zone), sombre(lecture, "i", zone)
    essai("sans ses images, la page montre le texte qu'une image collée recouvrait", avec > 0.9 and 0.02 < sans < 0.5, (round(avec, 2), round(sans, 2)))

    doc, page = page_neuve()
    zone = zone_du_texte(page)
    annotation = page.add_rect_annot(zone + (-10, -10, 10, 10))
    annotation.set_colors(stroke=(1, 1, 1), fill=(1, 1, 1))
    annotation.update()
    lecture, _ = lire(doc)
    avec, sans = sombre(lecture, "", zone), sombre(lecture, "a", zone)
    essai("sans ses annotations, la page montre le texte qu'un carré blanc recouvrait", avec < 0.01 and sans > 0.02, (round(avec, 3), round(sans, 2)))

    # Une zone de biffage que le fichier porte SANS l'avoir appliquee ne doit pas l'etre par le lecteur.
    doc, page = page_neuve()
    zone = zone_du_texte(page)
    page.add_redact_annot(zone)
    lecture, _ = lire(doc)
    restes = [sombre(lecture, familles, zone) for familles in ("", "i", "t", "ait")]
    essai("une zone de biffage non appliquée du fichier n'est pas appliquée en retirant les images ou les tracés",
          all(reste > 0.02 for reste in restes[:3]), [round(r, 3) for r in restes])
    octets = lecture.octets
    lecture.image(1, 1, False, 1.6, "it")
    essai("retirer pour voir dessous ne change pas un octet de la pièce tenue en mémoire", lecture.octets == octets and lecture.tranches[-1] == octets)


def ne_se_montre_pas() -> None:
    doc, page = page_neuve(render_mode=3)
    lecture, lue = lire(doc)
    essai("un texte en mode invisible est dit invisible, sans comparer la page à son image",
          natures(lue) == [("invisible", "mode invisible")] and lecture.analyse(1, 0)["comparee"] is False, natures(lue))

    doc, page = page_neuve(color=(1, 1, 1))
    essai("un texte blanc sur une page blanche est dit de la couleur du fond", natures(lire(doc)[1]) == [("invisible", "couleur du fond")])

    doc, page = page_neuve()
    page.draw_rect(pymupdf.Rect(40, 280, 400, 320), color=(0.1, 0.2, 0.6), fill=(0.1, 0.2, 0.6))
    page.insert_text((60, 305), "Bleu sur bleu", fontsize=12, color=(0.1, 0.2, 0.6))
    page.insert_text((60, 360), "Blanc sur rien, mais lisible sur bleu", fontsize=12, color=(0.1, 0.2, 0.6))
    essai("un texte de la couleur de l'aplat qui est derrière lui est dit de la couleur du fond, pas celui qui est à côté",
          natures(lire(doc)[1]) == [("texte", ""), ("invisible", "couleur du fond"), ("texte", "")], natures(lire(doc)[1]))

    doc, page = page_neuve()
    page.insert_text((-400, 300), "Texte hors de la page", fontsize=12)
    lecture, lue = lire(doc)
    hors = [e for e in lue["elements"] if e.get("cause") == "hors de la page"]
    essai("un texte placé hors de la page est dit hors de la page", len(hors) == 1 and hors[0]["texte"] == "Texte hors de la page", natures(lue))

    doc, page = page_neuve()
    lecture, lue = lire(doc)
    essai("une page sans rien de posé sur son texte noir ne se compare pas à son image",
          natures(lue) == [("texte", "")] and lecture.analyse(1, 0)["comparee"] is False)


def ecriture() -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=HAUT)
    page.insert_text((300, 500), "Texte couche du tableau", fontsize=12, rotate=90)
    page.draw_rect(zone_du_texte(page), color=(0, 0, 0), fill=(0, 0, 0))
    page.set_rotation(90)
    dessous = lire(doc)[1]["caches"][0]["dessous"][0]
    essai("un texte couché sur une page tournée se relit droit, sur toute sa longueur",
          dessous["angle"] % 360 == 0 and dessous["long"] > 8 * dessous["taille"] and dessous["texte"] == "Texte couche du tableau", dessous)

    doc, page = page_neuve("amorce")
    brut(doc, page, "BT /helv 12 Tf 60 500 Td [(Deux) -600 (mots) -600 (sans) -600 (espace)] TJ ET")
    textes = [e["texte"] for e in lire(doc)[1]["elements"] if e["nature"] == "texte"]
    essai("une ligne écrite sans espaces retrouve les siens", "Deux mots sans espace" in textes, textes)


def surlignage() -> None:
    doc, page = page_neuve()
    carre = pymupdf.Rect(200, 300, 290, 391)
    annotation = page.add_highlight_annot(carre.quad)
    doc.xref_set_key(annotation.xref, "AP", "null")
    doc.xref_set_key(annotation.xref, "Rect", f"[{carre.x0} {HAUT - carre.y1} {carre.x1} {HAUT - carre.y0}]")
    lecture, lue = lire(doc)
    note = [e for e in lue["elements"] if e["nature"] == "annotation"]
    essai("un surlignage sans dessin propre est dit tel", len(note) == 1 and note[0]["texte"] == "surlignage sans dessin propre", note)
    avec = lecture.page(1, 0).get_pixmap(colorspace=pymupdf.csRGB, alpha=False)
    sans = lecture.page(1, 0, annotations_=False).get_pixmap(colorspace=pymupdf.csRGB, alpha=False)
    a = np.frombuffer(avec.samples, np.uint8).reshape(avec.height, avec.width, 3).astype(np.int16)
    b = np.frombuffer(sans.samples, np.uint8).reshape(sans.height, sans.width, 3).astype(np.int16)
    lignes_, colonnes = np.nonzero(np.abs(a - b).max(axis=2) > 10)
    teinte = (colonnes.min(), lignes_.min(), colonnes.max() + 1, lignes_.max() + 1) if len(lignes_) else (0, 0, 0, 0)
    essai("il se dessine tel que le fichier le déclare : un carré, sans déborder",
          all(abs(v - w) <= 1.5 for v, w in zip(teinte, carre)) and len(lignes_) > 0.97 * carre.get_area(),
          f"teinte {teinte}, déclaré {tuple(round(v) for v in carre)}, {len(lignes_)} points sur {round(carre.get_area())}")
    cadre = note[0]["bbox"]
    essai("son cadre est celui du fichier", all(abs(v - w) < 0.004 for v, w in zip(cadre, (200 / 595, 300 / HAUT, 290 / 595, 391 / HAUT))), cadre)


def avarie() -> None:
    doc, page = page_neuve()
    entier = doc.tobytes()
    chemin = TRAVAIL / "tronque.pdf"
    chemin.write_bytes(entier[:len(entier) // 3])
    try:
        faits = lecture_pdf.Lecture(chemin).faits()
        essai("un fichier tronqué se lit, ou se refuse proprement", len(faits["pages"]) >= 1, "lu")
    except lecture_pdf.PieceIllisible as refus:
        essai("un fichier tronqué se refuse en clair, sans chemin", str(TRAVAIL) not in str(refus) and len(str(refus)) > 10, str(refus))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    TRAVAIL = Path(tempfile.mkdtemp(prefix="pdforensics-caches-"))
    try:
        ne_cache_pas()
        cache()
        faux_semblants()
        annotations_qui_masquent()
        voir_dessous()
        ne_se_montre_pas()
        ecriture()
        surlignage()
        avarie()
    finally:
        shutil.rmtree(TRAVAIL, ignore_errors=True)
    print("VERDICT :", "tout passe" if not ECHECS else f"{len(ECHECS)} échec(s) : " + " ; ".join(ECHECS))
    sys.exit(1 if ECHECS else 0)

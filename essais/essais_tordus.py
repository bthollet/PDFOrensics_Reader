# -*- coding: utf-8 -*-
"""Des pièces fabriquées TORDUES, une par axe où un vrai PDF peut différer des cinq pièces d'essai.

  python -B essais/essais_tordus.py

Pour chaque axe : la lecture rend-elle une réponse juste, ou au moins un refus
propre, plutôt qu'une réponse fausse en silence ?

- page tournée (90, 180, 270 degrés) : le tracé d'une zone recouverte tombe-t-il
  sur le cache que l'image montre ?
- page rognée (son cadre ne part pas de zéro) : même question ;
- mot de passe : refus dit en clair ;
- pièce longue : temps de lecture ;
- métadonnées XMP, fichier joint, annotation, signet, champ de formulaire : relevés dans la fiche ;
- beaucoup de versions ; une page ajoutée entre deux versions.

Tout est fabriqué dans un dossier temporaire, puis supprimé.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pymupdf

sys.dont_write_bytecode = True  # même lancé sans -B, rien ne s'écrit à côté des sources
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # le paquet est à côté du dossier des essais

from pdforensics import lecture_pdf  # noqa: E402

ECHECS: list[str] = []
VISIBLE, COUVERT = "Début visible", "FIN COUVERTE"


def essai(nom: str, vrai: bool, detail: object = "") -> None:
    print(("OK    " if vrai else "ECHEC ") + nom + (f" : {detail}" if detail != "" else ""))
    if not vrai:
        ECHECS.append(nom)


def page_cachee(doc, rotation: int = 0, rognage=None, cache: bool = True):
    """Une page avec une ligne, et un cache noir sur ses deux derniers mots."""
    page = doc.new_page(width=595, height=842)
    page.insert_text((80, 200), f"{VISIBLE} {COUVERT}", fontsize=14)
    zone = None
    for span in page.get_texttrace():
        lettres = span["chars"]
        texte = "".join(chr(c[0]) for c in lettres)
        debut = texte.find(COUVERT)
        zone = pymupdf.Rect(lettres[debut][3])
        for lettre in lettres[debut:]:
            zone |= pymupdf.Rect(lettre[3])
    if cache:
        page.draw_rect(zone + (-2, -2, 2, 2), color=(0, 0, 0), fill=(0, 0, 0))
    if rognage:
        page.set_cropbox(pymupdf.Rect(rognage))
    if rotation:
        page.set_rotation(rotation)
    return page


def gris(page) -> np.ndarray:
    image = page.get_pixmap(colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(image.samples, np.uint8).reshape(image.height, image.width).astype(np.int16)


def cache_dans_l_image(avec, sans) -> list[float]:
    """Où l'image montre le cache : là où la page avec cache diffère de la même page sans cache."""
    a, b = gris(avec), gris(sans)
    lignes, colonnes = np.nonzero(np.abs(a - b) > 40)
    haut, large = a.shape
    return [colonnes.min() / large, lignes.min() / haut, (colonnes.max() + 1) / large, (lignes.max() + 1) / haut]


def geometrie(dossier: Path, nom: str, rotation: int = 0, rognage=None) -> None:
    doc, temoin = pymupdf.open(), pymupdf.open()
    page_cachee(doc, rotation, rognage)
    page_cachee(temoin, rotation, rognage, cache=False)
    chemin = dossier / f"{nom}.pdf"
    doc.save(chemin)
    lecture = lecture_pdf.Lecture(chemin)
    faits = lecture.faits()
    caches = faits["pages"][0]["caches"]
    if len(caches) != 1:
        essai(f"{nom} : une zone recouverte relevée", False, f"{len(caches)} zone(s)")
        return
    vu, dit = cache_dans_l_image(lecture.doc(1)[0], temoin[0]), caches[0]["bbox"]
    ecart = max(abs(a - b) for a, b in zip(vu, dit))
    essai(f"{nom} : le tracé tombe sur le cache que l'image montre", ecart < 0.012 and caches[0]["dessous"][0]["texte"] == COUVERT,
          f"écart {ecart:.3f}, dessous {[d['texte'] for d in caches[0]['dessous']]}")
    page = faits["pages"][0]
    essai(f"{nom} : les tracés restent dans la page", all(-0.01 <= v <= 1.01 for e in page["elements"] for v in e["bbox"]),
          [e["bbox"] for e in page["elements"] if not all(-0.01 <= v <= 1.01 for v in e["bbox"])][:2])


def divers(dossier: Path) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "page protégée par un mot de passe d'essai")
    chemin = dossier / "mot de passe.pdf"
    doc.save(chemin, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="mot-de-passe-d-essai", owner_pw="mot-de-passe-du-proprietaire-d-essai")
    try:
        lecture_pdf.Lecture(chemin)
        essai("un PDF à mot de passe est refusé", False)
    except lecture_pdf.PieceIllisible as refus:
        essai("un PDF à mot de passe est refusé en clair", "mot de passe" in str(refus), str(refus))

    doc = pymupdf.open()
    for n in range(150):
        page = doc.new_page()
        for ligne in range(40):
            page.insert_text((60, 60 + ligne * 18), f"Page {n + 1}, ligne {ligne + 1} : texte d'essai pour mesurer la lecture d'une longue pièce.", fontsize=10)
    chemin = dossier / "longue.pdf"
    doc.save(chemin)
    debut = time.perf_counter()
    lecture = lecture_pdf.Lecture(chemin)
    faits = lecture.faits()
    duree = time.perf_counter() - debut
    essai("une pièce de 150 pages se lit en moins de 20 secondes", len(faits["pages"]) == 150 and duree < 20, f"{duree:.1f} s")
    debut = time.perf_counter()
    lecture.image(1, 75, False, 1.6)
    essai("une page d'une longue pièce se dessine en moins de 2 secondes", time.perf_counter() - debut < 2, f"{time.perf_counter() - debut:.2f} s")

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "version 1")
    chemin = dossier / "versions.pdf"
    doc.save(chemin)
    doc.close()
    for rang in range(2, 13):
        doc = pymupdf.open(chemin)
        if rang == 7:
            doc.new_page().insert_text((72, 100), "page ajoutée à la version 7")
        else:
            doc[0].insert_text((72, 100 + rang * 20), f"ajout de la version {rang}")
        doc.saveIncr()
        doc.close()
    faits = lecture_pdf.Lecture(chemin).faits()
    essai("douze enregistrements donnent douze versions", len(faits["versions"]) == 12 and faits["moteur"] == 12, (len(faits["versions"]), faits["moteur"]))
    essai("la page ajoutée à la version 7 est dite", "1 page ajoutée" in faits["versions"][6]["resume"], faits["versions"][6]["resume"])
    essai("chaque version dit son ajout", all("1 texte ajouté" in v["resume"] for v in faits["versions"][1:] if v["n"] != 7))

    doc = pymupdf.open()
    doc.new_page()
    chemin = dossier / "vide.pdf"
    doc.save(chemin)
    faits = lecture_pdf.Lecture(chemin).faits()
    essai("une page vide se lit", faits["pages"][0]["elements"] == [] and faits["pages"][0]["caches"] == [])

    doc = pymupdf.open()
    page = doc.new_page(width=2384, height=3370)
    page.insert_text((200, 400), "grand format", fontsize=60)
    chemin = dossier / "grand.pdf"
    doc.save(chemin)
    lecture = lecture_pdf.Lecture(chemin)
    image = lecture.image(1, 1, False, 3.0)
    essai("un grand format se dessine sans dépasser le plafond de pixels", image.startswith("data:image/"), f"{len(image) // 1024} Ko")


def riche(dossier: Path) -> None:
    """Métadonnées XMP, fichier joint, annotation, signet, champ de formulaire : tout se relève."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "pièce riche d'essai", fontsize=12)
    page.add_text_annot((300, 100), "note d'essai")
    doc.embfile_add("annexe-d-essai.txt", b"contenu d'essai")
    doc.set_toc([[1, "Signet d'essai", 1]])
    champ = pymupdf.Widget()
    champ.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    champ.field_name = "champ"
    champ.rect = pymupdf.Rect(72, 150, 250, 170)
    page.add_widget(champ)
    doc.set_xml_metadata('<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
                         '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" '
                         'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:CreatorTool="OUTIL D\'ESSAI">'
                         '<dc:creator><rdf:Seq><rdf:li>AUTEUR D\'ESSAI</rdf:li></rdf:Seq></dc:creator></rdf:Description></rdf:RDF>'
                         '</x:xmpmeta><?xpacket end="w"?>')
    chemin = dossier / "riche.pdf"
    doc.save(chemin)
    faits = lecture_pdf.Lecture(chemin).faits()
    fiche = dict(faits["fiche"])
    essai("le second jeu de métadonnées est lu", ("Auteur", "AUTEUR D'ESSAI") in [tuple(x) for x in faits["xmp"]]
          and ("Logiciel d'origine", "OUTIL D'ESSAI") in [tuple(x) for x in faits["xmp"]], faits["xmp"])
    essai("le fichier joint est nommé", len(faits["joints"]) == 1 and faits["joints"][0].startswith("annexe-d-essai.txt"), faits["joints"])
    essai("le signet et le champ de formulaire sont comptés", (fiche["Signets"], fiche["Champs de formulaire"]) == ("1", "1"),
          (fiche["Signets"], fiche["Champs de formulaire"]))
    essai("l'annotation est relevée avec son contenu", any(e["nature"] == "annotation" and "note d'essai" in e["texte"]
                                                           for e in faits["pages"][0]["elements"]))


def principal() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    travail = Path(tempfile.mkdtemp(prefix="pdforensics-tordus-"))
    try:
        geometrie(travail, "page droite")
        for angle in (90, 180, 270):
            geometrie(travail, f"page tournée de {angle}", rotation=angle)
        geometrie(travail, "page rognée", rognage=(40, 60, 555, 700))
        geometrie(travail, "page rognée et tournée", rotation=90, rognage=(40, 60, 555, 700))
        divers(travail)
        riche(travail)
    finally:
        shutil.rmtree(travail, ignore_errors=True)
    print("VERDICT :", "tout passe" if not ECHECS else f"{len(ECHECS)} échec(s) : " + " ; ".join(ECHECS))
    return 1 if ECHECS else 0


if __name__ == "__main__":
    sys.exit(principal())

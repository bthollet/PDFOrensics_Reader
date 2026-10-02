# -*- coding: utf-8 -*-
"""Lire les couches d'un PDF. Bibliotheque sans ecran, et sans autre dependance que PyMuPDF et numpy.

Une `Lecture` tient UNE piece en memoire, lue en place: aucun octet n'est
ecrit sur disque, aucun message ne porte un chemin ni un nom de fichier, et
la bibliotheque de rendu est rendue muette.

Elle rend:

- `entete()`: ce qui se dit du fichier sans lire ses pages une a une - fiche,
  metadonnees, versions enregistrees, calques, et la taille de chaque page;
- `page_faits(n)` et `suite(de)`: ce qu'une page contient - zones recouvertes,
  contenu des calques eteints, composition, blocs de texte. Une longue piece
  se lit ainsi par tranches;
- `faits()`: les deux ensemble, pour toute la piece;
- `image(version, page, calques, echelle)`: l'image d'une page, a la demande.

Les positions sont des fractions de page (x0, y0, x1, y1 entre 0 et 1): un
trace pose a un zoom tient a tous les autres. Ce qui fait une page, et ce
qu'elle ne montre pas, se lit dans `lecture_page`.
"""
from __future__ import annotations

import base64
import hashlib
import re
import time
from collections import OrderedDict
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pymupdf

from . import lecture_annotations
from . import lecture_page
from .lecture_page import Repere, propre  # noqa: F401 - `propre` reste offert sous ce nom

pymupdf.TOOLS.mupdf_display_errors(False)      # la bibliotheque n'ecrit rien d'elle-meme, ni erreur ni avertissement
pymupdf.TOOLS.mupdf_display_warnings(False)

ECHELLES = (1.6, 3.0, 4.5)
PIXELS_MAX = 24_000_000
IMAGES_MAX = 60_000_000      # signes d'images de pages gardes en memoire par piece
PARTOUT = pymupdf.Rect(-20000, -20000, 20000, 20000)
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre")
XMP = {"creator": "Auteur", "CreatorTool": "Logiciel d'origine", "Producer": "Logiciel qui a produit le PDF",
       "CreateDate": "Créé le", "ModifyDate": "Modifié le", "MetadataDate": "Métadonnées modifiées le",
       "title": "Titre", "description": "Description", "subject": "Mots-clés", "Keywords": "Mots-clés",
       "DocumentID": "Identifiant du document", "InstanceID": "Identifiant de cette version", "format": "Format"}


class PieceIllisible(Exception):
    """Le fichier ne se lit pas. Le message dit pourquoi, sans chemin ni nom."""


def fins_de_version(octets: bytes) -> list[int]:
    """Ou finit chaque marqueur de fin de fichier."""
    fins, depart = [], 0
    while True:
        position = octets.find(b"%%EOF", depart)
        if position < 0:
            return fins
        fins.append(position + 5)
        depart = position + 5


def date_lisible(brute: str | None) -> str:
    trouve = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", brute or "")
    if not trouve:
        return ""
    annee, mois, jour, heure, minute = trouve.groups()
    if not 1 <= int(mois) <= 12:
        return ""
    jour_dit = "1er" if int(jour) == 1 else str(int(jour))
    texte = f"{jour_dit} {MOIS[int(mois) - 1]} {annee}"
    if heure is not None:
        texte += f" à {int(heure)} h {minute or '00'}"
    return texte


def taille_lisible(octets: int) -> str:
    if octets < 1024 * 1024:
        return f"{max(1, round(octets / 1024))} Ko"
    return f"{octets / 1048576:.1f} Mo".replace(".", ",")


def cle(element: dict) -> tuple:
    return (element["nature"], tuple(round(v) for v in element["bbox"]), element["texte"], element.get("empreinte", ""))


def zones_changees(avant: np.ndarray, apres: np.ndarray, maille: int = 6) -> list[tuple]:
    """Les rectangles ou l'image de la page differe d'une version a la suivante."""
    if avant.shape != apres.shape:
        return [(0, 0, apres.shape[1], apres.shape[0])]
    lignes_, colonnes = np.nonzero(np.abs(avant - apres) > 24)
    if not len(lignes_):
        return []
    haut, large = -(-avant.shape[0] // maille), -(-avant.shape[1] // maille)
    grille = np.zeros((haut, large), bool)
    grille[lignes_ // maille, colonnes // maille] = True
    vues = np.zeros_like(grille)
    zones = []
    for y, x in zip(*np.nonzero(grille)):
        if vues[y, x]:
            continue
        pile, y0, y1, x0, x1 = [(y, x)], y, y, x, x
        vues[y, x] = True
        while pile:
            cy, cx = pile.pop()
            y0, y1, x0, x1 = min(y0, cy), max(y1, cy), min(x0, cx), max(x1, cx)
            for ny in range(max(0, cy - 2), min(haut, cy + 3)):
                for nx in range(max(0, cx - 2), min(large, cx + 3)):
                    if grille[ny, nx] and not vues[ny, nx]:
                        vues[ny, nx] = True
                        pile.append((ny, nx))
        zones.append((int(x0) * maille, int(y0) * maille, (int(x1) + 1) * maille, (int(y1) + 1) * maille))
    return zones


def pluriel(nombre: int, mot: str) -> str:
    if nombre < 2:
        return f"{nombre} {mot}"
    return f"{nombre} " + " ".join(m if m[-1] in "sx" else m + "s" for m in mot.split())


def resume(ajouts: list[dict], retraits: list[dict]) -> str:
    noms = {"texte": "texte", "invisible": "texte invisible", "image": "image", "annotation": "annotation"}
    morceaux = []
    for liste, verbe in ((ajouts, "ajouté"), (retraits, "retiré")):
        comptes: dict[str, int] = {}
        for element in liste:
            mot = noms.get(element["nature"]) or element["texte"]
            comptes[mot] = comptes.get(mot, 0) + 1
        for mot, nombre in comptes.items():
            feminin = mot in ("image", "annotation")
            morceaux.append(f"{pluriel(nombre, mot)} {verbe}{'e' if feminin else ''}{'s' if nombre > 1 else ''}")
    return ", ".join(morceaux)


def xmp_lisible(xml: str) -> list[tuple[str, str]]:
    """Le second jeu de metadonnees, en couples (libelle, valeur)."""
    debut = xml.find("<x:xmpmeta")
    fin = xml.rfind("</x:xmpmeta>")
    if debut < 0 or fin < 0:
        return []
    try:
        racine = ElementTree.fromstring(xml[debut:fin + len("</x:xmpmeta>")])
    except ElementTree.ParseError:
        return []
    rendu: list[tuple[str, str]] = []

    def local(nom: str) -> str:
        return nom.rsplit("}", 1)[-1]

    def visiter(element, propriete: str) -> None:
        nom = local(element.tag)
        if nom not in ("xmpmeta", "RDF", "Description", "Seq", "Bag", "Alt", "li"):
            propriete = nom
        if nom == "Description":
            for attribut, valeur in element.attrib.items():
                if local(attribut) != "about" and valeur.strip():
                    rendu.append((local(attribut), valeur.strip()))
        if len(element) == 0 and (element.text or "").strip() and propriete:
            rendu.append((propriete, element.text.strip()))
        for enfant in element:
            visiter(enfant, propriete)

    visiter(racine, "")
    return [(XMP.get(nom, nom), valeur[:200]) for nom, valeur in rendu[:40]]


class Lecture:
    """Une piece tenue en memoire: ses octets, ses versions, de quoi rendre une page."""

    def __init__(self, chemin: Path) -> None:
        try:
            self.octets = chemin.read_bytes()
        except OSError:
            raise PieceIllisible("Ce fichier ne s'ouvre pas : il est absent, verrouillé, ou son accès est refusé.") from None
        self._docs: dict[tuple, object] = {}
        self._analyses: dict[tuple, dict] = {}
        self._images: OrderedDict[tuple, str] = OrderedDict()
        self._sans_annotations: set[tuple] = set()
        self._pelees: set[tuple] = set()
        self._entete: dict | None = None
        self.sans_dessin: dict[int, set[int]] = {}
        try:
            entier = pymupdf.open(stream=self.octets, filetype="pdf")
        except Exception:  # noqa: BLE001 - le moteur leve plusieurs familles d'erreurs selon l'avarie
            raise PieceIllisible("Ce fichier ne se lit pas comme un PDF.") from None
        if entier.needs_pass:
            raise PieceIllisible("Ce PDF est protégé par un mot de passe : son contenu ne se lit pas sans lui.")
        if entier.page_count == 0:
            raise PieceIllisible("Ce fichier est abîmé : aucune page ne s'y lit." if entier.is_repaired
                                 else "Ce PDF n'a aucune page.")
        # Une version anterieure est une tranche du fichier qui se rouvre SANS reparation.
        self.tranches: list[bytes] = []
        for fin in fins_de_version(self.octets)[:-1]:
            tranche = self.octets[:fin] + b"\n"
            try:
                essai = pymupdf.open(stream=tranche, filetype="pdf")
                if not essai.is_repaired and essai.page_count and not essai.needs_pass:
                    self.tranches.append(tranche)
            except Exception:  # noqa: BLE001
                continue
        self.tranches.append(self.octets)
        self.moteur = entier.version_count

    # ------------------------------------------------------------ acces

    def doc(self, version: int, calques: bool = False, sorte: str = "avec"):
        """Un exemplaire de la piece en memoire.

        `avec`: avec ses annotations, les surlignages sans dessin propre
        dessines a la lettre. `sans`: ses pages perdent leurs annotations au
        moment ou on les demande, puis leur texte une fois qu'elles sont lues.
        `origine`: tel quel, pour comparer les versions.
        """
        cle_ = (version, sorte, calques)
        if cle_ not in self._docs:
            doc = pymupdf.open(stream=self.tranches[version - 1], filetype="pdf")
            if sorte == "avec" or sorte.startswith("pelee:"):
                sans = lecture_annotations.dessins_litteraux(doc)
                self.sans_dessin.setdefault(version, sans)
            if calques:
                for reglage in doc.layer_ui_configs():
                    if not reglage["on"]:
                        doc.set_layer_ui_config(reglage["number"], action=pymupdf.PDF_OC_ON)
            self._docs[cle_] = doc
        return self._docs[cle_]

    def page(self, version: int, n: int, annotations_: bool = True, calques: bool = False, sorte: str = ""):
        """Une page, avec ou sans ses annotations."""
        if annotations_:
            return self.doc(version, calques)[n]
        sorte = sorte or "sans"
        page = self.doc(version, calques, sorte)[n]
        if (version, sorte, calques, n) not in self._sans_annotations:
            annotation = page.first_annot
            while annotation:
                annotation = page.delete_annot(annotation)
            self._sans_annotations.add((version, sorte, calques, n))
        return page

    def empreinte(self, version: int, n: int) -> str:
        """Ce qui fait la page dans cette version, sans la dessiner: pour savoir si elle a change."""
        doc = self.doc(version, sorte="origine")
        page = doc[n]
        somme = hashlib.sha1(doc.xref_object(page.xref, compressed=True).encode("utf-8", "replace"))
        for xref in page.get_contents():
            somme.update(doc.xref_stream_raw(xref) or b"")
        for annotation in page.annots() or []:
            somme.update(doc.xref_object(annotation.xref, compressed=True).encode("utf-8", "replace"))
        for image in page.get_images(full=True):
            somme.update(doc.xref_object(image[0], compressed=True).encode("utf-8", "replace"))
        return somme.hexdigest()

    @staticmethod
    def _rvb(page, echelle: float) -> np.ndarray:
        image = page.get_pixmap(matrix=pymupdf.Matrix(echelle, echelle), colorspace=pymupdf.csRGB, alpha=False)
        return np.frombuffer(image.samples, np.uint8).reshape(image.height, image.width, 3)

    def _encre(self, version: int, n: int) -> tuple:
        """Ou l'image de la page change quand on retire son texte, l'image sans texte, et leur echelle.

        Le texte est retire de l'exemplaire `sans` lui-meme: les deux images
        partagent ainsi les images deja decodees de la page. Tout ce qui se lit
        du texte de cette page doit donc avoir ete lu AVANT cet appel.
        """
        try:
            page = self.page(version, n, annotations_=False)
            echelle = min(lecture_page.ECHELLE_ENCRE, (lecture_page.POINTS_MAX / max(page.rect.width * page.rect.height, 1)) ** 0.5)
            avec = self._rvb(page, echelle)
            page.add_redact_annot(PARTOUT, fill=False, cross_out=False)
            page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                                  text=pymupdf.PDF_REDACT_TEXT_REMOVE)
            sans = self._rvb(self.doc(version, sorte="sans")[n], echelle)
            table = lecture_page.table_d_encre(avec, sans)
            return (table, sans, avec, echelle) if table is not None else (None, None, None, 1.0)
        except Exception:  # noqa: BLE001 - une page dont le texte ne se retire pas: aucune zone n'y sera dite recouverte
            return None, None, None, 1.0

    def analyse(self, version: int, n: int) -> dict:
        """Tout ce qui compose une page d'une version: textes, traces, images, annotations, zones recouvertes."""
        if (version, n) not in self._analyses:
            sans = self.page(version, n, annotations_=False)
            rep = Repere(sans)
            images = sans.get_image_info(hashes=True)
            blocs = [b for b in sans.get_text("blocks") if b[6] == 0]
            lue = lecture_page.analyser(sans, rep, lambda: self._encre(version, n))
            elements = [{"nature": "invisible" if l["cause"] else "texte", "bbox": l["bbox"], "texte": l["texte"], "cause": l["cause"]}
                        for l in lecture_page.lignes(lue["textes"])]
            for image in images:
                elements.append({"nature": "image", "bbox": tuple(image["bbox"]),
                                 "texte": f'{image["width"]} × {image["height"]} pixels',
                                 "empreinte": (image.get("digest") or b"").hex()})
            for dessin in lue["traces"]:
                if rep.dans_la_page(dessin["bbox"]):
                    elements.append({"nature": "trace", "bbox": dessin["bbox"],
                                     "texte": (("aplat " if dessin["plein"] else "trait ") + dessin["couleur"]).strip()})
            for annotation in lecture_annotations.annotations(self.page(version, n), self.sans_dessin.get(version, set())):
                elements.append({"nature": "annotation", "bbox": annotation["bbox"],
                                 "texte": annotation["genre"] + (f" « {annotation['contenu']} »" if annotation["contenu"] else "")})
            # Ce que recouvre une annotation se lit sur la page AVEC ses annotations, comparee a la page sans elles.
            caches = lue["caches"] + lecture_annotations.zones_sous_annotation(self.page(version, n), rep, lue["textes"], lue["traces"], images)
            self._analyses[(version, n)] = {"elements": elements, "caches": caches, "repere": rep, "blocs": blocs,
                                            **{k: lue[k] for k in ("inexpliques", "comparee", "ratee", "non_unies", "non_comparees", "douteuses",
                                                                   "redessinees")}}
        return self._analyses[(version, n)]

    def _pixels(self, version: int, n: int) -> np.ndarray:
        image = self.doc(version)[n].get_pixmap(colorspace=pymupdf.csGRAY, alpha=False)
        return np.frombuffer(image.samples, np.uint8).reshape(image.height, image.width).astype(np.int16)

    # ------------------------------------------------------------ faits

    def _versions(self) -> list[dict]:
        rendu = []
        for numero in range(1, len(self.tranches) + 1):
            doc = self.doc(numero)
            meta = doc.metadata or {}
            fiche = {"n": numero, "date": date_lisible(meta.get("modDate") or meta.get("creationDate")),
                     "taille": taille_lisible(len(self.tranches[numero - 1])), "pages": doc.page_count,
                     "zones": [], "resume": ""}
            if numero > 1:
                avant_doc, morceaux = self.doc(numero - 1), []
                communes = min(doc.page_count, avant_doc.page_count)
                for n in range(doc.page_count):
                    if n >= communes:
                        fiche["zones"].append([{"id": f"v{numero}p{n + 1}z1", "bbox": [0, 0, 1, 1],
                                                "quoi": [{"sens": "ajout", "nature": "page", "texte": "page ajoutée"}]}])
                        continue
                    if self.empreinte(numero, n) == self.empreinte(numero - 1, n):
                        fiche["zones"].append([])
                        continue
                    apres_ = self.analyse(numero, n)
                    rep = apres_["repere"]
                    avant = {cle(e): e for e in self.analyse(numero - 1, n)["elements"]}
                    apres = {cle(e): e for e in apres_["elements"]}
                    ajouts = [e for k, e in apres.items() if k not in avant]
                    retraits = [e for k, e in avant.items() if k not in apres]
                    if ajouts or retraits:
                        morceaux.append(f"page {n + 1} : " + resume(ajouts, retraits))
                    zones = []
                    for rang, zone in enumerate(zones_changees(self._pixels(numero - 1, n), self._pixels(numero, n)), 1):
                        def proche(e, zone=zone, rep=rep) -> bool:
                            x0, y0, x1, y1 = rep.vue(e["bbox"])
                            return x0 - 1 <= zone[2] and x1 + 1 >= zone[0] and y0 - 1 <= zone[3] and y1 + 1 >= zone[1]
                        quoi = [("ajout", e) for e in ajouts if proche(e)] + [("retrait", e) for e in retraits if proche(e)]
                        zones.append({"id": f"v{numero}p{n + 1}z{rang}", "bbox": rep.fraction_image(zone),
                                      "quoi": [{"sens": s, "nature": e["nature"], "texte": e["texte"]} for s, e in quoi]})
                    fiche["zones"].append(zones)
                if doc.page_count != avant_doc.page_count:
                    ecart = doc.page_count - avant_doc.page_count
                    morceaux.append(pluriel(abs(ecart), "page") + (" ajoutée" if ecart > 0 else " retirée") + ("s" if abs(ecart) > 1 else ""))
                fiche["resume"] = " ; ".join(morceaux)
            rendu.append(fiche)
        return rendu

    def entete(self) -> dict:
        """Ce qui se dit du fichier avant de lire ses pages une a une."""
        if self._entete is None:
            versions = self._versions()
            avec = self.doc(len(self.tranches))
            meta = avec.metadata or {}
            catalogue = avec.pdf_catalog()
            polices, champs, tailles = set(), 0, []
            for page in avec:
                polices.update(re.sub(r"^[A-Z]{6}\+", "", f[3]) for f in page.get_fonts())
                champs += sum(1 for _ in page.widgets())
                tailles.append({"n": page.number + 1, "l": round(page.rect.width, 2), "h": round(page.rect.height, 2)})
            joints = []
            for nom in avec.embfile_names():
                info = avec.embfile_info(nom)
                joints.append(f"{info.get('filename') or nom} ({taille_lisible(info.get('length') or info.get('size') or 0)})")
            largeur, hauteur = avec[0].rect.width, avec[0].rect.height
            fiche = [
                ("Format", meta.get("format") or ""),
                ("Titre inscrit dans le fichier", meta.get("title") or "aucun"),
                ("Auteur inscrit dans le fichier", meta.get("author") or "aucun"),
                ("Logiciel d'origine", meta.get("creator") or "non indiqué"),
                ("Logiciel qui a produit le PDF", meta.get("producer") or "non indiqué"),
                ("Créé le", date_lisible(meta.get("creationDate")) or "non indiqué"),
                ("Modifié le", date_lisible(meta.get("modDate")) or "non indiqué"),
                ("Taille", taille_lisible(len(self.octets))),
                ("Pages", f"{avec.page_count}, de {largeur * 25.4 / 72:.0f} × {hauteur * 25.4 / 72:.0f} mm"),
                ("Protégé par mot de passe", "oui" if avec.is_encrypted else "non"),
                ("Champs de formulaire", str(champs)),
                ("Signets", str(len(avec.get_toc()))),
                ("Polices", ", ".join(sorted(polices)) or "aucune"),
            ]
            self._entete = {
                "fiche": fiche, "xmp": xmp_lisible(avec.get_xml_metadata() or ""), "joints": joints,
                "versions": versions, "pages": tailles,
                "calques": [{"nom": c["name"], "allume": bool(c["on"])} for c in avec.get_ocgs().values()],
                "balise": avec.xref_get_key(catalogue, "StructTreeRoot")[0] != "null",
                "moteur": self.moteur,
            }
        return dict(self._entete, pages=[dict(p) for p in self._entete["pages"]])

    def page_faits(self, n: int) -> dict:
        """Ce que contient la page n (a partir de 0), dans la derniere version."""
        derniere = len(self.tranches)
        eteints = {c["nom"] for c in self.entete()["calques"] if not c["allume"]}
        analyse = self.analyse(derniere, n)
        rep = analyse["repere"]
        caches = []
        for rang, cache in enumerate(analyse["caches"], 1):
            premiere = next((v for v in range(1, derniere + 1) if n < self.doc(v).page_count
                             and any(c["rect"] == cache["rect"] for c in self.analyse(v, n)["caches"])), None) \
                if derniere > 1 else None
            caches.append({"id": f"c{n + 1}-{rang}", "numero": rang, "version": premiere, "bbox": cache["bbox"],
                           "couleur": cache["couleur"], "nature": cache["nature"], "dessous": cache["dessous"],
                           "dessus": cache["dessus"], "genre": cache.get("genre", ""), "traces": cache.get("traces", 0),
                           "images": cache.get("images", 0)})
        hors = []
        if eteints:
            allume = self.page(derniere, n, annotations_=False, calques=True)
            hors = [{"texte": l["texte"], "bbox": l["bbox"], "calque": l["calque"]}
                    for l in lecture_page.lignes(lecture_page.textes(allume)) if l["calque"] in eteints]
            hors += [{"texte": (("aplat " if t["plein"] else "trait ") + t["couleur"]).strip(), "bbox": t["bbox"],
                      "calque": t["calque"]} for t in lecture_page.traces(allume) if t["calque"] in eteints]
        blocs = analyse["blocs"]
        return {
            "n": n + 1, "l": round(rep.large, 2), "h": round(rep.haut, 2),
            "caches": caches,
            "calques": [{"id": f"k{n + 1}-{rang}", "nom": e["calque"], "texte": e["texte"], "bbox": rep.fraction(e["bbox"])}
                        for rang, e in enumerate(hors, 1)],
            "elements": [dict({"id": f"e{n + 1}-{rang}", "nature": e["nature"], "texte": e["texte"], "bbox": rep.fraction(e["bbox"])},
                              **({"cause": e["cause"]} if e.get("cause") else {}))
                         for rang, e in enumerate(analyse["elements"], 1)],
            "blocs": [{"id": f"b{n + 1}-{rang}", "n": rang, "bbox": rep.fraction(b[:4]), "texte": " ".join(b[4].split())[:90]}
                      for rang, b in enumerate(blocs, 1)],
        }

    def suite(self, de: int, budget: float = 0.3) -> tuple[list[dict], int | None]:
        """Les pages a partir de `de`, autant qu'il s'en lit dans le temps donne (au moins une)."""
        total = self.doc(len(self.tranches)).page_count
        debut, pages, n = time.perf_counter(), [], max(0, int(de))
        while n < total and (not pages or time.perf_counter() - debut < budget):
            pages.append(self.page_faits(n))
            n += 1
        return pages, (n if n < total else None)

    def faits(self) -> dict:
        """Toute la piece: l'en-tete et chacune de ses pages."""
        rendu = self.entete()
        rendu["pages"] = [self.page_faits(n) for n in range(len(rendu["pages"]))]
        return rendu

    # ------------------------------------------------------------ images

    def _pelee(self, version: int, n: int, familles: str):
        """La page sans ce qui est pose sur elle: ses images (`i`), ses traces (`t`). Son texte reste.

        Le retrait se fait en memoire, par un biffage qui epargne le texte. Les
        zones de biffage que le FICHIER porte sans les avoir appliquees ne
        doivent pas l'etre ici: elles sont neutralisees avant.
        """
        sorte = "pelee:" + familles
        for cle_ in [c for c in self._docs if c[1].startswith("pelee:") and c[1] != sorte]:
            del self._docs[cle_]                       # un seul exemplaire pele a la fois: chacun pese autant que la piece
        self._pelees = {p for p in self._pelees if p[1] == sorte}
        doc = self.doc(version, sorte=sorte)
        if (version, sorte, n) not in self._pelees:
            for xref in [a.xref for a in doc[n].annots() or [] if a.type[1] == "Redact"]:
                doc.xref_set_key(xref, "Subtype", "/Square")
            page = doc[n]
            page.add_redact_annot(PARTOUT, fill=False, cross_out=False)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_REMOVE if "i" in familles else pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED if "t" in familles else pymupdf.PDF_REDACT_LINE_ART_NONE,
                text=getattr(pymupdf, "PDF_REDACT_TEXT_NONE", 1))
            self._pelees.add((version, sorte, n))
        return doc[n]

    def image(self, version: int, page: int, calques: bool = False, echelle: float = ECHELLES[0], sans: str = "") -> str:
        """L'image d'une page, en adresse de donnees. Rien n'est ecrit sur disque.

        `sans` nomme ce qu'on retire pour voir dessous: `a` les annotations,
        `i` les images, `t` les traces (aplats et filets). Le texte reste.
        """
        version = max(1, min(len(self.tranches), int(version)))
        echelle = echelle if echelle in ECHELLES else ECHELLES[0]
        familles = "".join(f for f in "ait" if f in str(sans or ""))
        cle_ = (version, page, bool(calques), echelle, familles)
        if cle_ in self._images:
            self._images.move_to_end(cle_)
            return self._images[cle_]
        doc = self.doc(version, calques=bool(calques))
        if not 1 <= page <= doc.page_count:
            raise PieceIllisible(f"La page {page} n'existe pas dans cette version.")
        feuille = self._pelee(version, page - 1, familles.replace("a", "")) if ("i" in familles or "t" in familles) else doc[page - 1]
        reelle = min(echelle, (PIXELS_MAX / max(feuille.rect.width * feuille.rect.height, 1)) ** 0.5)
        rendu = feuille.get_pixmap(matrix=pymupdf.Matrix(reelle, reelle), alpha=False, annots="a" not in familles)
        grande_image = any(pymupdf.Rect(i["bbox"]).get_area() > 0.4 * feuille.rect.get_area()
                           for i in feuille.get_image_info())
        octets, genre = (rendu.tobytes("jpeg", jpg_quality=84), "jpeg") if grande_image else (rendu.tobytes("png"), "png")
        adresse = f"data:image/{genre};base64," + base64.b64encode(octets).decode("ascii")
        self._images[cle_] = adresse
        # Les images gardees se comptent au poids: une page de scan fortement agrandie pese plusieurs millions de signes.
        while len(self._images) > 48 or (len(self._images) > 2 and sum(len(i) for i in self._images.values()) > IMAGES_MAX):
            self._images.popitem(last=False)
        return adresse

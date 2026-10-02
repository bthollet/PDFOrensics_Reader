# -*- coding: utf-8 -*-
"""Les pièces FABRIQUÉES pour essayer PDForensics. Rien n'y vient d'un vrai document.

Les textes disent ce qu'ils sont (« ligne visible », « texte resté sous le cache ») : aucun nom de
personne, d'entreprise ou de lieu, aucune somme. Les dates sont rondes, le premier jour d'un mois de
l'an 2000, et ne datent rien.

Chaque pièce est fabriquée pour porter une réponse connue :

- couches      : mot remplacé sous un aplat blanc, cache noir, calque éteint,
                 page numérisée avec texte invisible, note, trois enregistrements ;
- simple       : rien à relever, un seul enregistrement ;
- remplacement : une phrase REMPLACÉE dans le contenu même, deux enregistrements ;
- calque       : un calque AFFICHÉ à l'ouverture ;
- image        : une image seule, sans aucun texte.

Les pièces s'écrivent là où l'appelant le demande : un dossier temporaire, pour les essais ; le dossier
`exemples/` du dépôt, quand ce fichier est lancé directement. Deux fabrications donnent les mêmes octets :
les exemples du dépôt sont, à l'octet près, les pièces que les essais fabriquent et lisent.

  python -B essais/pieces_epreuve.py [DOSSIER]    fabrique les cinq pièces dans DOSSIER (par défaut : `exemples/`)
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pymupdf

INSECABLE = chr(0xA0)


def ecrire(page, x, y, texte, taille=11, gras=False, **options) -> None:
    page.insert_text((x, y), texte, fontname="hebo" if gras else "helv", fontsize=taille, **options)


def largeur(texte: str, taille: float = 11) -> float:
    return pymupdf.get_text_length(texte, fontname="helv", fontsize=taille)


def cadre_de(page, morceau: str):
    """Où le morceau est écrit sur la page, lu sur la page elle-même."""
    for span in page.get_texttrace():
        ligne = "".join(chr(c[0]) for c in span["chars"]).replace(INSECABLE, " ")
        debut = ligne.find(morceau)
        if debut >= 0:
            cadre = pymupdf.Rect(span["chars"][debut][3])
            for lettre in span["chars"][debut:debut + len(morceau)]:
                cadre |= pymupdf.Rect(lettre[3])
            return cadre
    raise LookupError(morceau)


def meta(titre: str, origine: str, produit: str, cree: str, modifie: str | None = None) -> dict:
    return {"title": titre, "creator": origine, "producer": produit,
            "creationDate": cree, "modDate": modifie or cree}


def enregistrer(doc, chemin: Path) -> None:
    """Le premier enregistrement. Sans identifiant de fichier tiré au hasard : deux fabrications donnent les mêmes octets."""
    doc.save(chemin, no_new_id=True)
    doc.close()


def reenregistrer(doc, chemin: Path) -> None:
    """Un enregistrement de plus, ajouté à la fin du fichier : c'est ce qui fait une version."""
    doc.save(chemin, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP, no_new_id=True)
    doc.close()


def numeriser(page) -> bytes:
    """Une page tapée, rendue en image de travers et bruitée : comme le ferait un numériseur."""
    matrice = pymupdf.Matrix(150 / 72, 150 / 72).prerotate(0.5)
    image = page.get_pixmap(matrix=matrice, colorspace=pymupdf.csGRAY, alpha=False)
    gris = np.frombuffer(image.samples, np.uint8).reshape(image.height, image.width).astype(np.float32)
    bruit = np.random.default_rng(7).normal(0, 5, gris.shape)
    gris = np.clip(gris * 0.9 + 14 + bruit, 0, 255).astype(np.uint8)
    numerisee = pymupdf.Pixmap(pymupdf.csGRAY, image.width, image.height, gris.tobytes(), False)
    return numerisee.tobytes("jpeg", jpg_quality=72)


class Flux:
    """Écrit des blocs de haut en bas et change de page quand la place manque."""

    def __init__(self, doc) -> None:
        self.doc = doc
        self.nouvelle()

    def nouvelle(self) -> None:
        self.page = self.doc.new_page(width=595, height=842)
        self.y = 70.0

    def ligne(self, texte: str, taille: float = 11, gras: bool = False, apres: float = 6, **options) -> float:
        if self.y > 790:
            self.nouvelle()
        ecrire(self.page, 60, self.y, texte, taille, gras, **options)
        ou = self.y
        self.y += taille * 1.3 + apres
        return ou

    def paragraphe(self, texte: str, taille: float = 11, apres: float = 6) -> None:
        lignes = max(1, math.ceil(largeur(texte, taille) / 460))
        for essai in range(8):
            hauteur = (lignes + essai) * taille * 1.3 + 4
            if self.y + hauteur > 800:
                self.nouvelle()
            cadre = pymupdf.Rect(60, self.y - taille, 535, self.y - taille + hauteur)
            reste = self.page.insert_textbox(cadre, texte, fontname="helv", fontsize=taille, lineheight=1.3)
            if reste >= 0:
                self.y += hauteur - reste + apres
                return
        raise RuntimeError("paragraphe trop long pour la page")


# ------------------------------------------------------------------ textes

PHRASES = (
    "Cette phrase d'essai remplit la page sans rien décrire de réel.",
    "Le texte qui suit n'a pas d'autre rôle que d'occuper des lignes.",
    "Chaque section reprend les mêmes phrases dans un ordre différent.",
    "Une pièce fabriquée doit se lire comme un texte ordinaire.",
    "Les lignes passent à la suivante quand la largeur manque.",
    "Aucun nom, aucun lieu et aucune somme ne figurent dans ce texte.",
    "La section se poursuit par une phrase plus courte.",
    "Le lecteur relève ces lignes comme du texte affiché.",
)
CONCLUSION = "Fin du paragraphe d'essai : rien n'est à relever dans cette section."
SECTIONS = ("Première section", "Deuxième section", "Troisième section", "Quatrième section",
            "Cinquième section", "Sixième section", "Septième section", "Huitième section")
PHRASE_AVANT = "Cette ligne annonce 10 éléments sur 100."
PHRASE_APRES = "Cette ligne annonce 20 éléments sur 100."


def sections(flux: Flux, titres) -> None:
    for rang, titre in enumerate(titres, 1):
        if flux.y > 700:
            flux.nouvelle()
        flux.ligne(f"Section {rang} - {titre}", 12, True, apres=4)
        flux.paragraphe(" ".join(PHRASES[(rang * 3 + i) % len(PHRASES)] for i in range(3)))
        flux.paragraphe(CONCLUSION)
        flux.ligne(f"Repère de la section : {rang * 100}.", apres=2)
        flux.ligne("La section est terminée.", apres=16)


def document(doc, titre: str, titres, calque: int = 0) -> tuple[Flux, float]:
    """Un document de plusieurs sections ; rend aussi la hauteur où la phrase à remplacer est écrite."""
    flux = Flux(doc)
    options = {"oc": calque} if calque else {}
    flux.ligne("Pièce fabriquée par les essais de PDForensics", 10, apres=20, **options)
    flux.ligne(titre, 16, True, apres=10)
    flux.ligne("Document inventé pour l'essai.", apres=2)
    ou = flux.ligne(PHRASE_AVANT, apres=18)
    sections(flux, titres)
    return flux, ou


# ------------------------------------------------------------------ pièces

LIGNES = (
    ("Première ligne visible", "repère A", "valeur 100"),
    ("Deuxième ligne visible", "repère B", "valeur 200"),
    ("Mot écrit à l'origine", "repère C", "valeur 300"),
    ("Quatrième ligne visible", "repère D", "valeur 400"),
)
MOT_ORIGINE = LIGNES[2][0]
MOT_REMPLACE = "Mot remplacé"
DEBUT_COUVERT = "Ligne en partie couverte : "
FIN_COUVERTE = "texte resté sous le cache."
LIGNE_AJOUTEE = "Ligne ajoutée au troisième enregistrement."
NOTE = "À vérifier"
CALQUE_ETEINT = "Brouillon"
CALQUE_AFFICHE = "En-tête"
# Hauteur, texte tapé, taille, gras, puis le même texte tel qu'une reconnaissance de caractères le relit.
NUMERISEES = (
    (90, "Page numérisée", 18, True, "Page numérisée"),
    (130, "Première ligne tapée, puis numérisée.", 11, False, "Première ligne tapée, puis numérisée."),
    (150, "Deuxième ligne, relue avec des fautes.", 11, False, "Deuxierne ligne, relue avec des fautes."),
    (170, "Troisième ligne : le texte invisible double l'image.", 11, False,
     "Troisieme ligne : le texte invisible double l'irnage."),
    (230, "Dernière ligne de la page numérisée.", 11, False, "Dernière ligne de la page numérisée."),
)


def couches(chemin: Path) -> None:
    def donnees(modifie: str) -> dict:
        return meta("Document d'essai n° 1", "Logiciel de saisie (essai)", "Export PDF (essai)",
                    "D:20000101120000+00'00'", modifie)

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    ecrire(page, 60, 64, "DOCUMENT D'ESSAI - pièce fabriquée", 10)
    ecrire(page, 60, 104, "Document d'essai n° 1", 18, True)
    ecrire(page, 60, 140, "Cette pièce est fabriquée par les essais : elle ne décrit rien de réel.")
    ecrire(page, 60, 157, "Objet : essayer la lecture des couches d'un fichier.")
    # Un aplat dessiné AVANT le texte : un décor, pas un cache.
    page.draw_rect(pymupdf.Rect(56, 186, 539, 207), color=None, fill=(0.9, 0.93, 0.91))
    for x, entete in ((62, "Ligne"), (330, "Repère"), (440, "Valeur")):
        ecrire(page, x, 201, entete, 11, True)
    for rang, (ligne, repere, valeur) in enumerate(LIGNES):
        y = 224 + 22 * rang
        ecrire(page, 62, y, ligne)
        ecrire(page, 330, y, repere)
        ecrire(page, 440, y, valeur)
        page.draw_line((56, y + 7), (539, y + 7), color=(0.75, 0.78, 0.77), width=0.6)
    ecrire(page, 62, 330, DEBUT_COUVERT + FIN_COUVERTE)
    calque = doc.add_ocg(CALQUE_ETEINT, on=False)
    ecrire(page, 120, 610, "BROUILLON", 70, True, color=(0.8, 0.8, 0.8), oc=calque,
           morph=(pymupdf.Point(120, 610), pymupdf.Matrix(-32)))
    ecrire(page, 62, 404, "Version de travail : ce texte est sur un calque éteint.",
           10, color=(0.35, 0.35, 0.35), oc=calque)

    source = pymupdf.open()
    tapee = source.new_page(width=595, height=842)
    for y, texte, taille, gras, _relu in NUMERISEES:
        ecrire(tapee, 60, y, texte, taille, gras)
    numerisee = doc.new_page(width=595, height=842)
    numerisee.insert_image(numerisee.rect, stream=numeriser(tapee))
    for y, _texte, taille, gras, relu in NUMERISEES:
        ecrire(numerisee, 60, y, relu, taille, gras, render_mode=3)
    doc.set_metadata(donnees("D:20000101120000+00'00'"))
    enregistrer(doc, chemin)

    # Deuxième enregistrement : un mot remplacé sous un aplat blanc, et une note.
    doc = pymupdf.open(chemin)
    page = doc[0]
    y = 224 + 22 * 2
    page.draw_rect(cadre_de(page, MOT_ORIGINE) + (-3, -1, 4, 1), color=None, fill=(1, 1, 1))
    ecrire(page, 62, y, MOT_REMPLACE)
    page.add_text_annot((546, y - 14), NOTE)
    doc.set_metadata(donnees("D:20000201120000+00'00'"))
    reenregistrer(doc, chemin)

    # Troisième enregistrement : un cache noir sur la fin d'une ligne, et une ligne ajoutée.
    doc = pymupdf.open(chemin)
    page = doc[0]
    page.draw_rect(cadre_de(page, FIN_COUVERTE) + (-2, -1, 2, 1), color=(0, 0, 0), fill=(0, 0, 0))
    ecrire(page, 62, 364, LIGNE_AJOUTEE)
    doc.set_metadata(donnees("D:20000301120000+00'00'"))
    reenregistrer(doc, chemin)


def simple(chemin: Path) -> None:
    doc = pymupdf.open()
    document(doc, "Document d'essai sans rien à relever", SECTIONS)
    doc.set_metadata(meta("Document d'essai n° 2", "Logiciel de saisie (essai)", "Logiciel de saisie (essai)",
                          "D:20000401120000+00'00'"))
    enregistrer(doc, chemin)


def remplacement(chemin: Path) -> None:
    def donnees(modifie: str) -> dict:
        return meta("Document d'essai n° 3", "Logiciel de saisie (essai)", "Logiciel de saisie (essai)",
                    "D:20000501120000+00'00'", modifie)

    doc = pymupdf.open()
    _flux, ou = document(doc, "Document d'essai à phrase remplacée", SECTIONS[:5])
    doc.set_metadata(donnees("D:20000501120000+00'00'"))
    enregistrer(doc, chemin)

    # Deuxième enregistrement : la phrase est RETIRÉE du contenu, une autre est écrite à sa place.
    doc = pymupdf.open(chemin)
    page = doc[0]
    page.add_redact_annot(cadre_de(page, PHRASE_AVANT) + (-1, -1, 1, 1), fill=False)
    page.apply_redactions()
    ecrire(page, 60, ou, PHRASE_APRES)
    doc.set_metadata(donnees("D:20000601120000+00'00'"))
    reenregistrer(doc, chemin)


def calque(chemin: Path) -> None:
    doc = pymupdf.open()
    affiche = doc.add_ocg(CALQUE_AFFICHE, on=True)
    document(doc, "Document d'essai à calque affiché", SECTIONS[:3], calque=affiche)
    doc.set_metadata(meta("Document d'essai n° 4", "Logiciel de saisie (essai)", "Export PDF (essai)",
                          "D:20000701120000+00'00'"))
    enregistrer(doc, chemin)


def image_seule(chemin: Path) -> None:
    source = pymupdf.open()
    flux = Flux(source)
    flux.ligne("PAGE D'ESSAI - pièce fabriquée", 10, apres=20)
    flux.ligne("Page tapée, puis rendue en image", 16, True, apres=10)
    flux.paragraphe("Cette page est écrite, puis rendue en image comme le ferait un numériseur : "
                    "le fichier ne garde aucun texte, seulement l'image.", apres=12)
    flux.ligne("Lignes de la page", 12, True, apres=4)
    for ligne in ("première ligne de la liste", "deuxième ligne de la liste",
                  "troisième ligne de la liste", "quatrième ligne de la liste"):
        flux.ligne("- " + ligne, apres=2)
    flux.y += 10
    flux.ligne("Fin de la page", 12, True, apres=4)
    flux.paragraphe("Rien de ce qui est écrit ici ne doit se retrouver comme texte dans la pièce.")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=numeriser(source[0]))
    doc.set_metadata(meta("", "Numériseur (essai)", "Numériseur (essai)", "D:20000801120000+00'00'"))
    enregistrer(doc, chemin)


# La clé, le nom du fichier, le dossier où il se range, et ce qui le fabrique.
PIECES = (
    ("couches", "Document d'essai à trois enregistrements", "Essais - couches", couches),
    ("simple", "Document d'essai sans rien à relever", "Essais - texte", simple),
    ("remplacement", "Document d'essai à phrase remplacée", "Essais - texte", remplacement),
    ("calque", "Document d'essai à calque affiché", "Essais - texte", calque),
    ("image", "Document d'essai en image seule", "Essais - image", image_seule),
)
DOSSIERS = sorted({dossier for _cle, _nom, dossier, _fabrique in PIECES}, key=str.casefold)


def fabriquer_tout(dossier: Path) -> dict[str, Path]:
    """Écrit les pièces dans leurs sous-dossiers ; rend le chemin de chacune par sa clé."""
    rendu = {}
    for cle, nom, famille, fabrique in PIECES:
        (dossier / famille).mkdir(parents=True, exist_ok=True)
        chemin = dossier / famille / f"{nom}.pdf"
        chemin.unlink(missing_ok=True)
        fabrique(chemin)
        rendu[cle] = chemin
    return rendu


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cible = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "exemples"
    for piece in fabriquer_tout(cible).values():
        print(f"{piece.stat().st_size:>8} octets  {piece.relative_to(cible).as_posix()}")

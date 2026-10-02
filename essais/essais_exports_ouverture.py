# -*- coding: utf-8 -*-
"""L'ouverture reelle des exports OpenDocument: LibreOffice les ouvre, en tire un PDF, et ce PDF est relu.

  python -B essais/essais_exports_ouverture.py              joue les essais d'export, puis fait ouvrir chaque fichier
  python -B essais/essais_exports_ouverture.py --images D   en plus, une image par page de chaque PDF, dans le dossier D

A NE LANCER QUE VOLONTAIREMENT. Pour mettre un document en pages, LibreOffice interroge l'imprimante
du poste: cela peut se voir comme des tentatives d'impression. Aucun flux automatique ne lance ce script.

Tout s'ecrit dans un dossier temporaire, supprime a la fin: les fichiers, les PDF que LibreOffice en
tire, et le profil a part que LibreOffice emploie. Seules les images demandees restent, la ou on les
demande. Sans LibreOffice, le script le dit et s'en tient a ce que essais_exports.py verifie deja.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True  # meme lance sans -B, rien ne s'ecrit a cote des sources

import essais_exports as base  # noqa: E402 - pose aussi le chemin du paquet
from essais_exports import ABSENT, ECHECS, FICHES, PRODUITS, essai  # noqa: E402


def libreoffice() -> str | None:
    """Ou LibreOffice est installe: dans un dossier de programmes de Windows, ou sur le chemin des commandes."""
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        racine = os.environ.get(variable, "")
        if racine and (Path(racine) / "LibreOffice" / "program" / "soffice.exe").is_file():
            return str(Path(racine) / "LibreOffice" / "program" / "soffice.exe")
    return shutil.which("soffice")


def convertir(soffice: str, fichiers: list[Path], dossier: Path) -> list[str]:
    """Fait convertir les fichiers en PDF par LibreOffice: sans affichage, avec un profil a part."""
    commande = [soffice, "-env:UserInstallation=" + (dossier / "profil").as_uri(), "--headless", "--norestore",
                "--convert-to", "pdf", "--outdir", str(dossier), *map(str, fichiers)]
    try:
        retour = subprocess.run(commande, capture_output=True, timeout=600, check=False)  # noqa: S603 - LibreOffice, sur nos fichiers
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return [f"LibreOffice ne répond pas ({type(erreur).__name__})"]
    return [f"LibreOffice sort sur le code {retour.returncode}"] if retour.returncode else []


def squelette(texte: str) -> str:
    """Le texte sans aucun blanc, ligatures defaites: un nom coupe en fin de ligne se retrouve quand meme."""
    return "".join(unicodedata.normalize("NFKC", texte).split())


def pages_du_pdf(pdf: Path, images: Path | None) -> tuple[list[str], set[str]]:
    """Le texte de chaque page, lu du haut vers le bas, et les polices que le PDF emploie."""
    import pymupdf

    with pymupdf.open(pdf) as document:
        textes = [page.get_text("text", sort=True) for page in document]
        polices = {police[3] for rang in range(len(document)) for police in document.get_page_fonts(rang)}
        if images is not None:
            images.mkdir(parents=True, exist_ok=True)
            for rang, page in enumerate(document, 1):
                page.get_pixmap(dpi=100).save(images / f"{pdf.stem}_page{rang}.png")
    return textes, polices


def pages_du_document(textes: list[str], polices: set[str]) -> list[str]:
    """Le PDF du document nominal: une fiche par page, des pages numerotees, la police declaree."""
    defauts = [] if len(textes) == 1 + len(FICHES) else [f"{len(textes)} pages pour {len(FICHES)} fiches"]
    for rang, fiche in enumerate(FICHES, 1):
        if rang >= len(textes) or not squelette(textes[rang]).startswith(squelette(fiche["nom"])):
            defauts.append(f"la fiche {rang} n'ouvre pas sa page")
    defauts += [f"page {rang} sans son numéro" for rang, texte in enumerate(textes, 1)
                if squelette(f"Page {rang} sur {len(textes)}") not in squelette(texte)]
    if not polices or any("LiberationSans" not in police for police in polices) or not any("Bold" in police for police in polices):
        defauts.append(f"polices : {sorted(polices)}")
    return defauts


def ouverture_reelle(dossier: Path, images: Path | None) -> None:
    """Fait ouvrir chaque fichier par LibreOffice, qui en tire un PDF; relit chaque PDF."""
    soffice = libreoffice()
    if not soffice:
        print("NON FAIT ouverture réelle : LibreOffice n'est pas installé, la vérification s'arrête à la structure.")
        return
    pannes = convertir(soffice, [fichier for fichier, _ in PRODUITS], dossier)
    pdfs = {fichier: dossier / f"{fichier.stem}.pdf" for fichier, _ in PRODUITS}
    essai("LibreOffice convertit chaque fichier en PDF",
          pannes + [f"pas de PDF pour {fichier.name}" for fichier, pdf in pdfs.items() if not pdf.is_file()], f"{len(pdfs)} fichiers")
    defauts: list[str] = []
    lus: dict[Path, tuple[list[str], set[str]]] = {}
    for fichier, attendus in PRODUITS:
        if not pdfs[fichier].is_file():
            continue
        try:
            lus[fichier] = pages_du_pdf(pdfs[fichier], images)
        except Exception as erreur:  # noqa: BLE001 - un PDF illisible est un defaut de l'essai, pas une panne du script
            defauts.append(f"{pdfs[fichier].name} ne se lit pas ({type(erreur).__name__})")
            continue
        corps = squelette("".join(lus[fichier][0]))
        absents = [attendu for attendu in attendus if squelette(attendu) not in corps]
        if absents or squelette(ABSENT) in corps:
            defauts.append(f"{pdfs[fichier].name} : {len(absents)} texte(s) absent(s) sur {len(attendus)}, ou témoin retrouvé")
    essai("PDF relus : titre, sous-titre et noms de pièces", defauts, f"{len(lus)} PDF")
    nominal = PRODUITS[0][0]
    essai("PDF du document : une fiche par page, pages numérotées, Liberation Sans",
          pages_du_document(*lus[nominal]) if nominal in lus else ["le PDF du document nominal manque"])


def principal() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    images = Path(os.path.abspath(sys.argv[sys.argv.index("--images") + 1])) if "--images" in sys.argv else None
    dossier = Path(tempfile.mkdtemp(prefix="pdforensics-ouverture-"))
    try:
        base.jouer(dossier)
        ouverture_reelle(dossier, images)
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    print("VERDICT :", "tout passe" if not ECHECS else f"{len(ECHECS)} échec(s) : " + " ; ".join(ECHECS))
    return 1 if ECHECS else 0


if __name__ == "__main__":
    sys.exit(principal())

# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller de PDForensics : un seul fichier, PDForensics.exe, fenêtre sans console.
#
#   python -B packaging/construire.py
#
# Les chemins partent de l'emplacement de cette recette : rien ne dépend du poste qui construit.
# L'exécutable embarque PyMuPDF : il se distribue selon l'AGPL-3.0 (voir LICENCES-TIERCES.md).
from pathlib import Path

RACINE = Path(SPECPATH).resolve().parent

analyse = Analysis(
    [str(RACINE / "packaging" / "lanceur.py")],
    pathex=[str(RACINE)],
    binaries=[],
    # Les fragments de l'écran : un gabarit, une feuille de style, des scripts. Ils se retrouvent à l'exécution
    # dans le dossier où l'exécutable déploie ses fichiers, sous pdforensics/ecran.
    datas=[(str(RACINE / "pdforensics" / "ecran"), "pdforensics/ecran")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
archive = PYZ(analyse.pure)
executable = EXE(
    archive,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="PDForensics",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,  # une panne ne montre ni chemin ni nom de fichier
)

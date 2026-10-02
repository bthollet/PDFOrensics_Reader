# -*- coding: utf-8 -*-
"""Construire PDForensics.exe avec PyInstaller.

  python -B packaging/construire.py [--sortie DOSSIER]

Tout s'écrit dans DOSSIER - par défaut `_construction_locale`, à la racine du dépôt, que Git ignore :
l'exécutable dans DOSSIER/dist, les fichiers de travail dans DOSSIER/build, le cache de PyInstaller dans
DOSSIER/cache. Rien n'est écrit ailleurs, et aucun chemin n'est supposé : tout part de l'emplacement de
ce fichier.

L'exécutable construit embarque PyMuPDF : il se distribue selon l'AGPL-3.0 (voir LICENCES-TIERCES.md).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def principal(arguments: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sortie = Path(os.path.abspath(arguments[arguments.index("--sortie") + 1])) if "--sortie" in arguments else RACINE / "_construction_locale"
    sortie.mkdir(parents=True, exist_ok=True)
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(sortie / "cache")  # le cache de PyInstaller reste dans le dossier de sortie
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # rien ne s'écrit à côté des sources, ni des bibliothèques
    import PyInstaller.__main__

    PyInstaller.__main__.run([str(RACINE / "packaging" / "PDForensics.spec"), "--noconfirm", "--clean",
                              "--distpath", str(sortie / "dist"), "--workpath", str(sortie / "build")])
    executable = sortie / "dist" / "PDForensics.exe"
    if not executable.is_file():
        print("ECHEC : l'exécutable n'a pas été construit.")
        return 1
    print(f"Exécutable construit : {executable.name}, {executable.stat().st_size} octets, dans le dossier dist de la sortie.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))

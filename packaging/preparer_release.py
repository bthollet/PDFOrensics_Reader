# -*- coding: utf-8 -*-
"""Rassembler ce qu'une release porte : l'exécutable, le zip des exemples, les textes de licence, la note de version.

  python -B packaging/preparer_release.py [--sortie DOSSIER]    écrit DOSSIER/release
  python -B packaging/preparer_release.py --verifier-etiquette  l'étiquette (variable ETIQUETTE) porte-t-elle la version du paquet ?

DOSSIER est celui de `construire.py` (par défaut `_construction_locale`, que Git ignore). Dans
DOSSIER/release sont posés :

- PDForensics.exe              l'exécutable construit, recopié de DOSSIER/dist ;
- PDForensics-exemples.zip     les PDF du dossier `exemples/`, les mêmes, dans la même arborescence ;
- AGPL-3.0.txt                 la licence sous laquelle l'exécutable se distribue, recopiée de `licences/` ;
- LICENCES-TIERCES-textes.txt  les textes de licence des bibliothèques, relevés dans les paquets installés ;
- notes-de-release.md          le texte de la release, avec la taille et l'empreinte de l'exécutable et du zip.

Le zip est fait pour se refaire à l'identique : entrées triées, date fixe, mêmes réglages de compression.

La variable DEPOT donne l'adresse du dépôt à citer dans la note ; ETIQUETTE, l'étiquette de la version
(par défaut : « v » suivi de la version du paquet).

Ce script ne publie rien : il écrit des fichiers sur le poste, et s'arrête là. Une release se crée à la
main, en brouillon, avec ces fichiers.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import zipfile
from importlib import metadata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
EXIGENCES = (("à l'exécution", RACINE / "requirements.txt"), ("pour construire", RACINE / "packaging" / "requirements-construction.txt"))
TEXTE_DE_LICENCE = re.compile(r"(?i)(licen[cs]e|copying|notice)")
ZIP_DES_EXEMPLES = "PDForensics-exemples.zip"
DATE_DU_ZIP = (2000, 1, 1, 12, 0, 0)  # la date que portent les entrées du zip : fixe, pour qu'il se refasse à l'identique


def version() -> str:
    """La version du paquet, lue dans son fichier sans l'importer."""
    trouve = re.search(r'^__version__ = "([^"]+)"$', (RACINE / "pdforensics" / "__init__.py").read_text(encoding="utf-8"), re.MULTILINE)
    if not trouve:
        raise SystemExit("la version du paquet ne se lit pas")
    return trouve.group(1)


def epingles(fichier: Path) -> list[tuple[str, str]]:
    """Les bibliothèques épinglées dans un fichier d'exigences : (nom, version)."""
    return re.findall(r"^([A-Za-z0-9_.-]+)==([^\s#]+)", fichier.read_text(encoding="utf-8"), re.MULTILINE)


def textes_des_licences() -> tuple[str, list[str]]:
    """Les textes de licence relevés dans les paquets installés, et ce qui manque."""
    morceaux, manques, vus = [], [], set()
    for usage, fichier in EXIGENCES:
        for nom, epingle in epingles(fichier):
            if nom.casefold() in vus:
                continue
            vus.add(nom.casefold())
            try:
                paquet = metadata.distribution(nom)
            except metadata.PackageNotFoundError:
                manques.append(f"{nom} n'est pas installé")
                continue
            if paquet.version != epingle:
                manques.append(f"{nom} est installé en version {paquet.version}, et non {epingle}")
            declaree = paquet.metadata.get("License-Expression") or (paquet.metadata.get("License") or "").strip().splitlines()[:1]
            declaree = declaree if isinstance(declaree, str) else (declaree[0] if declaree else "voir le texte")
            textes = [f for f in paquet.files or [] if ".dist-info" in f.parts[0] and TEXTE_DE_LICENCE.search(f.name)]
            morceaux.append(f"{'=' * 100}\n{nom} {paquet.version} - employé {usage} - licence déclarée : {declaree}\n{'=' * 100}\n")
            if not textes:
                morceaux.append("(Ce paquet ne joint aucun texte de licence : voir la licence déclarée ci-dessus.)\n")
            for texte in textes:
                morceaux.append(f"--- {texte.as_posix()} ---\n" + paquet.locate_file(texte).read_text(encoding="utf-8", errors="replace").rstrip() + "\n")
    python = Path(sys.base_prefix) / "LICENSE.txt"
    morceaux.append(f"{'=' * 100}\nPython {sys.version.split()[0]} - l'interpréteur embarqué dans l'exécutable\n{'=' * 100}\n")
    morceaux.append(python.read_text(encoding="utf-8", errors="replace").rstrip() + "\n" if python.is_file()
                    else "(Le texte de la licence de Python n'est pas joint à cette installation : il se lit sur le site de Python.)\n")
    return "\n".join(morceaux), manques


def zip_des_exemples(cible: Path) -> int:
    """Le zip des exemples : les PDF du dossier `exemples/`, sous le même chemin. Rend le nombre de fichiers."""
    fichiers = sorted((fichier for fichier in (RACINE / "exemples").rglob("*") if fichier.is_file()),
                      key=lambda fichier: fichier.relative_to(RACINE).as_posix())
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for fichier in fichiers:
            entree = zipfile.ZipInfo(fichier.relative_to(RACINE).as_posix(), date_time=DATE_DU_ZIP)
            entree.compress_type = zipfile.ZIP_DEFLATED
            entree.create_system = 0  # le même zip, quel que soit le poste qui le fait
            entree.external_attr = 0
            archive.writestr(entree, fichier.read_bytes(), compresslevel=9)
    return len(fichiers)


def empreinte(fichier: Path) -> str:
    return hashlib.sha256(fichier.read_bytes()).hexdigest()


def notes(etiquette: str, depot: str, executable: Path, exemples: Path, combien: int) -> str:
    versions = dict((nom.casefold(), v) for _usage, fichier in EXIGENCES for nom, v in epingles(fichier))
    source = f"{depot}/tree/{etiquette}" if depot else f"le dépôt de PDForensics, à l'étiquette `{etiquette}`"
    # D'où vient l'exécutable : le texte ne dit que ce qui a été fait.
    origine = ("Il a été construit à la demande sur une machine de GitHub : c'est une pièce de vérification, pas l'exécutable d'une release."
               if os.environ.get("GITHUB_ACTIONS") else
               "Il a été construit sur un poste, hors ligne, depuis ce dépôt, puis essayé fenêtre cachée et passé au contrôle de "
               "publication. Il n'a été essayé que sous Windows 11.")
    return f"""# PDForensics {etiquette}

PDForensics montre ce qu'un PDF contient sous la page qu'on voit : versions enregistrées, zones recouvertes,
calques éteints, texte invisible, métadonnées. Ce qui est ouvert est lu sur le poste et n'en sort pas.

## Fichiers joints

- `{executable.name}` : l'outil, pour Windows 64 bits. {executable.stat().st_size} octets, SHA-256 `{empreinte(executable)}`.
- `{exemples.name}` : {combien} PDF fabriqués pour l'essai, à ouvrir avec l'outil ; ce sont ceux du dossier `exemples/` du
  dépôt. {exemples.stat().st_size} octets, SHA-256 `{empreinte(exemples)}`.
- `AGPL-3.0.txt` : la licence sous laquelle l'exécutable se distribue ; le même texte que `licences/AGPL-3.0.txt` dans le dépôt.
- `LICENCES-TIERCES-textes.txt` : les textes de licence des bibliothèques que l'exécutable embarque, tels que leurs auteurs
  les publient.

## Licence

Cet exécutable embarque PyMuPDF {versions.get('pymupdf', '')} et MuPDF. **Il se distribue donc selon la licence GNU Affero General Public
License, version 3 (AGPL-3.0)**, dont le texte est joint. Le code de PDForensics lui-même est publié sous 0BSD ; cela ne change
rien à la licence de l'exécutable. Ce que l'exécutable embarque, et sous quelles licences, est dit dans `LICENCES-TIERCES.md`,
dans le dépôt.

Le code source correspondant à cet exécutable est : {source}. Il porte la recette de construction (`packaging/`) et les
versions exactes des bibliothèques (`requirements.txt`). Les sources de PyMuPDF et de MuPDF sont celles que leurs auteurs
publient pour ces versions.

## Avant de l'employer

- **L'exécutable n'est pas signé** : Windows peut afficher un avertissement au premier lancement.
- {origine}
- Il lui faut le moteur d'affichage Microsoft Edge WebView2, fourni avec Windows 11.
- Il n'écrit qu'un fichier hors d'un export : ses réglages, sous le dossier de données locales de l'utilisateur.
- Les exemples ne viennent d'aucun vrai document : leurs textes disent ce qu'ils sont, et leurs dates ne datent rien.
"""


def principal(arguments: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    etiquette = os.environ.get("ETIQUETTE", "") or "v" + version()
    if "--verifier-etiquette" in arguments:
        accord = etiquette == "v" + version()
        print(f"Étiquette {etiquette}, version du paquet {version()} : " + ("elles s'accordent." if accord else "ELLES NE S'ACCORDENT PAS."))
        return 0 if accord else 1
    sortie = Path(os.path.abspath(arguments[arguments.index("--sortie") + 1])) if "--sortie" in arguments else RACINE / "_construction_locale"
    executable, release = sortie / "dist" / "PDForensics.exe", sortie / "release"
    if not executable.is_file():
        print("ECHEC : l'exécutable n'est pas construit.")
        return 1
    textes, manques = textes_des_licences()
    if manques:
        print("ECHEC : " + " ; ".join(manques))
        return 1
    shutil.rmtree(release, ignore_errors=True)
    release.mkdir(parents=True)
    shutil.copyfile(executable, release / executable.name)
    combien = zip_des_exemples(release / ZIP_DES_EXEMPLES)
    shutil.copyfile(RACINE / "licences" / "AGPL-3.0.txt", release / "AGPL-3.0.txt")
    (release / "LICENCES-TIERCES-textes.txt").write_text(textes, encoding="utf-8", newline="\n")
    (release / "notes-de-release.md").write_text(notes(etiquette, os.environ.get("DEPOT", ""), release / executable.name, release / ZIP_DES_EXEMPLES,
                                                       combien), encoding="utf-8", newline="\n")
    for fichier in sorted(release.iterdir()):
        print(f"{fichier.stat().st_size:>10} octets  {empreinte(fichier)}  {fichier.name}")
    print(f"Release préparée pour {etiquette} : {len(list(release.iterdir()))} fichiers. Rien n'est publié.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))

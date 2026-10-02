# Licences tierces

Le code de ce dépôt est publié sous la licence 0BSD (fichier `LICENSE`). **L'exécutable `PDForensics.exe`, lui,
ne l'est pas** : il embarque PyMuPDF et MuPDF, publiés sous l'AGPL-3.0, et se distribue donc **selon la licence
GNU Affero General Public License, version 3**. Son texte est dans `licences/AGPL-3.0.txt` ; il est joint à
chaque release de l'exécutable.

Le code source correspondant à un exécutable publié est ce dépôt, à l'étiquette de la version : il porte le
code de PDForensics, la recette de construction (`packaging/`) et les versions exactes des bibliothèques
(`requirements.txt`, `packaging/requirements-construction.txt`). Les sources de PyMuPDF et de MuPDF sont
celles que leurs auteurs publient pour ces versions.

Qui redistribue l'exécutable, modifié ou non, doit respecter l'AGPL-3.0 : joindre son texte, et donner accès
au code source correspondant.

## Ce que l'exécutable embarque

| Composant | Version | Licence déclarée | Ce qu'il fait ici |
|---|---|---|---|
| PyMuPDF | 1.28.2 | AGPL-3.0, ou licence commerciale de son éditeur | lit les PDF |
| MuPDF, dans PyMuPDF | 1.28.2 | AGPL-3.0, ou licence commerciale de son éditeur | le moteur de lecture des PDF |
| pywebview | 6.2.1 | BSD-3-Clause | la fenêtre |
| numpy | 2.5.3 | BSD-3-Clause ; des parties embarquées sous 0BSD, MIT, Zlib et CC0-1.0 | compare les images de deux versions d'une page |
| pythonnet | 3.1.0 | MIT | le lien entre Python et la fenêtre de Windows |
| clr_loader | 0.3.1 | MIT | employé par pythonnet |
| cffi | 2.1.1 | MIT-0 | employé par clr_loader |
| pycparser | 3.0 | BSD-3-Clause | employé par cffi |
| proxy_tools | 0.1.0 | MIT | employé par pywebview |
| bottle | 0.13.4 | MIT | employé par pywebview ; PDForensics n'ouvre aucun serveur |
| typing_extensions | 4.16.0 | PSF-2.0 | employé par pywebview |
| Python | 3.12 | PSF-2.0 | l'interpréteur |
| Lanceur de PyInstaller | 6.22.2 | GPL-2.0 ou ultérieure, avec une exception : un programme construit avec PyInstaller n'est pas soumis à la GPL | démarre l'exécutable |
| Crochets d'exécution de pyinstaller-hooks-contrib | 2026.7 | Apache-2.0 pour les crochets embarqués à l'exécution | préparent les bibliothèques au démarrage |

S'y ajoutent des bibliothèques de Microsoft, fournies par les paquets ci-dessus et redistribuées selon les
licences de Microsoft qui le permettent : l'accès au moteur d'affichage Microsoft Edge WebView2 (avec
pywebview), des bibliothèques .NET (avec pythonnet) et la bibliothèque d'exécution de Visual C++ (avec Python).
MuPDF et numpy embarquent à leur tour des bibliothèques tierces, sous leurs propres licences, dont la liste
figure dans leurs sources.

Le moteur d'affichage Microsoft Edge WebView2 lui-même n'est pas embarqué : c'est celui du poste.

## Ce qui sert seulement à construire

Ces bibliothèques ne se retrouvent pas dans l'exécutable.

| Composant | Version | Licence déclarée |
|---|---|---|
| PyInstaller | 6.22.2 | GPL-2.0 ou ultérieure, avec l'exception dite ci-dessus |
| pyinstaller-hooks-contrib | 2026.7 | GPL-2.0 ou ultérieure pour les crochets de construction |
| altgraph | 0.17.5 | MIT |
| pefile | 2024.8.26 | MIT |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 ou BSD-2-Clause |
| setuptools | 84.0.0 | MIT |

## Les textes

Les textes de licence de ces bibliothèques sont dans les paquets installés. `packaging/preparer_release.py`
les relève et les rassemble dans `LICENCES-TIERCES-textes.txt`, joint à chaque release de l'exécutable avec
le texte de l'AGPL-3.0.

Les licences déclarées ci-dessus sont celles que chaque paquet annonce dans ses métadonnées, à la version
indiquée. Un changement de version demande de les relire.

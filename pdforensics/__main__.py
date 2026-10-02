# -*- coding: utf-8 -*-
"""Lancer PDForensics.

  python -B -m pdforensics                               la fenêtre ; l'explorateur s'ouvre sur le dossier personnel
  python -B -m pdforensics DOSSIER                       la fenêtre ; l'explorateur s'ouvre sur ce dossier
  python -B -m pdforensics --essai-pont DOSSIER RAPPORT  l'auto-essai : fenêtre cachée, compte rendu dans RAPPORT

L'exécutable construit prend les mêmes arguments. Rien ne s'écrit en console : la fenêtre n'en a pas.
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import application, auto_essai, moteur


def principal(arguments: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if arguments[:1] == ["--essai-pont"]:
        return auto_essai.lancer(Path(arguments[1]), Path(arguments[2])) if len(arguments) == 3 else 2
    try:
        moteur.exiger()
    except moteur.MoteurAbsent as absence:
        moteur.prevenir(str(absence))
        return 3
    if arguments:
        application.DEPART = Path(arguments[0]).resolve()
    application.ouvrir_fenetre(application.Api())
    return 0


if __name__ == "__main__":
    sys.exit(principal())

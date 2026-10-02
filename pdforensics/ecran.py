# -*- coding: utf-8 -*-
"""Assembler l'ecran: un gabarit, une feuille de style, et des fragments de script.

Les fragments du dossier `ecran/` sont les morceaux d'UNE seule fonction: ils
se lisent dans l'ordre de leur nom et partagent leurs variables. Ils se
decouvrent par leur forme (`*.js`), jamais par une liste: un fragment ajoute
est pris le jour meme.
"""
from __future__ import annotations

import sys
from pathlib import Path


def dossier_des_fragments() -> Path:
    """Ou sont les fragments: a cote de ce module, ou la ou l'executable deploie ses fichiers."""
    deploye = getattr(sys, "_MEIPASS", None)
    if deploye and (Path(deploye) / "pdforensics" / "ecran").is_dir():
        return Path(deploye) / "pdforensics" / "ecran"
    return Path(__file__).resolve().parent / "ecran"


def assembler(pont: str = "", apres: str = "") -> str:
    """L'ecran complet. `pont` s'insere avant le script (un pont de remplacement); `apres`, en fin de page."""
    dossier = dossier_des_fragments()
    gabarit = (dossier / "ecran.html").read_text(encoding="utf-8")
    style = (dossier / "ecran.css").read_text(encoding="utf-8")
    script = "\n".join(fragment.read_text(encoding="utf-8") for fragment in sorted(dossier.glob("*.js")))
    for repere in ("/*STYLE*/", "<!--PONT-->", "/*SCRIPT*/", "<!--APRES-->"):
        if gabarit.count(repere) != 1:
            raise RuntimeError(f"le repere {repere} manque ou se repete dans le gabarit")
    return (gabarit.replace("/*STYLE*/", style).replace("<!--PONT-->", pont)
            .replace("/*SCRIPT*/", script).replace("<!--APRES-->", apres))

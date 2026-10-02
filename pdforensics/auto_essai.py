# -*- coding: utf-8 -*-
"""L'auto-essai du pont : la vraie fenêtre, cachée, pilotée par les gestes de l'utilisateur.

  python -B -m pdforensics --essai-pont DOSSIER RAPPORT
  PDForensics.exe --essai-pont DOSSIER RAPPORT

La fenêtre s'ouvre sans se montrer, sur DOSSIER. Le pilote attend que l'écran soit prêt, compte ce que
l'explorateur liste, clique la première pièce, attend que toutes ses pages soient lues, puis écrit RAPPORT
et ferme.

CE QUE L'AUTO-ESSAI ÉCRIT, et rien d'autre : RAPPORT, un compte rendu JSON. Il porte des comptes, des
libellés de l'écran, le titre de la pièce ouverte (le nom de son fichier) et le nombre de ports ouverts
par ce processus ; aucun chemin. Les réglages de l'utilisateur ne sont ni lus ni écrits : pendant
l'auto-essai, le fichier de réglages est un fichier absent, à côté du rapport.

CE QU'IL NE VOIT PAS : les ports qu'ouvrirait un processus du moteur d'affichage, et non celui de l'outil.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from . import application, moteur

ATTENTE = 40.0  # secondes, pour chaque étape : une machine de construction est lente


def ports_du_processus() -> dict:
    """Combien de ports ce processus tient ouverts, lu dans la table des connexions du poste."""
    systeme = Path(os.environ.get("SystemRoot", "")) / "System32" / "netstat.exe"
    commande = [str(systeme) if systeme.is_file() else "netstat", "-ano"]
    sortie = subprocess.run(commande, capture_output=True, stdin=subprocess.DEVNULL, check=False,  # noqa: S603
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("ascii", "replace")
    lignes = [mots for mots in (ligne.split() for ligne in sortie.splitlines()) if mots and mots[0] in ("TCP", "UDP")]
    return {"connexions_lues": len(lignes), "ports": sum(1 for mots in lignes if mots[-1] == str(os.getpid()))}


def piloter(vue, releve: dict) -> None:
    """Les gestes de l'utilisateur, faits par leurs noms ; ce qui est vu va dans `releve`."""
    def js(code: str):
        return vue.evaluate_js(code)

    def attendre(code: str) -> bool:
        fin = time.monotonic() + ATTENTE
        while time.monotonic() < fin:
            if js(code):
                return True
            time.sleep(0.2)
        return False

    import webview

    releve["moteur"] = str(webview.renderer or "")
    releve["pret"] = attendre("!!(window.lecteur && window.lecteur.pret)")
    releve["bandeau"] = js("document.querySelector('.bandeau').textContent")
    releve["dossiers"] = js("document.querySelectorAll('#liste-src .dossier').length")
    releve["pieces"] = js("document.querySelectorAll('#liste-src .piece').length")
    if releve["pret"] and releve["pieces"]:
        js("document.querySelector('#liste-src .piece button').click()")
        releve["piece"] = attendre("!!window.lecteur.piece() && window.lecteur.complet()")  # la pièce, et toutes ses pages
        releve["titre"] = js("document.getElementById('titre').textContent")
        releve["comptes"] = js("Array.prototype.map.call(document.querySelectorAll('#regards .compte'),"
                               " function (c) { return c.textContent; }).join('/')")
    attendre("document.getElementById('verdict').textContent !== ''")
    releve["verdict"] = js("document.getElementById('verdict').textContent")
    releve.update(ports_du_processus())


def lancer(dossier: Path, rapport: Path) -> int:
    """Ouvre la fenêtre cachée sur `dossier`, la pilote, écrit `rapport`. Rend 0 si le rapport est écrit."""
    releve: dict = {"moteur": "", "pret": False}

    def pilote(vue) -> None:
        try:
            piloter(vue, releve)
        except Exception as erreur:  # noqa: BLE001 - une panne du pilote se lit dans le rapport, pas dans une console
            releve["erreur"] = type(erreur).__name__
        finally:
            vue.destroy()

    application.REGLAGES = Path(rapport).resolve().parent / "reglages_auto_essai_absents.json"
    application.DEPART = Path(dossier).resolve()
    try:
        releve["moteur_installe"] = moteur.exiger()
        api = application.Api()
        application.ouvrir_fenetre(api, apres=lambda vue, _api: pilote(vue), cachee=True)
    except moteur.MoteurAbsent:
        releve["moteur"] = "absent"
    except Exception as erreur:  # noqa: BLE001
        releve["erreur"] = type(erreur).__name__
    try:
        Path(rapport).write_text(json.dumps(releve, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        return 1
    return 0

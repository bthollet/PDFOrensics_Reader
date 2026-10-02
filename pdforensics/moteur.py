# -*- coding: utf-8 -*-
"""Le moteur d'affichage : PDForensics dessine son écran avec Microsoft Edge WebView2, et avec lui seul.

Sans lui, la bibliothèque de fenêtre se rabattrait sur un moteur ancien, qui ne sait pas dessiner cet
écran et qui inscrit un réglage dans le registre de Windows. L'outil préfère ne pas s'ouvrir, et le dire.

Le moteur se reconnaît à ce que Windows en dit lui-même : sa version, inscrite au registre par son
installeur. Rien n'est lancé pour le savoir.
"""
from __future__ import annotations

# Les canaux sous lesquels le moteur s'inscrit : la version courante, puis les versions d'essai.
CANAUX = ("{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}", "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",
          "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}", "{65C35B14-6C1D-4122-AC46-7148CC9D6497}")
ABSENT = ("PDForensics a besoin du moteur d'affichage Microsoft Edge WebView2, qui n'est pas installé sur ce poste. "
          "Il s'installe depuis le site de Microsoft.")


class MoteurAbsent(RuntimeError):
    """Aucun moteur d'affichage sur ce poste."""


def version() -> str:
    """La version du moteur d'affichage installé ; vide s'il n'y en a pas."""
    try:
        import winreg
    except ImportError:
        return ""
    inscriptions = ((winreg.HKEY_CURRENT_USER, "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\"),
                    (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\"),
                    (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\"))
    for canal in CANAUX:
        for racine, chemin in inscriptions:
            try:
                with winreg.OpenKey(racine, chemin + canal) as cle:
                    lue = str(winreg.QueryValueEx(cle, "pv")[0])
            except OSError:
                continue
            if any(part.strip("0") for part in lue.split(".")):  # « 0.0.0.0 » : désinstallé
                return lue
    return ""


def exiger() -> str:
    """La version du moteur ; lève MoteurAbsent s'il n'y en a pas."""
    lue = version()
    if not lue:
        raise MoteurAbsent(ABSENT)
    return lue


def prevenir(message: str) -> None:
    """Dit le message dans une boîte de Windows : l'outil n'a pas de console où l'écrire."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "PDForensics", 0x10)
    except (ImportError, AttributeError, OSError):
        pass

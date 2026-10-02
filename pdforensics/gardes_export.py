# -*- coding: utf-8 -*-
"""Ou l'export des fiches a le droit de s'ecrire.

Une fiche porte les metadonnees et le texte cache d'une piece: elle est aussi
sensible que la piece. L'export est donc refuse:

- dans un DOSSIER PROTEGE, et pour toute piece qui s'y trouve. Les dossiers
  proteges sont une liste des reglages de l'utilisateur (`reglages.json`,
  cle `proteges`): l'outil n'y ecrit jamais, et rien de ce qui en vient n'est
  exporte. Le logiciel ne sait pas ce qu'ils contiennent ni pourquoi ils sont
  proteges;
- dans un dossier temporaire;
- dans un dossier que Windows connait comme synchronise avec un service en ligne;
- dans un depot Git;
- dans le dossier d'une piece selectionnee.

Les refus se calculent par ce que le dossier EST, jamais par une liste de
chemins ecrite dans le code.

CE QUE CES GARDES NE SAVENT PAS VOIR, et qu'il faut donc savoir soi-meme:
- un dossier synchronise par un logiciel qui ne se declare pas a Windows
  (ni racine de synchronisation, ni attribut de fichier en ligne), un partage
  reseau, un dossier qu'une sauvegarde copie ailleurs;
- un depot Git dont le dossier `.git` vit ailleurs, ou un depot nu.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

EN_LIGNE = 0x1000 | 0x40000 | 0x80000 | 0x100000 | 0x400000  # hors ligne, rappel a l'ouverture, epingle, non epingle, rappel a la lecture


def norme(chemin) -> Path:
    # Le chemin REEL: un dossier protege atteint par son nom court, ou par un lien, reste le meme dossier.
    return Path(os.path.normcase(os.path.realpath(str(chemin))))


def est_sous(chemin, racine) -> bool:
    c, r = norme(chemin), norme(racine)
    return c == r or r in c.parents


def lignee(chemin) -> list[Path]:
    c = norme(chemin)
    return [c, *c.parents]


def protege(chemin, proteges) -> bool:
    return any(racine and est_sous(chemin, racine) for racine in proteges or [])


def dans_un_depot(chemin) -> bool:
    return any((p / ".git").exists() for p in lignee(chemin))


def temporaire(chemin) -> bool:
    racines = {tempfile.gettempdir(), os.environ.get("TEMP", ""), os.environ.get("TMP", "")}
    return any(racine and est_sous(chemin, racine) for racine in racines)


def racines_synchronisees() -> list[Path]:
    """Les dossiers que Windows connait comme synchronises avec un service en ligne."""
    racines = [os.environ.get(nom, "") for nom in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")]
    try:
        import winreg

        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\SyncRootManager"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as gestion:
            for rang in range(winreg.QueryInfoKey(gestion)[0]):
                try:
                    with winreg.OpenKey(gestion, winreg.EnumKey(gestion, rang) + r"\UserSyncRoots") as cle:
                        for valeur in range(winreg.QueryInfoKey(cle)[1]):
                            racines.append(str(winreg.EnumValue(cle, valeur)[1]))
                except OSError:
                    continue
    except (ImportError, OSError):
        pass
    return [norme(racine) for racine in racines if racine]


def synchronise(chemin) -> bool:
    if any(est_sous(chemin, racine) for racine in racines_synchronisees()):
        return True
    for parent in lignee(chemin):
        try:
            if getattr(parent.stat(), "st_file_attributes", 0) & EN_LIGNE:
                return True
        except OSError:
            continue
    return False


def refus_piece(piece, proteges) -> str:
    """Pourquoi la fiche de cette piece ne s'exporte pas; vide si elle s'exporte."""
    if protege(piece, proteges):
        return "Cette pièce est dans un dossier protégé : sa fiche ne s'exporte pas."
    return ""


def refus_destination(destination, pieces, proteges) -> str:
    """Pourquoi rien ne s'ecrit dans ce dossier; vide si l'on peut y ecrire."""
    if not norme(destination).is_dir():
        return "Ce dossier n'existe pas."
    if protege(destination, proteges):
        return "Ce dossier est protégé : l'outil n'y écrit pas."
    if temporaire(destination):
        return "Ce dossier est un dossier temporaire."
    if synchronise(destination):
        return "Ce dossier est synchronisé avec un service en ligne."
    if dans_un_depot(destination):
        return "Ce dossier est dans un dépôt Git : une fiche ne doit pas entrer dans un dépôt."
    for piece in pieces:
        if est_sous(destination, norme(piece).parent):
            return "Ce dossier contient une pièce sélectionnée, ou se trouve dedans : l'export ne s'écrit pas à côté des pièces."
    return ""

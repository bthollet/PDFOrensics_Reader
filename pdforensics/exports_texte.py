# -*- coding: utf-8 -*-
"""L'export en fiches: une fiche Markdown par piece, et un tableau CSV d'une ligne par piece.

Meme contrat que `exports_odf`: une fiche est {"nom", "identite": [[libelle,
valeur]], "rubriques": [{"titre", "compte", "lignes"}]}; le tableau est
{"colonnes", "lignes"}.

Un export n'ecrase jamais: un nom deja pris dans le dossier recoit un rang.
"""
from __future__ import annotations

import re
from pathlib import Path

INTERDITS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def noms_pris(dossier: Path) -> set[str]:
    """Les noms deja presents dans le dossier, pour n'en ecraser aucun."""
    return {entree.name.casefold() for entree in dossier.iterdir()}


def nom_de_fichier(nom: str, extension: str, pris: set[str]) -> str:
    """Un nom de fichier que Windows accepte, et qui n'en ecrase aucun autre."""
    base = INTERDITS.sub("-", nom).strip(" .")[:150] or "sans nom"
    candidat, rang = f"{base}{extension}", 1
    while candidat.casefold() in pris:
        rang += 1
        candidat = f"{base} ({rang}){extension}"
    pris.add(candidat.casefold())
    return candidat


def nom_de_dossier(nom: str) -> str:
    """Le nom d'un dossier a creer, ou vide s'il n'est pas acceptable."""
    propre = " ".join(str(nom).split()).strip(" .")
    return "" if not propre or len(propre) > 100 or INTERDITS.search(propre) else propre


def fiche_md(fiche: dict, sous_titre: str) -> str:
    lignes = [f"# Fiche du fichier : {fiche['nom']}", "", sous_titre, "", "## Identité", ""]
    lignes += [f"- {libelle} : {valeur}" for libelle, valeur in fiche.get("identite", [])]
    for rubrique in fiche.get("rubriques", []):
        lignes += ["", f"## {rubrique['titre']} ({rubrique['compte']})", ""]
        lignes += [f"- {ligne}" for ligne in rubrique.get("lignes", [])]
    return "\n".join(lignes) + "\n"


def tableau_csv(tableau: dict) -> str:
    def cellule(valeur) -> str:
        return '"' + str(valeur).replace('"', '""') + '"'

    rangs = [tableau.get("colonnes", [])] + list(tableau.get("lignes", []))
    return "".join(";".join(cellule(v) for v in rang) + "\r\n" for rang in rangs)


def ecrire_fiches(dossier: Path, sous_titre: str, fiches: list[dict], tableau: dict, ecrits: list[Path]) -> None:
    """Ecrit le tableau et une fiche par piece. `ecrits` recoit chaque fichier pose, pour pouvoir le retirer."""
    pris = noms_pris(dossier)
    chemin = dossier / nom_de_fichier("tableau des fiches", ".csv", pris)
    chemin.write_text(tableau_csv(tableau), encoding="utf-8-sig", newline="")
    ecrits.append(chemin)
    for fiche in fiches:
        chemin = dossier / nom_de_fichier("fiche - " + str(fiche.get("nom") or ""), ".md", pris)
        chemin.write_text(fiche_md(fiche, sous_titre), encoding="utf-8", newline="\n")
        ecrits.append(chemin)

# -*- coding: utf-8 -*-
"""Ou la lecture place-t-elle les lettres ? Sur des pieces REELLES, en ne rendant que des NOMBRES.

Meme regle que essai_pieces_reelles.py: lecture en place, en memoire, rien
d'ecrit, sorties du processus detournees, et une sortie faite d'entiers et de
mesures en points. Jamais un nom, un chemin, un texte, ni un message d'erreur.

  python -B essais/essai_reperes.py --liste FICHIER [--rang N]
  python -B essais/essai_reperes.py --dossier D --combien 12 [--graine 7] [--rang N]

`--rang N` ne lit que la piece de rang N du tirage (le meme tirage que
essai_pieces_reelles.py avec la meme graine).

Une ligne par piece ET par format de page (largeur, hauteur, rotation,
origine de la feuille). Pour chaque groupe de pages, deux releves des memes
lettres sont compares:

- le releve LETTRE A LETTRE (celui dont la lecture se sert, qui donne l'ordre
  du dessin et le mode de trace);
- le releve PAR LIGNES de la bibliotheque (la reference: c'est lui qui sert a
  copier le texte d'une page).

Colonnes:
- pages, lettres; `hors_lettre` et `hors_ligne`: lettres dont le centre tombe
  hors de la page, selon l'un et l'autre releve. Ils devraient s'accorder;
- `cadre_lettre` et `cadre_ligne`: le rectangle qui contient tous les centres
  (gauche/haut/droite/bas, en points). Un decalage ou un echange des axes se
  lit en les comparant;
- `hors_frais`: le releve lettre a lettre refait sur un exemplaire neuf de la
  piece, page seule. S'il differe de `hors_lettre`, l'ordre des appels compte;
- `hors_lecture`: lettres que la LECTURE tient pour hors de la page, et
  `repere`: la largeur et la hauteur dont elle se sert pour ces pages;
- `sens`: les sens d'ecriture les plus frequents (x,y x nombre);
- `transparentes`, `mode3`: lettres sans opacite, lettres en mode invisible;
- `formes`: objets de forme appeles par ces pages; `flux`: flux de contenu;
- `unite`: unite utilisateur declaree, si elle n'est pas 1.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

import pymupdf

from essai_pieces_reelles import canal_garde, pieces  # pose aussi le chemin du paquet

from pdforensics import lecture_pdf  # noqa: E402

COLONNES = ("large", "haut", "rotation", "origine", "rognee", "pages", "lettres", "hors_lettre", "hors_ligne", "cadre_lettre",
            "cadre_ligne", "hors_frais", "hors_lecture", "repere", "sens", "transparentes", "mode3", "formes", "flux", "unite")


def nombres(texte: str) -> list[float]:
    import re
    return [float(n) for n in re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", texte or "")]


def dehors(x: float, y: float, large: float, haut: float) -> bool:
    return not (0 <= x <= large and 0 <= y <= haut)


def cadre(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return "/".join(str(round(v)) for v in (min(xs), min(ys), max(xs), max(ys)))


def centres_lettre(page) -> tuple[list[tuple[float, float]], Counter, int, int]:
    """Les centres des lettres, selon le releve lettre a lettre, dans le repere de l'image de la page."""
    a, b, c, d, e, f = tuple(page.rotation_matrix)
    centres, sens, transparentes, mode3 = [], Counter(), 0, 0
    for span in page.get_texttrace():
        lettres = [l for l in span["chars"] if chr(l[0]).strip()]
        direction = span.get("dir") or (1, 0)
        sens[(round(direction[0], 1), round(direction[1], 1))] += len(lettres)
        opacite = span.get("opacity")
        transparentes += len(lettres) if opacite is not None and opacite < 0.02 else 0
        mode3 += len(lettres) if span["type"] == 3 else 0
        for lettre in lettres:
            x, y = (lettre[3][0] + lettre[3][2]) / 2, (lettre[3][1] + lettre[3][3]) / 2
            centres.append((a * x + c * y + e, b * x + d * y + f))
    return centres, sens, transparentes, mode3


def centres_ligne(page) -> list[tuple[float, float]]:
    """Les centres des memes lettres, selon le releve par lignes, ramenes eux aussi au repere de l'image."""
    a, b, c, d, e, f = tuple(page.rotation_matrix)
    centres = []
    # Par defaut, ce releve ECARTE les lettres hors de la feuille, deux fois: par un drapeau, et parce qu'il se borne
    # au cadre de la page. Lever le drapeau seul ne suffit pas (verifie sur piece fabriquee): il faut aussi un cadre large.
    sans_ecarter = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_MEDIABOX_CLIP
    for bloc in page.get_text("rawdict", flags=sans_ecarter, clip=pymupdf.Rect(-20000, -20000, 20000, 20000)).get("blocks", []):
        for ligne in bloc.get("lines", []):
            for span in ligne.get("spans", []):
                for lettre in span.get("chars", []):
                    if lettre.get("c", "").strip():
                        x0, y0, x1, y1 = lettre["bbox"]
                        x, y = (x0 + x1) / 2, (y0 + y1) / 2
                        centres.append((a * x + c * y + e, b * x + d * y + f))
    return centres


def decrire(chemin) -> list[dict]:
    octets = chemin.read_bytes()
    doc = pymupdf.open(stream=octets, filetype="pdf")
    if doc.needs_pass:
        return [{"large": "refus : mot de passe"}]
    lecture = lecture_pdf.Lecture(chemin)
    derniere = len(lecture.tranches)
    neuf = pymupdf.open(stream=octets, filetype="pdf")       # un exemplaire ou seul le releve lettre a lettre est appele
    groupes: dict[tuple, dict] = {}
    for n in range(doc.page_count):
        page = doc[n]
        feuille = nombres(doc.xref_get_key(page.xref, "MediaBox")[1]) or [page.mediabox.x0, page.mediabox.y0, 0, 0]
        cle = (round(page.rect.width), round(page.rect.height), page.rotation, f"{round(feuille[0])}/{round(feuille[1])}",
               int(page.cropbox != page.mediabox))
        g = groupes.setdefault(cle, {"pages": 0, "lettres": 0, "hors_lettre": 0, "hors_ligne": 0, "points_lettre": [], "points_ligne": [],
                                     "hors_frais": 0, "hors_lecture": 0, "reperes": Counter(), "sens": Counter(), "transparentes": 0,
                                     "mode3": 0, "formes": 0, "flux": 0, "unite": set()})
        large, haut = page.rect.width, page.rect.height
        lettre, sens, transparentes, mode3 = centres_lettre(page)
        ligne = centres_ligne(page)
        g["pages"] += 1
        g["lettres"] += len(lettre)
        g["hors_lettre"] += sum(dehors(x, y, large, haut) for x, y in lettre)
        g["hors_ligne"] += sum(dehors(x, y, large, haut) for x, y in ligne)
        g["points_lettre"] += lettre
        g["points_ligne"] += ligne
        g["sens"].update(sens)
        g["transparentes"] += transparentes
        g["mode3"] += mode3
        g["formes"] += sum(1 for _ in page.get_xobjects())
        g["flux"] += len(page.get_contents())
        unite = nombres(doc.xref_get_key(page.xref, "UserUnit")[1])
        if unite and unite[0] != 1:
            g["unite"].add(unite[0])
        # la meme page, sur un exemplaire ou rien d'autre n'a ete appele
        frais = neuf[n]
        g["hors_frais"] += sum(dehors(x, y, frais.rect.width, frais.rect.height) for x, y in centres_lettre(frais)[0])
        # ce que la lecture en fait
        analyse = lecture.analyse(derniere, n)
        rep = analyse["repere"]
        g["reperes"][f"{round(rep.large)}x{round(rep.haut)}"] += 1
        g["hors_lecture"] += sum(1 for e in analyse["elements"] if e.get("cause") == "hors de la page")
    lignes = []
    for cle, g in sorted(groupes.items(), key=lambda item: -item[1]["pages"]):
        lignes.append({
            "large": cle[0], "haut": cle[1], "rotation": cle[2], "origine": cle[3], "rognee": cle[4],
            "pages": g["pages"], "lettres": g["lettres"], "hors_lettre": g["hors_lettre"], "hors_ligne": g["hors_ligne"],
            "cadre_lettre": cadre(g["points_lettre"]), "cadre_ligne": cadre(g["points_ligne"]),
            "hors_frais": g["hors_frais"], "hors_lecture": g["hors_lecture"],
            "repere": ";".join(f"{k}*{v}" for k, v in g["reperes"].most_common(3)),
            "sens": ";".join(f"{k[0]},{k[1]}*{v}" for k, v in g["sens"].most_common(3)),
            "transparentes": g["transparentes"], "mode3": g["mode3"], "formes": g["formes"], "flux": g["flux"],
            "unite": "/".join(str(u) for u in sorted(g["unite"])),
        })
    return lignes


def main() -> int:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("--liste")
    lecteur.add_argument("--dossier")
    lecteur.add_argument("--combien", type=int, default=0)
    lecteur.add_argument("--graine", type=int, default=7)
    lecteur.add_argument("--rang", type=int, default=0)
    arguments = lecteur.parse_args()
    if not arguments.liste and not arguments.dossier:
        lecteur.error("--liste ou --dossier")
    canal = canal_garde()

    def dire(texte: str) -> None:
        canal.write(texte + "\n")
        canal.flush()

    try:
        a_lire = pieces(arguments)
    except Exception as erreur:  # noqa: BLE001
        dire("ARRET : la liste des pièces ne s'établit pas (" + type(erreur).__name__ + ").")
        return 2
    dire(" | ".join(["piece"] + list(COLONNES)))
    for rang, chemin in enumerate(a_lire, 1):
        if arguments.rang and rang != arguments.rang:
            continue
        try:
            lignes = decrire(chemin)
        except lecture_pdf.PieceIllisible:
            dire(f"{rang} | refus")
            continue
        except BaseException as erreur:  # noqa: BLE001
            dire(f"{rang} | PANNE : {type(erreur).__name__}")
            continue
        for ligne in lignes:
            dire(" | ".join([str(rang)] + [str(ligne.get(colonne, "")) for colonne in COLONNES]))
    dire("FIN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

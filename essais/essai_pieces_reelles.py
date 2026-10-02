# -*- coding: utf-8 -*-
"""Eprouver la lecture sur des pieces REELLES, en ne rendant que des NOMBRES.

Ce script lit des PDF en place, en memoire, et n'ecrit rien. Sa sortie est
faite pour pouvoir etre montree a n'importe qui: des comptes, des durees, et
un vocabulaire ferme. Il n'imprime JAMAIS un nom de fichier, un chemin, un
texte, une date, un nom de logiciel ni le message d'une erreur. Une piece est
designee par son rang dans un tirage melange.

Les deux sorties du processus sont detournees des le depart: ni la
bibliotheque, ni l'interpreteur ne peuvent rien imprimer d'eux-memes. Seul ce
script ecrit, par le canal qu'il s'est garde.

  python -B essais/essai_pieces_reelles.py --liste FICHIER   un chemin de PDF par ligne
  python -B essais/essai_pieces_reelles.py --dossier D --combien 12 [--graine 7]

Ce qu'il mesure, piece par piece:
- la piece se lit-elle (lu / refus d'un genre connu / panne, par son type);
- pages, versions relevees, et versions selon la bibliotheque: s'accordent-elles;
- zones recouvertes, et ce qu'en dit un TEMOIN qui ne doit rien au detecteur:
  sur l'image finale de la page, l'endroit du texte reste dessous est-il uni
  (`uniformes`) ou porte-t-il encore quelque chose (`texte visible`, releve
  suspect) ? Les zones ou du texte est ecrit par-dessus, et celles qu'une
  image recouvre, echappent a ce temoin et sont comptees a part;
- texte que la page ne montre pas, par cause; lignes invisibles SANS cause
  nommee (`inexpliques`: la lecture ne les rapporte pas, ce compte dit ce que
  ce choix laisse passer); pages ou l'image a du etre comparee, et pages ou
  cette comparaison a echoue (`comparaisons_ratees`: la lecture n'y dit alors
  aucune zone; `non_comparees` compte les lettres qu'elle a laissees de cote);
  `non_unies`: lettres que l'image ne montre pas, sous quelque chose qui n'est
  pas une teinte unie (un trace qui redessine la lettre, un scan): non dites
  recouvertes; `positions_douteuses`: lignes que le releve lettre a lettre
  place hors de la page et que le releve par lignes y voit dedans: la lecture
  ne les dit pas hors de la page; `redessinees`: lettres sous un aplat, que le
  meme signe redessine a la meme place par-dessus: la page les montre;
- calques, lignes de texte, images, traces, annotations, annotations sans
  dessin propre; elements qui debordent de la page;
- la page la plus chargee, le poids des faits envoyes a l'ecran, les durees
  (en-tete seul, puis piece entiere).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pymupdf

sys.dont_write_bytecode = True  # meme lance sans -B, rien ne s'ecrit a cote des sources
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # le paquet est a cote du dossier des essais

from pdforensics import lecture_pdf  # noqa: E402

REFUS = {"mot de passe": "mot de passe", "abîmé": "abîmé", "ne se lit pas comme": "pas un PDF", "aucune page": "sans page",
         "ne s'ouvre pas": "inaccessible"}
CAUSES = ("mode invisible", "transparent", "hors de la page", "couleur du fond")
MODULES = ("lecture_pdf.py", "lecture_page.py", "lecture_annotations.py", "essai_pieces_reelles.py")
COLONNES = ("etat", "pages", "versions", "versions_moteur", "pages_changees", "caches", "uniformes", "ecrit par-dessus",
            "texte visible", "par_image", "par_annotation", "calques", "calques_eteints", "textes", "invisibles", "mode invisible", "transparent",
            "hors de la page", "couleur du fond", "inexpliques", "pages_comparees", "comparaisons_ratees", "non_unies",
            "non_comparees", "positions_douteuses", "redessinees", "images", "traces", "annotations",
            "sans_dessin", "debordent", "pages_tournees", "page_la_plus_chargee", "xmp", "joints", "balise", "reparee",
            "avertissements", "faits_ko", "entete_s", "lecture_s", "dessin_ms")


def canal_garde():
    """Le seul canal par lequel ce script ecrit; tout le reste part dans le vide."""
    garde = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
    vide = os.open(os.devnull, os.O_WRONLY)
    os.dup2(vide, 1)
    os.dup2(vide, 2)
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    return garde


def pieces(arguments) -> list[Path]:
    if arguments.liste:
        lignes = Path(arguments.liste).read_text(encoding="utf-8-sig").splitlines()
        trouvees = [Path(ligne.strip().strip('"')) for ligne in lignes if ligne.strip()]
    else:
        trouvees = sorted(p for p in Path(arguments.dossier).rglob("*") if p.suffix.lower() == ".pdf" and p.is_file())
    tirage = random.Random(arguments.graine)
    tirage.shuffle(trouvees)
    return trouvees[:arguments.combien] if arguments.combien else trouvees


def ou_la_panne() -> str:
    """Le type de l'erreur et l'endroit de CE code ou elle est nee; jamais son message."""
    genre, _valeur, trace = sys.exc_info()
    ici = [cadre for cadre in traceback.extract_tb(trace) if Path(cadre.filename).name in MODULES]
    dernier = ici[-1] if ici else None
    return f"{genre.__name__}" + (f" dans {dernier.name}, ligne {dernier.lineno}" if dernier else "")


def uni(image: np.ndarray, boite) -> bool:
    """Sur l'image finale de la page, cet endroit est-il d'une seule teinte ?"""
    haut, large = image.shape
    x0, y0, x1, y1 = boite
    zone = image[max(0, int(y0 * haut) + 1):max(1, int(y1 * haut) - 1), max(0, int(x0 * large) + 1):max(1, int(x1 * large) - 1)]
    return bool(zone.size) and float((np.abs(zone - np.median(zone)) <= 24).mean()) >= 0.97


def temoin_des_caches(lecture: lecture_pdf.Lecture, faits: dict) -> dict:
    """Ce que l'image finale de la page dit de chaque zone recouverte, sans rien devoir au detecteur."""
    rendu = {"uniformes": 0, "ecrit par-dessus": 0, "texte visible": 0, "par_image": 0, "par_annotation": 0}
    derniere = len(lecture.tranches)
    for page in faits["pages"]:
        if not page["caches"]:
            continue
        image = lecture._pixels(derniere, page["n"] - 1)  # noqa: SLF001 - meme rendu que la lecture
        for cache in page["caches"]:
            if cache["nature"] == "annotation":
                rendu["par_annotation"] += 1
            elif cache["dessus"]:
                rendu["ecrit par-dessus"] += 1
            elif cache["nature"] != "aplat":
                rendu["par_image"] += 1
            elif all(uni(image, dessous["bbox"]) for dessous in cache["dessous"]):
                rendu["uniformes"] += 1
            else:
                rendu["texte visible"] += 1
    return rendu


def eprouver(chemin: Path) -> dict:
    ligne = {"etat": "lu"}
    pymupdf.TOOLS.reset_mupdf_warnings()
    debut = time.perf_counter()
    try:
        lecture = lecture_pdf.Lecture(chemin)
        lecture.entete()
        ligne["entete_s"] = round(time.perf_counter() - debut, 2)
        faits = lecture.faits()
    except lecture_pdf.PieceIllisible as refus:
        return {"etat": "refus : " + next((code for motif, code in REFUS.items() if motif in str(refus)), "autre")}
    except Exception:  # noqa: BLE001 - une panne se compte, elle n'arrete pas l'epreuve
        return {"etat": "PANNE : " + ou_la_panne(), "lecture_s": round(time.perf_counter() - debut, 2)}
    ligne["lecture_s"] = round(time.perf_counter() - debut, 2)
    elements = [e for page in faits["pages"] for e in page["elements"]]

    def nature(nom: str) -> int:
        return sum(1 for e in elements if e["nature"] == nom)

    derniere = len(lecture.tranches)
    entier = lecture.doc(derniere)
    analyses = [lecture.analyse(derniere, n) for n in range(len(faits["pages"]))]
    debordent = 0
    for analyse in analyses:
        rep = analyse["repere"]
        for element in analyse["elements"]:
            x0, y0, x1, y1 = rep.vue(element["bbox"])
            debordent += int(x0 < -1 or y0 < -1 or x1 > rep.large + 1 or y1 > rep.haut + 1)
    ligne.update({
        "pages": len(faits["pages"]), "versions": len(faits["versions"]), "versions_moteur": faits["moteur"],
        "pages_changees": sum(1 for v in faits["versions"] for zones in v["zones"] if zones),
        "caches": sum(len(p["caches"]) for p in faits["pages"]),
        "calques": len(faits["calques"]), "calques_eteints": sum(1 for c in faits["calques"] if not c["allume"]),
        "textes": nature("texte"), "invisibles": nature("invisible"), "images": nature("image"),
        "traces": nature("trace"), "annotations": nature("annotation"),
        "inexpliques": sum(a["inexpliques"] for a in analyses), "pages_comparees": sum(int(a["comparee"]) for a in analyses),
        "comparaisons_ratees": sum(int(a["ratee"]) for a in analyses), "non_unies": sum(a["non_unies"] for a in analyses),
        "non_comparees": sum(a["non_comparees"] for a in analyses), "positions_douteuses": sum(a["douteuses"] for a in analyses),
        "redessinees": sum(a["redessinees"] for a in analyses),
        "sans_dessin": len(lecture.sans_dessin.get(derniere, ())), "debordent": debordent,
        "pages_tournees": sum(1 for page in entier if page.rotation),
        "page_la_plus_chargee": max(len(p["elements"]) for p in faits["pages"]),
        "xmp": len(faits["xmp"]), "joints": len(faits["joints"]), "balise": int(faits["balise"]),
        "reparee": int(bool(entier.is_repaired)),
        "avertissements": len([a for a in (pymupdf.TOOLS.mupdf_warnings(reset=False) or "").splitlines() if a.strip()]),
        "faits_ko": len(json.dumps(faits, ensure_ascii=False)) // 1024,
    })
    for cause in CAUSES:
        ligne[cause] = sum(1 for e in elements if e["nature"] == "invisible" and e.get("cause") == cause)
    try:
        ligne.update(temoin_des_caches(lecture, faits))
    except Exception:  # noqa: BLE001
        ligne["etat"] = "PANNE a l'image des caches : " + ou_la_panne()
    try:
        debut = time.perf_counter()
        a_dessiner = sorted({1, (len(faits["pages"]) + 1) // 2, len(faits["pages"])})
        for numero in a_dessiner:
            if not lecture.image(len(faits["versions"]), numero, False, 1.6).startswith("data:image/"):
                raise ValueError("image")
        if len(faits["versions"]) > 1:
            lecture.image(1, 1, False, 1.6)
        ligne["dessin_ms"] = round((time.perf_counter() - debut) * 1000 / len(a_dessiner))
    except Exception:  # noqa: BLE001
        ligne["etat"] = "PANNE au dessin : " + ou_la_panne()
    return ligne


def bilan(lignes: list[dict]) -> list[str]:
    lues = [l for l in lignes if l["etat"] == "lu"]

    def somme(colonne: str) -> int:
        return sum(l.get(colonne, 0) for l in lues)

    rendu = [f"BILAN : {len(lignes)} pièces, {len(lues)} lues, "
             f"{sum(1 for l in lignes if l['etat'].startswith('refus'))} refus, "
             f"{sum(1 for l in lignes if l['etat'].startswith('PANNE'))} pannes."]
    if lues:
        rendu.append(
            f"        versions en désaccord avec la bibliothèque : {sum(1 for l in lues if l['versions'] != l['versions_moteur'])} ; "
            f"zones recouvertes : {somme('caches')}, dont {somme('uniformes')} confirmées par le témoin, "
            f"{somme('ecrit par-dessus')} écrites par-dessus, {somme('par_image')} sous une image, {somme('texte visible')} suspectes ; "
            f"lignes invisibles : {somme('invisibles')}, et {somme('inexpliques')} sans cause nommée, non rapportées ; "
            f"pages comparées à l'image : {somme('pages_comparees')} sur {somme('pages')} ; "
            f"éléments qui débordent de la page : {somme('debordent')} ; "
            f"lecture la plus longue : {max(l['lecture_s'] for l in lues)} s ; "
            f"page la plus chargée : {max(l['page_la_plus_chargee'] for l in lues)} éléments ; "
            f"faits les plus lourds : {max(l['faits_ko'] for l in lues)} Ko.")
    return rendu


def main() -> int:
    lecteur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    lecteur.add_argument("--liste")
    lecteur.add_argument("--dossier")
    lecteur.add_argument("--combien", type=int, default=0)
    lecteur.add_argument("--graine", type=int, default=7)
    arguments = lecteur.parse_args()
    if not arguments.liste and not arguments.dossier:
        lecteur.error("--liste ou --dossier")
    canal = canal_garde()

    def dire(texte: str) -> None:
        canal.write(texte + "\n")
        canal.flush()

    try:
        a_lire = pieces(arguments)
    except Exception as erreur:  # noqa: BLE001 - le message d'une erreur de dossier porte un chemin
        dire("ARRET : la liste des pièces ne s'établit pas (" + type(erreur).__name__ + ").")
        return 2
    dire(" | ".join(["piece"] + list(COLONNES)))
    lignes = []
    for rang, chemin in enumerate(a_lire, 1):
        try:
            ligne = eprouver(chemin)
        except BaseException as erreur:  # noqa: BLE001 - meme une interruption ne doit rien imprimer d'autre
            ligne = {"etat": "PANNE hors lecture : " + type(erreur).__name__}
        lignes.append(ligne)
        dire(" | ".join([str(rang)] + [str(ligne.get(colonne, "")) for colonne in COLONNES]))
    for phrase in bilan(lignes):
        dire(phrase)
    return 0


if __name__ == "__main__":
    sys.exit(main())

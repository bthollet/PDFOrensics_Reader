# -*- coding: utf-8 -*-
"""Ce qu'UNE page contient: textes, traces, images, annotations - et ce que la page ne montre pas.

UN TEXTE EST-IL CACHE ? L'invariant n'est pas geometrique. Un aplat dessine
apres un texte ne le cache pas s'il est rogne ailleurs, transparent, pose en
mode de melange, ou d'une forme qui passe a cote des lettres. Ce qui reste
vrai quel que soit le mecanisme: une lettre que la page ne montre pas ne
change rien a l'image quand on la retire. La lecture compare donc l'image de
la page AVEC son texte et SANS lui, lettre par lettre; la geometrie ne sert
plus qu'a dire CE QUI cache (un aplat, une image, la couleur du fond, le bord
de la page).

Un seul cas echappe a l'image: du texte ecrit PAR-DESSUS un aplat qui en
recouvre un autre. La difference d'image y vient du texte du dessus. La
lecture s'en remet alors a la geometrie, sous conditions strictes: aplat
plein, opaque, hors de tout melange, et dont la forme contient la lettre.

La comparaison coute deux dessins de la page. Elle n'est faite que si elle
peut changer quelque chose: une lettre a quelque chose de dessine apres elle
a son endroit, ou un texte dont rien ne PROUVE qu'il tranche sur son fond.

Une lettre invisible sans cause nommee n'est pas rapportee comme un fait: une
police sans dessin pour ce signe donnerait la meme image. Elle est comptee
(`inexpliques`), pour qu'un essai puisse voir ce que ce choix laisse passer.
"""
from __future__ import annotations

import math
import re
import unicodedata

import numpy as np

INSECABLE = chr(0xA0)
INCONNU = chr(0xFFFD)        # ce que rend la bibliotheque pour un signe dont la police ne donne pas la lettre
ECHELLE_ENCRE = 1.5          # resolution de la comparaison avec / sans texte
POINTS_MAX = 4_000_000       # au-dela, la comparaison se fait a une echelle plus faible


def propre(texte: str) -> str:
    """Les espaces insecables d'une police redeviennent des espaces."""
    return " ".join(texte.replace(INSECABLE, " ").split())


def nom_de_couleur(couleur) -> str:
    if couleur is None:
        return ""
    if max(couleur) < 0.2:
        return "noir"
    if min(couleur) > 0.97:
        return "blanc"
    if max(couleur) - min(couleur) < 0.08:
        return "gris"
    return "de couleur"


class Repere:
    """La page telle que son image la montre. La matrice de rotation est calculee UNE fois par page.

    Le moteur rend textes, traces, images et annotations dans le repere de la
    page NON tournee; l'image de la page et ses dimensions sont celles de la
    page TOURNEE. Tout passe donc par `vue`.
    """

    def __init__(self, page) -> None:
        self.m = tuple(page.rotation_matrix)
        self.rotation = page.rotation
        self.large, self.haut = page.rect.width or 1.0, page.rect.height or 1.0

    def point(self, x: float, y: float) -> tuple[float, float]:
        a, b, c, d, e, f = self.m
        return a * x + c * y + e, b * x + d * y + f

    def vue(self, rect) -> tuple[float, float, float, float]:
        (xa, ya), (xb, yb) = self.point(rect[0], rect[1]), self.point(rect[2], rect[3])
        return min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)

    def fraction_image(self, rect) -> list[float]:
        """Une zone deja exprimee dans le repere de l'image, bornee a la page."""
        def borne(valeur: float, taille: float) -> float:
            return round(min(1.0, max(0.0, valeur / taille)), 5)
        return [borne(rect[0], self.large), borne(rect[1], self.haut), borne(rect[2], self.large), borne(rect[3], self.haut)]

    def fraction(self, rect) -> list[float]:
        return self.fraction_image(self.vue(rect))

    def dans_la_page(self, rect) -> bool:
        """Une part de ce rectangle tombe-t-elle dans la page ?"""
        x0, y0, x1, y1 = self.vue(rect)
        return x1 >= 0 and y1 >= 0 and x0 <= self.large and y0 <= self.haut

    def centre_dedans(self, boite) -> bool:
        x, y = self.point((boite[0] + boite[2]) / 2, (boite[1] + boite[3]) / 2)
        return 0 <= x <= self.large and 0 <= y <= self.haut


# --------------------------------------------------------------- ce que la page porte

def texte_de(lettres, taille: float, sens) -> str:
    """Les lettres d'un trait de texte, avec une espace la ou la ligne laisse un vide."""
    morceaux, precedente = [], None
    couche = abs(sens[0]) >= abs(sens[1])
    for lettre in lettres:
        signe, boite = chr(lettre[0]), lettre[3]
        if precedente is not None and signe.strip() and morceaux and morceaux[-1].strip():
            if couche:
                vide = boite[0] - precedente[2] if sens[0] >= 0 else precedente[0] - boite[2]
            else:
                vide = boite[1] - precedente[3] if sens[1] >= 0 else precedente[1] - boite[3]
            if vide > 0.18 * taille:
                morceaux.append(" ")
        morceaux.append(signe)
        precedente = boite
    return lisible(propre("".join(morceaux)))


def lisible(texte: str) -> str:
    """Un texte dont la police ne dit pas a quelles lettres correspondent ses signes se dit tel, au lieu de s'afficher en signes vides."""
    if INCONNU not in texte:
        return texte
    signes = sum(1 for c in texte if not c.isspace())
    if texte.count(INCONNU) * 2 >= signes:
        return f"(illisible : {signes} signes d'une police sans table de correspondance)"
    return re.sub(INCONNU + "+", "[?]", texte)


def couleur_rvb(couleur) -> tuple[float, float, float] | None:
    if not couleur:
        return None
    if len(couleur) == 1:
        return couleur[0], couleur[0], couleur[0]
    if len(couleur) == 3:
        return tuple(couleur)
    if len(couleur) == 4:
        c, m, j, n = couleur
        return (1 - c) * (1 - n), (1 - m) * (1 - n), (1 - j) * (1 - n)
    return None


def textes(page) -> list[dict]:
    rendu = []
    for span in page.get_texttrace():
        lettres = [c for c in span["chars"] if chr(c[0]).strip()]
        if not lettres:
            continue
        opacite = span.get("opacity")
        rendu.append({
            "texte": texte_de(span["chars"], span["size"], span.get("dir") or (1, 0)), "bbox": tuple(span["bbox"]),
            "mode": span["type"], "seqno": span["seqno"], "calque": span.get("layer") or "", "taille": span["size"],
            "police": span.get("font") or "",
            "sens": span.get("dir") or (1, 0), "lettres": lettres, "couleur": couleur_rvb(span.get("color")),
            "opacite": 1.0 if opacite is None else opacite, "cause": "",
        })
    return rendu


def traces(page) -> list[dict]:
    """Les traces de la page, chacun ramene a ce que sa zone de decoupe en laisse voir."""
    rendu, decoupes, melanges = [], {}, {}
    for dessin in page.get_drawings(extended=True):
        niveau, genre = dessin.get("level", 0), dessin.get("type")
        for table in (decoupes, melanges):               # ce qui est plus profond que ce niveau n'a plus cours
            for n in [n for n in table if n >= niveau]:
                del table[n]
        if genre == "clip":
            decoupes[niveau] = tuple(dessin["scissor"])
            continue
        if genre == "group":
            opacite = dessin.get("opacity")
            melanges[niveau] = (dessin.get("blendmode") or "Normal") != "Normal" or (1.0 if opacite is None else opacite) < 0.99
            continue
        x0, y0, x1, y1 = dessin["rect"]
        if decoupes:
            dx0, dy0, dx1, dy1 = decoupes[max(decoupes)]
            x0, y0, x1, y1 = max(x0, dx0), max(y0, dy0), min(x1, dx1), min(y1, dy1)
            if x1 < x0 or y1 < y0:
                continue                                 # entierement rogne: ce trace ne dessine rien
        plein = dessin.get("fill") is not None
        opacite = dessin.get("fill_opacity") if plein else dessin.get("stroke_opacity")
        opacite = 1.0 if opacite is None else opacite
        rendu.append({
            "bbox": (x0, y0, x1, y1), "plein": plein, "seqno": dessin["seqno"], "opacite": opacite,
            "couleur": nom_de_couleur(dessin.get("fill") if plein else dessin.get("color")),
            "teinte": couleur_rvb(dessin.get("fill")) if plein else None,
            "calque": dessin.get("layer") or "", "nature": "aplat",
            "franc": plein and opacite >= 0.99 and not any(melanges.values()),
            "items": dessin["items"] if plein else None,
        })
    return rendu


def poses(page) -> list[dict]:
    """Les images et les degrades poses sur la page, avec leur rang dans l'ordre du dessin."""
    rendu = []
    for rang, (genre, boite) in enumerate(page.get_bboxlog()):
        if genre in ("fill-image", "fill-imgmask", "fill-shade"):
            rendu.append({"bbox": tuple(boite), "seqno": rang, "nature": "dégradé" if genre == "fill-shade" else "image",
                          "couleur": "", "teinte": None, "franc": False, "items": None, "plein": True})
    return rendu


def lignes(ecrits: list[dict]) -> list[dict]:
    """Les textes regroupes par ligne: une page lue mot a mot ne devient pas mille traces."""
    rendu: list[dict] = []
    for ecrit in ecrits:
        dernier = rendu[-1] if rendu else None
        if (dernier and dernier["cause"] == ecrit["cause"] and dernier["calque"] == ecrit["calque"]
                and abs(dernier["bbox"][1] - ecrit["bbox"][1]) < 2 and abs(dernier["bbox"][3] - ecrit["bbox"][3]) < 2
                and -1 <= ecrit["bbox"][0] - dernier["bbox"][2] < 1.5 * ecrit["taille"]):
            dernier["texte"] = propre(dernier["texte"] + " " + ecrit["texte"])
            dernier["bbox"] = (dernier["bbox"][0], min(dernier["bbox"][1], ecrit["bbox"][1]),
                               ecrit["bbox"][2], max(dernier["bbox"][3], ecrit["bbox"][3]))
        else:
            rendu.append({k: ecrit[k] for k in ("texte", "bbox", "cause", "calque", "taille")})
    return rendu


# --------------------------------------------------------------- ce que la page ne montre pas

def aretes(items) -> list[tuple]:
    """Le contour d'un trace, en segments; chaque sous-chemin est referme, comme le fait un remplissage."""
    segments, depart, courant = [], None, None

    def relier(a, b) -> None:
        nonlocal depart, courant
        if courant is None or abs(a[0] - courant[0]) > 1e-6 or abs(a[1] - courant[1]) > 1e-6:
            if courant is not None and depart is not None and courant != depart:
                segments.append((courant, depart))
            depart = a
        segments.append((a, b))
        courant = b

    for item in items:
        genre = item[0]
        if genre == "l":
            relier(tuple(item[1]), tuple(item[2]))
        elif genre == "re":
            r = item[1]
            coins = [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]
            for i in range(4):
                relier(coins[i], coins[(i + 1) % 4])
        elif genre == "qu":
            q = item[1]
            coins = [tuple(q[0]), tuple(q[1]), tuple(q[3]), tuple(q[2])]
            for i in range(4):
                relier(coins[i], coins[(i + 1) % 4])
        elif genre == "c":
            p = [tuple(v) for v in item[1:5]]
            precedent = p[0]
            for pas in range(1, 9):
                t = pas / 8
                u = 1 - t
                suivant = (u ** 3 * p[0][0] + 3 * u * u * t * p[1][0] + 3 * u * t * t * p[2][0] + t ** 3 * p[3][0],
                           u ** 3 * p[0][1] + 3 * u * u * t * p[1][1] + 3 * u * t * t * p[2][1] + t ** 3 * p[3][1])
                relier(precedent, suivant)
                precedent = suivant
    if courant is not None and depart is not None and courant != depart:
        segments.append((courant, depart))
    return segments


def contient(couverture: dict, x: float, y: float) -> bool:
    """Ce point est-il sous cette couverture ? Sa forme compte, pas seulement son rectangle."""
    x0, y0, x1, y1 = couverture["bbox"]
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    items = couverture["items"]
    if not items or (len(items) == 1 and items[0][0] == "re"):
        return True
    if "aretes" not in couverture:
        couverture["aretes"] = aretes(items)
    dedans = False
    for (ax, ay), (bx, by) in couverture["aretes"]:
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            dedans = not dedans
    return dedans


def milieu(boite) -> tuple[float, float]:
    return (boite[0] + boite[2]) / 2, (boite[1] + boite[3]) / 2


def se_touchent(a, b) -> bool:
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def tranche_sur_son_fond(ecrit: dict, poses_avant: list[dict]) -> bool:
    """Est-il PROUVE, sans dessiner la page, que ce texte se distingue de ce qu'il y a derriere lui ?

    Derriere lui: le dernier aplat, image ou degrade dessine AVANT lui a son
    endroit; a defaut, le blanc de la page. La preuve n'existe que pour un
    aplat franc de couleur connue. Dans le doute, la page sera dessinee.
    """
    if ecrit["couleur"] is None:
        return False
    x, y = milieu(ecrit["bbox"])
    derriere = [k for k in poses_avant if k["seqno"] < ecrit["seqno"] and contient(k, x, y)]
    if not derriere:
        fond = (1.0, 1.0, 1.0)
    else:
        dernier = max(derriere, key=lambda k: k["seqno"])
        if not dernier["franc"] or dernier["teinte"] is None:
            return False
        fond = dernier["teinte"]
    return max(abs(a - b) for a, b in zip(ecrit["couleur"], fond)) > 0.12


def table_d_encre(avec: np.ndarray, sans: np.ndarray) -> np.ndarray | None:
    """Table sommee des points ou l'image change quand on retire le texte."""
    if avec.shape != sans.shape:
        return None
    change = np.abs(avec.astype(np.int16) - sans).max(axis=2) > 12
    table = np.zeros((change.shape[0] + 1, change.shape[1] + 1), np.int32)
    table[1:, 1:] = change.cumsum(0, dtype=np.int32).cumsum(1, dtype=np.int32)
    return table


def lettres_vues(table: np.ndarray, boites: np.ndarray, echelle: float) -> np.ndarray:
    """Pour chaque lettre (sa boite, dans le repere de l'image): la page la montre-t-elle ?"""
    haut, large = table.shape[0] - 1, table.shape[1] - 1
    x0, y0, x1, y1 = (boites * echelle).T
    dx, dy = 0.12 * (x1 - x0), 0.12 * (y1 - y0)
    gx = np.clip(np.floor(x0 + dx), 0, large).astype(np.int64)
    gy = np.clip(np.floor(y0 + dy), 0, haut).astype(np.int64)
    hx = np.clip(np.maximum(np.ceil(x1 - dx), gx + 1), 0, large).astype(np.int64)
    hy = np.clip(np.maximum(np.ceil(y1 - dy), gy + 1), 0, haut).astype(np.int64)
    return (table[hy, hx] - table[gy, hx] - table[hy, gx] + table[gy, gx]) >= 2


def couleur_du_fond(fond: np.ndarray, boite, echelle: float, couleur) -> bool:
    """Ce texte est-il ecrit de la couleur de ce qu'il y a derriere lui ?"""
    if couleur is None:
        return False
    x0, y0, x1, y1 = (int(v * echelle) for v in boite)
    zone = fond[max(0, y0):max(0, y1) + 1, max(0, x0):max(0, x1) + 1]
    if not zone.size:
        return False
    derriere = zone.reshape(-1, 3).mean(axis=0)
    return bool(np.abs(derriere - np.array(couleur) * 255).max() <= 24)


def noyau_uni(image: np.ndarray, boite, echelle: float) -> bool:
    """Au coeur de la boite d'une lettre, l'image FINALE de la page est-elle d'une seule teinte ?

    Ce qui est pose sur une lettre peut la redessiner: un texte converti en
    traces, un scan qui montre le meme mot. Le lecteur voit alors la lettre,
    et rien n'est cache. Une lettre n'est dite recouverte que si, a son
    endroit, la page ne montre qu'une teinte unie.
    """
    x0, y0, x1, y1 = (v * echelle for v in boite)
    dx, dy = 0.25 * (x1 - x0), 0.3 * (y1 - y0)
    zone = image[max(0, int(y0 + dy)):max(0, int(y1 - dy)) + 1, max(0, int(x0 + dx)):max(0, int(x1 - dx)) + 1]
    if not zone.size:
        return False
    points = zone.reshape(-1, 3).astype(np.int16)
    return float((np.abs(points - np.median(points, axis=0)).max(axis=1) <= 30).mean()) >= 0.92


def signe_sans_lettre(code: int) -> bool:
    """Ce code ne designe aucune lettre: une espace, un signe de commande, ou le code d'une police sans correspondance."""
    return code == 0xFFFD or unicodedata.category(chr(code))[0] in "ZC"


def analyser(page, rep: Repere, encre) -> dict:
    """Tout ce qui compose une page SANS ses annotations, et ce qu'elle ne montre pas.

    `encre()` rend (table, fond, avec, echelle): ou l'image change quand on
    retire le texte, l'image sans texte, l'image finale, et leur echelle. Elle
    rend (None, None, None, 1) si la comparaison n'a pas pu se faire: la
    lecture ne dit alors AUCUNE zone recouverte sur cette page, plutot que de
    s'en remettre a une geometrie que rien ne confirme. Elle n'est appelee que
    si la comparaison peut compter.
    """
    ecrits, dessins = textes(page), traces(page)
    couvertures = [d for d in dessins if d["plein"]] + poses(page)
    # --- premier passage, sans rien dessiner: qui est hors page, qui a quelque chose par-dessus
    comparer = False
    for ecrit in ecrits:
        ecrit["dedans"] = [rep.centre_dedans(l[3]) for l in ecrit["lettres"]]
        sans_opacite = ecrit["opacite"] < 0.02          # a confirmer par l'image: une opacite declaree n'est pas un fait
        if ecrit["mode"] == 3:
            ecrit["cause"] = "mode invisible"
        elif not any(ecrit["dedans"]):
            ecrit["cause"] = "hors de la page"
        apres = [k for k in couvertures if k["seqno"] > ecrit["seqno"] and se_touchent(k["bbox"], ecrit["bbox"])]
        ecrit["sur"] = [[k for k in apres if contient(k, *milieu(l[3]))] if apres and dedans else []
                        for l, dedans in zip(ecrit["lettres"], ecrit["dedans"])]
        if any(ecrit["sur"]) or (not ecrit["cause"] and (sans_opacite or not tranche_sur_son_fond(ecrit, couvertures))):
            comparer = True
    douteuses = hors_page_recoupe(page, rep, ecrits)
    table, fond, avec, echelle = encre() if comparer else (None, None, None, 1.0)
    vues = None
    if table is not None:
        boites = np.array([rep.vue(l[3]) for e in ecrits for l in e["lettres"]], dtype=np.float64).reshape(-1, 4)
        vues = lettres_vues(table, boites, echelle)
    # --- les signes que la page montre au moins une fois: ceux-la ont un dessin
    encres, rang = set(), 0
    for ecrit in ecrits:
        debut, rang = rang, rang + len(ecrit["lettres"])
        ecrit["montrees"] = [bool(v) for v in vues[debut:rang]] if vues is not None else None
        if ecrit["montrees"]:
            encres.update((ecrit["police"], l[1]) for l, vue in zip(ecrit["lettres"], ecrit["montrees"]) if vue)
    # --- second passage: ce qui cache chaque lettre que la page ne montre pas
    inexpliques, non_unies, non_comparees, caches = 0, 0, 0, {}
    for ecrit in ecrits:
        montrees = ecrit["montrees"]
        if not ecrit["cause"] and ecrit["opacite"] < 0.02 and (montrees is None or not any(montrees)):
            ecrit["cause"] = "transparent"
        couvertes = 0
        for i, lettre in enumerate(ecrit["lettres"]):
            dessus = ecrit["sur"][i]
            if not dessus:
                continue
            if montrees is None:
                non_comparees += 1
                continue
            if (ecrit["police"], lettre[1]) not in encres and signe_sans_lettre(lettre[0]):
                continue                                  # un signe sans dessin n'est pas une lettre cachee
            franches = [k for k in dessus if k["franc"]]
            posees = [k for k in dessus if k["franc"] or k["nature"] != "aplat"]
            cachee = bool(ecrit["cause"]) or not montrees[i]
            choisie, par_dessus = None, ""
            if cachee and posees and noyau_uni(avec, rep.vue(lettre[3]), echelle):
                # un aplat franc est ce qui cache, meme si une image ou un degrade vient encore par-dessus
                choisie = max(franches or posees, key=lambda k: k["seqno"])
            elif franches:
                # l'image ne peut pas trancher sous un texte ecrit par-dessus: la geometrie stricte tranche
                plus_haute = max(franches, key=lambda k: k["seqno"])
                par_dessus = _texte_par_dessus(ecrits, plus_haute, ecrit, lettre)
                if par_dessus:
                    choisie = plus_haute
                elif cachee:
                    non_unies += 1
            elif cachee and posees:
                non_unies += 1
            if choisie is not None:
                couvertes += 1
                cache = caches.setdefault(id(choisie), {"couverture": choisie, "dessous": {}, "lettres": 0, "memes": 0})
                cache["dessous"].setdefault(id(ecrit), (ecrit, []))[1].append(lettre)
                cache["lettres"] += 1
                cache["memes"] += int(par_dessus == "meme")
        if not ecrit["cause"] and montrees is not None and not any(montrees) and not couvertes:
            if couleur_du_fond(fond, rep.vue(ecrit["bbox"]), echelle, ecrit["couleur"]):
                ecrit["cause"] = "couleur du fond"
            else:
                inexpliques += 1
    zones, redessinees = [], 0
    for cache in sorted(caches.values(), key=lambda c: c["couverture"]["seqno"]):
        couverture = cache["couverture"]
        if cache["memes"] == cache["lettres"]:
            # tout ce qui est dessous est redessine a l'identique par-dessus: la page le montre, ce n'est pas une zone recouverte.
            # Des qu'une lettre differe, la zone est gardee ENTIERE: un montant dont un seul chiffre change se relit en entier.
            redessinees += cache["lettres"]
            continue
        dessous = [texte_dessous(rep, ecrit, prises) for ecrit, prises in cache["dessous"].values()]
        par_dessus = []
        for ecrit in ecrits:
            if ecrit["seqno"] > couverture["seqno"] and not ecrit["cause"]:
                prises = [l for l in ecrit["lettres"] if contient(couverture, *milieu(l[3]))]
                if prises:
                    par_dessus.append(texte_de(prises, ecrit["taille"], ecrit["sens"]))
        zones.append({"rect": tuple(round(v, 1) for v in couverture["bbox"]), "bbox": rep.fraction(couverture["bbox"]),
                      "couleur": couverture["couleur"], "nature": couverture["nature"], "dessous": dessous, "dessus": par_dessus})
    return {"textes": ecrits, "traces": dessins, "caches": zones, "inexpliques": inexpliques, "comparee": comparer,
            "ratee": comparer and table is None, "non_unies": non_unies, "non_comparees": non_comparees, "douteuses": douteuses,
            "redessinees": redessinees}


def texte_dessous(rep: Repere, ecrit: dict, prises: list) -> dict:
    """Les lettres d'un trait de texte restees sous ce qui les recouvre: leur texte, et de quoi le reposer a sa place."""
    cadre = [min(l[3][0] for l in prises), min(l[3][1] for l in prises), max(l[3][2] for l in prises), max(l[3][3] for l in prises)]
    depart = rep.point(*prises[0][2])          # ou commence la ligne de base, sur l'image
    # Le sens d'ecriture est un degre de liberte du fichier, distinct de la rotation de la page:
    # un tableau couche s'ecrit de bas en haut sur une page qui, elle, tourne. L'angle se lit sur l'image.
    sx, sy = ecrit["sens"]
    (ox, oy), (px, py) = rep.point(0, 0), rep.point(sx, sy)
    return {"texte": texte_de(prises, ecrit["taille"], ecrit["sens"]), "bbox": rep.fraction(cadre),
            "taille": round(ecrit["taille"], 2), "x": round(depart[0] / rep.large, 5), "y": round(depart[1] / rep.haut, 5),
            "long": round(abs(sx) * (cadre[2] - cadre[0]) + abs(sy) * (cadre[3] - cadre[1]), 2),
            "angle": round(math.degrees(math.atan2(py - oy, px - ox))), "invisible": ecrit["mode"] == 3}


def lettres_hors_page_selon_les_lignes(page, rep: Repere) -> list[tuple[float, float]]:
    """Les centres des lettres que le releve PAR LIGNES de la bibliotheque place hors de la page.

    Par defaut ce releve ecarte tout ce qui est hors de la feuille, et il le
    fait DEUX fois: par un drapeau, et parce qu'il se borne au cadre de la
    page. Il faut lever les deux - verifie sur piece fabriquee: le drapeau
    seul ne suffit pas - sinon il ne pourrait jamais en compter une seule.
    """
    import pymupdf

    centres = []
    partout = pymupdf.Rect(-20000, -20000, 20000, 20000)
    for bloc in page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_MEDIABOX_CLIP, clip=partout).get("blocks", []):
        for ligne in bloc.get("lines", []):
            for span in ligne.get("spans", []):
                for lettre in span.get("chars", []):
                    if lettre.get("c", "").strip() and not rep.centre_dedans(lettre["bbox"]):
                        centres.append(milieu(lettre["bbox"]))
    return centres


def hors_page_recoupe(page, rep: Repere, ecrits: list[dict]) -> int:
    """Un texte n'est dit hors de la page que si DEUX releves l'y placent.

    Le releve lettre a lettre et le releve par lignes ne viennent pas du meme
    code. Sur une vraie piece, le premier a place hors de la page des
    centaines de lignes que le second voyait dedans. Quand ils ne s'accordent
    pas, la lecture ne dit rien, et compte ce qu'elle a laisse de cote.
    """
    hors = [e for e in ecrits if e["cause"] == "hors de la page"]
    if not hors:
        return 0
    try:
        dehors = lettres_hors_page_selon_les_lignes(page, rep)
    except Exception:  # noqa: BLE001 - sans second releve, rien n'est confirme
        dehors = []
    douteuses = 0
    for ecrit in hors:
        x0, y0, x1, y1 = ecrit["bbox"]
        if not any(x0 - 3 <= x <= x1 + 3 and y0 - 3 <= y <= y1 + 3 for x, y in dehors):
            ecrit["cause"] = ""
            ecrit["douteux"] = True
            douteuses += 1
    return douteuses


def _texte_par_dessus(ecrits: list[dict], couverture: dict, ecrit: dict, lettre) -> str:
    """Ce qui est dessine APRES cette couverture, sur cette lettre.

    `""`: rien. `"autre"`: un autre texte y est ecrit. `"meme"`: le meme signe
    y est redessine a la meme place - un titre ecrit sous un bandeau puis
    redessine par-dessus, comme le font les logiciels de mise en page. La page
    montre alors la lettre: rien n'est cache au lecteur.
    """
    if "dessus" not in couverture:
        couverture["dessus"] = [(l[3], e["police"], l[1], l[0]) for e in ecrits if e["seqno"] > couverture["seqno"] and e["mode"] != 3
                                for l in e["lettres"] if contient(couverture, *milieu(l[3]))]
    boite = lettre[3]
    large, haut = boite[2] - boite[0], boite[3] - boite[1]
    rendu = ""
    for b, police, glyphe, code in couverture["dessus"]:
        if b[0] < boite[2] and b[2] > boite[0] and b[1] < boite[3] and b[3] > boite[1]:
            meme_signe = (police == ecrit["police"] and glyphe == lettre[1]) or (code == lettre[0] and code != 0xFFFD)
            if meme_signe and abs(b[0] - boite[0]) <= 0.25 * large and abs(b[1] - boite[1]) <= 0.25 * haut:
                return "meme"
            rendu = "autre"
    return rendu

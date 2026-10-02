# -*- coding: utf-8 -*-
"""Les règles du contrôle de publication : ce qui se lit dans des octets, dans un texte, dans un nom.

Ce module ne lit ni dépôt, ni exécutable : pour des octets ou un texte qu'on lui donne, il dit ce qui doit
être refusé. Le mode d'emploi, la liste de ce qui est refusé et ce que le contrôle ne voit pas sont écrits
en tête de controle_publication.py.

LES CHAÎNES INTERDITES NE SONT PAS DANS LE DÉPÔT, sous aucune forme. Leur liste est un fichier tenu hors
du dépôt, donné au contrôle par --interdits. Ce code ne porte que des motifs génériques - un chemin de
dossier personnel, une adresse de courriel, les noms du poste lus sur le poste au moment du contrôle - et
une chaîne inventée, le témoin, que le contrôle plante pour faire ses preuves.

LA LISTE est un fichier de texte en UTF-8. Une chaîne par ligne, cherchée sans tenir compte de la casse ;
« # » en tête de ligne ouvre un commentaire ; une ligne entre crochets ouvre une rubrique :

  [partout]                      des chaînes refusées partout : dépôt, textes publiés, exécutable ;
  [comptees dans un executable]  des chaînes refusées dans le dépôt et les textes publiés, et seulement
                                 comptées dans un exécutable, où des bibliothèques tierces les portent ;
  [tolerees]                     des phrases entières qui passent telles quelles, quoi qu'elles contiennent.

Sans rubrique, une chaîne est refusée partout. Les chaînes ne sont jamais imprimées : un constat les
désigne par leur rang dans la liste, et montre le mot où elles ont été trouvées, masqué par des étoiles.

DEUX TOLÉRANCES, et pas d'autre. La première est écrite ici : le nom du compte GitHub qui porte le dépôt.
Il se lit là où il vit - l'adresse du dépôt distant, l'adresse « noreply » des commits - et passe dans
l'identité des commits et dans l'adresse du dépôt (github.com/compte/...), quoi qu'il contienne, et nulle
part ailleurs. La seconde se déclare dans la liste : ses phrases tolérées. Le contrôle compte ce que
chacune des deux a laissé passer, et le dit.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import stat
from pathlib import Path

TEMOIN = "temoin" + "interdit"  # la seule chaîne interdite écrite dans le dépôt : inventée, plantée, elle doit être retrouvée
RUBRIQUES = {"[partout]": "partout", "[comptees dans un executable]": "comptees", "[tolerees]": "tolerees"}
LISTE: dict[str, list[str]] = {"partout": [TEMOIN], "comptees": [], "tolerees": []}
COMPTES: dict[str, list[int]] = {}  # dans un exécutable, pour chaque chaîne seulement comptée : [occurrences, fichiers]
TOLEREES = {"adresses": 0, "phrases": 0}  # ce que les deux tolérances ont laissé passer

EN_TETE_PDF = b"%" + b"PDF-"
EXEMPLES = "exemples/"  # le seul dossier du dépôt où un PDF a sa place
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic", ".avif"}
EN_TETES_IMAGE = (bytes([0x89]) + b"PNG", bytes([0xFF, 0xD8, 0xFF]), b"GIF8", b"RIFF", b"BM")
CACHES_DE_GIT = {".github", ".gitignore", ".gitattributes"}  # les seuls fichiers et dossiers cachés qu'un commit porte
CONSTRUCTION = "_construction_locale"  # où la construction et les essais écrivent, sur le poste
CHEMIN_PERSONNEL = re.compile(r"(?i)(?:[a-z]:|/[a-z])[\\/]+users[\\/]+([^\\/\s\"'<>|:*?]+)")
COURRIEL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,}")  # bornes : la recherche reste rapide dans un binaire
COURRIEL_EN_OCTETS = re.compile(COURRIEL.pattern.encode("ascii"))
NOREPLY_GITHUB = re.compile(r"(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com")
INVISIBLES = {chr(c) for c in [*range(0x09), 0x0B, 0x0C, *range(0x0E, 0x20), *range(0x7F, 0xA1), 0xAD, *range(0x200B, 0x2010),
                               *range(0x2028, 0x2030), *range(0x2060, 0x2065), 0xFEFF]}


# ------------------------------------------------------------------ la liste

def lire_la_liste(chemin: Path) -> tuple[dict[str, list[str]], list[str]]:
    """La liste tenue hors du dépôt, et ce qui empêche de s'y fier. Le témoin y est toujours, en tête."""
    liste, erreurs, rubrique = {"partout": [TEMOIN], "comptees": [], "tolerees": []}, [], "partout"
    try:
        lignes = chemin.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return liste, ["le fichier de la liste ne se lit pas"]
    for numero, ligne in enumerate(lignes, 1):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ligne.startswith("[") and ligne.endswith("]"):
            rubrique = RUBRIQUES.get(ligne.casefold(), "")
            if not rubrique:
                erreurs.append(f"ligne {numero} : cette rubrique n'existe pas")
                rubrique = "partout"
            continue
        chaine = ligne.casefold()
        if len(chaine) < 4:
            erreurs.append(f"ligne {numero} : une chaîne de moins de quatre signes se trouverait partout")
        elif chaine not in liste["partout"] + liste["comptees"] + liste["tolerees"]:
            liste[rubrique].append(chaine)
    if len(liste["partout"]) + len(liste["comptees"]) < 2:
        erreurs.append("la liste ne porte aucune chaîne")
    return liste, erreurs


def fixer_la_liste(liste: dict[str, list[str]]) -> None:
    LISTE.update({cle: list(liste[cle]) for cle in LISTE})
    COMPTES.clear()


@contextlib.contextmanager
def liste_d_essai(partout: list[str], comptees: list[str] | None = None, tolerees: list[str] | None = None):
    """Une autre liste le temps d'une épreuve : la vraie, et ses comptes, sont remis en place ensuite."""
    vraie, comptes, tolerances = {cle: list(valeur) for cle, valeur in LISTE.items()}, dict(COMPTES), dict(TOLEREES)
    fixer_la_liste({"partout": partout, "comptees": comptees or [], "tolerees": tolerees or []})
    try:
        yield
    finally:
        fixer_la_liste(vraie)
        COMPTES.update(comptes)
        TOLEREES.update(tolerances)


def interdites() -> list[str]:
    """Toutes les chaînes cherchées, dans l'ordre de la liste : le rang d'une chaîne est sa place ici, le témoin au rang 0."""
    return LISTE["partout"] + LISTE["comptees"]


def masque(texte: str) -> str:
    """Le même texte, ses chaînes interdites remplacées par des étoiles : le contrôle n'écrit jamais ce qu'il refuse."""
    for chaine in sorted(interdites(), key=len, reverse=True):
        texte = re.sub(re.escape(chaine), lambda trouve: "*" * len(trouve.group(0)), texte, flags=re.IGNORECASE)
    return texte


def mot_masque(source: bytes, position: int, taille: int, chaine: str) -> str:
    """Le mot où la chaîne a été trouvée, masqué : de quoi la retrouver dans le fichier, sans l'écrire."""
    fenetre = source[max(0, position - 60):position + taille + 60].replace(b"\x00", b"").decode("latin-1")
    trouve = re.search(r"[a-z0-9_]{0,20}" + re.escape(chaine) + r"[a-z0-9_]{0,20}", fenetre)
    return masque(trouve.group(0) if trouve else chaine)


def chaines(lieu: str, octets: bytes, executable: bool = False) -> list[tuple[str, str, str]]:
    """Les chaînes de la liste dans ces octets : sans tenir compte de la casse, en UTF-8 puis en UTF-16, dans ses deux ordres d'octets."""
    try:
        huit = octets.decode("utf-8").casefold().encode("utf-8")  # un texte : les majuscules accentuées sont pliées aussi
    except UnicodeDecodeError:
        huit = octets.lower()
    seize = octets.lower()
    for phrase in LISTE["tolerees"]:
        aiguille = phrase.encode("utf-8")
        TOLEREES["phrases"] += huit.count(aiguille)
        huit = huit.replace(aiguille, b"-")
    constats = []
    for rang, chaine in enumerate(interdites()):
        # Un texte en UTF-16 porte la chaîne dans les deux ordres, à un octet près : le plus grand des deux comptes est le bon.
        trouvees = [trouvee(huit, chaine, "utf-8", ""),
                    max(trouvee(seize, chaine, "utf-16-le", " en UTF-16"), trouvee(seize, chaine, "utf-16-be", " en UTF-16"), key=lambda t: t[0])]
        if executable and chaine in LISTE["comptees"]:
            if trouvees[0][0] + trouvees[1][0]:
                compte = COMPTES.setdefault(chaine, [0, 0])
                compte[0] += trouvees[0][0] + trouvees[1][0]
                compte[1] += 1
            continue
        for nombre, forme, source, position, taille in trouvees:
            if nombre:
                constats.append(("CHAINE", lieu, f"chaîne n° {rang} de la liste, {nombre} fois{forme} : " + mot_masque(source, position, taille, chaine)))
    return constats


def trouvee(source: bytes, chaine: str, codage: str, forme: str) -> tuple[int, str, bytes, int, int]:
    """Combien de fois la chaîne est dans ces octets déjà pliés, sous ce codage : (nombre, forme, source, première position, taille).

    Les octets ne sont pliés que pour les lettres sans accent. Une chaîne accentuée est donc cherchée deux fois :
    telle qu'elle est, et ses lettres accentuées en capitales.
    """
    nombre, position, taille = 0, -1, 0
    for aiguille in {chaine.encode(codage), chaine.upper().encode(codage).lower()}:
        ici = source.count(aiguille)
        if ici and position < 0:
            position, taille = source.find(aiguille), len(aiguille)
        nombre += ici
    return nombre, forme, source, position, taille


# ------------------------------------------------------- les règles génériques

def est_reglages(nom: str, octets: bytes) -> bool:
    """Un fichier de réglages de l'outil : par son nom, ou par sa forme."""
    feuille = nom.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    if re.fullmatch(r"reglages.*\.json", feuille):
        return True
    if not feuille.endswith(".json"):
        return False
    try:
        lu = json.loads(octets.decode("utf-8"))
    except ValueError:
        return False
    return isinstance(lu, dict) and "proteges" in lu


def hors_commit(chemin: str) -> str:
    """Pourquoi ce chemin n'a pas sa place dans un commit ; rien, s'il l'a."""
    morceaux = chemin.replace("\\", "/").split("/")
    if any(morceau.startswith(".") and morceau not in CACHES_DE_GIT for morceau in morceaux):
        return "un fichier ou un dossier caché, qui n'est pas de ceux que Git emploie"
    if CONSTRUCTION in morceaux or "__pycache__" in morceaux or morceaux[-1].casefold().endswith((".pyc", ".pyo")):
        return "ce que la construction ou un passage laisse sur le poste"
    if morceaux[-1].casefold().endswith((".log", ".tmp", ".bak")):
        return "un journal, ou un fichier de travail"
    return ""


def texte_examine(lieu: str, texte: str, noms: dict[str, str], invisibles: bool = True) -> list[tuple[str, str, str]]:
    """Les règles qui se lisent dans un texte : chemins personnels, adresses, noms du poste, caractères invisibles."""
    constats = [("CHEMIN", lieu, "dossier personnel de " + trouve.group(1)[:1] + "…") for trouve in CHEMIN_PERSONNEL.finditer(texte)]
    for adresse in sorted(set(COURRIEL.findall(texte))):
        local, _, domaine = adresse.rpartition("@")
        if local.casefold() != "noreply" and domaine.casefold() != "users.noreply.github.com":
            constats.append(("COURRIEL", lieu, local[:1] + "…@" + domaine))
    plie = texte.casefold()
    constats += [("POSTE", lieu, "un " + quoi) for nom, quoi in noms.items() if nom in plie]
    trouves = sorted({f"U+{ord(c):04X}" for c in texte if c in INVISIBLES}) if invisibles else []
    return constats + ([("INVISIBLE", lieu, " ".join(trouves))] if trouves else [])


def poste_dans_des_octets(lieu: str, octets: bytes, noms: dict[str, str]) -> list[tuple[str, str, str]]:
    """Un nom propre au poste dans des octets qui ne sont pas du texte : en UTF-8, ou en UTF-16 dans ses deux ordres d'octets."""
    plie = octets.lower()
    return [("POSTE", lieu, "un " + quoi) for nom, quoi in noms.items()
            if any(nom.encode(codage) in plie for codage in ("utf-8", "utf-16-le", "utf-16-be"))]


def adresse_du_depot(comptes: set[str]) -> re.Pattern | None:
    """Le motif de la tolérance écrite ici : l'adresse d'un dépôt de ces comptes sur GitHub, « github.com/compte/ »."""
    noms = "|".join(re.escape(compte) for compte in sorted(comptes) if compte)
    return re.compile(("(?i)github\\.com/(?:" + noms + ")(?=/)").encode("ascii")) if noms else None


def sans_adresse_du_depot(octets: bytes, adresse: re.Pattern | None) -> bytes:
    """Les mêmes octets, l'adresse du dépôt mise de côté : le compte n'y est pas examiné."""
    if adresse is None:
        return octets
    octets, tolerees = adresse.subn(b"github.com/-", octets)
    TOLEREES["adresses"] += tolerees
    return octets


def effacer(dossier: Path) -> None:
    """Supprime un dossier temporaire, fichiers en lecture seule compris : Git enregistre les siens ainsi."""
    def liberer(fonction, chemin, _erreur) -> None:
        os.chmod(chemin, stat.S_IWRITE)
        fonction(chemin)

    try:
        shutil.rmtree(dossier, onexc=liberer)
    except OSError:
        pass

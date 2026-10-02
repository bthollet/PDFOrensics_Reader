# -*- coding: utf-8 -*-
"""Le contrôle de publication d'un dépôt : ce qui est indexé, ce qui est présent, tout l'historique, chaque commit.

Le mode d'emploi et la liste de ce qui est refusé sont en tête de controle_publication.py ; les règles,
dans controle_regles.py ; la lecture des PDF, dans controle_pdf.py.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
from pathlib import Path

import controle_pdf
from controle_regles import (EN_TETES_IMAGE, IMAGES, NOREPLY_GITHUB, TOLEREES, adresse_du_depot, chaines, est_reglages, hors_commit,
                             poste_dans_des_octets, sans_adresse_du_depot, texte_examine)

LICENCES = {"licences/AGPL-3.0.txt": "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"}
SEPARATEUR, FIN = chr(0x1F), chr(0x1E)


def git(arguments: list[str], racine: Path | None = None, entree: bytes | None = None, brut: bool = False, **environnement: str):
    """La sortie d'une commande Git, dans le dépôt `racine` s'il est donné. Une commande qui échoue rend une sortie vide."""
    commande = ["git", *(["-C", str(racine)] if racine else []), "-c", "core.quotepath=false", *arguments]
    try:
        sortie = subprocess.run(commande, input=entree, capture_output=True, check=False,  # noqa: S603
                                env={**os.environ, **environnement} if environnement else None).stdout
    except OSError:
        sortie = b""
    return sortie if brut else sortie.decode("utf-8", "replace")


def noms_du_poste() -> dict[str, str]:
    """Les noms propres à ce poste, en minuscules, avec ce qu'ils sont. Ils ne s'impriment jamais."""
    noms: dict[str, str] = {}
    for quoi, valeur in (("nom d'utilisateur", os.environ.get("USERNAME", "")), ("nom de machine", os.environ.get("COMPUTERNAME", "")),
                         ("nom de machine", platform.node()), ("dossier personnel", Path.home().name)):
        if len(valeur) >= 3:
            noms.setdefault(valeur.casefold(), quoi)
    for cle in ("user.name", "user.email"):
        valeur = git(["config", "--global", "--get", cle]).strip().partition("@")[0]
        for morceau in re.split(r"[^A-Za-z0-9]+", valeur):
            if len(morceau) >= 4:
                noms.setdefault(morceau.casefold(), "identité Git globale du poste")
    return noms


def comptes_du_depot(racine: Path) -> set[str]:
    """Le compte qui porte le dépôt, lu là où il vit : l'adresse du dépôt distant, l'adresse noreply des commits."""
    comptes = set(re.findall(r"github\.com[:/]+([A-Za-z0-9-]+)/", git(["remote", "-v"], racine)))
    return comptes | {trouve.group(1) for trouve in map(NOREPLY_GITHUB.fullmatch, git(["log", "--all", "--format=%ae%n%ce"], racine).split()) if trouve}


def examiner(lieu: str, octets: bytes, noms: dict[str, str], executable: bool = False,
             adresse: re.Pattern | None = None) -> list[tuple[str, str, str]]:
    """Tous les constats pour un fichier : son nom, puis son contenu."""
    pdf = controle_pdf.est_pdf(lieu, octets)
    if not executable and not pdf:
        octets = sans_adresse_du_depot(octets, adresse)  # la tolérance écrite : le compte, dans l'adresse du dépôt
    constats = chaines(lieu, lieu.encode("utf-8"), executable) + chaines(lieu, octets, executable)
    if est_reglages(lieu, octets):
        constats.append(("REGLAGES", lieu, "un fichier de réglages de l'outil"))
    if executable:
        return constats + poste_dans_des_octets(lieu, octets, noms) + ([("PDF", lieu, "un PDF embarqué")] if pdf else [])
    constats += texte_examine(lieu, lieu, noms) + ([("HORS", lieu, hors_commit(lieu))] if hors_commit(lieu) else [])
    if pdf:  # un PDF n'a sa place que dans le dossier des exemples, et il y est ouvert et lu
        if not controle_pdf.est_un_exemple(lieu, octets):
            return constats + [("PDF", lieu, "un PDF hors du dossier des exemples, ou qui n'en porte que le nom")]
        return constats + poste_dans_des_octets(lieu, octets, noms) + controle_pdf.examiner_pdf(lieu, octets, noms)
    suffixe = "." + lieu.rsplit(".", 1)[-1].casefold() if "." in lieu else ""
    try:
        texte = octets.decode("utf-8")
    except UnicodeDecodeError:
        texte = None
    if suffixe in IMAGES or octets.startswith(EN_TETES_IMAGE):
        constats.append(("IMAGE", lieu, "une image"))
    elif texte is None or b"\x00" in octets:
        constats.append(("BINAIRE", lieu, "un fichier qui n'est pas du texte"))
    if texte is not None and b"\x00" not in octets:
        constats += texte_examine(lieu, texte, noms)
    return constats


def commit_examine(commit: dict, noms: dict[str, str], pseudonymes: set[str]) -> list[tuple[str, str, str]]:
    """L'identité d'un commit, puis son message. Seuls passent un pseudonyme de GitHub et l'adresse noreply qui le porte."""
    lieu, constats, reste = "commit " + commit["id"][:12], [], [commit["message"]]
    for role, nom, adresse in (("auteur", commit["an"], commit["ae"]), ("committer", commit["cn"], commit["ce"])):
        trouve = NOREPLY_GITHUB.fullmatch(adresse)
        if trouve and nom == trouve.group(1):
            pseudonymes.add(nom)
        elif (nom, adresse) != ("GitHub", "noreply@github.com"):
            constats.append(("IDENTITE", lieu, role + " : ni un pseudonyme de GitHub, ni l'adresse noreply qui le porte"))
            reste += [nom, adresse]
    corps = "\n".join(reste)
    return constats + chaines(lieu, corps.encode("utf-8")) + texte_examine(lieu, corps, noms)


def objets(racine: Path, empreintes: list[str]) -> dict[str, bytes]:
    """Le contenu des fichiers enregistrés sous ces identifiants (les arbres et les commits sont laissés)."""
    sortie = git(["cat-file", "--batch"], racine, entree=("\n".join(empreintes) + "\n").encode("ascii"), brut=True)
    rendu, position = {}, 0
    while position < len(sortie):
        fin = sortie.index(b"\n", position)
        mots = sortie[position:fin].decode("ascii").split()
        if len(mots) != 3:  # un objet absent : « identifiant missing »
            position = fin + 1
            continue
        if mots[1] == "blob":
            rendu[mots[0]] = sortie[fin + 1:fin + 1 + int(mots[2])]
        position = fin + 1 + int(mots[2]) + 1
    return rendu


def controler_depot(racine: Path, noms: dict[str, str]) -> tuple[list, list[str]]:
    constats, lignes = [], []
    sommet = git(["rev-parse", "--show-toplevel"], racine).strip()
    if git(["rev-parse", "--is-inside-work-tree"], racine).strip() != "true" or not sommet or Path(sommet).resolve() != racine:
        return [("DEPOT", str(racine.name), "ce dossier n'est pas la racine d'un dépôt Git lisible : rien n'a pu être examiné")], lignes
    comptes = comptes_du_depot(racine)
    adresse = adresse_du_depot(comptes)
    TOLEREES.update(adresses=0, phrases=0)
    controle_pdf.LUS.update(dict.fromkeys(controle_pdf.LUS, 0))
    # 1. Ce qui est indexé : ce que le prochain commit enregistrera.
    indexes = [ligne.split("\t", 1) for ligne in git(["ls-files", "-s", "-z"], racine).split("\0") if ligne]
    index = {chemin: tete.split()[1] for tete, chemin in indexes}
    # 2. Tout ce que l'historique a enregistré, dans toutes les branches et étiquettes.
    historique = {}
    for ligne in git(["rev-list", "--objects", "--all"], racine).splitlines():
        identifiant, _, chemin = ligne.partition(" ")
        if chemin:
            historique.setdefault(identifiant, chemin)
    contenus = objets(racine, sorted(set(index.values()) | set(historique)))
    vus: set[tuple[str, str]] = set()
    for chemin, identifiant in list(index.items()) + [(chemin, identifiant) for identifiant, chemin in historique.items()]:
        if identifiant in contenus and (chemin, identifiant) not in vus:
            vus.add((chemin, identifiant))
            constats += examiner(chemin, contenus[identifiant], noms, adresse=adresse)
    enregistres = sum(1 for identifiant in historique if identifiant in contenus)
    # 3. Les fichiers présents : suivis, ou ni suivis ni ignorés.
    presents = [chemin for chemin in git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"], racine).split("\0") if chemin]
    for chemin in presents:
        fichier = racine / chemin
        if fichier.is_file():
            octets = fichier.read_bytes()
            if (chemin, hashlib.sha1(b"blob %d\0" % len(octets) + octets).hexdigest()) not in vus:  # noqa: S324 - l'identifiant de Git
                constats += examiner(chemin, octets, noms, adresse=adresse)
            if chemin in LICENCES and hashlib.sha256(octets).hexdigest() != LICENCES[chemin]:
                constats.append(("LICENCE", chemin, "ce texte n'est pas, à l'octet près, celui qui est attendu"))
    constats += [("LICENCE", chemin, "le texte de licence attendu est absent") for chemin in LICENCES if chemin not in presents]
    # 4. Le dossier entier, fichiers ignorés compris : ni réglages de l'outil, ni PDF hors de ce qui vient d'être lu.
    partout = 0
    for dossier, sous_dossiers, fichiers in os.walk(racine):
        if ".git" in sous_dossiers:
            sous_dossiers.remove(".git")
        for nom in fichiers:
            partout += 1
            chemin = (Path(dossier) / nom).relative_to(racine).as_posix()
            if chemin in presents:
                continue
            if nom.casefold().endswith(".pdf"):
                constats.append(("PDF", chemin, "un PDF posé dans le dossier du dépôt, hors du dossier des exemples"))
            if nom.casefold().endswith(".json") and est_reglages(chemin, (Path(dossier) / nom).read_bytes()):
                constats.append(("REGLAGES", chemin, "un fichier de réglages posé dans le dossier du dépôt, hors de ce que Git suit"))
    # 5. L'identité et le message de chaque commit, puis de chaque étiquette.
    pseudonymes: set[str] = set()
    forme = "%x1f".join(["%H", "%an", "%ae", "%cn", "%ce", "%B"]) + "%x1e"
    commits = [dict(zip(("id", "an", "ae", "cn", "ce", "message"), bloc.strip("\n").split(SEPARATEUR)))
               for bloc in git(["log", "--all", "--format=" + forme], racine).split(FIN) if bloc.strip("\n")]
    for commit in commits:
        constats += commit_examine(commit, noms, pseudonymes) if len(commit) == 6 else [("IDENTITE", "commit", "un commit ne se lit pas")]
    forme = "%1f".join(["%(refname:short)", "%(objecttype)", "%(taggername)", "%(taggeremail)", "%(contents)"]) + "%1e"
    etiquettes = [bloc.strip("\n").split(SEPARATEUR)
                  for bloc in git(["for-each-ref", "refs/tags", "--format=" + forme], racine).split(FIN) if bloc.strip("\n")]
    for etiquette in etiquettes:
        constats += chaines("étiquette", etiquette[0].encode("utf-8")) + texte_examine("étiquette " + etiquette[0], etiquette[0], noms)
        if len(etiquette) == 5 and etiquette[1] == "tag":  # une étiquette annotée porte une identité et un message
            courriel = etiquette[3].strip("<>")
            constats += commit_examine({"id": "étiquette " + etiquette[0], "an": etiquette[2], "ae": courriel, "cn": etiquette[2], "ce": courriel,
                                        "message": etiquette[4]}, noms, pseudonymes)
    lus = controle_pdf.LUS
    lignes.append(f"Examiné : {len(index)} fichiers indexés ; {len(presents)} fichiers présents, suivis ou non ignorés ; "
                  f"{enregistres} fichiers de l'historique ; {partout} fichiers dans le dossier entier, pour les réglages et les PDF.")
    lignes.append(f"PDF des exemples : {lus['pdf']} lus avec la bibliothèque, {lus['versions']} versions ouvertes, {lus['pages']} pages, "
                  f"{lus['objets']} objets décodés.")
    lignes.append(f"Commits : {len(commits)} examinés" + (" (aucun commit encore)" if not commits else "") + f" ; étiquettes : {len(etiquettes)}.")
    if comptes:
        lignes.append("Compte qui porte le dépôt : son nom est toléré dans l'identité des commits et dans l'adresse du dépôt, et là seulement "
                      f"({TOLEREES['adresses']} adresse(s) du dépôt dans les fichiers examinés).")
    return constats, lignes

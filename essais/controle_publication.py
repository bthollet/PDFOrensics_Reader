# -*- coding: utf-8 -*-
"""Contrôle de publication : ce que le dépôt, ses exemples, l'exécutable et les textes publiés ne doivent jamais porter.

  python -B essais/controle_publication.py --interdits LISTE                      le dépôt
  python -B essais/controle_publication.py --interdits LISTE --executable CHEMIN  un exécutable construit
  python -B essais/controle_publication.py --interdits LISTE --exemples ZIP       le zip des exemples joint à une release
  python -B essais/controle_publication.py --interdits LISTE --textes FICHIER     un texte publié hors du dépôt :
                                                                                  note de version, message de commit

  --sans-liste    à la place de --interdits : les règles génériques seules, et le verdict le dit
  --poste-neutre  sur une machine de construction, dont les noms ne sont ceux de personne
  --tiers         avec --textes, pour les textes de licence des bibliothèques : les adresses de leurs auteurs
                  sont comptées, pas refusées

À lancer avant chaque commit, sur ce qui est indexé, et avant chaque envoi. Il sort sur un code non nul
s'il refuse ; le verdict se lit sur sa dernière ligne.

LA LISTE des chaînes interdites est un fichier tenu HORS du dépôt : le dépôt n'en porte aucune, sous
aucune forme. Sa forme, et ses trois rubriques, sont décrites en tête de controle_regles.py. Une liste
posée dans le dossier du dépôt est refusée. Sans liste, il faut le demander (--sans-liste).

LE DÉPÔT. Sont examinés : ce qui est indexé (ce que le prochain commit enregistrera), les fichiers
présents (suivis, ou ni suivis ni ignorés), tout ce que l'historique a enregistré un jour, dans toutes
les branches et étiquettes, et l'identité et le message de chaque commit. Sont refusés :

  CHAINE     une chaîne de la liste, sans tenir compte de la casse, en UTF-8 comme en UTF-16 ;
  CHEMIN     un chemin du dossier personnel d'un utilisateur ;
  COURRIEL   une adresse de courriel autre qu'une adresse « noreply » ;
  POSTE      un nom propre au poste où le contrôle tourne : utilisateur, machine, identité Git globale ;
  PDF        un PDF hors du dossier des exemples, par son nom ou par son en-tête ; un PDF qui ne se lit pas ;
  BINAIRE    un fichier qui n'est pas du texte ;
  IMAGE      une image : ni capture d'écran, ni illustration ;
  REGLAGES   un fichier de réglages de l'outil, posé n'importe où dans le dossier du dépôt ;
  INVISIBLE  un caractère de contrôle ou un caractère invisible ;
  HORS       ce qui n'a pas sa place dans un commit : un dossier caché qui n'est pas de ceux de Git, ce que
             la construction laisse sur le poste, un journal ;
  IDENTITE   un commit signé autrement que par un pseudonyme de GitHub et son adresse « noreply » ;
  LICENCE    un texte de licence joint qui n'est pas, à l'octet près, celui qui est attendu.

LES PDF DES EXEMPLES. Le dossier `exemples/` est le seul où un PDF a sa place. Chacun y est OUVERT avec
la bibliothèque et lu : ses métadonnées, son second jeu de métadonnées, le texte de CHAQUE VERSION
enregistrée, ses calques éteints, son texte invisible, ses annotations, ses fichiers joints, les noms de
ses polices, ses flux décompressés (voir controle_pdf.py). Les mêmes règles s'y appliquent.

LE ZIP DES EXEMPLES ne porte que ces PDF, les mêmes, à l'octet près, que ceux du dossier (EXEMPLES).

L'EXÉCUTABLE. Ses octets sont examinés, puis chaque fichier de son archive, décompressé : modules compilés
un par un, bibliothèque de base, bibliothèques, données. Sont refusés : CHAINE, POSTE, PDF, REGLAGES, et un
module compilé qui porte un chemin absolu (MODULE). Une bibliothèque tierce porte des adresses et des
chemins de ceux qui l'ont construite : ils sont comptés, pas refusés ; les chaînes de la rubrique
« comptées dans un exécutable » de la liste le sont aussi.

DEUX TOLÉRANCES, décrites en tête de controle_regles.py : le nom du compte qui porte le dépôt, dans
l'adresse du dépôt et l'identité des commits ; les phrases que la liste déclare tolérées.

CE QUE CE CONTRÔLE NE VOIT PAS : une chaîne coupée par un signe ou un retour à la ligne ; un texte dans
une image ; une donnée personnelle qui n'est ni une adresse, ni un chemin, ni un nom du poste, ni une
chaîne de la liste ; une consigne interne, une sortie d'essai ou un journal que rien ne distingue d'un
fichier ordinaire ; un PDF sans son nom ni son en-tête ; ce qu'une bibliothèque tierce tiendrait
compressé à l'intérieur d'elle-même ; ce qu'un PDF porte et que sa lecture ne rend pas (controle_pdf.py).
"""
from __future__ import annotations

import io
import marshal
import os
import re
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True  # même lancé sans -B, rien ne s'écrit à côté des sources

import controle_pdf  # noqa: E402
from controle_depot import comptes_du_depot, controler_depot, examiner, noms_du_poste  # noqa: E402
from controle_regles import (COMPTES, CONSTRUCTION, COURRIEL_EN_OCTETS, EXEMPLES, LISTE, TOLEREES, adresse_du_depot, chaines,  # noqa: E402
                             fixer_la_liste, interdites, lire_la_liste, masque, sans_adresse_du_depot, texte_examine)
from controle_temoins import PDF_PLANTES, temoins  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
# Ce que le contrôle doit retrouver dans l'archive d'un exécutable, pour prouver qu'il en lit le contenu compressé.
TEMOINS_ARCHIVE = {"d'un module du paquet": b"pdforensics : phrase temoin du controle de publication",
                   "d'un fragment de l'écran": b"lu sur ce poste et n'en sort pas"}
MODES = ("--executable", "--exemples", "--textes")
ABSOLU = re.compile(r"(?i)^(?:[a-z]:)?[\\/]")


# -------------------------------------------------------------- l'exécutable

def fichiers_de_l_archive(chemin: Path):
    """Chaque fichier que l'exécutable embarque, décompressé : (genre, nom, octets). Le genre « code » est du Python compilé."""
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(chemin))
    for nom, entree in archive.toc.items():
        if entree[-1] == "z":  # l'archive des modules Python
            modules = archive.open_embedded_archive(nom)
            for module in modules.toc:
                octets = modules.extract(module, raw=True)
                if octets is not None:
                    yield "module", module, octets
            continue
        octets = archive.extract(nom)
        yield ("code" if entree[-1] in ("s", "m", "M") else "fichier"), nom, octets
        if octets[:2] == b"PK" and zipfile.is_zipfile(io.BytesIO(octets)):  # une archive dans l'archive : la bibliothèque de base
            with zipfile.ZipFile(io.BytesIO(octets)) as interne:
                for membre in interne.namelist():
                    yield ("code" if membre.casefold().endswith(".pyc") else "fichier"), nom + "/" + membre, interne.read(membre)


def noms_inscrits(octets: bytes, inscrits: set[str]) -> bool:
    """Les noms de fichiers qu'un module compilé porte, relevés dans son code et dans tout ce qu'il contient. Faux s'il ne se relit pas."""
    for depart in (0, 16):  # un module de l'archive est du code nu ; un fichier compilé le fait précéder de seize octets
        try:
            code = marshal.loads(octets[depart:])
        except Exception:  # noqa: BLE001, S112 - ce qui ne se relit pas d'une façon s'essaie de l'autre
            continue
        if hasattr(code, "co_filename"):
            pile = [code]
            while pile:
                courant = pile.pop()
                inscrits.add(courant.co_filename)
                pile += [constante for constante in courant.co_consts if hasattr(constante, "co_filename")]
            return True
    return False


def controler_executable(chemin: Path, noms: dict[str, str]) -> tuple[list, list[str]]:
    lignes, comptes, retrouves, personnels = [], {"module": 0, "code": 0, "fichier": 0}, {}, set()
    adresses = construction = non_relus = 0
    inscrits: set[str] = set()
    brut = chemin.read_bytes()
    constats = examiner("les octets de l'exécutable", brut, noms, executable=True)
    aiguilles = [CONSTRUCTION.encode(codage) for codage in ("utf-8", "utf-16-le", "utf-16-be")]
    construction += sum(brut.lower().count(aiguille) for aiguille in aiguilles)
    try:
        for genre, nom, octets in fichiers_de_l_archive(chemin):
            comptes[genre] += 1
            constats += examiner(nom, octets, noms, executable=True)
            if genre != "fichier" and not noms_inscrits(octets, inscrits):
                non_relus += 1
            for quoi, phrase in TEMOINS_ARCHIVE.items():
                if phrase in octets:
                    retrouves.setdefault(quoi, genre)
            personnels |= {trouve.group(1).decode("ascii", "replace").casefold() for trouve in re.finditer(
                rb"(?i)[a-z]:[\\/]+users[\\/]+([A-Za-z0-9._~ -]+)", octets)}
            adresses += len(COURRIEL_EN_OCTETS.findall(octets))
            construction += sum((nom.encode("utf-8") + b"\n" + octets).lower().count(aiguille) for aiguille in aiguilles)
    except ImportError:
        constats.append(("ARCHIVE", chemin.name, "PyInstaller n'est pas installé : le contenu compressé de l'exécutable n'a pas été lu"))
    except Exception as erreur:  # noqa: BLE001 - une archive illisible est un refus, pas une panne du contrôle
        constats.append(("ARCHIVE", chemin.name, f"l'archive de l'exécutable ne se lit pas ({type(erreur).__name__})"))
    absolus = sorted(nom for nom in inscrits if ABSOLU.match(nom))
    constats += [("MODULE", "un module compilé", "il porte le chemin absolu d'un fichier : " + masque(nom)[:3] + "…") for nom in absolus[:20]]
    if non_relus:
        constats.append(("ARCHIVE", chemin.name, f"{non_relus} module(s) compilé(s) ne se relisent pas avec ce Python : leurs noms de fichiers "
                         "n'ont pas été examinés"))
    lignes.append(f"Examiné : {len(brut)} octets ; dans l'archive, décompressés, {comptes['module']} modules, {comptes['code']} autres "
                  f"fichiers de code compilé et {comptes['fichier']} fichiers.")
    lignes.append(f"Modules compilés relus un par un : {len(inscrits)} noms de fichiers inscrits, dont {len(absolus)} absolu(s).")
    for quoi, phrase in TEMOINS_ARCHIVE.items():
        if quoi not in retrouves:
            constats.append(("ARCHIVE", chemin.name, f"la phrase témoin {quoi} n'a pas été retrouvée : le contenu n'est pas lu, ou ce n'est pas PDForensics"))
        else:
            lignes.append(f"Témoin de l'archive : la phrase {quoi} est retrouvée dans le contenu décompressé"
                          + (", et aussi dans les octets bruts." if phrase in brut else ", et pas dans les octets bruts : la lecture du contenu compressé est prouvée."))
    lignes.append(f"Compté, sans refus : {adresses} adresses de courriel de bibliothèques tierces ; dossiers personnels cités : "
                  + (", ".join(sorted(nom[:1] + "…" + f" ({len(nom)} signes)" for nom in personnels)) or "aucun")
                  + f" ; le nom du dossier de construction : {construction} fois.")
    if LISTE["comptees"]:
        rangs = {chaine: rang for rang, chaine in enumerate(interdites())}
        lignes.append("Compté, sans refus, pour les chaînes que la liste dit seulement comptées dans un exécutable : " + " ; ".join(
            f"n° {rangs[chaine]} : {COMPTES.get(chaine, [0, 0])[0]} fois dans {COMPTES.get(chaine, [0, 0])[1]} fichier(s)" for chaine in LISTE["comptees"]) + ".")
    return constats, lignes


# ------------------------------------------------ le zip des exemples, les textes

def exemples_du_depot() -> dict[str, bytes]:
    """Les PDF du dossier des exemples, tels qu'ils sont dans l'arbre : nom dans le dépôt -> octets."""
    return {fichier.relative_to(RACINE).as_posix(): fichier.read_bytes() for fichier in sorted((RACINE / EXEMPLES).rglob("*")) if fichier.is_file()}


def controler_exemples(chemin: Path, noms: dict[str, str]) -> tuple[list, list[str]]:
    controle_pdf.LUS.update(dict.fromkeys(controle_pdf.LUS, 0))
    attendus = exemples_du_depot()
    constats = controle_pdf.examiner_zip(chemin.name, chemin.read_bytes(), noms, attendus)
    lus = controle_pdf.LUS
    return constats, [f"Examiné : {chemin.stat().st_size} octets ; {lus['pdf']} PDF lus avec la bibliothèque, {lus['versions']} versions ouvertes, "
                      f"{lus['pages']} pages, {lus['objets']} objets décodés ; comparés aux {len(attendus)} fichiers du dossier des exemples."]


def controler_textes(chemin: Path, noms: dict[str, str], tiers: bool) -> tuple[list, list[str]]:
    octets = chemin.read_bytes()
    try:
        texte = octets.decode("utf-8")
    except UnicodeDecodeError:
        return [("BINAIRE", chemin.name, "ce fichier n'est pas un texte en UTF-8")], []
    lignes = [f"Examiné : {len(octets)} octets, {len(texte.splitlines())} lignes."]
    octets = sans_adresse_du_depot(octets, adresse_du_depot(comptes_du_depot(RACINE)))
    constats = chaines(chemin.name, chemin.name.encode("utf-8")) + chaines(chemin.name, octets) + texte_examine(chemin.name, texte, noms)
    lignes.append(f"L'adresse du dépôt y est tolérée {TOLEREES['adresses']} fois.")
    if tiers:  # des textes de licence de bibliothèques : ils portent les adresses de leurs auteurs, et parfois des sauts de page
        comptes = [sum(1 for code, _lieu, _detail in constats if code == quoi) for quoi in ("COURRIEL", "INVISIBLE")]
        constats = [constat for constat in constats if constat[0] not in ("COURRIEL", "INVISIBLE")]
        lignes.append(f"Texte de tiers. Compté, sans refus : {comptes[0]} adresse(s) de courriel de ses auteurs ; caractères de contrôle : "
                      + ("oui" if comptes[1] else "aucun") + ".")
    return constats, lignes


# ------------------------------------------------------------------ le passage

def sous(chemin: Path, dossier: Path) -> bool:
    """Ce chemin est-il dans ce dossier, quels que soient les noms sous lesquels on les écrit ?"""
    un, deux = os.path.normcase(os.path.realpath(chemin)), os.path.normcase(os.path.realpath(dossier))
    return un == deux or un.startswith(deux.rstrip("\\/") + os.sep)


def principal(arguments: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    def valeur(option: str) -> Path | None:
        suite = arguments[arguments.index(option) + 1:arguments.index(option) + 2] if option in arguments else []
        return Path(os.path.abspath(suite[0])) if suite else None

    mode = next((option for option in MODES if option in arguments), "")
    cible = valeur(mode) if mode else None
    quoi = {"--executable": "l'exécutable ", "--exemples": "le zip des exemples ", "--textes": "le texte publié "}
    print("Contrôle de publication de PDForensics : " + (quoi[mode] + cible.name if cible else "le dépôt"))
    liste = valeur("--interdits")
    if (mode and cible is None) or sum(option in arguments for option in MODES) > 1 or (liste is None) == ("--sans-liste" not in arguments):
        print("Il faut une liste (--interdits FICHIER) ou la dire absente (--sans-liste), et un seul objet à contrôler : voir l'en-tête de ce fichier.")
        print("VERDICT : REFUS, le contrôle n'a pas tourné")
        return 2
    if liste is not None:
        lue, erreurs = lire_la_liste(liste)
        if sous(liste, RACINE):
            erreurs.append("elle est posée dans le dossier du dépôt : elle doit vivre hors de lui")
        if erreurs:
            for erreur in erreurs:
                print("REFUS LISTE     la liste des chaînes interdites : " + erreur)
            print("VERDICT : REFUS, la liste des chaînes interdites ne peut pas servir")
            return 2
        fixer_la_liste(lue)
        print(f"Liste, lue hors du dépôt : {len(LISTE['partout']) - 1} chaînes refusées partout, {len(LISTE['comptees'])} refusées dans le dépôt "
              f"et les textes et seulement comptées dans un exécutable, {len(LISTE['tolerees'])} phrase(s) tolérée(s).")
    else:
        print("AUCUNE LISTE de chaînes interdites (--sans-liste) : seules les règles génériques, et le témoin, sont appliqués.")
    manques, plantes = temoins()
    print(f"Témoins : {plantes} - " + ("tout ce qui devait être refusé l'a été, et ce qui était propre est resté propre." if not manques
                                       else "LE CONTRÔLE N'A PAS FAIT SES PREUVES."))
    print(f"PDF plantés : {PDF_PLANTES['nombre']}, dont {PDF_PLANTES['aveugles']} où la chaîne ne se voit pas dans les octets du fichier : "
          "seule leur lecture la trouve.")
    for manque in manques:
        print("  MANQUE " + manque)
    noms = {} if "--poste-neutre" in arguments else noms_du_poste()
    connu = Path.home().name.casefold() in interdites()
    print(f"Ce poste : {len(noms)} noms propres recherchés" + (" (machine de construction : aucun)" if "--poste-neutre" in arguments else "")
          + " ; le nom de son dossier personnel " + ("est" if connu else "n'est pas") + " une chaîne de la liste.")
    TOLEREES.update(adresses=0, phrases=0)
    COMPTES.clear()
    if cible is not None and not cible.is_file():
        constats, lignes = [("ARCHIVE", cible.name, "ce fichier n'existe pas")], []
    elif mode == "--executable":
        constats, lignes = controler_executable(cible, noms)
    elif mode == "--exemples":
        constats, lignes = controler_exemples(cible, noms)
    elif mode == "--textes":
        constats, lignes = controler_textes(cible, noms, "--tiers" in arguments)
    else:
        constats, lignes = controler_depot(RACINE, noms)
    for ligne in lignes:
        print(ligne)
    if LISTE["tolerees"]:
        print(f"Phrases tolérées de la liste : rencontrées {TOLEREES['phrases']} fois dans ce qui a été examiné.")
    for code, lieu, detail in sorted(set(constats)):
        print(f"REFUS {code:9} {masque(lieu)} : {detail}")
    refus = len(set(constats)) + len(manques)
    print("VERDICT : " + (f"REFUS, {refus} constat(s)" if refus else "rien à redire"
                          + ("" if liste is not None else ", sur les règles génériques seules : aucune liste de chaînes interdites n'a été donnée")))
    return 1 if refus else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))

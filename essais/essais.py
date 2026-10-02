# -*- coding: utf-8 -*-
"""Les essais de PDForensics, sur des pièces fabriquées et sur elles seules.

  python -B essais/essais.py                      les exemples, la lecture, le pont, l'écran assemblé, les réglages, les gardes d'export
  python -B essais/essais.py --fenetre            ouvre la vraie fenêtre, cachée, et la pilote par son pont
  python -B essais/essais.py --executable CHEMIN  le même essai de fenêtre, fait par l'exécutable construit

Chaque essai imprime « OK » ou « ECHEC ». Un essai qui ne peut pas se faire sur ce poste imprime
« NON FAIT » et dit pourquoi : ce n'est ni un succès ni un échec, et le verdict le compte à part.

Tout se fabrique dans un dossier temporaire, supprimé à la fin. Les réglages de l'utilisateur ne sont
ni lus ni écrits : un fichier de réglages d'essai, dans ce dossier temporaire, les remplace.
"""
from __future__ import annotations

import contextlib
import ctypes
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # même lancé sans -B, rien ne s'écrit à côté des sources
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))  # le paquet est à côté du dossier des essais, où que le dépôt soit posé

import pieces_epreuve  # noqa: E402
from pdforensics import application, ecran, exports_texte, gardes_export, moteur  # noqa: E402

ECHECS: list[str] = []
NON_FAITS: list[str] = []


def essai(nom: str, vrai: bool, detail: object = "") -> None:
    print(("OK    " if vrai else "ECHEC ") + nom + (f" : {detail}" if detail != "" else ""))
    if not vrai:
        ECHECS.append(nom)


def non_fait(nom: str, pourquoi: str) -> None:
    print(f"NON FAIT {nom} : {pourquoi}")
    NON_FAITS.append(nom)


@contextlib.contextmanager
def neutralisees(*gardes: str):
    """Des gardes d'emplacement mises hors jeu LE TEMPS D'UN ESSAI : ici, le seul dossier libre est temporaire."""
    vraies = {nom: getattr(gardes_export, nom) for nom in gardes}
    for nom in gardes:
        setattr(gardes_export, nom, lambda chemin: False)
    try:
        yield
    finally:
        for nom, vraie in vraies.items():
            setattr(gardes_export, nom, vraie)


def lecture(api: application.Api, chemins: dict[str, Path], travail: Path) -> None:
    def lire(cle: str) -> dict:
        reponse = api.lire_tout(str(chemins[cle]))
        essai(f"{cle} se lit", reponse["ok"], reponse.get("raison", ""))
        return reponse["piece"]

    def compte(piece: dict, nature: str) -> int:
        return sum(1 for page in piece["pages"] for e in page["elements"] if e["nature"] == nature)

    couches = lire("couches")
    caches = [c for page in couches["pages"] for c in page["caches"]]
    essai("couches : trois versions", len(couches["versions"]) == 3 and couches["moteur"] == 3,
          (len(couches["versions"]), couches["moteur"]))
    releves = [(c["couleur"], c["version"], [d["texte"] for d in c["dessous"]], c["dessus"]) for c in caches]
    essai("couches : deux zones recouvertes, avec leur texte et leur version", releves ==
          [("blanc", 2, [pieces_epreuve.MOT_ORIGINE], [pieces_epreuve.MOT_REMPLACE]), ("noir", 3, [pieces_epreuve.FIN_COUVERTE], [])],
          releves)
    essai("couches : un calque éteint et son contenu", couches["calques"] == [{"nom": pieces_epreuve.CALQUE_ETEINT, "allume": False}]
          and len(couches["pages"][0]["calques"]) == 2)
    comptes = (compte(couches, "invisible"), compte(couches, "image"), compte(couches, "annotation"))
    essai("couches : cinq lignes de texte invisible, une image, une annotation", comptes == (5, 1, 1), comptes)
    essai("couches : la version 3 dit ce qu'elle ajoute", couches["versions"][2]["resume"] == "page 1 : 1 texte ajouté, 1 aplat noir ajouté",
          couches["versions"][2]["resume"])
    essai("couches : la page 2 n'a changé dans aucune version", all(v["zones"][1] == [] for v in couches["versions"][1:]))

    simple = lire("simple")
    essai("simple : une version, rien de recouvert, aucun calque",
          (len(simple["versions"]), sum(len(p["caches"]) for p in simple["pages"]), simple["calques"]) == (1, 0, []))
    remplacement = lire("remplacement")
    zones = remplacement["versions"][1]["zones"][0]
    essai("remplacement : une phrase remplacée, sans zone recouverte",
          remplacement["versions"][1]["resume"] == "page 1 : 1 texte ajouté, 1 texte retiré" and len(zones) == 1
          and sorted(q["sens"] for q in zones[0]["quoi"]) == ["ajout", "retrait"]
          and sum(len(p["caches"]) for p in remplacement["pages"]) == 0, remplacement["versions"][1]["resume"])
    calque = lire("calque")
    essai("calque : un calque, affiché", calque["calques"] == [{"nom": pieces_epreuve.CALQUE_AFFICHE, "allume": True}])
    image = lire("image")
    comptes = (compte(image, "image"), compte(image, "texte"), compte(image, "invisible"))
    essai("image : une image seule, aucun texte", comptes == (1, 0, 0), comptes)

    dessin = api.image(str(chemins["couches"]), 3, 1, False, 1.6)
    essai("une page se dessine", dessin["ok"] and dessin["src"].startswith("data:image/png;base64,"))
    essai("une page hors bornes est refusée", not api.image(str(chemins["couches"]), 3, 9, False, 1.6)["ok"])
    faux = travail / "faux" / "pas un pdf.pdf"
    faux.parent.mkdir()
    faux.write_text("ceci n'est pas un PDF", encoding="utf-8")
    refus = api.lire(str(faux))
    essai("un faux PDF est refusé sans chemin dans le message", not refus["ok"] and str(faux.parent) not in refus["raison"]
          and faux.name not in refus["raison"], refus.get("raison"))
    essai("un fichier absent est refusé", not api.lire(str(faux.parent / "absent.pdf"))["ok"])
    entete = api.lire(str(chemins["couches"]))["piece"]
    essai("l'en-tête d'une pièce donne la taille de ses pages, pas encore leur contenu",
          [sorted(p) for p in entete["pages"]] == [["h", "l", "n"], ["h", "l", "n"]] and len(entete["versions"]) == 3)
    tranche = api.pages(str(chemins["couches"]), 1)
    essai("les pages se lisent par tranches, et la dernière le dit", tranche["ok"] and [p["n"] for p in tranche["pages"]] == [2]
          and tranche["suite"] is None and "elements" in tranche["pages"][0])


def outils_de_mesure(chemins: dict[str, Path], racine: Path) -> None:
    """Les trois outils faits pour de vraies pièces, essayés ici sur les pièces fabriquées : ils ne rendent que des nombres."""
    secrets = [racine.parent.name, *pieces_epreuve.DOSSIERS, *(chemin.stem for chemin in chemins.values()),
               pieces_epreuve.MOT_ORIGINE, pieces_epreuve.FIN_COUVERTE, pieces_epreuve.NOTE, "(essai)"]
    for outil, attendu in (("essai_pieces_reelles.py", "BILAN : 5 pièces, 5 lues, 0 refus, 0 pannes."),
                           ("essai_annotations.py", "BILAN : 5 pièces, 1 annotations décrites."), ("essai_reperes.py", "\nFIN.")):
        retour = subprocess.run([sys.executable, "-B", str(RACINE / "essais" / outil), "--dossier", str(racine)], capture_output=True,  # noqa: S603
                                check=False, stdin=subprocess.DEVNULL, timeout=300, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        sortie = retour.stdout.decode("utf-8", "replace")
        essai(f"{outil} lit les cinq pièces fabriquées et rend son bilan", retour.returncode == 0 and attendu in sortie,
              sortie.strip().splitlines()[-1:] or retour.returncode)
        fuites = [secret for secret in secrets if secret.casefold() in sortie.casefold()]
        essai(f"{outil} ne rend ni nom de fichier, ni dossier, ni texte d'une pièce", not fuites and retour.stderr == b"", len(fuites))


def explorateur(api: application.Api, racine: Path) -> None:
    depart, foyer = api.depart(), str(Path.home())
    essai("le départ s'ouvre sur le dossier personnel, pour les pièces comme pour l'export",
          (depart["dossier"], depart["export"]) == (foyer, foyer))
    essai("aucun raccourci ne mène à des pièces fabriquées",
          all(r["nom"] in ("Bureau", "Documents", "Téléchargements") or r["chemin"].rstrip("\\") == r["nom"] for r in depart["raccourcis"]),
          [r["nom"] for r in depart["raccourcis"]])
    application.DEPART = racine
    try:
        depart = api.depart()
    finally:
        application.DEPART = None
    essai("lancé sur un dossier, l'outil s'y ouvre", (depart["dossier"], depart["export"]) == (str(racine), str(racine)))
    liste = api.lister(str(racine))
    essai("la racine montre trois dossiers et aucun PDF", ([d["nom"] for d in liste["dossiers"]], liste["pdfs"])
          == (pieces_epreuve.DOSSIERS, []), [d["nom"] for d in liste["dossiers"]])
    textes = api.lister(str(racine / "Essais - texte"))
    essai("un dossier montre ses PDF et son parent", len(textes["pdfs"]) == 3 and textes["parent"] == str(racine))
    essai("un dossier absent le dit", api.lister(str(racine / "nulle part"))["refus"] == "Ce dossier n'existe pas.")
    essai("un chemin de fichier ouvre son dossier", api.lister(textes["pdfs"][0]["chemin"])["chemin"] == textes["chemin"])


def ecran_assemble(travail: Path) -> None:
    html = ecran.assembler()
    bandeau = html.partition('<div class="bandeau">')[2].partition("</div>")[0]
    essai("le bandeau dit PDForensics, et que rien ne sort du poste", bandeau.startswith("<strong>PDForensics</strong>")
          and "lu sur ce poste et n'en sort pas" in bandeau and "prototype" not in bandeau.casefold(), bandeau)
    essai("la fenêtre s'appelle PDForensics", "<title>PDForensics</title>" in html and application.NOM == "PDForensics")
    dehors = [mot for mot in ("http://", "https://", "<link", 'src="', "@import", "url(") if mot in html]
    essai("l'écran ne charge rien de l'extérieur", not dehors, dehors)
    deploye = travail / "deploye"
    shutil.copytree(ecran.dossier_des_fragments(), deploye / "pdforensics" / "ecran")
    sys._MEIPASS = str(deploye)  # ce que pose un exécutable construit, quand il déploie ses fichiers
    try:
        essai("empaqueté, l'écran prend ses fragments là où l'exécutable les déploie",
              ecran.dossier_des_fragments() == deploye / "pdforensics" / "ecran" and ecran.assembler() == html)
    finally:
        del sys._MEIPASS


def exemples(fabriquees: Path) -> None:
    """Les exemples du dépôt sont les pièces que ces essais fabriquent et lisent : ce qui est vérifié des unes vaut pour les autres."""
    def arbre(racine: Path) -> dict[str, bytes]:
        return {fichier.relative_to(racine).as_posix(): fichier.read_bytes() for fichier in sorted(racine.rglob("*")) if fichier.is_file()}

    deposes, fabriques = arbre(RACINE / "exemples"), arbre(fabriquees)
    essai("le dossier des exemples porte les cinq pièces fabriquées, et rien d'autre", len(deposes) == 5 and sorted(deposes) == sorted(fabriques),
          len(deposes))
    differents = sum(1 for nom, octets in fabriques.items() if deposes.get(nom) != octets)
    essai("chaque exemple est, à l'octet près, la pièce que ces essais fabriquent et lisent", not differents, f"{differents} différent(s)")


def reglages(api: application.Api, vrais: Path) -> None:
    locales = application.dossier_des_donnees_locales()
    if os.name == "nt":
        essai("les réglages vivent sous le dossier de données locales que Windows désigne",
              vrais == locales / "PDForensics" / "reglages.json" and application.fichier_reglages() == vrais
              and locales.is_dir() and locales.name == "Local", locales.name)
    else:
        non_fait("les réglages vivent sous le dossier de données locales que Windows désigne", "ce poste n'est pas sous Windows")
    ailleurs = [RACINE, Path(application.__file__).resolve().parent, Path(sys.executable).resolve().parent]
    essai("les réglages ne vivent ni dans le dépôt, ni à côté de l'outil", not any(gardes_export.est_sous(vrais, lieu) for lieu in ailleurs))
    essai("sans réglages, aucun dossier n'est protégé : la liste ne vient que de l'utilisateur",
          api.reglages() == {"proteges": [], "export": ""}, api.reglages())


def nom_court(chemin: Path) -> str:
    """Le nom court que Windows donne à un chemin, quand le disque en tient ; vide sinon."""
    try:
        tampon = ctypes.create_unicode_buffer(1024)
        longueur = ctypes.windll.kernel32.GetShortPathNameW(str(chemin), tampon, 1024)
    except (AttributeError, OSError):
        return ""
    return tampon.value if 0 < longueur < 1024 else ""


def gardes(travail: Path) -> None:
    depot, libre, protege = travail / "faux depot", travail / "libre", travail / "protege"
    for dossier in (depot / ".git", depot / "docs", libre / "sous-dossier", protege / "dedans"):
        dossier.mkdir(parents=True)
    hors_depot = not gardes_export.dans_un_depot(travail)
    essai("un dossier d'un dépôt est reconnu", gardes_export.dans_un_depot(depot / "docs") and gardes_export.dans_un_depot(depot))
    if hors_depot:
        essai("un dossier hors de tout dépôt n'est pas pris pour un dépôt", not gardes_export.dans_un_depot(libre))
    else:
        non_fait("un dossier hors de tout dépôt n'est pas pris pour un dépôt", "le dossier temporaire de ce poste est lui-même dans un dépôt")
    essai("un dossier temporaire est reconnu", gardes_export.temporaire(tempfile.gettempdir()) and gardes_export.temporaire(libre))
    essai("les racines synchronisées se lisent sans erreur", isinstance(gardes_export.racines_synchronisees(), list),
          f"{len(gardes_export.racines_synchronisees())} racine(s)")
    piece = protege / "dedans" / "piece.pdf"
    essai("refus : dossier absent", gardes_export.refus_destination(travail / "absent", [], []) == "Ce dossier n'existe pas.")
    essai("refus : dossier temporaire", "temporaire" in gardes_export.refus_destination(libre, [], []))
    essai("refus : destination dans un dossier protégé", "protégé" in gardes_export.refus_destination(protege / "dedans", [], [str(protege)]))
    essai("refus : pièce d'un dossier protégé", gardes_export.refus_piece(piece, [str(protege)]) != "" and gardes_export.refus_piece(piece, []) == "")
    with neutralisees("temporaire", "synchronise"):
        essai("refus : dans un dépôt", "dépôt Git" in gardes_export.refus_destination(depot / "docs", [], []))
        if hors_depot:
            essai("refus : dans le dossier d'une pièce sélectionnée",
                  "à côté des pièces" in gardes_export.refus_destination(libre / "sous-dossier", [str(libre / "piece.pdf")], []))
            essai("accord : un dossier libre", gardes_export.refus_destination(libre, [], []) == "")
        else:
            non_fait("refus : dans le dossier d'une pièce sélectionnée, et accord dans un dossier libre", "voir plus haut")
    vraies_racines = gardes_export.racines_synchronisees
    gardes_export.racines_synchronisees = lambda: [gardes_export.norme(libre)]
    try:
        essai("un dossier sous une racine synchronisée est reconnu", gardes_export.synchronise(libre / "sous-dossier"))
        with neutralisees("temporaire"):
            essai("refus : dossier synchronisé", "synchronisé" in gardes_export.refus_destination(libre / "sous-dossier", [], []))
    finally:
        gardes_export.racines_synchronisees = vraies_racines
    essai("la garde de l'espace de travail a disparu : un refus ne dépend plus de l'endroit où l'outil est posé",
          not hasattr(gardes_export, "espace_de_travail") and list(inspect.signature(gardes_export.refus_destination).parameters)
          == ["destination", "pieces", "proteges"])
    # Un même dossier porte deux noms sous Windows quand le disque tient des noms courts : la garde doit reconnaître les deux.
    long = protege / "un dossier au nom long"
    long.mkdir()
    court = nom_court(long)
    if court and Path(court).name != long.name:
        essai("un dossier protégé est reconnu sous son nom court comme sous son nom long",
              gardes_export.protege(court, [str(long)]) and gardes_export.protege(long, [court])
              and "protégé" in gardes_export.refus_destination(court, [], [str(long)]))
    else:
        non_fait("un dossier protégé est reconnu sous son nom court comme sous son nom long", "ce disque ne tient pas de noms courts")


def export(api: application.Api, chemins: dict[str, Path], travail: Path) -> None:
    """L'écriture, gardes d'emplacement neutralisées POUR L'ESSAI : le seul dossier libre ici est temporaire."""
    sorties, protege = travail / "sorties", travail / "protege a l'export"
    sorties.mkdir()
    protege.mkdir()
    essai("le fichier de réglages n'existe pas tant que rien n'est réglé", not application.REGLAGES.exists())
    api._regler(proteges=[str(protege)])
    essai("les réglages s'écrivent dans leur dossier, créé au besoin", application.REGLAGES.is_file() and application.REGLAGES.parent != travail)
    fiches = [{"nom": "Pièce / d'essai : une", "identite": [["Format", "PDF 1.7"]],
               "rubriques": [{"titre": "Versions enregistrées", "compte": 1, "lignes": ["Version 1."]}]},
              {"nom": "Pièce / d'essai : une", "identite": [], "rubriques": []}]
    tableau = {"colonnes": ["Pièce", "Pages"], "lignes": [["Pièce ; \"une\"", 2], ["deux", 1]]}
    essai("le dossier temporaire est refusé par la vraie garde", not api.exporter("fiches", str(sorties), fiches, tableau, [])["ok"])
    essai("un dossier ne se crée pas là où l'export est refusé", not api.creer_dossier(str(sorties), "neuf", [])["ok"] and not (sorties / "neuf").exists())
    with neutralisees("temporaire", "synchronise"):
        cree = api.creer_dossier(str(sorties), "  Fiches des fichiers  ", [])
        essai("le bouton crée le dossier demandé", cree["ok"] and Path(cree["chemin"]).is_dir() and Path(cree["chemin"]).name == "Fiches des fichiers",
              cree.get("raison", ""))
        if not cree["ok"]:
            return
        essai("un dossier du même nom n'est pas recréé", "existe déjà" in api.creer_dossier(str(sorties), "Fiches des fichiers", []).get("raison", ""))
        essai("un nom de dossier impossible est refusé", not api.creer_dossier(str(sorties), "a/b", [])["ok"] and not api.creer_dossier(str(sorties), "  ", [])["ok"])
        essai("un dossier ne se crée pas dans un dossier protégé", "protégé" in api.creer_dossier(str(protege), "neuf", []).get("raison", ""))
        dossier = Path(cree["chemin"])
        rendu = api.exporter("fiches", str(dossier), fiches, tableau, [str(chemins["couches"])])
        ecrits = sorted(p.name for p in dossier.iterdir())
        essai("les fiches et le tableau s'écrivent dans le dossier affiché", rendu["ok"] and rendu["dossier"] == str(dossier) and ecrits ==
              ["fiche - Pièce - d'essai - une (2).md", "fiche - Pièce - d'essai - une.md", "tableau des fiches.csv"], ecrits or rendu.get("raison"))
        csv = (dossier / "tableau des fiches.csv").read_bytes()
        essai("le tableau s'ouvre dans un tableur français", csv.startswith(b"\xef\xbb\xbf") and b'"Pi\xc3\xa8ce ; ""une""";"2"\r\n' in csv)
        essai("la fiche porte son identité et ses rubriques",
              "## Versions enregistrées (1)" in (dossier / "fiche - Pièce - d'essai - une.md").read_text(encoding="utf-8"))
        avant = {p.name: p.read_bytes() for p in dossier.iterdir()}
        encore = api.exporter("fiches", str(dossier), fiches, tableau, [])
        essai("un second export n'écrase rien", encore["ok"] and all((dossier / nom).read_bytes() == octets for nom, octets in avant.items())
              and len(list(dossier.iterdir())) == 6, sorted(p.name for p in dossier.iterdir()))
        essai("une pièce d'un dossier protégé arrête tout l'export",
              not api.exporter("fiches", str(dossier), fiches, tableau, [str(protege / "piece.pdf")])["ok"])
        essai("une destination dans le dossier d'une pièce est refusée", "à côté des pièces" in
              api.exporter("fiches", str(chemins["couches"].parent), fiches, tableau, [str(chemins["couches"])]).get("raison", ""))
        for genre, nom in (("odt", "Fiches des fichiers.odt"), ("ods", "Tableau des fiches.ods")):
            rendu = api.exporter(genre, str(dossier), fiches, tableau, [])
            essai(f"l'export {genre} écrit son fichier", rendu["ok"] and rendu["fichiers"] == [nom] and (dossier / nom).stat().st_size > 800,
                  rendu.get("raison", ""))
            rendu = api.exporter(genre, str(dossier), fiches, tableau, [])
            essai(f"un second export {genre} prend un autre nom", rendu["ok"] and rendu["fichiers"] == [nom.replace(".", " (2).")],
                  rendu.get("fichiers", rendu.get("raison")))
        presents = sorted(p.name for p in dossier.iterdir())
        vraie_fiche = exports_texte.fiche_md
        exports_texte.fiche_md = lambda fiche, sous_titre: (_ for _ in ()).throw(RuntimeError("panne d'essai"))
        try:
            rate = api.exporter("fiches", str(dossier), fiches, tableau, [])
        finally:
            exports_texte.fiche_md = vraie_fiche
        essai("un export raté retire ce qu'il a posé, et rien d'autre", not rate["ok"] and sorted(p.name for p in dossier.iterdir()) == presents,
              rate.get("raison", ""))
        essai("les réglages gardent les dossiers protégés et le dernier dossier d'export, rien d'autre",
              api.reglages() == {"proteges": [str(protege)], "export": str(dossier)}
              and sorted(json.loads(application.REGLAGES.read_text(encoding="utf-8"))) == ["export", "proteges"])


def fenetre(commande: list[str], chemins: dict[str, Path], travail: Path) -> None:
    """La vraie fenêtre, cachée, lancée comme le ferait l'utilisateur : le pont répond-il, et aucun port n'est-il ouvert ?"""
    if not moteur.version():
        non_fait("la fenêtre cachée et son pont", "aucun moteur d'affichage (Microsoft Edge WebView2) sur ce poste")
        return
    rapport = travail / "rapport" / "rapport.json"
    rapport.parent.mkdir()
    appel = [*commande, "--essai-pont", str(chemins["couches"].parent), str(rapport)]
    try:
        retour = subprocess.run(appel, cwd=str(RACINE), timeout=300, check=False, stdin=subprocess.DEVNULL,  # noqa: S603
                                capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}).returncode
    except subprocess.TimeoutExpired:
        essai("l'auto-essai rend la main", False, "aucune réponse en cinq minutes")
        return
    except OSError as erreur:
        essai("l'auto-essai se lance", False, type(erreur).__name__)
        return
    try:
        lu = json.loads(rapport.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lu = {}
    essai("la fenêtre démarre et son pont répond", retour == 0 and lu.get("pret") is True and lu.get("moteur") == "edgechromium",
          {"code": retour, **{cle: lu.get(cle) for cle in ("moteur", "pret", "erreur")}})
    essai("le bandeau dit PDForensics, et que rien ne sort du poste",
          str(lu.get("bandeau", "")).startswith("PDForensics") and "n'en sort pas" in str(lu.get("bandeau", "")), lu.get("bandeau"))
    essai("l'explorateur s'ouvre sur le dossier demandé et liste sa pièce", (lu.get("dossiers"), lu.get("pieces")) == (1, 1),
          (lu.get("dossiers"), lu.get("pieces")))
    essai("un clic ouvre et lit la pièce", lu.get("piece") is True and lu.get("titre") == chemins["couches"].stem, lu.get("titre"))
    essai("les regards portent les comptes de la pièce", lu.get("comptes") == "2/1/3", lu.get("comptes"))
    essai("le dossier d'essai, temporaire, est refusé à l'export par la vraie garde", "temporaire" in str(lu.get("verdict", "")), lu.get("verdict"))
    essai("aucun port n'est ouvert par ce processus", lu.get("ports") == 0 and lu.get("connexions_lues", 0) > 0,
          f"{lu.get('ports')} sur {lu.get('connexions_lues')} connexions du poste")
    essai("l'auto-essai n'écrit que son rapport", sorted(p.name for p in rapport.parent.iterdir()) == ["rapport.json"])


def principal() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    travail = Path(os.path.abspath(tempfile.mkdtemp(prefix="pdforensics-essais-")))
    vrais_reglages, application.REGLAGES = application.REGLAGES, travail / "reglages" / "essai" / "reglages.json"
    try:
        chemins = pieces_epreuve.fabriquer_tout(travail / "pieces")
        if "--fenetre" in sys.argv:
            fenetre([sys.executable, "-B", "-m", "pdforensics"], chemins, travail)
        elif "--executable" in sys.argv:
            executable = Path(os.path.abspath(sys.argv[sys.argv.index("--executable") + 1]))
            essai("l'exécutable à essayer existe", executable.is_file())
            if executable.is_file():
                fenetre([str(executable)], chemins, travail)
        else:
            pont = application.Api()
            exemples(travail / "pieces")
            lecture(pont, chemins, travail)
            outils_de_mesure(chemins, travail / "pieces")
            explorateur(pont, travail / "pieces")
            ecran_assemble(travail)
            reglages(pont, vrais_reglages)
            gardes(travail)
            export(pont, chemins, travail)
    finally:
        application.REGLAGES = vrais_reglages
        shutil.rmtree(travail, ignore_errors=True)
    suite = f" ({len(NON_FAITS)} non fait(s))" if NON_FAITS else ""
    print("VERDICT :", f"tout passe{suite}" if not ECHECS else f"{len(ECHECS)} échec(s){suite} : " + " ; ".join(ECHECS))
    return 1 if ECHECS else 0


if __name__ == "__main__":
    sys.exit(principal())

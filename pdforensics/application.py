# -*- coding: utf-8 -*-
"""PDForensics: la fenetre, et le pont entre l'ecran et la lecture.

- Aucun serveur, aucun port: l'ecran parle a Python par le pont de pywebview.
- Aucun reseau: l'ecran ne charge ni script ni police de l'exterieur.
- Aucune trace de ce qui est ouvert: fenetre en mode prive, pieces lues en
  place et tenues en memoire, pas de fichiers recents, pas de journal, rien
  d'affiche en console. Le SEUL fichier ecrit hors d'un export est
  `reglages.json`: les dossiers proteges et le dernier dossier d'export. Il vit
  dans le dossier de donnees locales de l'utilisateur, jamais a cote de l'outil.
- L'export ne s'ecrit que la ou `gardes_export` l'accepte, et n'ecrase rien.

Lancer: python -B -m pdforensics
"""
from __future__ import annotations

import datetime
import json
import os
import threading
from collections import OrderedDict
from pathlib import Path

from . import exports_odf, exports_texte, gardes_export, lecture_pdf

NOM = "PDForensics"


def dossier_des_donnees_locales() -> Path:
    """Le dossier ou Windows range les donnees locales de la session: demande a Windows, sans rien supposer du poste."""
    try:
        import ctypes

        tampon = ctypes.create_unicode_buffer(1024)
        # 28 est le numero que Windows donne a ce dossier; il rend zero quand il l'a trouve.
        if ctypes.windll.shell32.SHGetFolderPathW(None, 28, None, 0, tampon) == 0 and tampon.value:
            return Path(tampon.value)
    except (AttributeError, ImportError, OSError):
        pass
    return Path.home() / ".local" / "share"  # hors de Windows: l'endroit d'usage


def fichier_reglages() -> Path:
    """Ou vit le fichier de reglages: dans le dossier de donnees locales de l'utilisateur, et la seulement."""
    return dossier_des_donnees_locales() / NOM / "reglages.json"


REGLAGES = fichier_reglages()
DEPART: Path | None = None  # le dossier ou les explorateurs s'ouvrent, quand l'outil est lance sur un dossier
SYSTEME = 0x4
LISTE_MAX = 4000
GENRES = {"fiches": "des fiches et un tableau", "odt": "un document LibreOffice", "ods": "un tableau LibreOffice"}


class Api:
    """Ce que l'ecran peut demander. Les noms commencant par un tiret bas ne lui sont pas offerts."""

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._lectures: OrderedDict[tuple, lecture_pdf.Lecture] = OrderedDict()
        self._fenetre = None
        self._dernier_export: Path | None = None

    # ------------------------------------------------------- explorateur

    def depart(self) -> dict:
        foyer = Path.home()
        raccourcis = []
        for nom, dossier in (("Bureau", "Desktop"), ("Documents", "Documents"), ("Téléchargements", "Downloads")):
            if (foyer / dossier).is_dir():
                raccourcis.append({"nom": nom, "chemin": str(foyer / dossier)})
        for lecteur in os.listdrives():
            raccourcis.append({"nom": lecteur.rstrip("\\"), "chemin": lecteur})
        reglages = self.reglages()
        depart = str(DEPART or foyer)
        export = reglages["export"] if reglages["export"] and Path(reglages["export"]).is_dir() else depart
        return {"raccourcis": raccourcis, "dossier": depart,
                "export": export, "reglages": reglages, "dialogues": self._fenetre is not None}

    def lister(self, chemin: str) -> dict:
        dossier = Path(os.path.abspath(os.path.expandvars(str(chemin).strip().strip('"'))))
        if dossier.is_file():
            dossier = dossier.parent
        rendu = {"chemin": str(dossier), "nom": dossier.name or str(dossier),
                 "parent": str(dossier.parent) if dossier.parent != dossier else "",
                 "dossiers": [], "pdfs": [], "refus": "", "tronque": 0}
        try:
            with os.scandir(dossier) as entrees:
                for entree in entrees:
                    try:
                        etat = entree.stat(follow_symlinks=False)
                        if getattr(etat, "st_file_attributes", 0) & SYSTEME:
                            continue
                        if entree.is_dir():
                            rendu["dossiers"].append({"nom": entree.name, "chemin": entree.path})
                        elif entree.name.lower().endswith(".pdf"):
                            rendu["pdfs"].append({"nom": entree.name, "chemin": entree.path,
                                                  "taille": lecture_pdf.taille_lisible(etat.st_size)})
                    except OSError:
                        continue
        except PermissionError:
            rendu["refus"] = "L'accès à ce dossier est refusé."
        except (FileNotFoundError, NotADirectoryError):
            rendu["refus"] = "Ce dossier n'existe pas."
        except OSError:
            rendu["refus"] = "Ce dossier ne s'ouvre pas."
        for liste in (rendu["dossiers"], rendu["pdfs"]):
            liste.sort(key=lambda e: e["nom"].casefold())
        total = len(rendu["dossiers"]) + len(rendu["pdfs"])
        if total > LISTE_MAX:
            rendu["tronque"] = total - LISTE_MAX
            rendu["dossiers"] = rendu["dossiers"][:LISTE_MAX]
            rendu["pdfs"] = rendu["pdfs"][:max(0, LISTE_MAX - len(rendu["dossiers"]))]
        return rendu

    def _dialogue(self) -> str:
        import webview

        genre = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        choix = self._fenetre.create_file_dialog(genre) if self._fenetre else None
        return str(choix[0]) if choix else ""

    def choisir_dossier(self) -> str:
        return self._dialogue()

    # ----------------------------------------------------------- lecture

    def _lecture(self, chemin: str) -> lecture_pdf.Lecture:
        fichier = Path(chemin)
        try:
            etat = fichier.stat()
        except OSError:
            raise lecture_pdf.PieceIllisible("Ce fichier ne s'ouvre pas : il est absent, ou son accès est refusé.") from None
        cle = (str(fichier), etat.st_mtime_ns, etat.st_size)
        if cle not in self._lectures:
            self._lectures[cle] = lecture_pdf.Lecture(fichier)
            while len(self._lectures) > 2:           # une piece tient ses octets et plusieurs exemplaires en memoire
                self._lectures.popitem(last=False)
        self._lectures.move_to_end(cle)
        return self._lectures[cle]

    def lire(self, chemin: str) -> dict:
        """L'en-tete de la piece: tout ce qui se dit avant de lire ses pages, et la taille de chacune."""
        with self._verrou:
            try:
                piece = self._lecture(chemin).entete()
            except lecture_pdf.PieceIllisible as refus:
                return {"ok": False, "raison": str(refus)}
            except Exception as erreur:  # noqa: BLE001 - une avarie de lecture ne doit pas fermer la fenetre
                return {"ok": False, "raison": "La lecture de ce fichier a échoué (" + type(erreur).__name__ + ")."}
        piece.update({"chemin": str(chemin), "nom": Path(chemin).stem, "dossier": Path(chemin).parent.name})
        return {"ok": True, "piece": piece}

    def pages(self, chemin: str, de: int) -> dict:
        """Le contenu des pages a partir de `de` (0 pour la premiere): une tranche, et ou reprendre."""
        with self._verrou:
            try:
                lues, suite = self._lecture(chemin).suite(int(de))
            except lecture_pdf.PieceIllisible as refus:
                return {"ok": False, "raison": str(refus)}
            except Exception as erreur:  # noqa: BLE001
                return {"ok": False, "raison": "La lecture des pages a échoué (" + type(erreur).__name__ + ")."}
        return {"ok": True, "pages": lues, "suite": suite}

    def lire_tout(self, chemin: str) -> dict:
        """La piece entiere d'un seul appel: pour les essais et les outils, pas pour l'ecran."""
        rendu = self.lire(chemin)
        de = 0
        while rendu["ok"] and de is not None:
            tranche = self.pages(chemin, de)
            if not tranche["ok"]:
                return tranche
            for page in tranche["pages"]:
                rendu["piece"]["pages"][page["n"] - 1] = page
            de = tranche["suite"]
        return rendu

    def image(self, chemin: str, version: int, page: int, calques: bool, echelle: float, sans: str = "") -> dict:
        """L'image d'une page; `sans` nomme ce qu'on en retire pour voir dessous (a: annotations, i: images, t: traces)."""
        with self._verrou:
            try:
                return {"ok": True, "src": self._lecture(chemin).image(int(version), int(page), bool(calques), float(echelle),
                                                                         str(sans or ""))}
            except lecture_pdf.PieceIllisible as refus:
                return {"ok": False, "raison": str(refus)}
            except Exception as erreur:  # noqa: BLE001
                return {"ok": False, "raison": "Cette page ne se dessine pas (" + type(erreur).__name__ + ")."}

    # ----------------------------------------------------------- reglages

    def reglages(self) -> dict:
        """Les dossiers proteges et le dernier dossier d'export: le seul fichier que l'outil garde."""
        try:
            lus = json.loads(REGLAGES.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            lus = {}
        proteges = [str(p) for p in lus.get("proteges") or [] if isinstance(p, str) and p.strip()]
        return {"proteges": proteges, "export": str(lus.get("export") or "")}

    def _regler(self, **valeurs) -> dict:
        reglages = self.reglages()
        reglages.update(valeurs)
        try:
            REGLAGES.parent.mkdir(parents=True, exist_ok=True)
            REGLAGES.write_text(json.dumps(reglages, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass  # des reglages qui ne s'ecrivent pas ne font pas echouer ce qui vient de reussir
        return reglages

    def examiner(self, destination: str, pieces: list) -> dict:
        """Ce qui s'exporte, ce qui ne s'exporte pas, et pourquoi."""
        proteges = self.reglages()["proteges"]
        return {
            "pieces": {str(p): gardes_export.refus_piece(p, proteges) for p in pieces},
            "destination": gardes_export.refus_destination(destination, pieces, proteges),
        }

    def creer_dossier(self, parent: str, nom: str, pieces: list) -> dict:
        """Un dossier neuf dans le dossier affiche, la ou un export a le droit de s'ecrire."""
        refus = gardes_export.refus_destination(parent, pieces, self.reglages()["proteges"])
        if refus:
            return {"ok": False, "raison": refus}
        propre = exports_texte.nom_de_dossier(nom)
        if not propre:
            return {"ok": False, "raison": "Ce nom de dossier n'est pas accepté."}
        try:
            (Path(parent) / propre).mkdir(exist_ok=False)
        except FileExistsError:
            return {"ok": False, "raison": "Un dossier de ce nom existe déjà ici."}
        except OSError:
            return {"ok": False, "raison": "Le dossier ne se crée pas à cet endroit."}
        return {"ok": True, "chemin": str(Path(parent) / propre)}

    # ------------------------------------------------------------- export

    def exporter(self, genre: str, destination: str, fiches: list, tableau: dict, pieces: list) -> dict:
        """Ecrit l'export DANS le dossier affiche, sans rien ecraser. Un export rate retire ce qu'il a pose."""
        proteges = self.reglages()["proteges"]
        if genre not in GENRES:
            return {"ok": False, "raison": "Cette forme d'export n'existe pas."}
        if not fiches:
            return {"ok": False, "raison": "Aucune pièce à exporter."}
        if any(gardes_export.refus_piece(p, proteges) for p in pieces):
            return {"ok": False, "raison": "Une pièce d'un dossier protégé est dans la demande : rien n'a été écrit."}
        refus = gardes_export.refus_destination(destination, pieces, proteges)
        if refus:
            return {"ok": False, "raison": refus}
        maintenant = datetime.datetime.now()
        jour = f"{'1er' if maintenant.day == 1 else maintenant.day} {lecture_pdf.MOIS[maintenant.month - 1]} {maintenant.year}"
        sous_titre = f"Relevé du {jour} : {lecture_pdf.pluriel(len(fiches), 'pièce')}."
        dossier, ecrits = Path(destination), []
        try:
            if genre == "fiches":
                exports_texte.ecrire_fiches(dossier, sous_titre, fiches, tableau, ecrits)
            else:
                document = genre == "odt"
                nom = exports_texte.nom_de_fichier("Fiches des fichiers" if document else "Tableau des fiches",
                                                   ".odt" if document else ".ods", exports_texte.noms_pris(dossier))
                ecrits.append(dossier / nom)
                ecrire = exports_odf.ecrire_odt if document else exports_odf.ecrire_ods
                ecrire(dossier / nom, Path(nom).stem, sous_titre, fiches, tableau)
        except Exception as erreur:  # noqa: BLE001 - un export rate ne laisse rien derriere lui
            for chemin in ecrits:  # seulement ce que CET export vient de poser
                chemin.unlink(missing_ok=True)
            return {"ok": False, "raison": "L'écriture de l'export a échoué (" + type(erreur).__name__ + ") : rien n'a été laissé."}
        self._dernier_export = dossier
        self._regler(export=str(destination))
        return {"ok": True, "dossier": str(dossier), "ecrits": len(ecrits), "quoi": GENRES[genre],
                "fichiers": [chemin.name for chemin in ecrits]}

    def montrer_export(self) -> bool:
        if self._dernier_export and self._dernier_export.is_dir():
            os.startfile(self._dernier_export)  # noqa: S606 - ouvre le dossier ou l'outil vient d'ecrire
            return True
        return False


def ouvrir_fenetre(api: Api, apres=None, cachee: bool = False) -> None:
    import webview

    from . import ecran

    api._fenetre = webview.create_window(NOM, html=ecran.assembler(), js_api=api, width=1480,
                                         height=920, min_size=(900, 600), text_select=True, hidden=cachee)
    if apres:
        webview.start(apres, (api._fenetre, api), private_mode=True, http_server=False, debug=False)
    else:
        webview.start(private_mode=True, http_server=False, debug=False)


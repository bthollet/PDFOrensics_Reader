# -*- coding: utf-8 -*-
"""Les preuves du contrôle de publication : il plante lui-même ce qu'il doit refuser, et vérifie qu'il le retrouve.

Un contrôle qui ne trouve rien sans avoir fait ses preuves ne vaut rien. Avant de conclure, il fabrique
donc, dans un dossier temporaire supprimé ensuite :

- des fichiers, chacun pour une règle, et des fichiers propres qui doivent le rester ;
- une liste de chaînes interdites, pour prouver qu'elle se lit, avec ses rubriques et ses refus ;
- des commits, d'abord décrits, puis réels dans un dépôt jetable où une chaîne enregistrée puis retirée
  doit rester refusée ;
- des PDF, où la chaîne plantée ne se voit pas dans les octets : dans l'auteur, dans une VERSION
  ANTÉRIEURE et plus dans la dernière, dans un calque éteint, en texte invisible, dans une annotation,
  dans un fichier joint, dans le second jeu de métadonnées ; et un PDF propre, accepté dans le dossier
  des exemples, refusé ailleurs.

Puis chaque chaîne de la vraie liste est plantée en mémoire, en capitales, sous trois codages : une chaîne
que le contrôle ne saurait pas retrouver est un manque, pas un silence.

Chaque fonction rend ce qui a MANQUÉ : une liste vide dit que tout ce qui devait être refusé l'a été.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import controle_pdf
from controle_depot import commit_examine, controler_depot, examiner, git
from controle_regles import (COMPTES, EN_TETE_PDF, EN_TETES_IMAGE, TEMOIN, TOLEREES, adresse_du_depot, chaines, effacer, interdites,
                             lire_la_liste, liste_d_essai)

PDF_PLANTES = {"nombre": 0, "aveugles": 0}  # combien de PDF plantés, et dans combien la chaîne ne se voyait pas dans les octets


def codes(constats: list) -> set[str]:
    return {code for code, _lieu, _detail in constats}


def temoins() -> tuple[list[str], str]:
    """Rend ce qui a manqué, et la phrase qui dit ce qui a été planté."""
    barre = chr(92)
    personnel = "C:" + barre + "Users" + barre + "quelquun" + barre + "Documents"
    adresse = "quelquun" + "@" + "exemple.invalid"  # un domaine réservé : cette adresse ne peut être celle de personne
    noms = {"nomdepostefictif": "nom de machine"}
    plantes = {
        "temoin_chaine.txt": (("Une ligne ordinaire, puis " + TEMOIN.upper() + " en capitales.").encode("utf-8"), {"CHAINE"}),
        "temoin_utf16.txt": (("avant " + TEMOIN + " après").encode("utf-16-le"), {"CHAINE", "BINAIRE"}),
        "temoin_utf16_grand_boutiste.txt": (("avant " + TEMOIN + " après").encode("utf-16-be"), {"CHAINE", "BINAIRE"}),
        "temoin_" + TEMOIN + "_dans_le_nom.txt": (b"rien dans le contenu", {"CHAINE"}),
        "temoin_en_tete.dat": (EN_TETE_PDF + b"1.7\nun faux PDF", {"PDF"}),
        "temoin.pdf": (b"un fichier qui porte le nom d'un PDF", {"PDF"}),
        "temoin_chemin.txt": (("ouvert depuis " + personnel).encode("utf-8"), {"CHEMIN"}),
        "temoin_courriel.txt": (("écrire à " + adresse).encode("utf-8"), {"COURRIEL"}),
        "temoin_poste.txt": (b"construit sur NomDePosteFictif", {"POSTE"}),
        "temoin_binaire.bin": (bytes(range(256)), {"BINAIRE"}),
        "temoin_capture.png": (EN_TETES_IMAGE[0] + bytes(24), {"IMAGE"}),
        "reglages.json": (json.dumps({"proteges": [personnel], "export": personnel}).encode("utf-8"), {"REGLAGES", "CHEMIN"}),
        "autre_nom.json": (json.dumps({"proteges": [], "export": ""}).encode("utf-8"), {"REGLAGES"}),
        "temoin_invisible.txt": (("un signe" + chr(0x200B) + "invisible").encode("utf-8"), {"INVISIBLE"}),
        ".outil/consignes.txt": (b"un dossier cache, qui n'est pas de ceux de Git", {"HORS"}),
        "_construction_locale/sortie.txt": (b"ce que la construction laisse sur le poste", {"HORS"}),
        "essais/journal.log": (b"un journal", {"HORS"}),
        ".github/flux.yml": (b"name: un flux", set()),
        "propre.txt": (("Un fichier sans rien à redire ; noreply" + "@" + "exemple.invalid est une adresse permise.").encode("utf-8"), set()),
        # La tolérance écrite : un compte dont le nom porte la chaîne témoin passe dans l'adresse de son dépôt, et là seulement.
        "temoin_adresse_du_depot.txt": (("Les versions : https://github.com/x" + TEMOIN + "/depot/releases").encode("utf-8"), set()),
        "temoin_compte_hors_adresse.txt": (("Le compte x" + TEMOIN + ", cité hors de l'adresse de son dépôt.").encode("utf-8"), {"CHAINE"}),
        "temoin_autre_compte.txt": (("https://github.com/y" + TEMOIN + "/depot : un autre compte que celui du dépôt.").encode("utf-8"), {"CHAINE"}),
    }
    manques, tolerance = [], adresse_du_depot({"x" + TEMOIN})
    dossier = Path(os.path.realpath(tempfile.mkdtemp(prefix="pdforensics-controle-")))
    try:
        for nom, (octets, attendus) in plantes.items():
            (dossier / nom).parent.mkdir(parents=True, exist_ok=True)
            (dossier / nom).write_bytes(octets)
            trouves = codes(examiner(nom, (dossier / nom).read_bytes(), noms, adresse=tolerance))
            if not attendus <= trouves or (not attendus and trouves):
                manques.append(f"{nom} : attendu {sorted(attendus) or 'rien'}, trouvé {sorted(trouves) or 'rien'}")
        manques += liste_plantee(dossier)
        pdf, nombre_de_pdf = pdf_plantes(dossier, noms)
    finally:
        effacer(dossier)
    for codage in ("utf-16-le", "utf-16-be"):
        trouves = codes(examiner("un binaire", ("x" + TEMOIN).encode(codage) + "NomDePosteFictif".encode(codage), noms, executable=True))
        if trouves != {"CHAINE", "POSTE"}:
            manques.append(f"octets d'un exécutable, en {codage} : attendu CHAINE et POSTE, trouvé {sorted(trouves) or 'rien'}")
    permis = {"id": "0" * 40, "an": "pseudonyme", "ae": "123+pseudonyme" + "@" + "users.noreply.github.com", "message": "Un message ordinaire."}
    fabriques = (({**permis, "cn": permis["an"], "ce": permis["ae"]}, set()),
                 ({**permis, "cn": "Personne A", "ce": adresse}, {"IDENTITE", "COURRIEL"}),
                 ({**permis, "cn": permis["an"], "ce": permis["ae"], "message": "Un message qui cite " + TEMOIN + "."}, {"CHAINE"}))
    for rang, (commit, attendus) in enumerate(fabriques, 1):
        trouves = codes(commit_examine(commit, noms, set()))
        if trouves != attendus:
            manques.append(f"commit fabriqué {rang} : attendu {sorted(attendus) or 'rien'}, trouvé {sorted(trouves) or 'rien'}")
    manques += pdf + rubriques_de_la_liste() + chaines_de_la_liste() + temoin_d_historique(permis["an"], permis["ae"], adresse)
    return manques, (f"{len(plantes)} fichiers, une liste et {nombre_de_pdf} PDF plantés dans un dossier temporaire, deux jeux d'octets, "
                     f"3 commits fabriqués, un dépôt jetable de 4 commits, et les {len(interdites())} chaînes cherchées, plantées en mémoire")


def liste_plantee(dossier: Path) -> list[str]:
    """Une liste écrite pour l'épreuve : elle doit se lire, rubrique par rubrique, et dire ce qui empêche de s'y fier."""
    fichier = dossier / "liste_d_epreuve.txt"
    fichier.write_text("# Un commentaire\nPremiere Chaine\n\n[comptees dans un executable]\nSeconde\n[tolerees]\nUne phrase toleree\n"
                       "[rubrique inconnue]\nabc\n", encoding="utf-8")
    liste, erreurs = lire_la_liste(fichier)
    attendue = {"partout": [TEMOIN, "premiere chaine"], "comptees": ["seconde"], "tolerees": ["une phrase toleree"]}
    manques = [] if (liste, len(erreurs)) == (attendue, 2) else ["la liste d'épreuve n'est pas lue comme elle est écrite"]
    vide = dossier / "liste_vide.txt"
    vide.write_text("# rien\n", encoding="utf-8")
    if not lire_la_liste(vide)[1] or not lire_la_liste(dossier / "absente.txt")[1]:
        manques.append("une liste vide, ou absente, n'est pas signalée")
    return manques


def rubriques_de_la_liste() -> list[str]:
    """Ce qu'une chaîne seulement comptée et une phrase tolérée laissent passer, et ce qu'elles ne laissent pas passer."""
    comptee, phrase = "chaine" + "comptee", "une phrase qui cite " + TEMOIN + " et qui passe"
    with liste_d_essai([TEMOIN], [comptee], [phrase]):
        cas = (
            ("une chaîne comptée est refusée dans un fichier du dépôt", bool(chaines("f", ("x" + comptee.upper()).encode("utf-8")))),
            ("une chaîne comptée n'est pas refusée dans un exécutable", not chaines("f", comptee.encode("utf-16-le"), executable=True)),
            ("une chaîne comptée y est comptée", COMPTES.get(comptee) == [1, 1]),
            ("une chaîne refusée partout l'est aussi dans un exécutable", bool(chaines("f", TEMOIN.encode("utf-16-be"), executable=True))),
            ("une phrase tolérée passe, en capitales comme en minuscules",
             not chaines("f", ("Avant. " + phrase.upper() + " Après.").encode("utf-8")) and TOLEREES["phrases"] >= 1),
            ("la chaîne d'une phrase tolérée reste refusée hors de cette phrase", bool(chaines("f", ("Une phrase qui cite " + TEMOIN).encode("utf-8")))),
        )
    return [f"rubriques de la liste : il n'est pas vrai qu'{quoi}" for quoi, vrai in cas if not vrai]


def chaines_de_la_liste() -> list[str]:
    """Chaque chaîne cherchée, plantée en mémoire, en capitales, sous trois codages : elle doit être retrouvée à son rang."""
    toutes, manques = interdites(), []
    with liste_d_essai(toutes):
        for rang, chaine in enumerate(toutes):
            for codage in ("utf-8", "utf-16-le", "utf-16-be"):
                details = [detail for _code, _lieu, detail in chaines("une épreuve", ("avant " + chaine.upper() + " après").encode(codage))]
                if not any(f"n° {rang} de" in detail for detail in details):
                    manques.append(f"la chaîne n° {rang} de la liste, plantée en {codage}, n'est pas retrouvée")
    return manques


def pdf_plantes(dossier: Path, noms: dict[str, str]) -> tuple[list[str], int]:
    """Des PDF fabriqués pour l'épreuve : la chaîne plantée ne se voit pas dans leurs octets, seule leur lecture la trouve."""
    try:
        import pymupdf
    except ImportError:
        return ["PyMuPDF n'est pas installé : les PDF plantés n'ont pas pu être fabriqués, ni lus"], 0
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    hors_alphabet = chr(0x3A9)  # un signe qui force une chaîne de PDF à s'écrire en UTF-16, donc en chiffres

    def page_neuve(texte: str = "Une page d'essai, sans rien à redire."):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 100), texte)
        return doc, page

    def octets_de(doc) -> bytes:
        return doc.tobytes(deflate=True, no_new_id=True)

    plantes: list[tuple[str, bytes, set[str], str]] = []  # nom, octets, ce qui doit être trouvé, et où
    doc, _ = page_neuve()
    propre = octets_de(doc)
    plantes += [("exemples/propre.pdf", propre, set(), ""), ("ailleurs/propre.pdf", propre, {"PDF"}, "")]
    doc, _ = page_neuve()
    doc.set_metadata({"author": hors_alphabet + " " + TEMOIN, "title": "Un titre ordinaire"})
    plantes.append(("exemples/auteur.pdf", octets_de(doc), {"CHAINE"}, "métadonnée author"))
    # Une version antérieure porte la chaîne ; la dernière ne la porte plus : le texte a été retiré, puis le fichier réenregistré.
    chemin = dossier / "version.pdf"
    doc, _ = page_neuve("Ligne de la version 1 : " + TEMOIN)
    doc.save(chemin, deflate=True, no_new_id=True)
    doc.close()
    doc = pymupdf.open(chemin)
    doc[0].add_redact_annot(doc[0].rect, fill=False)
    doc[0].apply_redactions()
    doc[0].insert_text((72, 100), "Ligne de la version 2, sans rien à redire.")
    doc.save(chemin, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP, deflate=True, no_new_id=True)
    derniere = "".join(page.get_text() for page in doc)
    doc.close()
    plantes.append(("exemples/version.pdf", chemin.read_bytes(), {"CHAINE"}, "version 1"))
    doc, page = page_neuve()
    page.insert_text((72, 200), TEMOIN, oc=doc.add_ocg("Calque", on=False))
    plantes.append(("exemples/calque.pdf", octets_de(doc), {"CHAINE"}, "tous calques allumés"))
    doc, page = page_neuve()
    page.insert_text((72, 200), TEMOIN, render_mode=3)
    plantes.append(("exemples/invisible.pdf", octets_de(doc), {"CHAINE"}, "texte"))
    doc, page = page_neuve()
    page.add_text_annot((72, 200), hors_alphabet + " " + TEMOIN)
    plantes.append(("exemples/annotation.pdf", octets_de(doc), {"CHAINE"}, "annotation"))
    doc, page = page_neuve()
    doc.embfile_add("annexe.txt", ("contenu : " + TEMOIN).encode("utf-8"))
    plantes.append(("exemples/joint.pdf", octets_de(doc), {"CHAINE"}, "fichier joint"))
    doc, page = page_neuve()
    doc.set_xml_metadata('<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
                         '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" '
                         'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator><rdf:Seq><rdf:li>' + TEMOIN.upper()
                         + '</rdf:li></rdf:Seq></dc:creator></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')
    plantes.append(("exemples/xmp.pdf", octets_de(doc), {"CHAINE"}, "second jeu de métadonnées"))

    manques = [] if TEMOIN not in derniere else ["PDF planté : la dernière version porte encore la chaîne, le cas ne prouve rien"]
    aveugles = []
    for nom, octets, attendus, ou in plantes:
        constats = examiner(nom, octets, noms)
        if codes(constats) != attendus:
            manques.append(f"PDF planté {nom} : attendu {sorted(attendus) or 'rien'}, trouvé {sorted(codes(constats)) or 'rien'}")
        elif ou and not any(ou in lieu for code, lieu, _detail in constats if code == "CHAINE"):
            manques.append(f"PDF planté {nom} : la chaîne n'a pas été trouvée là où elle est ({ou})")
        if attendus == {"CHAINE"} and not chaines(nom, octets):
            aveugles.append(nom)
        if nom == "exemples/version.pdf" and any("version 2" in lieu for code, lieu, _detail in constats if code == "CHAINE"):
            manques.append("PDF planté exemples/version.pdf : la chaîne est dite dans la dernière version, où elle n'est plus")
    # La preuve que le PDF est LU : dans ces deux cas au moins, une recherche sur les octets du fichier ne trouve rien.
    for nom in ("exemples/auteur.pdf", "exemples/version.pdf"):
        if nom not in aveugles:
            manques.append(f"PDF planté {nom} : la chaîne se voyait dans les octets du fichier, l'épreuve ne prouve pas la lecture")
    PDF_PLANTES.update(nombre=len(plantes), aveugles=len(aveugles))
    return manques, len(plantes)


def temoin_d_historique(pseudonyme: str, noreply: str, adresse: str) -> list[str]:
    """Un dépôt jetable, avec de vrais commits : ce qu'un commit a porté un jour doit rester refusé, même retiré ensuite."""
    travail = Path(os.path.realpath(tempfile.mkdtemp(prefix="pdforensics-historique-")))
    depot, sans_reglages, manques = travail / "depot", travail / "aucun-reglage-git", []
    depot.mkdir()
    sans_reglages.write_bytes(b"")

    # Le dépôt jetable ne lit aucun réglage Git du poste : ni identité, ni crochet, ni signature.
    isole = {"GIT_CONFIG_GLOBAL": str(sans_reglages), "GIT_CONFIG_NOSYSTEM": "1"}

    def enregistrer(message: str, nom: str = pseudonyme, courriel: str = noreply) -> None:
        git(["add", "-A"], depot, **isole)
        git(["commit", "-q", "-m", message], depot, **isole,
            GIT_AUTHOR_NAME=nom, GIT_AUTHOR_EMAIL=courriel, GIT_COMMITTER_NAME=nom, GIT_COMMITTER_EMAIL=courriel)

    def trouves() -> set[str]:
        return codes(controler_depot(depot, {})[0]) - {"LICENCE"}  # ce dépôt jetable n'a pas de licence jointe

    lus, tolerees = dict(controle_pdf.LUS), dict(TOLEREES)  # ce dépôt jetable ne compte pas dans ce qui est lu du vrai
    try:
        git(["init", "-q", "-b", "main"], depot, **isole)
        (depot / "propre.txt").write_text("rien à redire\n", encoding="utf-8")
        enregistrer("Un premier commit propre")
        etapes = [("un commit propre", set(), trouves())]
        (depot / "plante.txt").write_text("une ligne qui cite " + TEMOIN + "\n", encoding="utf-8")
        enregistrer("Un fichier de plus")
        (depot / "plante.txt").unlink()
        enregistrer("Le fichier est retiré")
        etapes.append(("une chaîne enregistrée puis retirée", {"CHAINE"}, trouves()))
        (depot / "autre.txt").write_text("rien à redire non plus\n", encoding="utf-8")
        enregistrer("Un commit signé d'une identité ordinaire", "Personne A", adresse)
        etapes.append(("une identité ordinaire", {"CHAINE", "IDENTITE", "COURRIEL"}, trouves()))
        nombre = len(git(["rev-list", "--all"], depot).split())
        manques += [f"dépôt jetable, {quoi} : attendu {sorted(attendus) or 'rien'}, trouvé {sorted(vus) or 'rien'}"
                    for quoi, attendus, vus in etapes if attendus != vus]
        manques += [] if nombre == 4 else [f"dépôt jetable : {nombre} commits créés au lieu de 4"]
    finally:
        effacer(travail)
        controle_pdf.LUS.update(lus)
        TOLEREES.update(tolerees)
    return manques + ([] if not travail.exists() else ["le dépôt jetable n'a pas pu être supprimé du dossier temporaire"])

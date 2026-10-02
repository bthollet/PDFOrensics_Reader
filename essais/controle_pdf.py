# -*- coding: utf-8 -*-
"""Ce qu'un PDF porte, lu avec la bibliothèque : pour le contrôle de publication.

Un PDF est un conteneur. Une recherche de chaînes sur ses octets ne voit rien de ce qui y est
compressé, ni ce qu'une chaîne codée dit, ni ce qu'une version antérieure portait. Chaque PDF est donc
OUVERT, et ce qu'il contient est examiné avec les règles de controle_regles :

- les flux tels qu'ils sont dans le fichier, décompressés un à un, même ceux qu'aucune version ne cite plus ;
- CHAQUE VERSION ENREGISTRÉE - le fichier coupé à chacune de ses fins de fichier, puis rouvert : ses
  métadonnées, son second jeu de métadonnées (XMP), ses signets, les noms de ses calques, ses fichiers
  joints (nom et contenu), le texte de chaque page calques tels quels puis tous calques allumés - texte
  invisible et texte hors de la page compris -, ses annotations, ses champs, les noms de ses polices ;
- chaque objet de chaque version : sa source, les chaînes qui y sont écrites (décodées), son flux décodé
  et son flux brut.

CE QUE CETTE LECTURE NE VOIT PAS : un texte dessiné dans une image ; un texte écrit dans une police à
codage propre que la bibliothèque ne sait pas ramener à des lettres ; le contenu d'un calque que le
fichier n'offre pas d'allumer ; un PDF protégé par un mot de passe, qui est refusé faute d'être lu.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
import zlib

from controle_regles import EN_TETE_PDF, EXEMPLES, chaines, poste_dans_des_octets, texte_examine

FLUX = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
HEXA = re.compile(r"(?<!<)<([0-9A-Fa-f\s]+)>(?!>)")
ECHAPPES = {"n": 10, "r": 13, "t": 9, "b": 8, "f": 12}
LUS = {"pdf": 0, "versions": 0, "objets": 0, "pages": 0}  # ce qui a été ouvert et lu, pour le dire


def est_pdf(lieu: str, octets: bytes) -> bool:
    """Un PDF : par son nom, ou par son en-tête."""
    return lieu.casefold().endswith(".pdf") or EN_TETE_PDF in octets[:1024]


def est_un_exemple(lieu: str, octets: bytes) -> bool:
    """Un PDF à sa place : dans le dossier des exemples, sous son nom, avec son en-tête."""
    return lieu.startswith(EXEMPLES) and lieu.casefold().endswith(".pdf") and EN_TETE_PDF in octets[:1024]


def fins_de_version(octets: bytes) -> list[int]:
    """Où finit chaque marqueur de fin de fichier : un enregistrement de plus en ajoute un."""
    fins, depart = [], 0
    while (position := octets.find(b"%%EOF", depart)) >= 0:
        fins.append(position + 5)
        depart = position + 5
    return fins


def texte_de_chaine(brut: bytes) -> str:
    """Une chaîne de PDF en texte : en UTF-16 si elle l'annonce, sinon un octet par signe."""
    if brut[:2] == bytes([0xFE, 0xFF]):
        return brut[2:].decode("utf-16-be", "replace")
    if brut[:2] == bytes([0xFF, 0xFE]):
        return brut[2:].decode("utf-16-le", "replace")
    return brut.decode("latin-1")


def chaines_d_objet(source: str) -> list[str]:
    """Les chaînes écrites dans la source d'un objet, décodées : entre chevrons (en chiffres), puis entre parenthèses."""
    rendu = []
    for trouve in HEXA.finditer(source):
        chiffres = re.sub(r"\s", "", trouve.group(1))
        rendu.append(texte_de_chaine(bytes.fromhex(chiffres + "0" * (len(chiffres) % 2))))
    position, fin, barre = 0, len(source), chr(92)
    while position < fin:
        if source[position] != "(":
            position += 1
            continue
        profondeur, position, octets = 1, position + 1, bytearray()
        while position < fin and profondeur:
            signe = source[position]
            if signe == barre and position + 1 < fin:
                suivant = source[position + 1]
                octal = re.match(r"[0-7]{1,3}", source[position + 1:position + 4])
                if octal:
                    octets.append(int(octal.group(0), 8) & 0xFF)
                    position += 1 + len(octal.group(0))
                    continue
                if suivant in ECHAPPES:
                    octets.append(ECHAPPES[suivant])
                elif suivant not in "\r\n":
                    octets += suivant.encode("latin-1", "replace")
                position += 2
                continue
            profondeur += (signe == "(") - (signe == ")")
            if profondeur:
                octets += signe.encode("latin-1", "replace")
            position += 1
        rendu.append(texte_de_chaine(bytes(octets)))
    return rendu


def _voir(constats: list, lieu: str, noms: dict[str, str], quoi) -> None:
    """Examine un texte, ou des octets, tirés d'un PDF."""
    if isinstance(quoi, str) and quoi:
        constats.extend(chaines(lieu, quoi.encode("utf-8", "replace")) + texte_examine(lieu, quoi, noms, invisibles=False))
    elif isinstance(quoi, (bytes, bytearray)) and quoi:
        constats.extend(chaines(lieu, bytes(quoi)) + poste_dans_des_octets(lieu, bytes(quoi), noms)
                        + texte_examine(lieu, bytes(quoi).decode("latin-1"), noms, invisibles=False))


def _version(pymupdf, lieu: str, doc, noms: dict[str, str], constats: list) -> None:
    """Tout ce qu'une version enregistrée porte."""
    def voir(ou: str, quoi) -> None:
        _voir(constats, f"{lieu}, {ou}", noms, quoi)

    for cle, valeur in (doc.metadata or {}).items():
        voir("métadonnée " + cle, str(valeur or ""))
    voir("second jeu de métadonnées", doc.get_xml_metadata() or "")
    for signet in doc.get_toc(simple=True):
        voir("signet", str(signet[1]))
    for calque in doc.get_ocgs().values():
        voir("nom de calque", str(calque.get("name") or ""))
    for nom in doc.embfile_names():
        info = doc.embfile_info(nom)
        voir("fichier joint, nom", " \n".join([str(nom)] + [str(valeur) for valeur in info.values()]))
        contenu = doc.embfile_get(nom)
        if est_pdf(str(nom), contenu):
            constats.extend(examiner_pdf(f"{lieu}, fichier joint", contenu, noms))
        voir("fichier joint, contenu", contenu)
    for passe in ("calques tels quels", "tous calques allumés"):
        if passe != "calques tels quels":
            for reglage in doc.layer_ui_configs():
                if not reglage["on"]:
                    doc.set_layer_ui_config(reglage["number"], action=pymupdf.PDF_OC_ON)
        for page in doc:
            traits = ["".join(chr(lettre[0]) for lettre in trait["chars"]) for trait in page.get_texttrace()]
            # Les traits de texte, ligne à ligne, puis bout à bout (un mot coupé entre deux traits), puis le texte tel que la bibliothèque le copie.
            voir(f"page {page.number + 1}, texte, {passe}", "\n".join(traits) + "\n" + "".join(traits) + "\n" + page.get_text("text"))
    for page in doc:
        LUS["pages"] += 1
        for annotation in page.annots() or []:
            voir(f"page {page.number + 1}, annotation", " \n".join(str(valeur) for valeur in annotation.info.values()))
        for champ in page.widgets() or []:
            voir(f"page {page.number + 1}, champ", " \n".join(str(valeur or "") for valeur in (champ.field_name, champ.field_label, champ.field_value)))
        for police in page.get_fonts(full=True):
            voir(f"page {page.number + 1}, police", " ".join(str(valeur) for valeur in police[3:5]))
    for xref in range(1, doc.xref_length()):
        try:
            source = doc.xref_object(xref, compressed=True)
        except Exception:  # noqa: BLE001 - un objet qui ne se lit pas n'arrête pas la lecture des autres
            continue
        LUS["objets"] += 1
        voir(f"objet {xref}", source)
        voir(f"objet {xref}, chaînes", "\n".join(chaines_d_objet(source)))
        if doc.xref_is_stream(xref):
            for flux in (doc.xref_stream(xref), doc.xref_stream_raw(xref)):
                voir(f"objet {xref}, flux", flux or b"")


def examiner_pdf(lieu: str, octets: bytes, noms: dict[str, str]) -> list[tuple[str, str, str]]:
    """Tout ce qu'un PDF porte, et qu'une recherche sur ses octets ne verrait pas."""
    try:
        import pymupdf
    except ImportError:
        return [("PDF", lieu, "PyMuPDF n'est pas installé : ce PDF n'a pas pu être lu")]
    pymupdf.TOOLS.mupdf_display_errors(False)  # la bibliothèque n'écrit rien d'elle-même
    pymupdf.TOOLS.mupdf_display_warnings(False)
    constats: list[tuple[str, str, str]] = []
    LUS["pdf"] += 1
    for rang, trouve in enumerate(FLUX.finditer(octets), 1):
        try:
            _voir(constats, f"{lieu}, flux {rang} du fichier", noms, zlib.decompressobj().decompress(trouve.group(1)))
        except zlib.error:
            continue  # un flux qui n'est pas compressé ainsi : ses octets ont déjà été examinés
    fins, ouvertes = fins_de_version(octets), 0
    for rang, tranche in enumerate([octets[:fin] + b"\n" for fin in fins[:-1]] + [octets], 1):
        try:
            doc = pymupdf.open(stream=tranche, filetype="pdf")
        except Exception:  # noqa: BLE001 - une tranche qui ne s'ouvre pas n'est pas une version
            continue
        if doc.needs_pass:
            constats.append(("PDF", lieu, "ce PDF est protégé par un mot de passe : son contenu ne se lit pas"))
            continue
        ouvertes += 1
        LUS["versions"] += 1
        try:
            _version(pymupdf, f"{lieu}, version {rang}", doc, noms, constats)
        except Exception as erreur:  # noqa: BLE001 - une version qui ne se lit pas jusqu'au bout est un refus, pas une panne
            constats.append(("PDF", lieu, f"la version {rang} ne se lit pas jusqu'au bout ({type(erreur).__name__})"))
    if not ouvertes:
        constats.append(("PDF", lieu, "ce PDF ne s'ouvre pas : rien n'a pu y être lu"))
    return constats


def examiner_zip(lieu: str, octets: bytes, noms: dict[str, str], attendus: dict[str, bytes] | None) -> list[tuple[str, str, str]]:
    """Le zip des exemples : il ne porte que des PDF du dossier des exemples, les mêmes que ceux de l'arbre, et chacun est lu."""
    constats = chaines(lieu, lieu.encode("utf-8")) + chaines(lieu, octets) + poste_dans_des_octets(lieu, octets, noms)
    try:
        archive = zipfile.ZipFile(io.BytesIO(octets))
    except zipfile.BadZipFile:
        return constats + [("EXEMPLES", lieu, "ce fichier ne se lit pas comme un zip")]
    portes: dict[str, bytes] = {}
    with archive:
        _voir(constats, f"{lieu}, commentaire", noms, archive.comment)
        for entree in archive.infolist():
            ici = f"{lieu} : {entree.filename}"
            _voir(constats, ici, noms, entree.filename)
            _voir(constats, ici, noms, entree.comment + entree.extra)
            if entree.is_dir():
                continue
            contenu = archive.read(entree)
            if not est_un_exemple(entree.filename, contenu):
                constats.append(("EXEMPLES", ici, "le zip des exemples porte autre chose qu'un PDF du dossier des exemples"))
                continue
            portes[entree.filename] = contenu
            constats += examiner_pdf(ici, contenu, noms)
    if attendus is not None:
        def empreintes(fichiers: dict[str, bytes]) -> dict[str, str]:
            return {nom: hashlib.sha256(contenu).hexdigest() for nom, contenu in fichiers.items()}
        if empreintes(portes) != empreintes(attendus):
            constats.append(("EXEMPLES", lieu, "le zip ne porte pas exactement les exemples de l'arbre"))
    return constats

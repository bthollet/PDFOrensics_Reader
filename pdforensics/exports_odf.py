# -*- coding: utf-8 -*-
"""L'export OpenDocument des fiches: UN document Writer (.odt), ou UN tableau Calc (.ods).

Meme contrat que `exports_texte`: une fiche est {"nom", "identite": [[libelle,
valeur]], "rubriques": [{"titre", "compte", "lignes"}]}; le tableau est
{"colonnes", "lignes"}, une ligne par piece.

Le fichier est une archive OpenDocument 1.2: `mimetype` en premiere entree, non
compressee et sans champ supplementaire, puis content.xml, styles.xml, meta.xml
et le manifeste. Il s'ecrit d'un seul coup - un provisoire a cote, puis son nom
definitif - et n'ecrase jamais: FileExistsError si le fichier existe.

CE QUE LE FICHIER DIT DE LUI-MEME, et rien d'autre: le generateur, le titre
recu et la date de creation. Ni auteur, ni machine, ni dossier.
"""
from __future__ import annotations

import os
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

GENERATEUR = "PDForensics"
VERSION_ODF = "1.2"
MIME_ODT = "application/vnd.oasis.opendocument.text"
MIME_ODS = "application/vnd.oasis.opendocument.spreadsheet"
MANIFESTE = "META-INF/manifest.xml"
# La vue d'ensemble du document Writer ne garde du tableau que ces colonnes, dans cet ordre.
COLONNES_VUE = ("Pièce", "Pages", "Versions enregistrées", "Zones recouvertes", "Calques éteints",
                "Lignes de texte invisible", "Images", "Annotations")
TITRE_VUE = "Vue d'ensemble"
LARGEUR_UTILE = 17.0  # centimetres entre les marges d'une page A4 en portrait
VALEUR_COURTE = 6  # signes au plus: un compte, un oui, un non
LARGEUR_MINI_ODS, LARGEUR_MAXI_ODS = 2.2, 12.0  # centimetres; au-dela, le texte passe a la ligne dans sa case

_OASIS = "urn:oasis:names:tc:opendocument:xmlns:"
_ESPACES = "".join(f' xmlns:{prefixe}="{adresse}"' for prefixe, adresse in (
    ("office", _OASIS + "office:1.0"), ("style", _OASIS + "style:1.0"), ("text", _OASIS + "text:1.0"),
    ("table", _OASIS + "table:1.0"), ("fo", _OASIS + "xsl-fo-compatible:1.0"),
    ("svg", _OASIS + "svg-compatible:1.0"), ("meta", _OASIS + "meta:1.0"),
    ("dc", "http://purl.org/dc/elements/1.1/")))
_POLICES = ('<office:font-face-decls><style:font-face style:name="Liberation Sans" '
            'svg:font-family="&apos;Liberation Sans&apos;" style:font-family-generic="swiss" style:font-pitch="variable"/>'
            "</office:font-face-decls>")

# Ce que XML 1.0 interdit - controles hors tabulation et retours, demi-codes isoles, U+FFFE, U+FFFF -
# et les controles C1, qui n'ont rien a faire dans un texte: tout cela est retire.
_INTERDITS = dict.fromkeys([*range(0x09), 0x0B, 0x0C, *range(0x0E, 0x20), *range(0x7F, 0xA0),
                            *range(0xD800, 0xE000), 0xFFFE, 0xFFFF])

# ------------------------------------------------------------------ styles
# Les styles du document Writer. Les noms Standard, Title, Heading_20_1... sont ceux que LibreOffice
# connait: il les montre sous leur nom francais, et l'utilisateur peut les retoucher d'un seul geste.
_STYLES_ODT = """<office:styles>
<style:default-style style:family="paragraph">
<style:paragraph-properties fo:orphans="2" fo:widows="2" style:tab-stop-distance="1.25cm"/>
<style:text-properties style:font-name="Liberation Sans" fo:font-size="10pt" fo:language="fr" fo:country="FR" fo:hyphenate="false"/>
</style:default-style>
<style:default-style style:family="table">
<style:table-properties table:border-model="collapsing"/>
</style:default-style>
<style:style style:name="Standard" style:family="paragraph">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.2cm" fo:text-align="start"/>
</style:style>
<style:style style:name="Title" style:family="paragraph" style:parent-style-name="Standard">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.15cm" fo:text-align="start"/>
<style:text-properties fo:font-size="20pt" fo:font-weight="bold"/>
</style:style>
<style:style style:name="Subtitle" style:family="paragraph" style:parent-style-name="Standard">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.7cm" fo:text-align="start"/>
<style:text-properties fo:font-size="11pt" fo:font-style="normal" fo:color="#555555"/>
</style:style>
<style:style style:name="Heading" style:family="paragraph" style:parent-style-name="Standard">
<style:paragraph-properties fo:margin-top="0.45cm" fo:margin-bottom="0.2cm" fo:keep-with-next="always"/>
<style:text-properties fo:font-size="12pt" fo:font-weight="bold"/>
</style:style>
<style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" style:parent-style-name="Heading" style:default-outline-level="1">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.3cm" fo:keep-with-next="always"/>
<style:text-properties fo:font-size="15pt" fo:font-weight="bold"/>
</style:style>
<style:style style:name="Heading_20_2" style:display-name="Heading 2" style:family="paragraph" style:parent-style-name="Heading" style:default-outline-level="2">
<style:paragraph-properties fo:margin-top="0.45cm" fo:margin-bottom="0.2cm" fo:keep-with-next="always"/>
<style:text-properties fo:font-size="12pt" fo:font-weight="bold"/>
</style:style>
<style:style style:name="Ligne_20_de_20_rubrique" style:display-name="Ligne de rubrique" style:family="paragraph" style:parent-style-name="Standard">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0.1cm"/>
</style:style>
<style:style style:name="Table_20_Contents" style:display-name="Table Contents" style:family="paragraph" style:parent-style-name="Standard">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0cm" fo:text-align="start"/>
<style:text-properties fo:font-size="9pt"/>
</style:style>
<style:style style:name="Table_20_Heading" style:display-name="Table Heading" style:family="paragraph" style:parent-style-name="Table_20_Contents">
<style:paragraph-properties fo:text-align="start"/>
<style:text-properties fo:font-weight="bold"/>
</style:style>
<style:style style:name="Footer" style:family="paragraph" style:parent-style-name="Standard">
<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0cm" fo:text-align="center"/>
<style:text-properties fo:font-size="8pt" fo:color="#555555"/>
</style:style>
<text:list-style style:name="Puces">
<text:list-level-style-bullet text:level="1" text:bullet-char="•">
<style:list-level-properties text:list-level-position-and-space-mode="label-alignment">
<style:list-level-label-alignment text:label-followed-by="listtab" text:list-tab-stop-position="0.8cm" fo:text-indent="-0.4cm" fo:margin-left="0.8cm"/>
</style:list-level-properties>
<style:text-properties style:font-name="Liberation Sans"/>
</text:list-level-style-bullet>
</text:list-style>
</office:styles>
<office:automatic-styles>
<style:page-layout style:name="A4_portrait">
<style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" style:print-orientation="portrait" fo:margin-top="2cm" fo:margin-bottom="1.5cm" fo:margin-left="2cm" fo:margin-right="2cm"/>
<style:footer-style>
<style:header-footer-properties fo:min-height="0.6cm" fo:margin-top="0.5cm"/>
</style:footer-style>
</style:page-layout>
</office:automatic-styles>
<office:master-styles>
<style:master-page style:name="Standard" style:page-layout-name="A4_portrait">
<style:footer>
<text:p text:style-name="Footer">Page <text:page-number text:select-page="current">1</text:page-number> sur <text:page-count>1</text:page-count></text:p>
</style:footer>
</style:master-page>
</office:master-styles>"""

# Les styles propres au contenu du document: la page neuve de chaque fiche, les cases des tableaux.
_AUTOMATIQUES_ODT = """<style:style style:name="P_Fiche" style:family="paragraph" style:parent-style-name="Heading_20_1">
<style:paragraph-properties fo:break-before="page"/>
</style:style>
<style:style style:name="P_Entete" style:family="paragraph" style:parent-style-name="Table_20_Heading">
<style:text-properties fo:font-size="8pt"/>
</style:style>
<style:style style:name="P_Entete_centre" style:family="paragraph" style:parent-style-name="Table_20_Heading">
<style:paragraph-properties fo:text-align="center"/>
<style:text-properties fo:font-size="8pt"/>
</style:style>
<style:style style:name="P_Centre" style:family="paragraph" style:parent-style-name="Table_20_Contents">
<style:paragraph-properties fo:text-align="center"/>
</style:style>
<style:style style:name="Rangee" style:family="table-row">
<style:table-row-properties fo:keep-together="always"/>
</style:style>
<style:style style:name="Case_entete" style:family="table-cell">
<style:table-cell-properties fo:background-color="#e6e6e6" fo:border="0.5pt solid #808080" fo:padding="0.08cm" style:vertical-align="middle"/>
</style:style>
<style:style style:name="Case" style:family="table-cell">
<style:table-cell-properties fo:border="0.5pt solid #808080" fo:padding="0.08cm" style:vertical-align="middle"/>
</style:style>
"""

# Les styles du tableau Calc: la police, puis une page A4 en paysage dont l'en-tete porte titre et sous-titre.
_STYLES_ODS = """<office:styles>
<style:default-style style:family="table-cell">
<style:text-properties style:font-name="Liberation Sans" fo:font-size="10pt" fo:language="fr" fo:country="FR"/>
</style:default-style>
<style:style style:name="Default" style:family="table-cell"/>
</office:styles>
<office:automatic-styles>
<style:page-layout style:name="A4_paysage">
<style:page-layout-properties fo:page-width="29.7cm" fo:page-height="21cm" style:print-orientation="landscape" fo:margin-top="1.5cm" fo:margin-bottom="1.5cm" fo:margin-left="1.5cm" fo:margin-right="1.5cm"/>
<style:header-style>
<style:header-footer-properties fo:min-height="1cm" fo:margin-bottom="0.3cm"/>
</style:header-style>
<style:footer-style>
<style:header-footer-properties fo:min-height="0.6cm" fo:margin-top="0.3cm"/>
</style:footer-style>
</style:page-layout>
</office:automatic-styles>
<office:master-styles>
<style:master-page style:name="Default" style:page-layout-name="A4_paysage">
<style:header>{entete}</style:header>
<style:footer>
<text:p><text:sheet-name>Feuille</text:sheet-name>, page <text:page-number>1</text:page-number> sur <text:page-count>1</text:page-count></text:p>
</style:footer>
</style:master-page>
</office:master-styles>"""

_AUTOMATIQUES_ODS = """<style:style style:name="Feuille" style:family="table" style:master-page-name="Default">
<style:table-properties table:display="true" style:writing-mode="lr-tb"/>
</style:style>
<style:style style:name="Rangee" style:family="table-row">
<style:table-row-properties fo:break-before="auto" style:use-optimal-row-height="true"/>
</style:style>
<style:style style:name="Entete" style:family="table-cell" style:parent-style-name="Default">
<style:table-cell-properties fo:background-color="#e6e6e6" fo:wrap-option="wrap" style:vertical-align="middle"/>
<style:text-properties fo:font-weight="bold"/>
</style:style>
<style:style style:name="Corps" style:family="table-cell" style:parent-style-name="Default">
<style:table-cell-properties fo:wrap-option="wrap" style:vertical-align="top"/>
</style:style>
"""


# ------------------------------------------------------------------- texte

def _texte(valeur: object) -> str:
    """Toute valeur en texte: rien pour None, oui ou non pour un booleen."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    return valeur if isinstance(valeur, str) else str(valeur)


def _lignes(valeur: object) -> list[str]:
    """Les lignes d'un texte, sans les caracteres que XML 1.0 interdit; au moins une, meme vide."""
    return [ligne.translate(_INTERDITS) for ligne in _texte(valeur).splitlines()] or [""]


def _propre(valeur: object) -> str:
    """Le texte nettoye, chaque retour a la ligne ramene a un seul signe."""
    return "\n".join(_lignes(valeur))


def _une_ligne(valeur: object) -> str:
    """Le texte nettoye, ramene a une seule ligne: pour un titre, un nom, un libelle."""
    return " ".join(_lignes(valeur)).replace("\t", " ").strip(" ")


def _xml_espaces(bloc: str) -> str:
    """Texte echappe. Une espace ne s'ecrit telle quelle qu'entre deux mots: au bord ou repetee, c'est <text:s/>.

    Un lecteur OpenDocument fond les blancs qui se suivent et ignore ceux des bords: sans cette
    balise, deux espaces n'en feraient plus qu'une.
    """
    sortie: list[str] = []
    debut = 0
    while debut < len(bloc):
        fin = debut
        while fin < len(bloc) and (bloc[fin] == " ") == (bloc[debut] == " "):
            fin += 1
        if bloc[debut] != " ":
            sortie.append(escape(bloc[debut:fin]))
        else:
            nombre = fin - debut
            if 0 < debut and fin < len(bloc):  # entre deux mots: la premiere espace reste une espace
                sortie.append(" ")
                nombre -= 1
            if nombre:
                sortie.append(f'<text:s text:c="{nombre}"/>')
        debut = fin
    return "".join(sortie)


def _xml_ligne(ligne: str) -> str:
    """Une ligne deja nettoyee, en contenu de paragraphe: les tabulations deviennent <text:tab/>."""
    return "<text:tab/>".join(_xml_espaces(bloc) for bloc in ligne.split("\t"))


def _xml_texte(valeur: object) -> str:
    """Un texte quelconque en contenu de paragraphe: ses retours a la ligne deviennent <text:line-break/>."""
    return "<text:line-break/>".join(_xml_ligne(ligne) for ligne in _lignes(valeur))


def _paire(entree: object) -> tuple[str, str]:
    """Libelle et valeur d'une ligne d'identite, meme quand l'entree est incomplete."""
    morceaux = list(entree) if isinstance(entree, (list, tuple)) else [entree]
    morceaux += ["", ""]
    return _une_ligne(morceaux[0]), _propre(morceaux[1])


def _case(valeurs: list, rang: int) -> object:
    """La valeur de ce rang, ou rien si la ligne est plus courte que le tableau."""
    return valeurs[rang] if rang < len(valeurs) else None


# ----------------------------------------------------------------- archive

def _racine(nom: str, corps: str) -> str:
    """Un fichier XML de l'archive: la declaration, puis la racine office:nom et ses espaces de noms."""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<office:{nom}{_ESPACES} office:version="{VERSION_ODF}">'
            f"{corps}</office:{nom}>")


def _meta(titre: str, instant: datetime) -> str:
    """meta.xml: le generateur, le titre et la date de creation. Ni auteur, ni machine."""
    titre = _une_ligne(titre)
    xml = f"<meta:generator>{escape(GENERATEUR)}</meta:generator>"
    if titre:
        xml += f"<dc:title>{escape(titre)}</dc:title>"
    xml += f"<meta:creation-date>{instant.isoformat()}</meta:creation-date>"
    return _racine("document-meta", f"<office:meta>{xml}</office:meta>")


def _manifeste(mime: str, noms: list[str]) -> str:
    """Le manifeste: le type du document, puis chaque fichier de l'archive.

    La norme veut que ni `mimetype` ni le manifeste lui-meme n'y figurent.
    """
    entrees = f'<manifest:file-entry manifest:full-path="/" manifest:version="{VERSION_ODF}" manifest:media-type="{mime}"/>'
    entrees += "".join(f'<manifest:file-entry manifest:full-path="{nom}" manifest:media-type="text/xml"/>' for nom in noms)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<manifest:manifest xmlns:manifest="{_OASIS}manifest:1.0" '
            f'manifest:version="{VERSION_ODF}">{entrees}</manifest:manifest>')


def _entree(nom: str, instant: datetime, compression: int) -> zipfile.ZipInfo:
    """L'en-tete d'une entree de l'archive, datee de la creation du document."""
    entree = zipfile.ZipInfo(nom, date_time=instant.timetuple()[:6])
    entree.compress_type = compression
    return entree


def _nommer(provisoire: Path, chemin: Path) -> None:
    """Donne au provisoire son nom definitif, en un seul geste, sans jamais ecraser un fichier."""
    if os.name == "nt":
        os.rename(provisoire, chemin)  # Windows refuse de renommer vers un nom deja pris
    else:
        os.link(provisoire, chemin)  # ailleurs, renommer ecraserait: le lien, lui, refuse un nom deja pris
        os.unlink(provisoire)


def _ecrire_archive(chemin: Path, mime: str, instant: datetime, parties: dict[str, str]) -> None:
    """Ecrit l'archive d'un seul coup: un provisoire a cote, puis son nom definitif. N'ecrase jamais."""
    if os.path.lexists(chemin):
        raise FileExistsError(f"Ce fichier existe déjà, il n'est pas écrasé : {chemin}")
    parties = {**parties, MANIFESTE: _manifeste(mime, list(parties))}
    provisoire = chemin.with_name(f"{chemin.name}.{os.getpid()}-{os.urandom(4).hex()}.partiel")
    flux = open(provisoire, "xb")  # creation exclusive: ce provisoire est a nous, et a nous seuls
    try:
        with flux:
            with zipfile.ZipFile(flux, "w") as archive:
                # `mimetype` d'abord, sans compression ni champ supplementaire: le type se lit a l'octet 38
                archive.writestr(_entree("mimetype", instant, zipfile.ZIP_STORED), mime.encode("ascii"))
                for nom, xml in parties.items():
                    archive.writestr(_entree(nom, instant, zipfile.ZIP_DEFLATED), xml.encode("utf-8"))
            flux.flush()
            os.fsync(flux.fileno())
        _nommer(provisoire, chemin)
    except BaseException:
        if os.path.lexists(provisoire):
            os.unlink(provisoire)  # une ecriture ratee ne laisse rien derriere elle
        raise


# ------------------------------------------------------- document Writer

def _cellule(case: str, paragraphe: str, valeur: object) -> str:
    """Une cellule de tableau Writer, avec son style de case et son style de paragraphe."""
    return (f'<table:table-cell table:style-name="{case}" office:value-type="string">'
            f'<text:p text:style-name="{paragraphe}">{_xml_texte(valeur)}</text:p></table:table-cell>')


def _rangee(cellules: list[str]) -> str:
    return '<table:table-row table:style-name="Rangee">' + "".join(cellules) + "</table:table-row>"


def _table(nom: str, style: str, colonnes: int, entete: str, rangees: list[str]) -> str:
    """Un tableau Writer; ses colonnes portent les styles style.A, style.B, etc."""
    xml = f'<table:table table:name="{nom}" table:style-name="{style}">'
    xml += "".join(f'<table:table-column table:style-name="{style}.{chr(65 + rang)}"/>' for rang in range(colonnes))
    if entete:  # la rangee d'en-tetes se repete en haut de chaque page que le tableau occupe
        xml += f"<table:table-header-rows>{entete}</table:table-header-rows>"
    return xml + "".join(rangees) + "</table:table>"


def _styles_table(style: str, largeurs: list[float]) -> str:
    """Les styles d'un tableau Writer: il occupe la largeur de la page, chaque colonne a la sienne."""
    xml = (f'<style:style style:name="{style}" style:family="table"><style:table-properties '
           f'style:width="{sum(largeurs):.3f}cm" table:align="margins" fo:margin-top="0cm" fo:margin-bottom="0.3cm" '
           'table:border-model="collapsing"/></style:style>')
    for rang, largeur in enumerate(largeurs):
        xml += (f'<style:style style:name="{style}.{chr(65 + rang)}" style:family="table-column">'
                f'<style:table-column-properties style:column-width="{largeur:.3f}cm"/></style:style>')
    return xml


def _vue_ensemble(tableau: dict) -> tuple[list[str], list[list[str]]]:
    """En-tetes et rangees de la vue d'ensemble: les colonnes convenues, dans l'ordre convenu."""
    colonnes = [_une_ligne(colonne) for colonne in tableau.get("colonnes") or []]
    rangs = [colonnes.index(nom) for nom in COLONNES_VUE if nom in colonnes]
    rangees = [[_propre(_case(ligne, rang)) for rang in rangs] for ligne in tableau.get("lignes") or []]
    return [colonnes[rang] for rang in rangs], rangees


def _largeurs_vue(entetes: list[str], rangees: list[list[str]], courtes: list[bool]) -> list[float]:
    """Largeurs en centimetres: au plus juste pour les colonnes de comptes, le reste aux colonnes de texte.

    Une colonne de comptes suit le plus long mot de son en-tete, qui passe a la ligne entre deux mots
    et jamais au milieu d'un seul. Un en-tete inconnu demain y trouve sa largeur de la meme facon.
    """
    largeurs = [0.0] * len(entetes)
    for rang, entete in enumerate(entetes):
        if courtes[rang]:
            mots = entete.split(" ") + [rangee[rang] for rangee in rangees]
            largeurs[rang] = max(1.3, 0.15 * max(len(mot) for mot in mots) + 0.3)
    larges = courtes.count(False)
    if larges:
        part = max((LARGEUR_UTILE - sum(largeurs)) / larges, 3.0)
        largeurs = [largeur or part for largeur in largeurs]
    echelle = LARGEUR_UTILE / sum(largeurs)
    return [largeur * echelle for largeur in largeurs]


def _section_vue(entetes: list[str], rangees: list[list[str]]) -> tuple[str, str]:
    """Styles et corps de la vue d'ensemble: un titre, puis un tableau compact d'une rangee par piece."""
    courtes = [all(len(rangee[rang]) <= VALEUR_COURTE for rangee in rangees) for rang in range(len(entetes))]
    styles = _styles_table("Vue", _largeurs_vue(entetes, rangees, courtes))
    entete = _rangee([_cellule("Case_entete", "P_Entete_centre" if courte else "P_Entete", nom)
                      for nom, courte in zip(entetes, courtes)])
    corps = [_rangee([_cellule("Case", "P_Centre" if courte else "Table_20_Contents", valeur)
                      for valeur, courte in zip(rangee, courtes)]) for rangee in rangees]
    titre = f'<text:h text:style-name="Heading_20_1" text:outline-level="1">{escape(TITRE_VUE)}</text:h>'
    return styles, titre + _table("Vue_d_ensemble", "Vue", len(entetes), entete, corps)


def _rubrique_odt(rubrique: dict) -> str:
    """Une rubrique: « Titre (compte) » en titre de niveau 2, puis ses lignes en liste a puces."""
    titre, compte = _une_ligne(rubrique.get("titre")), _une_ligne(rubrique.get("compte"))
    if compte:
        titre = f"{titre} ({compte})"
    xml = f'<text:h text:style-name="Heading_20_2" text:outline-level="2">{_xml_ligne(titre)}</text:h>'
    puces = "".join(f'<text:list-item><text:p text:style-name="Ligne_20_de_20_rubrique">{_xml_texte(ligne)}</text:p></text:list-item>'
                    for ligne in rubrique.get("lignes") or [])
    return xml + (f'<text:list text:style-name="Puces">{puces}</text:list>' if puces else "")


def _fiche_odt(rang: int, fiche: dict) -> str:
    """Une fiche: le nom en titre de niveau 1 sur une page neuve, l'identite en tableau, puis les rubriques."""
    nom = _une_ligne(fiche.get("nom")) or "Pièce sans nom"
    xml = f'<text:h text:style-name="P_Fiche" text:outline-level="1">{_xml_ligne(nom)}</text:h>'
    identite = [_paire(entree) for entree in fiche.get("identite") or []]
    if identite:
        rangees = [_rangee([_cellule("Case_entete", "Table_20_Heading", libelle), _cellule("Case", "Table_20_Contents", valeur)])
                   for libelle, valeur in identite]
        xml += _table(f"Identite_{rang}", "Identite", 2, "", rangees)
    return xml + "".join(_rubrique_odt(rubrique) for rubrique in fiche.get("rubriques") or [])


def _contenu_odt(titre: str, sous_titre: str, fiches: list[dict], tableau: dict) -> str:
    """content.xml du document Writer: titre, sous-titre, vue d'ensemble, puis une fiche par piece."""
    styles = _AUTOMATIQUES_ODT + _styles_table("Identite", [6.0, LARGEUR_UTILE - 6.0])
    corps = [f'<text:p text:style-name="{style}">{_xml_ligne(texte)}</text:p>'
             for style, texte in (("Title", _une_ligne(titre)), ("Subtitle", _une_ligne(sous_titre))) if texte]
    entetes, rangees = _vue_ensemble(tableau)
    if entetes and rangees:
        styles_vue, vue = _section_vue(entetes, rangees)
        styles += styles_vue
        corps.append(vue)
    elif not fiches:
        corps.append('<text:p text:style-name="Standard">Aucune pièce.</text:p>')
    corps += [_fiche_odt(rang, fiche) for rang, fiche in enumerate(fiches, 1)]
    return _racine("document-content", f"{_POLICES}<office:automatic-styles>{styles}</office:automatic-styles>"
                   f"<office:body><office:text>{''.join(corps)}</office:text></office:body>")


def ecrire_odt(chemin: Path, titre: str, sous_titre: str, fiches: list[dict], tableau: dict) -> None:
    """Ecrit UN document Writer, A4 en portrait: le titre, une vue d'ensemble, puis une fiche par page."""
    instant = datetime.now().replace(microsecond=0)
    _ecrire_archive(Path(chemin), MIME_ODT, instant, {
        "content.xml": _contenu_odt(titre, sous_titre, fiches, tableau),
        "styles.xml": _racine("document-styles", _POLICES + _STYLES_ODT),
        "meta.xml": _meta(titre, instant),
    })


# ---------------------------------------------------------- tableau Calc

def _cellule_ods(valeur: object, style: str = "") -> str:
    """Une cellule de feuille: numerique pour un entier, vide pour rien, en texte pour tout le reste."""
    attribut = f' table:style-name="{style}"' if style else ""
    if isinstance(valeur, int) and not isinstance(valeur, bool):
        return (f'<table:table-cell{attribut} office:value-type="float" office:value="{valeur}">'
                f"<text:p>{valeur}</text:p></table:table-cell>")
    lignes = _lignes(valeur)
    if lignes == [""]:
        return f"<table:table-cell{attribut}/>"
    paragraphes = "".join(f"<text:p>{_xml_ligne(ligne)}</text:p>" for ligne in lignes)
    return f'<table:table-cell{attribut} office:value-type="string">{paragraphes}</table:table-cell>'


def _rangee_ods(valeurs: list, nombre: int, style: str = "") -> str:
    """Une rangee de feuille, completee de cellules vides jusqu'au nombre de colonnes."""
    cellules = "".join(_cellule_ods(_case(valeurs, rang), style) for rang in range(nombre))
    return f'<table:table-row table:style-name="Rangee">{cellules}</table:table-row>'


def _largeur_ods(entete: str, valeurs: list) -> float:
    """Largeur d'une colonne en centimetres: le plus long mot de l'en-tete, ou la plus longue valeur, bornee."""
    signes = [len(mot) for mot in entete.split(" ")]
    signes += [len(ligne) for valeur in valeurs for ligne in _lignes(valeur)]
    return min(max(0.2 * max(signes) + 0.4, LARGEUR_MINI_ODS), LARGEUR_MAXI_ODS)


def _feuille(rang: int, nom: str, entetes: list, lignes: list[list]) -> tuple[str, str]:
    """Styles de colonnes et table d'une feuille: les en-tetes en gras, puis une rangee par ligne."""
    entetes = [_une_ligne(entete) for entete in entetes]
    nombre = max([len(entetes), 1] + [len(ligne) for ligne in lignes])  # une feuille a toujours une colonne
    styles, colonnes = "", ""
    for colonne in range(nombre):
        largeur = _largeur_ods(_case(entetes, colonne) or "", [_case(ligne, colonne) for ligne in lignes])
        styles += (f'<style:style style:name="co{rang}_{colonne + 1}" style:family="table-column">'
                   f'<style:table-column-properties fo:break-before="auto" style:column-width="{largeur:.2f}cm"/></style:style>')
        colonnes += f'<table:table-column table:style-name="co{rang}_{colonne + 1}" table:default-cell-style-name="Corps"/>'
    entete = _rangee_ods(entetes, nombre, "Entete")
    corps = "".join(_rangee_ods(ligne, nombre) for ligne in lignes)
    return styles, (f'<table:table table:name="{escape(nom)}" table:style-name="Feuille">{colonnes}'
                    f"<table:table-header-rows>{entete}</table:table-header-rows>{corps}</table:table>")


def _lignes_detail(fiches: list[dict]) -> list[list[str]]:
    """Feuille « Détail »: pour chaque piece, ses lignes d'identite, puis une ligne par ligne de rubrique."""
    lignes: list[list[str]] = []
    for fiche in fiches:
        nom = _une_ligne(fiche.get("nom"))
        for libelle, valeur in map(_paire, fiche.get("identite") or []):
            lignes.append([nom, "Identité", " : ".join(part for part in (libelle, valeur) if part)])
        for rubrique in fiche.get("rubriques") or []:
            titre = _une_ligne(rubrique.get("titre"))
            lignes += [[nom, titre, _propre(ligne)] for ligne in rubrique.get("lignes") or []]
    return lignes


def _contenu_ods(fiches: list[dict], tableau: dict) -> str:
    """content.xml du tableau Calc: la feuille « Tableau », puis la feuille « Détail »."""
    feuilles = [_feuille(1, "Tableau", tableau.get("colonnes") or [], tableau.get("lignes") or []),
                _feuille(2, "Détail", ["Pièce", "Rubrique", "Ligne"], _lignes_detail(fiches))]
    styles = _AUTOMATIQUES_ODS + "".join(styles for styles, _ in feuilles)
    tables = "".join(table for _, table in feuilles)
    return _racine("document-content", f"{_POLICES}<office:automatic-styles>{styles}</office:automatic-styles>"
                   f"<office:body><office:spreadsheet>{tables}</office:spreadsheet></office:body>")


def _styles_ods(titre: str, sous_titre: str) -> str:
    """styles.xml du tableau Calc; titre et sous-titre s'impriment en tete de chaque page."""
    entete = "".join(f"<text:p>{_xml_ligne(texte)}</text:p>" for texte in (_une_ligne(titre), _une_ligne(sous_titre)) if texte)
    return _racine("document-styles", _POLICES + _STYLES_ODS.format(entete=entete or "<text:p/>"))


def ecrire_ods(chemin: Path, titre: str, sous_titre: str, fiches: list[dict], tableau: dict) -> None:
    """Ecrit UN tableau Calc: la feuille « Tableau », une ligne par piece, et la feuille « Détail »."""
    instant = datetime.now().replace(microsecond=0)
    _ecrire_archive(Path(chemin), MIME_ODS, instant, {
        "content.xml": _contenu_ods(fiches, tableau),
        "styles.xml": _styles_ods(titre, sous_titre),
        "meta.xml": _meta(titre, instant),
    })

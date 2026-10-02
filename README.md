# PDForensics

PDF Reader that helps you see what you usually dont

> **In short (English).** PDForensics is a Windows desktop tool that shows what a PDF holds beneath the page you
> see: saved revisions, covered-up areas and the text left underneath, switched-off layers, invisible text and
> metadata. Files are read locally and in memory; nothing leaves the machine, and the tool opens no network port.
> Five made-up sample PDFs come with it (`exemples/`). The interface is in French. The source code in this
> repository is released under 0BSD. **The Windows executable bundles PyMuPDF and is therefore distributed
> under the AGPL-3.0.**

PDForensics montre ce qu'un PDF contient sous la page qu'on voit : versions enregistrées, zones recouvertes,
calques éteints, texte invisible, métadonnées. Ce qui est ouvert est lu sur le poste et n'en sort pas.

## Ce que l'outil relève

- **Les versions enregistrées.** Un PDF garde souvent ses enregistrements successifs. L'outil rouvre chacun,
  le compare au précédent, et montre où la page a changé.
- **Les zones recouvertes.** Ce qui est posé sur un texte ne l'efface pas : l'outil relève le texte resté
  dessous, et celui qui a été écrit par-dessus. Le regard « Voir dessous » fait disparaître, à l'affichage
  seulement, ce qui est posé sur la page.
- **Les calques éteints** à l'ouverture, et ce qu'ils portent.
- **Le texte invisible**, et la cause pour laquelle la page ne le montre pas.
- **La fiche du fichier** : métadonnées, second jeu de métadonnées (XMP), fichiers joints, polices, signets.
- **De quoi la page est faite** : textes, images, tracés, annotations, et l'ordre où le fichier écrit ses blocs.

## Ce que l'outil appelle « recouvert » et « invisible »

Une **zone recouverte** est un endroit où quelque chose (un aplat, une image, un dégradé) est posé sur du
texte, et où **l'image de la page ne montre plus ce texte**. L'outil ne se fie pas à la géométrie : un aplat
dessiné après un texte ne le cache pas s'il est rogné ailleurs, transparent, posé en mode de mélange, effacé
par un masque, ou d'une forme qui passe à côté des lettres. Il compare donc l'image de la page avec son texte
et sans lui, lettre par lettre. La géométrie ne sert qu'à nommer ce qui cache. Elle ne tranche seule que là où
l'image ne peut rien dire : un texte réécrit par-dessus l'aplat.

Des précisions, venues de vraies pièces :

- ce qui est posé sur une lettre peut la redessiner (un texte converti en contours, une image numérisée du
  même mot). L'outil voit alors la lettre : rien n'est caché. Une lettre n'est dite recouverte que si, à son
  endroit, l'image finale de la page est d'une teinte unie ;
- un signe sans dessin n'est pas une lettre : une espace, ou le signe d'une police qui ne dit pas à quelles
  lettres correspondent ses signes. Un texte fait de tels signes est dit « illisible » ;
- un texte écrit sous un aplat puis redessiné à l'identique par-dessus (un titre sous son bandeau) n'est pas
  caché non plus. Dès qu'une lettre diffère, la zone est signalée, avec l'ancien texte entier.

Si la comparaison d'image échoue sur une page, l'outil n'y dit aucune zone recouverte, plutôt que de s'en
remettre à la géométrie.

Une **annotation opaque** qui masque du contenu est une zone recouverte quel que soit ce qu'il y a dessous -
texte, tracés, image : l'outil dessine la page avec ses annotations et sans elles, et compare.

### Voir dessous

Le regard « Voir dessous » marque les zones recouvertes et permet de **faire disparaître ce qui est posé sur
la page** : annotations, images, aplats et tracés, chacun par son interrupteur ; un curseur les efface peu à
peu. Le texte de la page reste. Par défaut, il retire ce qui recouvre dans la pièce ouverte, ou les seules
annotations. Rien n'est modifié dans le fichier : la page est redessinée en mémoire. Une zone de biffage que
le fichier porte sans l'avoir appliquée n'est pas appliquée par l'outil.

### Invisible

Un **texte invisible** est un texte présent dans le fichier et que la page ne montre pas, pour une cause que
l'outil sait nommer : écrit en mode invisible (la couche de reconnaissance d'une page numérisée), écrit sans
opacité, écrit de la couleur du fond, ou placé hors de la page.

Une **annotation sans dessin propre** est une annotation que le fichier décrit sans la dessiner : chaque
lecteur PDF l'affiche à sa façon. Pour un surlignage, l'outil dessine les quadrilatères tels que le fichier
les déclare, sans les arrondir.

## L'écran

Il n'y a pas de capture d'écran dans ce dépôt : l'écran se décrit en mots.

- **En haut, un bandeau** rappelle que ce qui est ouvert est lu sur le poste et n'en sort pas.
- **À gauche, un volet** qui montre l'un de ses deux explorateurs. Un petit menu, en bas, passe de l'un à
  l'autre ; un bouton replie le volet.
  - **Pièces** : un explorateur de fichiers, ouvert sur le dossier personnel, qui va partout où Windows laisse
    aller. Le champ du haut accepte un chemin collé. Chaque PDF a une case à cocher ; « Tout sélectionner »
    coche ceux du dossier affiché, et la sélection se garde d'un dossier à l'autre.
  - **Export** : un second explorateur, pour choisir où l'export s'écrit. Un bouton crée un dossier dans le
    dossier affiché. Une phrase dit si ce dossier accepte l'export, et sinon pourquoi. Trois formes : des
    fiches (une fiche `.md` par pièce et un tableau `.csv`), un document LibreOffice (`.odt`), un tableau
    LibreOffice (`.ods`).
- **À droite, la pièce.** Sept regards, chacun par une icône dont le nom et l'explication s'affichent au
  survol, un seul à la fois : la page, la fiche du fichier, voir dessous, le contenu non affiché,
  les versions enregistrées, de quoi la page est faite, l'ordre de lecture. Un regard sans objet pour le
  fichier ouvert est désactivé, et dit pourquoi. Un bouton fait pivoter l'affichage d'un quart de tour ; le
  fichier n'est pas modifié.
- **Le zoom.** Pincer sur le pavé tactile, ou tourner la molette en tenant Ctrl : la page grossit sous le
  pointeur. Les boutons « − » et « + » vont de 40 % à 400 % ; « Largeur » revient à la pleine largeur.
- **Le détail d'un tracé**, en bas, tient en trois lignes et se déroule. « Tout lire » l'ouvre en grand ; la
  croix le masque, et le tracé reste sur la page.
- **Une longue pièce s'ouvre tout de suite.** L'écran montre d'abord ce qui se dit du fichier, puis lit ses
  pages par tranches ; le sous-titre et la phrase disent où en est la lecture. Tant qu'elle dure, un compte
  n'est que celui des pages déjà lues.

## Ce que l'outil lit, et ce qu'il écrit

- Il **lit** les PDF en place, en mémoire. Il n'en fait aucune copie et n'écrit jamais dans leur dossier.
- Il n'ouvre **ni serveur, ni port, ni connexion** : l'écran ne charge rien de l'extérieur.
- Il ne garde **aucune trace** de ce qui a été ouvert : pas de fichiers récents, pas de journal, pas de cache
  sur disque, fenêtre en mode privé. Tant que la fenêtre est ouverte, le moteur d'affichage de Windows tient
  un dossier de profil temporaire, supprimé à la fermeture. Si la fenêtre est tuée au lieu d'être fermée, ce
  dossier, vide de contenu, peut rester dans le dossier temporaire de Windows.
- Le **seul fichier** qu'il écrit hors d'un export est `PDForensics\reglages.json`, dans le dossier où Windows
  range les données locales des applications de votre session (l'outil demande cet emplacement à Windows) : la
  liste des dossiers protégés et le dernier dossier d'export. Ce fichier ne vit jamais à côté de l'exécutable.
- Un **export** s'écrit dans le dossier affiché par l'explorateur d'export. Il n'écrase jamais : un nom déjà
  pris reçoit un rang. Un export raté retire ce qu'il a posé.

## Où l'export est refusé

Une fiche porte les métadonnées et le texte caché d'une pièce : elle est aussi sensible que la pièce.
L'export est donc refusé :

- dans un **dossier protégé**, et pour toute pièce qui s'y trouve ;
- dans un dossier temporaire ;
- dans un dossier que Windows connaît comme synchronisé avec un service en ligne ;
- dans un dépôt Git ;
- dans le dossier d'une pièce sélectionnée.

**Les dossiers protégés** sont des dossiers où l'outil n'écrit jamais, et dont les pièces ne s'exportent pas.
Le logiciel ne sait pas ce qu'ils contiennent : c'est une liste, sous la clé `proteges` du fichier de
réglages. Il n'y a pas encore d'écran pour la modifier : on édite le fichier, puis on relance l'outil.

```json
{
 "proteges": ["D:\\Archives\\A ne pas exporter"],
 "export": ""
}
```

Un dossier se reconnaît par ce qu'il est sur le disque : sous son nom long comme sous son nom court, et à
travers un lien.

**Ce que ces refus ne savent pas voir** : un dossier synchronisé par un logiciel qui ne se déclare pas à
Windows, un partage réseau, un dossier qu'une sauvegarde recopie ailleurs, un dépôt Git dont le dossier
`.git` vit ailleurs.

## Limites connues

- Une zone noircie dans l'image même d'une page numérisée ne se distingue pas d'une tache : seuls les caches
  posés par-dessus la page sont relevés.
- Un aplat ou une image posés sur des tracés ou sur une autre image ne sont pas signalés comme zone
  recouverte : un dessin ordinaire est fait de formes posées les unes sur les autres. On voit dessous en les
  faisant disparaître. Seuls le texte recouvert, et ce qu'une annotation masque, sont signalés.
- Faire disparaître « aplats et tracés » efface aussi les lettres d'une page dont le texte a été converti en
  contours.
- Un texte que la page ne montre pas, et dont l'outil ne sait pas nommer la cause (une police sans dessin pour
  ce signe, un texte rogné par une découpe), n'est pas rapporté. `essais/essai_pieces_reelles.py` les compte.
- Quand un texte est réécrit exactement par-dessus un aplat, l'image ne permet pas de dire si l'ancien texte
  est caché : l'outil s'en remet alors à la géométrie, et ne retient que les aplats pleins, opaques et hors
  mélange.
- Les dates viennent du fichier : elles disent ce que le fichier déclare, pas ce qui s'est passé.
- L'ordre de lecture d'un fichier balisé n'est pas dessiné : l'outil dit seulement si le fichier le décrit.
- Une page insérée au milieu d'un fichier, entre deux versions, fait paraître modifiées toutes les pages
  qui la suivent.
- Les raccourcis des explorateurs (Bureau, Documents, Téléchargements, lecteurs) ne se règlent pas.
- Un PDF protégé par un mot de passe n'est pas lu.
- L'outil est fait pour Windows, et son interface n'existe qu'en français.

## Lancer

**L'exécutable.** `PDForensics.exe` se prend dans les
[releases de ce dépôt](https://github.com/bthollet/PDFOrensics_Reader/releases) et se lance d'un double-clic :
il n'y a rien à installer. Il n'est pas signé : Windows peut afficher un avertissement au premier lancement.
Il lui faut le moteur d'affichage Microsoft Edge WebView2, fourni avec Windows 11 ; sans lui, l'outil le dit
et ne s'ouvre pas.

**Depuis les sources**, avec Python 3.12 sous Windows :

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -B -m pdforensics
```

Un dossier donné en argument sert de départ aux deux explorateurs : `PDForensics.exe D:\Pieces`.

## Les exemples

Le dossier `exemples/` porte cinq PDF **fabriqués** par `essais/pieces_epreuve.py` : ils ne viennent d'aucun
vrai document. Leurs textes disent ce qu'ils sont (« ligne visible », « texte resté sous le cache »), sans nom
de personne, d'entreprise ni de lieu, sans aucune somme ; leurs dates, le premier jour d'un mois de l'an 2000,
ne datent rien. Chaque release les porte aussi, tels quels, dans `PDForensics-exemples.zip`.

Pour les voir : lancer l'outil sur ce dossier (`PDForensics.exe D:\exemples`), ou y aller par l'explorateur.
Ce que chacun montre est ce que les essais y vérifient :

| Exemple | Ce que l'outil y relève |
|---|---|
| `Essais - couches/Document d'essai à trois enregistrements.pdf` | Trois versions enregistrées. Deux zones recouvertes, avec leur texte et leur version : sous un aplat blanc, à la version 2, « Mot écrit à l'origine », et par-dessus « Mot remplacé » ; sous un cache noir, à la version 3, « texte resté sous le cache. ». Un calque éteint, « Brouillon », et son contenu. Cinq lignes de texte invisible, une image, une annotation. La version 3 dit ce qu'elle ajoute : « page 1 : 1 texte ajouté, 1 aplat noir ajouté » ; la page 2 n'a changé dans aucune version. |
| `Essais - texte/Document d'essai sans rien à relever.pdf` | Une seule version, rien de recouvert, aucun calque. |
| `Essais - texte/Document d'essai à phrase remplacée.pdf` | À sa deuxième version, une phrase remplacée dans le contenu même, sans zone recouverte : « page 1 : 1 texte ajouté, 1 texte retiré ». |
| `Essais - texte/Document d'essai à calque affiché.pdf` | Un calque, « En-tête », affiché à l'ouverture. |
| `Essais - image/Document d'essai en image seule.pdf` | Une image seule, aucun texte. |

Ces fichiers sont, à l'octet près, les pièces que les essais fabriquent et lisent : `essais/essais.py` le
vérifie. `python -B essais/pieces_epreuve.py` les refait, avec la même version de la bibliothèque.

## Construire l'exécutable

```text
.venv\Scripts\python -m pip install -r packaging\requirements-construction.txt
.venv\Scripts\python -B packaging\construire.py
```

L'exécutable s'écrit dans `_construction_locale\dist`, que Git ignore.

**Aucun flux ne publie, et aucun ne tourne tout seul.** Une release se prépare à la main : une personne
construit l'exécutable depuis le dépôt à l'étiquette de la version, joue l'essai de la fenêtre dessus, le
passe au contrôle de publication, rassemble ce qui l'accompagne (`packaging\preparer_release.py` : le zip des
exemples, les textes de licence, la note de version), puis crée la release en brouillon et la relit avant de
la publier.

Les deux flux de `.github/workflows/` ne se déclenchent ni à un envoi, ni à une demande de fusion, ni à la
pose d'une étiquette : ils se lancent à la main, et n'ont que le droit de lire le dépôt. `essais.yml` joue
les essais sur une machine de GitHub. `construction.yml` y construit en plus l'exécutable, le contrôle, et
le dépose comme pièce du passage, sans rien publier. Ils n'ont pas encore tourné : rien de ce qu'ils font
n'a été vérifié sur GitHub.

## Essais

Les essais ne lisent que des pièces qu'ils fabriquent, dans un dossier temporaire supprimé à la fin. Le
dépôt ne porte d'autre PDF que les cinq exemples, qui sont ces mêmes pièces.

```text
python -B essais/essais.py                      les exemples, la lecture, le pont, l'écran, les réglages, les gardes d'export
python -B essais/essais_tordus.py               pages tournées, rognées, mot de passe, longue pièce
python -B essais/essais_caches.py               ce qui cache un texte, et ce qui y ressemble sans le cacher
python -B essais/essais_exports.py              les exports OpenDocument, relus sans lancer aucun autre logiciel
python -B essais/essais.py --fenetre            la vraie fenêtre, cachée, pilotée par son pont
python -B essais/essais.py --executable CHEMIN  le même essai, fait par l'exécutable construit
```

Chaque essai imprime « OK » ou « ECHEC » ; le verdict est sur la dernière ligne. Un essai qui ne peut pas se
faire sur le poste - la fenêtre, sans moteur d'affichage - imprime « NON FAIT » et dit pourquoi.

L'essai de la fenêtre passe par l'auto-essai de l'outil, `--essai-pont DOSSIER RAPPORT` : la fenêtre s'ouvre
sans se montrer, sur DOSSIER, et n'écrit que RAPPORT, un compte rendu sans aucun chemin. Il regarde les ports
du processus de l'outil, pas ceux du moteur d'affichage.

`essais/essais_exports_ouverture.py` fait en plus ouvrir les exports par LibreOffice. À ne lancer que
volontairement : pour mettre un document en pages, LibreOffice interroge l'imprimante du poste, ce qui peut se
voir comme des tentatives d'impression. Aucun flux automatique ne le lance.

### Sur de vraies pièces, sans rien en montrer

```text
python -B essais/essai_pieces_reelles.py --dossier D --combien 12
python -B essais/essai_annotations.py --liste FICHIER
python -B essais/essai_reperes.py --dossier D --combien 12
```

Ces trois scripts lisent des PDF en place, n'écrivent rien, et ne rendent que des nombres et un vocabulaire
fermé : jamais un nom de fichier, un chemin, un texte, ni le message d'une erreur. Une pièce y est désignée
par son rang dans un tirage. Les deux sorties du processus sont détournées : la bibliothèque ne peut rien
imprimer d'elle-même. Le premier porte un témoin qui ne doit rien au détecteur : sur l'image finale,
l'endroit d'un texte dit caché est-il uni ? Le deuxième décrit les annotations ; le troisième compare deux
relevés de l'endroit où sont les lettres. Les essais ordinaires les jouent sur les pièces fabriquées, et
vérifient qu'aucun nom ni aucun texte n'en sort.

## Contrôle de publication

```text
python -B essais/controle_publication.py --interdits LISTE                      le dépôt
python -B essais/controle_publication.py --interdits LISTE --executable CHEMIN  un exécutable construit
python -B essais/controle_publication.py --interdits LISTE --exemples ZIP       le zip des exemples d'une release
python -B essais/controle_publication.py --interdits LISTE --textes FICHIER     un texte publié hors du dépôt
```

À lancer avant chaque commit et avant chaque envoi. Il examine ce qui est indexé, les fichiers présents,
tout l'historique et l'identité de chaque commit ; pour un exécutable, ses octets puis le contenu de son
archive, décompressé, modules compilés un par un. Il refuse une image, un fichier binaire, un chemin de
dossier personnel, une adresse de courriel autre qu'une adresse « noreply », un nom propre au poste, un
fichier de réglages posé dans le dépôt, un dossier caché qui n'est pas de ceux de Git, et les chaînes d'une
liste.

**Cette liste n'est pas dans le dépôt**, sous aucune forme : c'est un fichier que chacun tient à part et donne
par `--interdits` (une chaîne par ligne ; sa forme est décrite en tête de `essais/controle_regles.py`). Le
code ne porte que des règles génériques. Sans liste, il faut le demander (`--sans-liste`), et le verdict le
dit.

**Un PDF n'a sa place que dans `exemples/`**, et il y est ouvert et lu avec la bibliothèque : métadonnées,
texte de chaque version enregistrée, calques éteints, texte invisible, annotations, fichiers joints, noms des
polices, flux décompressés. Une recherche sur les octets du fichier n'y verrait rien.

Avant de conclure, le contrôle plante lui-même ce qu'il doit refuser - dans des fichiers, dans des PDF (dans
l'auteur, dans une version antérieure), puis dans l'historique d'un dépôt jetable - et vérifie qu'il le
retrouve. Ce qu'il ne voit pas est dit en tête de `essais/controle_publication.py`.

Un commit se signe d'un pseudonyme de GitHub et de son adresse « noreply » : le contrôle refuse toute autre
identité. Il a deux tolérances : le nom du compte qui porte le dépôt passe dans l'identité des commits et dans
l'adresse du dépôt, et nulle part ailleurs ; la liste peut déclarer des phrases qui passent telles quelles. Il
compte ce que chacune a laissé passer, et le dit.

## Licences

- **Le code de ce dépôt** : 0BSD (fichier `LICENSE`). Titulaire : PDForensics contributors.
- **L'exécutable** : il embarque PyMuPDF et MuPDF, publiés sous l'AGPL-3.0, et se distribue donc **selon
  l'AGPL-3.0**, dont le texte est dans `licences/AGPL-3.0.txt` et accompagne chaque release. Le code source
  correspondant à un exécutable publié est ce dépôt, à l'étiquette de la version.
- **Ce que l'exécutable embarque**, et sous quelles licences : `LICENCES-TIERCES.md`. Les textes de ces
  licences accompagnent chaque release, dans `LICENCES-TIERCES-textes.txt`.
- **Les exemples** : fabriqués par le code de ce dépôt, ils sont publiés sous la même licence que lui, 0BSD.

## Fichiers

| Fichier | Rôle |
|---|---|
| `pdforensics/lecture_pdf.py` | Lire un PDF : l'en-tête, les pages par tranches, les versions, l'image d'une page. Sans écran. |
| `pdforensics/lecture_page.py` | Ce qu'une page contient, et ce qu'elle ne montre pas. |
| `pdforensics/lecture_annotations.py` | Les annotations d'une page, et celles que le fichier laisse sans dessin propre. |
| `pdforensics/application.py` | La fenêtre, et le pont entre l'écran et la lecture. |
| `pdforensics/ecran.py`, `pdforensics/ecran/` | L'écran : un gabarit, une feuille de style, des fragments de script. |
| `pdforensics/gardes_export.py` | Où l'export a le droit de s'écrire. |
| `pdforensics/exports_texte.py`, `pdforensics/exports_odf.py` | Les trois formes d'export. |
| `pdforensics/moteur.py` | Reconnaître le moteur d'affichage du poste. |
| `pdforensics/auto_essai.py`, `pdforensics/__main__.py` | L'auto-essai du pont, et le lancement. |
| `essais/pieces_epreuve.py` | Cinq PDF fabriqués à la demande, à réponse connue. |
| `exemples/` | Ces cinq PDF, posés dans le dépôt pour qui veut essayer l'outil. |
| `essais/essais*.py` | Les essais, sur pièces fabriquées seulement. |
| `essais/essai_pieces_reelles.py`, `essais/essai_annotations.py`, `essais/essai_reperes.py` | Éprouver la lecture sur de vraies pièces, en ne rendant que des nombres. |
| `essais/controle_publication.py` | Ce que le dépôt, ses exemples, l'exécutable et les textes publiés ne doivent jamais porter. |
| `essais/controle_regles.py`, `essais/controle_pdf.py`, `essais/controle_depot.py`, `essais/controle_temoins.py` | Ses règles, sa lecture des PDF, sa lecture du dépôt, et les preuves qu'il fait avant de conclure. |
| `packaging/` | La recette de l'exécutable, et ce qui accompagne une release. |
| `licences/`, `LICENCES-TIERCES.md` | Le texte de l'AGPL-3.0, et les licences de ce que l'exécutable embarque. |

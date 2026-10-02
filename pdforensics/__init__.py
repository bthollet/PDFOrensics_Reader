# -*- coding: utf-8 -*-
"""PDForensics : lire les couches d'un PDF.

Ce qu'un PDF contient sous la page qu'on voit : versions enregistrées, zones
recouvertes, calques éteints, texte invisible, métadonnées. Tout se lit sur le
poste, en mémoire ; rien n'en sort.
"""
__version__ = "0.1.0"

# Une phrase que le contrôle de publication recherche dans l'exécutable construit : s'il la retrouve dans
# l'archive, c'est qu'il a bien lu le contenu compressé, et pas seulement les octets du fichier.
TEMOIN_DE_LECTURE = "pdforensics : phrase temoin du controle de publication"

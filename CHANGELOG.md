# Journal des versions

## 0.1.0

Première version publique. La date s'inscrira ici le jour de la publication.

- Lecteur des couches d'un PDF : versions enregistrées, zones recouvertes, calques éteints, texte invisible,
  métadonnées, composition des pages, ordre de lecture.
- Un explorateur de fichiers, ouvert sur le dossier personnel, et sept regards sur la pièce ouverte.
- Export en lot : des fiches (`.md`) et leur tableau (`.csv`), un document LibreOffice (`.odt`), un tableau
  LibreOffice (`.ods`).
- Gardes d'export : dossier protégé, dossier temporaire, dossier synchronisé, dépôt Git, dossier d'une pièce
  sélectionnée.
- Réglages sous le dossier de données locales de l'utilisateur, jamais à côté de l'exécutable.
- Cinq PDF d'exemple, fabriqués par les essais : dans `exemples/`, et dans le zip joint à la release.
- Exécutable Windows, construit par PyInstaller, distribué selon l'AGPL-3.0.

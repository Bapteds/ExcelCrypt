# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Dates au format AAAA-MM-JJ.
Le projet n'est pas sous git : **chaque modification notable doit être ajoutée ici**, dans `[Non publié]`, avec les fichiers concernés, puis la fiche correspondante de `brain/files/` mise à jour.

## [Non publié]

### Ajouté
- 2026-09-29 — Dossier `brain/` : `INDEX.md`, `CHANGELOG.md`, `design/` (architecture, produit, sécurité, interface), une fiche par fichier dans `files/`, et `CLAUDE.md` à la racine.

## [0.1.0] — 2026-09-29
État initial documenté (reconstitué à partir du code, pas d'historique antérieur).

### Moteur et CLI (`excelcrypt.py`)
- Jetons déterministes `ENC_` + HMAC-SHA256 tronqué à 64 bits, type inclus dans l'empreinte.
- Jetons lisibles `PREFIXE_0042` stables via le coffre.
- Coffre AES-256-GCM format v2 (`entries`, `aliases`, `counters`), lecture du format v1.
- Clé maître avec deux sous-clés HKDF ; protection facultative par mot de passe (Argon2id + AES-256-GCM, `EXCELCRYPT-KEY-2`).
- Sélection par colonnes, lignes, cellules et plages (`B5`, `A2:C40`, `12-30`, `D:F`, noms de colonnes).
- 10 détecteurs : email, phone_fr, phone_de, iban, card, vat, steuer_id, nir, rvnr, siret (sommes de contrôle quand elles existent).
- Propagation des valeurs masquées dans tout le classeur ; masquage des en-têtes.
- Commandes `keygen`, `passwd`, `inspect`, `encrypt`, `scan` (code retour 2 en cas de fuite), `decrypt`.
- Formats `.xlsx`, `.xlsm` (VBA conservé), `.csv` ; restauration des types (nombres, dates) et des noms de feuilles.

### Interface (`gui.py`, `ui/index.html`)
- Fenêtre pywebview, charte DIVE Turbinen, langues fr/de/en.
- Parcours Protéger (sélection au clic, glisser, Maj+clic, plages, ⌘Z, suggestions), Vue IA, contrôle avant envoi avec correction en un clic.
- Profils avec application automatique, traitement par lot (dossier), gestion de la clé, du coffre et du mot de passe.
- Parcours Restaurer avec aperçu et signalement des jetons inconnus.

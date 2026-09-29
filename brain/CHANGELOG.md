# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Dates au format AAAA-MM-JJ.
Le projet n'est pas sous git : **chaque modification notable doit être ajoutée ici**, dans `[Non publié]`, avec les fichiers concernés, puis la fiche correspondante de `brain/files/` mise à jour.

## [Non publié]

### Corrigé
- 2026-09-29 — `excelcrypt.py` : `encrypt_file` enregistre le coffre **avant** le fichier de sortie (plus de jetons irrécupérables si l'écriture du coffre échoue).
- 2026-09-29 — `excelcrypt.py` : `encrypt_file` et `decrypt_file` refusent d'écraser le fichier source (`same_output`).
- 2026-09-29 — `excelcrypt.py` : `mask_text` protège les jetons existants et insérés ; un littéral ou une regex (« ENC », chiffres…) ne peut plus corrompre un jeton.
- 2026-09-29 — `excelcrypt.py` : les feuilles restaurées qui prendraient le nom d'une feuille existante sont suffixées ` (2)` (Excel refusait l'enregistrement).
- 2026-09-29 — `excelcrypt.py` : `load_key` signale un chemin de clé mal tapé (`key_missing`) au lieu de « Clé invalide » ; `$EXCELCRYPT_PASSWORD` vaut aussi pour une clé protégée passée par `$EXCELCRYPT_KEY`.
- 2026-09-29 — `gui.py` : `new_key`, `set_key_password`, `delete_profile` renvoient `write_denied` au lieu de lever une exception ; `file_info` tolère un fichier disparu.
- 2026-09-29 — `gui.py` : `encrypt` / `decrypt` vérifient regex et verrou **avant** d'ouvrir le dialogue d'enregistrement.
- 2026-09-29 — `gui.py` : extension imposée sans écrasement silencieux (`with_suffix`, nouvelle erreur `file_exists`) ; `decrypt` refuse aussi `same_output`.
- 2026-09-29 — `gui.py` : `new_key` ne réutilise plus un `.vault` appartenant à une autre clé.
- 2026-09-29 — `gui.py` : noms de profils insensibles à la casse partout ; les lots ignorent les sorties d'un lot précédent (`is_output_of`) ; `batch_decrypt` renvoie `state`.
- 2026-09-29 — `gui.py` : `get_state` ne déchiffre le coffre que s'il a changé (cache).
- 2026-09-29 — `ui/index.html` : ⌘Z annule aussi les changements d'options (détections, valeurs, regex, interrupteurs), qui sont désormais historisés.
- 2026-09-29 — `ui/index.html` : les regex sont validées par Python (`api.check_regexes`), la syntaxe réellement appliquée.
- 2026-09-29 — `ui/index.html` : `errText` retombe sur le français comme `t()` ; lecture de fichier non interruptible par Échap ; libellé « Enregistrer » dédié pour le mot de passe ; taille inconnue affichée « — ».
- 2026-09-29 — `ui/index.html` : code mort supprimé (`TOKEN_RE`, clés i18n `emails`, `phones`, `phonesDe`, `sumEmails`, `sumPhones`, `sumPhonesDe`) ; `S.findings` déclaré.

### Ajouté
- 2026-09-29 — `gui.py` : méthode `check_regexes` exposée à la page.
- 2026-09-29 — Dépôt git (`main`), `.gitignore` complété (`.DS_Store`, `*.tmp`).
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

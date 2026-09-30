# Architecture

## Vue d'ensemble
```
┌──────────────────────────── ui/index.html ────────────────────────────┐
│ JS pur, sans framework. État global S, i18n fr/de/en, 4 vues, modale   │
│ unique. Ne voit JAMAIS la clé ni les valeurs du coffre.                │
└──────────────┬──────────────────────────────────▲─────────────────────┘
   window.pywebview.api.X(...)  (21 méthodes)      │ evaluate_js :
   → Promise<dict> | {error, code, params}         │ onTaskStart, onTaskProgress,
               │                                    │ onBatchProgress, onFileDropped
┌──────────────▼──────────────── gui.py ───────────┴─────────────────────┐
│ class Api : état privé (_keys, _file, _sheets…), dialogues natifs,      │
│ verrou _busy pour les tâches longues, profils, lots, réglages JSON.     │
└──────────────┬─────────────────────────────────────────────────────────┘
               │ import excelcrypt as ec
┌──────────────▼──────────── excelcrypt.py ──────────────────────────────┐
│ Moteur + CLI. SheetSelection/parse_refs → Detectors → Propagation →     │
│ Tokenizer (HMAC) → Vault (AES-GCM) ; read_preview, _process,            │
│ encrypt_file / scan_file / decrypt_file ; cmd_* + main().               │
└──────────────┬─────────────────────────────────────────────────────────┘
               ▼
   excelcrypt.key · excelcrypt.vault · *.xlsx/.xlsm/.csv · excelcrypt_gui.json · excelcrypt_profiles.json
```

## Découpage
| Couche | Fichier | Responsabilité | Fiche |
|---|---|---|---|
| Moteur | `excelcrypt.py` | crypto, sélection, détection, lecture/écriture, CLI | `files/excelcrypt.py.md` |
| Pont | `gui.py` | API exposée à la page, dialogues, état de session, lots | `files/gui.py.md` |
| Interface | `ui/index.html` | rendu, interactions, i18n, charte | `files/ui-index.html.md` |

**Règle** : toute logique métier ou crypto va dans `excelcrypt.py` (utilisable en CLI). `gui.py` orchestre, `ui/index.html` affiche.

## Flux « Protéger »
1. `api.load(path)` → `ec.read_preview` (500 lignes max) + `ec.detect_column` pour les suggestions.
2. L'utilisateur construit une sélection par feuille (`cols`, `rows`, `cells`, `ranges`, 1-based comme Excel) + options (détecteurs, valeurs, regex, `maskHeaders`, `propagate`).
3. **Vue IA** : `api.preview` → `ec.Tokenizer(dry_run=True)`, le coffre n'est ni lu ni écrit.
4. **Contrôle avant envoi** : `api.scan` → `ec.scan_file` (clé aléatoire, liste des fuites probables).
5. `api.encrypt` → `ec.encrypt_file` → `_process` : pour chaque cellule, masquage entier ou `mask_text` (propagation → littéraux → détecteurs) ; écriture du fichier puis `Vault.save()`.

## Flux « Restaurer »
`api.decrypt` → `ec.decrypt_file` : recherche `ENC_<hex>` et les alias lisibles des anciennes versions partout (cellules, en-têtes, noms de feuilles), les remplace par la valeur typée du coffre (nombres et dates retrouvent leur format) et signale les jetons inconnus.

## Contrat d'erreur
Le moteur lève `ExcelCryptError(message_fr, code, **params)`. `gui.py` renvoie `{error, code, params}`. La page traduit avec `errText()` à partir de `I18N[lang]["err_" + code]`. **Nouveau code d'erreur = ajouter `err_<code>` dans fr, de et en.**

## Formats de fichiers
Entrée/sortie : `.xlsx`, `.xlsm` (VBA conservé), `.csv`, `.tsv`, `.txt` (`EXCEL_EXT`, `CSV_EXT`, `excelcrypt.py:84-85` ; le lot de la GUI exclut `.txt`). `.xls` refusé (`xls_unsupported`). Sorties : `<nom>_chiffre.<ext>` et `<nom>_dechiffre.<ext>` (`default_output`).
Clé, coffre : voir `files/excelcrypt.key.md`, `files/excelcrypt.vault.md`, `design/security.md`.

## Limites connues (choix assumés, non corrigés)
- Un alias lisible d'une ancienne version (`CONTACT_0042`) déjà présent dans une cellule d'entrée est re-tokenisé : `is_token` ne reconnaît que `ENC_…`, car un alias ressemble à du texte ordinaire (`ORDER_2024`).
- CSV : tout est texte, donc `"12"` (CSV) et `12` (Excel) donnent deux jetons différents.
- `scan_file` ignore la ligne d'en-tête et les formules.
- Polices Inter / JetBrains Mono non embarquées (repli sur les polices système).
- `logo.svg` existe en double (racine et `ui/`).

## Dette corrigée (branche `fix/dette-connue`, 2026-09-29)
Voir `brain/CHANGELOG.md` § Corrigé : ordre coffre → fichier, refus d'écraser l'original, jetons protégés dans `mask_text`, doublons de feuilles, erreurs `gui.py` toujours renvoyées en `{error, code}`, contrôles avant dialogues, extensions sans écrasement silencieux, lots qui ne retraitent pas leurs sorties, cache du compteur de coffre, annulation des options, validation des regex par Python, code mort supprimé.

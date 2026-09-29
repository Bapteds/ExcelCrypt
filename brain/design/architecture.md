# Architecture

## Vue d'ensemble
```
┌──────────────────────────── ui/index.html ────────────────────────────┐
│ JS pur, sans framework. État global S, i18n fr/de/en, 4 vues, modale   │
│ unique. Ne voit JAMAIS la clé ni les valeurs du coffre.                │
└──────────────┬──────────────────────────────────▲─────────────────────┘
   window.pywebview.api.X(...)  (20 méthodes)      │ evaluate_js :
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
2. L'utilisateur construit une sélection par feuille (`cols`, `rows`, `cells`, `ranges`, 1-based comme Excel) + options (détecteurs, valeurs, regex, `maskHeaders`, `propagate`, `readable`).
3. **Vue IA** : `api.preview` → `ec.Tokenizer(dry_run=True)`, le coffre est lu mais jamais écrit.
4. **Contrôle avant envoi** : `api.scan` → `ec.scan_file` (clé aléatoire, liste des fuites probables).
5. `api.encrypt` → `ec.encrypt_file` → `_process` : pour chaque cellule, masquage entier ou `mask_text` (propagation → littéraux → détecteurs) ; écriture du fichier puis `Vault.save()`.

## Flux « Restaurer »
`api.decrypt` → `ec.decrypt_file` : recherche `ENC_<hex>` et les alias lisibles partout (cellules, en-têtes, noms de feuilles), les remplace par la valeur typée du coffre (nombres et dates retrouvent leur format) et signale les jetons inconnus.

## Contrat d'erreur
Le moteur lève `ExcelCryptError(message_fr, code, **params)`. `gui.py` renvoie `{error, code, params}`. La page traduit avec `errText()` à partir de `I18N[lang]["err_" + code]`. **Nouveau code d'erreur = ajouter `err_<code>` dans fr, de et en.**

## Formats de fichiers
Entrée/sortie : `.xlsx`, `.xlsm` (VBA conservé), `.csv`, `.tsv`, `.txt` (`EXCEL_EXT`, `CSV_EXT`, `excelcrypt.py:84-85` ; le lot de la GUI exclut `.txt`). `.xls` refusé (`xls_unsupported`). Sorties : `<nom>_chiffre.<ext>` et `<nom>_dechiffre.<ext>` (`default_output`).
Clé, coffre : voir `files/excelcrypt.key.md`, `files/excelcrypt.vault.md`, `design/security.md`.

## Dette connue (relevée pendant la documentation)
- `encrypt_file` écrit la sortie **avant** le coffre, et rien n'empêche `out == path`.
- `gui.py` : certaines méthodes laissent passer des exceptions (`new_key`, `set_key_password`, `delete_profile`) ; la Promise JS est alors rejetée au lieu de recevoir `{error, code}`.
- `gui.py` : `encrypt` ouvre le dialogue d'enregistrement avant de vérifier regex et verrou.
- `ui/index.html` : ⌘Z restaure aussi les options sans que leur modification ait été historisée ; code mort (`TOKEN_RE`, clés i18n `emails`/`phones`…).
- Regex validées en syntaxe JS côté page, exécutées en syntaxe Python côté moteur.
- `product.md` et `design-system.md` (racine) viennent d'un autre projet DIVE (voir `design/product.md`, `design/ui.md`).

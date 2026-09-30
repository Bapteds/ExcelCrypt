# gui.py

> Application de bureau ExcelCrypt : ouvre une fenêtre native pywebview qui affiche `ui/index.html` et expose à la page une classe `Api` qui délègue tout le travail à `excelcrypt.py`. · Lignes : 650 · Dépendances : stdlib (`json`, `os`, `re`, `subprocess`, `sys`, `threading`, `time`, `pathlib`), `webview` (pywebview) + `webview.dom.DOMEventHandler`, `openpyxl.utils.get_column_letter`, `excelcrypt` (importé sous `ec`).

## Vue d'ensemble

- **Démarrage** : `main()` (`gui.py:629`) instancie `Api`, crée la fenêtre `"ExcelCrypt"` (1320×840, min 1024×660, fond `#F5F7FA`) pointant sur `UI_DIR / "index.html"` avec `js_api=api`, injecte la fenêtre dans `api._window`, puis lance `webview.start(bind, window, debug="--debug" in sys.argv)`. `bind` branche le glisser-déposer natif.
- **Cycle de vie** : la construction de `Api` lit `excelcrypt_gui.json` puis tente de charger la clé. Côté page, `boot()` (`ui/index.html:1406`, déclenché par l'événement `pywebviewready`) appelle `api.get_state()`, puis `list_profiles()`. Si aucune langue n'est enregistrée, la page affiche le choix de langue ; si la clé est verrouillée, la modale de déverrouillage.
- **Où vivent clé et coffre** : uniquement dans l'instance `Api`, côté Python : `_keys` (`ec.Keys`, clé maîtresse dérivée), `_key_path`, `_vault_path`. Par défaut `APP_DIR/excelcrypt.key` et `APP_DIR/excelcrypt.vault` (`ec.DEFAULT_KEY`, `ec.DEFAULT_VAULT`).
- **Principe « la clé ne quitte jamais Python »** : la page ne reçoit que des métadonnées (nom, chemin, `ok`, `protected`, `locked`, nombre d'entrées du coffre) et des valeurs déjà masquées. Tous les attributs d'`Api` sont préfixés par `_` car pywebview expose à JavaScript tout attribut/méthode public (commentaire `gui.py:93`). Le mot de passe de la clé transite de JS vers Python (`unlock_key`, `set_key_password`, `new_key`), jamais l'inverse.
- **Chemins** : `APP_DIR` (`gui.py:29`) = dossier de l'exécutable si l'app est gelée (PyInstaller, `sys.frozen`), sinon dossier de `gui.py`. `UI_DIR` (`gui.py:30`) = `sys._MEIPASS/ui` en mode gelé, sinon `APP_DIR/ui`.

## Fichiers de configuration / état

| Fichier | Constante | Format | Lu | Écrit |
|---|---|---|---|---|
| `excelcrypt_gui.json` | `SETTINGS` (`gui.py:31`) | `{"key": "<chemin>", "vault": "<chemin>", "lang": "fr\|de\|en"}` (`lang` omis tant qu'aucune langue n'est choisie), indentation 2 | `_load_settings` au démarrage | `_save_settings` : après `set_lang`, `choose_key` (succès), `new_key`, `choose_vault`. Erreurs d'écriture ignorées silencieusement. |
| `excelcrypt_profiles.json` | `PROFILES` (`gui.py:32`) | `{"profiles": [ {name, updated, columns, headerRow, opts, ...}, ... ]}`, `ensure_ascii=False`, indentation 2. Le contenu d'un profil est défini par la page ; `gui.py` n'impose que `name` et ajoute `updated` (`"%Y-%m-%d %H:%M"`). `batch_encrypt` lit `columns`, `headerRow`, `opts` (`values`, `regexes`, `detectors`, `maskHeaders`, `propagate` ; un `readable` des anciens profils est ignoré). | `_profiles` à chaque appel | `save_profile`, `delete_profile` |
| Clé (`*.key`) | `_key_path` | géré par `excelcrypt.py` | `ec.Keys.from_file`, `ec.key_is_protected` | `ec.generate_key` (`new_key`), `ec.write_key` (`set_key_password`) |
| Coffre (`*.vault`) | `_vault_path` | géré par `excelcrypt.py` | `ec.Vault(...)` (`get_state`, aperçu) | indirectement par `ec.encrypt_file` |

Les deux JSON sont écrits à côté de l'exécutable/du script (`APP_DIR`), pas dans un dossier utilisateur.

## Sections

### Constantes et configuration (`gui.py:29-54`)

- `APP_DIR`, `UI_DIR`, `SETTINGS`, `PROFILES` — voir ci-dessus.
- `PREVIEW_ROWS = 500` — `gui.py:33` — nombre maximal de lignes lues pour l'aperçu.
- `LANGS = ("fr", "de", "en")` — `gui.py:34` — langues acceptées.
- `SUPPORTED = ec.EXCEL_EXT | ec.CSV_EXT` — `gui.py:35` — `.xlsx .xlsm .csv .tsv .txt`.
- `DIALOG_TEXT` — `gui.py:37` — libellés des filtres des dialogues natifs par langue (clés `sheets`, `all`, `key`, `vault`) et suffixes des noms de fichiers de sortie (`enc` : `chiffre`/`geschuetzt`/`protected` ; `dec` : `dechiffre`/`wiederhergestellt`/`restored`). Sans accents dans les suffixes : pywebview n'accepte que lettres et espaces dans les libellés de filtres.
- `SENSITIVE_HINTS` — `gui.py:47` — regex insensible à la casse (FR/EN/DE) sur les en-têtes de colonnes évoquant des données personnelles (nom, e-mail, téléphone, adresse, IBAN, SIRET, NIR, naissance, Steuer, Kreditkarte…). Utilisée pour le drapeau `suggested` de `load`.

### Fonctions utilitaires (`gui.py:57-67`)

- `error(code: str, message: str, **params) -> dict` — `gui.py:57` — construit `{"error": message, "code": code, "params": params}`. `code` + `params` sont traduits côté page (`errText`, `ui/index.html:1334`, clé `err_<code>`), `error` (français) sert de repli.
- `from_exc(e: ec.ExcelCryptError) -> dict` — `gui.py:62` — même forme à partir d'une exception du moteur (`str(e)`, `e.code`, `e.params`).
- `file_info(p: Path) -> dict` — `gui.py:66` — `{"name", "path", "dir", "bytes"}` (`stat().st_size`, `None` si le fichier a disparu).
- `with_suffix(p, suffix) -> (Path, dict | None)` — `gui.py:74` — impose une extension ; si elle change et que le fichier final existe déjà, renvoie l'erreur `file_exists` (le dialogue natif n'a confirmé l'écrasement que pour le nom tapé).
- `is_output_of(p, kind) -> bool` — `gui.py:85` — vrai si le nom se termine par `_<suffixe enc|dec>` dans l'une des 3 langues (`DIALOG_TEXT`) ; sert à exclure des lots les sorties d'un lot précédent.

### Classe `Api` — construction et état (`gui.py:90-180`)

- `class Api` — `gui.py:90` — objet passé en `js_api`. Ses méthodes publiques sont appelables depuis JS via `window.pywebview.api.<nom>(...)` et renvoient une Promise.
- `__init__(self)` — `gui.py:96` — initialise `_window=None`, `_keys=None`, chemins par défaut, `_file=None`, `_sheets={}` (valeurs brutes typées de l'aperçu, par feuille), `_header_row=1`, `_lang=None` (premier lancement), `_busy=threading.Lock()`, `_vault_count` (cache de `get_state`) ; appelle `_load_settings()` puis `_load_key()`.
- `_load_settings(self)` — `gui.py:111` — lit `SETTINGS` ; met à jour `_key_path`, `_vault_path`, `_lang` (seulement si dans `LANGS`). `OSError`/`ValueError` ignorées.
- `_save_settings(self)` — `gui.py:120` — écrit `SETTINGS` (`key`, `vault`, `lang` si défini). `OSError` ignorée.
- `_load_key(self, password: str | None = None) -> ec.ExcelCryptError | None` — `gui.py:129` — remet `_keys` à `None` ; si le fichier clé n'existe pas → `None` ; si la clé est protégée (`ec.key_is_protected`) et qu'aucun mot de passe n'est fourni → `None` (clé « verrouillée », pas une erreur) ; sinon `ec.Keys.from_file(path, password)`. Renvoie l'`ExcelCryptError` éventuelle au lieu de la lever.
- `_t` (propriété) — `gui.py:143` — `DIALOG_TEXT[self._lang or "fr"]`.
- `_file_types(self, kind: str = "sheets") -> tuple` — `gui.py:146` — filtres des dialogues : `sheets` → tableurs `(*.xlsx;*.xlsm;*.csv;*.tsv;*.txt)` + « tous les fichiers » ; `key` → `(*.key)` + « tous les fichiers » ; `vault` → `(*.vault)` seul.
- `set_lang(self, lang: str) -> dict` — `gui.py:152` — valide contre `LANGS`, mémorise et sauvegarde. `{"ok": True}` / `{"ok": False}`.
- `get_state(self) -> dict` — `gui.py:159` — état global pour la page (forme dans le tableau API). Si une clé est chargée et le coffre existe, ouvre `ec.Vault(self._vault_path, self._keys)` pour compter les entrées ; `ExcelCryptError` → `vault.ok = False`. Le nombre d'entrées est mis en cache dans `_vault_count` (`gui.py:106`) avec la signature (chemin, mtime, taille, objet clé) : le coffre n'est déchiffré que s'il a changé. `OSError` → `vault.ok = False`.

### Dialogues natifs et système (`gui.py:183-215`)

- `_open_dialog(self, file_types=None, directory="") -> Path | None` — `gui.py:183` — `create_file_dialog(FileDialog.OPEN)` ; premier fichier choisi ou `None`.
- `_save_dialog(self, filename: str, directory: str = "", file_types=None) -> Path | None` — `gui.py:188` — `FileDialog.SAVE` avec nom proposé ; gère un retour `str` ou tuple selon la plateforme. La confirmation d'écrasement est celle du dialogue natif.
- `_folder_dialog(self, directory: str = "") -> Path | None` — `gui.py:195` — `FileDialog.FOLDER`, même normalisation.
- `pick_file(self) -> str | None` — `gui.py:201` — dialogue d'ouverture filtré sur les tableurs ; chemin ou `None`.
- `reveal(self, path: str) -> None` — `gui.py:205` — affiche le fichier/dossier dans le gestionnaire de fichiers : macOS `open -R` (fichier) / `open` (dossier), Windows `explorer /select,`, autres `xdg-open` sur le dossier parent. `OSError` ignorée. `subprocess.run` bloquant.

### Clé et coffre (`gui.py:218-279`)

- `choose_key(self) -> dict` — `gui.py:218` — dialogue d'ouverture `*.key` dans le dossier de la clé courante. Annulation → `{"cancelled": True}`. Tente `_load_key()` sur le nouveau chemin ; en cas d'erreur, restaure l'ancien chemin, recharge l'ancienne clé et renvoie `from_exc(err)`. Succès → sauvegarde des réglages, `{"ok": True, "state": ...}`. Une clé protégée est acceptée et reste verrouillée (`state.key.locked`).
- `unlock_key(self, password: str) -> dict` — `gui.py:232` — `_load_key(password or None)`. Erreur moteur (mauvais mot de passe…) → `from_exc` ; mot de passe vide sur clé protégée → `error("key_locked", ...)`. Succès → `{"ok": True, "state": ...}`.
- `set_key_password(self, password: str) -> dict` — `gui.py:238` — ajoute, change ou retire (chaîne vide) le mot de passe via `ec.write_key(self._key_path, self._keys.master, password or None)` ; la clé maîtresse ne change pas. Sans clé chargée → `error("no_key")`. `OSError` → `write_denied`.
- `new_key(self, password: str = "") -> dict` — `gui.py:248` — dialogue d'enregistrement (`excelcrypt.key` proposé), suffixe imposé par `with_suffix` (`file_exists` si le nom corrigé existe), `ec.generate_key(p, force=True, password=...)` (écrase le fichier). Si le coffre courant existe, bascule `_vault_path` sur `<nouvelle clé>.vault`, ou `<nouvelle clé> (2).vault`… si ce nom est déjà pris (un coffre appartient à sa clé). Recharge la clé, sauvegarde les réglages, renvoie `{"ok": True, "state": ...}`. `OSError` → `write_denied`.
- `choose_vault(self) -> dict` — `gui.py:271` — dialogue d'**enregistrement** (permet de désigner un coffre existant ou nouveau), suffixe forcé à `.vault` (sans refus si le fichier existe : ouvrir un coffre existant est voulu), sauvegarde. `{"ok": True, "state": ...}` ou `{"cancelled": True}`.

### Profils (`gui.py:282-312`)

- `_profiles(self) -> list[dict]` — `gui.py:282` — liste `profiles` de `PROFILES` ; `[]` si absent ou illisible.
- `_write_profiles(self, profiles: list[dict]) -> None` — `gui.py:288` — réécrit tout le fichier. Laisse passer `OSError`.
- `list_profiles(self) -> list[dict]` — `gui.py:291` — profils triés par nom (`casefold`).
- `save_profile(self, profile: dict) -> dict` — `gui.py:294` — nom obligatoire (sinon `error("profile_name")`) ; remplace un profil de même nom (comparaison insensible à la casse), ajoute `updated`. `OSError` → `error("write_denied", name=...)`. Renvoie `{"ok": True, "profiles": [...]}`.
- `delete_profile(self, name: str) -> dict` — `gui.py:306` — supprime par nom sans tenir compte de la casse (même règle que `save_profile`), `{"ok": True, "profiles": [...]}` ; `OSError` → `write_denied`.
- `check_regexes(self, patterns) -> dict` — `gui.py:357` — compile chaque motif avec `re` (la syntaxe qui sera réellement appliquée) et renvoie `{motif: message}` pour les motifs invalides. Appelée par `validateRegex` (`ui/index.html:1873`).

### Lecture et aperçu (`gui.py:315-423`)

- `load(self, path: str, header_row: int = 1, remember: bool = True) -> dict` — `gui.py:315` — `ec.read_preview(p, max(1, header_row), PREVIEW_ROWS)`. `ExcelCryptError` → `from_exc` ; toute autre exception (fichier corrompu, protégé…) → `error("read_failed", detail=...)`. Si `remember`, mémorise `_file`, `_sheets` (valeurs brutes), `_header_row`. Pour chaque feuille et colonne calcule : `idx`, `letter` (`get_column_letter`), `name`, `unique` (nb de valeurs texte distinctes), `empty`, `filled`, `example` (60 caractères max), `detected` (`ec.detect_column`, seulement si `remember`), `suggested` (`SENSITIVE_HINTS` sur l'en-tête ou détecteur trouvé). Renvoie `{"file": file_info | {"ext"}, "sheets": [{"name", "total", "columns", "rows"}]}` où `rows` est converti en texte (`ec.value_as_text`). `remember=False` sert à consulter un fichier restauré sans remplacer le fichier de travail.
- `parse_refs(self, sheet: str, text: str) -> dict` — `gui.py:367` — valide une saisie de plages (`B5`, `A2:C40`, `12-30`, `D:F`, nom de colonne) via `ec.parse_refs(text, header)` en utilisant l'en-tête mémorisé de la feuille. `{"selection": sel.to_dict(), "errors": [...]}`.
- `_mask_options(opts: dict)` (staticmethod) — `gui.py:374` — à partir de `opts` : `literals` (valeurs non vides de `values`), compile chaque regex de `regexes` (les invalides vont dans `errors {regex: message}`), filtre `detectors` sur `ec.DETECTORS`, puis `ec.build_detectors(keys, valid)`. Renvoie `(literals, detectors, errors)`.
- `preview(self, sheet: str, selections: dict, opts: dict) -> dict` — `gui.py:386` — rend les lignes de l'aperçu « telles que l'IA les verra » avec de vrais jetons, via `ec.Tokenizer(self._keys, dry_run=True)` (le coffre n'est ni lu ni écrit). Étapes : sélections par feuille (`ec.SheetSelection.from_dict`), en-têtes masqués si `maskHeaders` (`mask_cell` sur les colonnes sélectionnées), propagation si `propagate` (`ec.Propagation` alimentée avec les cellules sélectionnées de **toutes** les feuilles, puis `compile()`), puis `tk.mask_cell` cellule par cellule. Feuille inconnue → `{"rows": []}`. Renvoie `{"rows", "header", "regexErrors", "hasKey"}`. Le numéro de ligne Excel est `self._header_row + 1 + index`.

### Chiffrer / déchiffrer (`gui.py:426-539`)

- `_progress_cb(self)` — `gui.py:426` — fabrique un callback `cb(done, total)` qui appelle `window.onTaskProgress(<pourcentage>)` au plus toutes les 0,1 s (le dernier palier n'est donc pas garanti).
- `_run_options(self, selection: dict, opts: dict)` — `gui.py:436` — `_mask_options` + conversion des sélections ; renvoie `(literals, detectors, errors, select)` où `select(sheet, header)` renvoie la `SheetSelection` de la feuille ou une sélection vide.
- `scan(self, selection: dict, opts: dict, header_row: int = 1) -> dict` — `gui.py:441` — contrôle avant envoi sur le fichier complet (aucune écriture). Erreurs : `no_file`, `regex_invalid` (`pattern`), `busy`. Prend `_busy` (non bloquant), émet `onTaskStart('scan', nom)`, appelle `ec.scan_file(file, select, literals, detectors, header_row, progress=..., mask_headers=..., propagate=...)`. `ExcelCryptError` → `from_exc`, autre → `read_failed`. Renvoie `{"ok": True, "findings": [...]}` (liste renvoyée par le moteur).
- `encrypt(self, selection: dict, opts: dict, header_row: int = 1) -> dict` — `gui.py:463` — prérequis `no_key`, `no_file`, puis `regex_invalid` et `busy` (`_busy.locked()`) **avant** tout dialogue ; dialogue d'enregistrement proposant `ec.default_output(src, suffixe enc)` dans le dossier source (annulation → `{"cancelled": True}`) ; extension de la source imposée par `with_suffix` (`file_exists`) ; refuse la sortie identique à l'original (`same_output`) ; prise du verrou. Émet `onTaskStart('encrypt', nom)` et appelle `ec.encrypt_file(src, out, keys, vault_path, select, literals, detectors, header_row, progress, mask_headers, propagate)`. Erreurs : `from_exc`, `PermissionError` → `write_denied` (fichier ouvert dans Excel), autre → `encrypt_failed`. Dans tous les cas libère le verrou. Renvoie `{"ok", "masked", "unique", "output": file_info, "key", "vault", "state"}` (`unique` = nombre total d'entrées du coffre selon `encrypt_file`).
- `decrypt(self, path: str | None = None) -> dict` — `gui.py:502` — prérequis `no_key`, `vault_missing`, `busy` avant tout dialogue ; source = `path` (glisser-déposer) ou dialogue d'ouverture ; `ec.check_format(src)` ; dialogue d'enregistrement avec suffixe `dec`, extension imposée par `with_suffix` (`file_exists`) ; `same_output` ; prise du verrou. Émet `onTaskStart('decrypt', nom)`, appelle `ec.decrypt_file(src, out, keys, vault_path, progress=...)`. Erreurs : `from_exc`, `write_denied`, `decrypt_failed`. Renvoie `{"ok", "restored", "unknown" (50 premiers jetons inconnus triés), "unknownCount", "source", "output"}`.

### Traitement par lot (`gui.py:542-626`)

- `_pick_batch_folders(self, kind)` — `gui.py:542` — dialogue dossier source (ouvert sur le dossier du fichier courant) ; liste non récursive des fichiers `SUPPORTED` **hors `.txt`**, en excluant les noms commençant par `~$` ou `.` et les sorties ExcelCrypt de ce type (`is_output_of(p, kind)`, `kind` = `enc` ou `dec`) ; si des fichiers existent, dialogue dossier destination. Renvoie `(src, dst, files)` ; `(None, None, [])` si annulé, `(src, None, [])` si dossier vide.
- `batch_encrypt(self, profile_name: str) -> dict` — `gui.py:554` — protège tout un dossier avec un profil ; colonnes retrouvées par nom via `ec.profile_selection(cols, header)`. Profil retrouvé sans tenir compte de la casse. Erreurs : `no_key`, `profile_missing`, `batch_empty`, `busy` ; annulation → `{"cancelled": True}`. Les erreurs de regex du profil sont ignorées (regex invalides simplement écartées). Pour chaque fichier : `onBatchProgress(i, n, nom)`, `ec.scan_file` (compte des fuites) puis `ec.encrypt_file` vers `dst / default_output(f, enc)`. Erreurs par fichier collectées dans `results` sans interrompre le lot. Fin : `onBatchProgress(n, n, '')`. Renvoie `{"ok", "kind": "encrypt", "results": [{name, ok, masked, output, leaks} | {name, ok: False, error, code, params}], "folder", "state"}`.
- `batch_decrypt(self) -> dict` — `gui.py:597` — restaure un dossier. Erreurs : `no_key`, `vault_missing`, `batch_empty`, `busy`. Par fichier : `ec.decrypt_file` vers `dst / default_output(f, dec)`. Renvoie `{"ok", "kind": "decrypt", "results": [{name, ok, restored, output, unknown}|erreur], "folder", "state"}`.

### Lancement (`gui.py:629-650`)

- `main()` — `gui.py:629` — voir Vue d'ensemble.
- `on_drop(event)` (fonction interne) — `gui.py:637` — lit `event["dataTransfer"]["files"][*]["pywebviewFullPath"]` (chemin complet fourni par pywebview) et transmet **le premier** chemin à `window.onFileDropped(...)`.
- `bind(win)` (fonction interne) — `gui.py:643` — appelée par `webview.start` une fois la fenêtre prête : `win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)` (preventDefault et stopPropagation).
- `if __name__ == "__main__": main()` — `gui.py:649`.

## API exposée au JavaScript

Toutes les méthodes s'appellent `window.pywebview.api.X(...)` ; la page stocke cet objet dans `api` (`ui/index.html:1408`). Les erreurs ont la forme `{error, code, params}` ; les annulations `{cancelled: true}`.

| Méthode | Paramètres | Retour | Appels `excelcrypt.py` | Appelant(s) `ui/index.html` |
|---|---|---|---|---|
| `set_lang` (`gui.py:152`) | `lang` | `{ok}` | — | `setLang` l.1367 |
| `get_state` (`gui.py:159`) | — | `{platform, lang, key:{name,path,ok,exists,protected,locked}, vault:{name,path,exists,count,ok}, detectors:[clés]}` | `key_is_protected`, `Vault`, `DETECTORS` | `boot` l.1409 |
| `pick_file` (`gui.py:201`) | — | `str \| null` | — | `pickAndLoad` l.1465 |
| `reveal` (`gui.py:205`) | `path` | `null` | — | l.1975, 2059, 2121, 2451 |
| `choose_key` (`gui.py:218`) | — | `{ok, state}` / `{cancelled}` / erreur | `Keys.from_file`, `key_is_protected` | l.2027 |
| `unlock_key` (`gui.py:232`) | `password` | `{ok, state}` / erreur (`key_locked`, moteur) | `Keys.from_file` | l.2212 |
| `set_key_password` (`gui.py:238`) | `password` (vide = retirer) | `{ok, state}` / `no_key` | `write_key` | l.2242, 2253 |
| `new_key` (`gui.py:248`) | `password=""` | `{ok, state}` / `{cancelled}` | `generate_key`, `Keys.from_file` | l.2051 |
| `choose_vault` (`gui.py:271`) | — | `{ok, state}` / `{cancelled}` | (via `get_state`) | l.2063 |
| `list_profiles` (`gui.py:291`) | — | `[profil]` | — | `loadProfiles` l.2310 |
| `save_profile` (`gui.py:294`) | `profile` (dict) | `{ok, profiles}` / `profile_name`, `write_denied` | — | l.2385 |
| `delete_profile` (`gui.py:306`) | `name` | `{ok, profiles}` | — | l.2399 |
| `load` (`gui.py:315`) | `path, header_row=1, remember=True` | `{file:{name,path,dir,bytes,ext}, sheets:[{name,total,columns:[{idx,letter,name,unique,empty,filled,example,detected,suggested}],rows}]}` / erreur | `read_preview`, `detect_column`, `value_as_text` | `loadFile` l.1470 ; aperçu restauré l.1950 (`remember=false`) |
| `check_regexes` (`gui.py:357`) | `patterns` | `{motif: message}` | — (`re.compile`) | `validateRegex` l.1873 |
| `parse_refs` (`gui.py:367`) | `sheet, text` | `{selection, errors}` | `parse_refs`, `SheetSelection.to_dict` | l.1799 |
| `preview` (`gui.py:386`) | `sheet, selections, opts` | `{rows, header, regexErrors, hasKey}` | `build_detectors`, `Tokenizer(dry_run=True)`, `SheetSelection.from_dict`, `Propagation`, `value_as_text` | l.1844 |
| `scan` (`gui.py:441`) | `selection, opts, header_row=1` | `{ok, findings}` / erreur | `scan_file` | l.1914 (`doEncrypt`) |
| `encrypt` (`gui.py:463`) | `selection, opts, header_row=1` | `{ok, masked, unique, output, key, vault, state}` / `{cancelled}` / erreur | `default_output`, `encrypt_file` | l.1922 (`doEncrypt`) |
| `decrypt` (`gui.py:502`) | `path=null` | `{ok, restored, unknown[≤50], unknownCount, source, output}` / `{cancelled}` / erreur | `check_format`, `default_output`, `decrypt_file` | l.1945 (`doDecrypt`) |
| `batch_encrypt` (`gui.py:554`) | `profile_name` | `{ok, kind:"encrypt", results, folder, state}` / `{cancelled}` / erreur | `profile_selection`, `scan_file`, `encrypt_file`, `default_output` | `runBatch` l.2433 |
| `batch_decrypt` (`gui.py:597`) | — | `{ok, kind:"decrypt", results, folder, state}` / `{cancelled}` / erreur | `decrypt_file`, `default_output` | `runBatch` l.2433 |

Codes d'erreur émis par `gui.py` : `key_locked`, `no_key`, `profile_name`, `write_denied`, `read_failed`, `regex_invalid`, `busy`, `no_file`, `same_output`, `vault_missing`, `encrypt_failed`, `decrypt_failed`, `profile_missing`, `batch_empty` (tous présents en `err_<code>` dans `ui/index.html`), plus les codes des `ExcelCryptError` du moteur relayés par `from_exc`.

## Événements Python → JS

Tous via `self._window.evaluate_js(...)` (ou `window.evaluate_js` dans `main`), noms de fichiers échappés par `json.dumps`.

| Appel JS | Émis par | Récepteur `ui/index.html` |
|---|---|---|
| `window.onTaskStart(kind, name)` (`kind` ∈ `scan`, `encrypt`, `decrypt`) | `scan` `gui.py:451`, `encrypt` `gui.py:485`, `decrypt` `gui.py:527` | l.1932 (affiche la modale d'attente) |
| `window.onTaskProgress(pct)` | `_progress_cb` `gui.py:433` (limité à 10/s) | l.1933 (barre de progression) |
| `window.onBatchProgress(i, n, name)` | `batch_encrypt` `gui.py:580`, `gui.py:592` ; `batch_decrypt` `gui.py:613`, `gui.py:623` | l.2454 |
| `window.onFileDropped(path)` | `on_drop` `gui.py:641` | l.2515 (ouvre le fichier, ou le restaure en mode `restore`) |

## Points d'attention / pièges

- **Threading** : pywebview exécute chaque appel `js_api` dans un thread séparé. Seules les opérations longues (`scan`, `encrypt`, `decrypt`, `batch_*`) prennent `_busy` en mode non bloquant et renvoient `busy` si occupé. `load`, `preview`, `parse_refs`, `get_state` ne sont pas verrouillés et partagent `_sheets`, `_file`, `_keys` ; la page gère elle-même les réponses obsolètes de `preview` (compteur `aiSeq`). `evaluate_js` est appelé depuis ces threads de travail.
- **Ordre des contrôles** : `encrypt` et `decrypt` vérifient regex et verrou (`_busy.locked()`) **avant** d'ouvrir un dialogue, puis prennent le verrou après. Garder cet ordre pour toute nouvelle action longue.
- **Dialogues natifs** : les libellés de filtres doivent contenir uniquement lettres et espaces (d'où `DIALOG_TEXT` sans ponctuation). Le retour de `create_file_dialog` est une chaîne ou un tuple selon la plateforme, normalisé dans `_save_dialog`/`_folder_dialog`. `choose_vault` utilise un dialogue d'enregistrement, pas d'ouverture.
- **Extensions forcées** : `.key`, `.vault`, et pour chiffrer/déchiffrer l'extension de la source (`with_suffix`). Toujours passer par `with_suffix` : si l'extension corrigée désigne un fichier existant, l'action est refusée (`file_exists`) au lieu d'écraser sans confirmation. Exception : `choose_vault`.
- **`new_key`** écrase le fichier clé choisi dans le dialogue (`force=True`, écrasement confirmé par le dialogue natif) ; si l'ancien coffre existe, un nouveau nom de coffre libre est choisi.
- **Exceptions** : toute méthode exposée doit renvoyer `{error, code, params}` plutôt que lever (une exception rejette la Promise JS sans message traduit). Les écritures disque capturent `OSError` → `write_denied`.
- **Chemins** : les JSON de réglages et profils ainsi que la clé/le coffre par défaut sont dans `APP_DIR` (à côté du script ou de l'exécutable gelé ; dans un bundle macOS, `sys.executable` est sous `Contents/MacOS`). Aucune écriture si le dossier est en lecture seule (échec silencieux pour les réglages, `write_denied` pour `save_profile`).
- **Lot** : non récursif, `.txt` exclu, fichiers `~$*` (verrous Office) et cachés ignorés ; les sorties d'un lot précédent (`_<suffixe>` dans l'une des 3 langues) sont ignorées, donc un dossier de destination identique au dossier source ne provoque pas de double traitement. `batch_encrypt` fait un scan puis un chiffrement par fichier (lecture double).
- **`scan`/`encrypt` utilisent le `header_row` passé en paramètre**, tandis que `preview` et `parse_refs` s'appuient sur l'état mémorisé par le dernier `load(remember=True)`.
- **Noms de profils** : insensibles à la casse partout (enregistrement, suppression, lot).
- **i18n des erreurs** : le texte `error` est toujours en français ; la traduction passe par `code` + `params` et `errText` (`ui/index.html:1334`). Tout nouveau code doit être ajouté en `err_<code>` dans les trois langues de `I18N`.
- **Aperçu** : `detected` n'est calculé que pour `remember=True` ; `PREVIEW_ROWS = 500` limite les statistiques de colonnes (`unique`, `empty`…) aux 500 premières lignes, `total` venant du moteur.
- **Coût de `get_state`** : le coffre n'est déchiffré que si sa signature a changé (cache `_vault_count`).
- **Mode debug** : `python gui.py --debug` active les outils de développement de la webview.

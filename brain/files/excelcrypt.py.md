# excelcrypt.py
> Cœur métier et CLI de pseudonymisation réversible de fichiers Excel/CSV (jetons HMAC, coffre AES-GCM, clé optionnellement protégée par Argon2id). · Lignes : 1247 · Dépendances : `cryptography` (AESGCM, HKDF, Argon2id, InvalidTag), `openpyxl` (obligatoire, `sys.exit` si absent — `excelcrypt.py:56-60`), stdlib (argparse, base64, csv, datetime, getpass, hashlib, hmac, json, os, re, sys, unicodedata, dataclasses, pathlib, typing).

## Vue d'ensemble
Le module remplace des valeurs sensibles d'un classeur `.xlsx/.xlsm` ou d'un CSV par des jetons déterministes (`ENC_` + 16 hex, ou jetons « lisibles » `PREFIXE_0042`). Le jeton est un HMAC-SHA256 tronqué de la valeur typée, calculé avec une sous-clé dérivée par HKDF de la clé maître (32 octets). La correspondance jeton -> valeur typée est stockée dans un coffre `.vault` chiffré AES-256-GCM avec une seconde sous-clé.

- **Encrypt** (`encrypt_file`) : ouvre le coffre, appelle `_process` (1re passe optionnelle de relevé des valeurs masquées pour la « propagation », 2e passe de masquage cellule par cellule selon une `SheetSelection`, des littéraux, des détecteurs et la propagation), écrit le fichier de sortie puis sauvegarde le coffre (atomique).
- **Scan** (`scan_file`) : même `_process` en mode simulation (clé aléatoire, pas de coffre), puis relève ce qui ressemble encore à une donnée personnelle hors des zones masquées.
- **Decrypt** (`decrypt_file`) : cherche tout jeton (`ENC_…` ou lisible) n'importe où dans chaque cellule / nom de feuille et le remplace par la valeur du coffre (typée si la cellule entière est un jeton, texte sinon).

L'interface graphique (`gui.py`) importe le module (`import excelcrypt as ec`) ; toute la cryptographie reste ici.

## Constantes et formats
| Nom | Valeur / rôle | Ligne |
|---|---|---|
| `DEFAULT_KEY` | `"excelcrypt.key"` | `excelcrypt.py:62` |
| `DEFAULT_VAULT` | `"excelcrypt.vault"` | `excelcrypt.py:63` |
| `KEY_ENV` | `"EXCELCRYPT_KEY"` : clé base64 (ou texte de clé protégée) via l'environnement | `excelcrypt.py:64` |
| `PASSWORD_ENV` | `"EXCELCRYPT_PASSWORD"` : mot de passe de la clé fichier | `excelcrypt.py:65` |
| `TOKEN_PREFIX` | `"ENC_"` | `excelcrypt.py:67` |
| `TOKEN_HEX_LEN` | `16` (64 bits) | `excelcrypt.py:68` |
| `TOKEN_RE` | `ENC_` + 16 hex, non suivi d'un hex, insensible à la casse ; groupe 1 = hex | `excelcrypt.py:69` |
| `ALIAS_RE` | jeton lisible `PREFIXE_\d{4,}` : préfixe `[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*`, bornes `(?<![\w])` / `(?!\w)` ; groupe 1 = préfixe, 2 = numéro | `excelcrypt.py:71` |
| `ANY_TOKEN_RE` | union `TOKEN_RE | ALIAS_RE`, IGNORECASE | `excelcrypt.py:72` |
| `EMAIL_RE` | `[\w.+-]+@[\w-]+(?:\.[\w-]+)+` | `excelcrypt.py:74` |
| `PHONE_FR_RE` | `+33`/`0` + 9 chiffres, séparateur identique partout (backref `\1`), isolé | `excelcrypt.py:76` |
| `PHONE_DE_RE` | `+49`/`0049`/`0` (+ `(0)` optionnel) + indicatif 2-5 chiffres + abonné, refuse les groupes de chiffres adjacents | `excelcrypt.py:79-80` |
| `VAULT_MAGIC` | `b"XLCV1"` (en-tête du coffre et AAD AES-GCM) | `excelcrypt.py:82` |
| `KEY_MAGIC` | `"EXCELCRYPT-KEY-2"` (en-tête de clé protégée et AAD AES-GCM) | `excelcrypt.py:83` |
| `EXCEL_EXT` | `{".xlsx", ".xlsm"}` | `excelcrypt.py:84` |
| `CSV_EXT` | `{".csv", ".tsv", ".txt"}` | `excelcrypt.py:85` |
| `CSV_SHEET` | `"(csv)"` : nom de feuille virtuel d'un CSV | `excelcrypt.py:86` |
| `PROPAGATE_MIN_LEN` | `3` : valeurs plus courtes jamais propagées | `excelcrypt.py:87` |
| `ColumnSelector` | alias de type `Callable[[str, list], SheetSelection | set[int] | None]` (None = ignorer la feuille) | `excelcrypt.py:91` |
| `Progress` | `Callable[[int, int], None]` (fait, total) | `excelcrypt.py:92` |
| `_REF_CELL` | `([A-Za-z]{1,3})(\d+)` | `excelcrypt.py:148` |
| `DETECTORS` | dict clé -> `Detector` (voir Détecteurs) | `excelcrypt.py:283` |
| `ARGON2` | `{"iterations": 3, "lanes": 4, "memory_cost": 64*1024}` (64 Mio) | `excelcrypt.py:383` |

**Format du fichier clé** (`write_key`, `excelcrypt.py:445`) :
- Non protégé : `base64(master 32 octets)` + `\n`.
- Protégé : ligne `EXCELCRYPT-KEY-2`, puis une ligne JSON `{"kdf":"argon2id","argon2":{…},"salt":b64(16 o),"nonce":b64(12 o),"ct":b64(AESGCM(master))}`. Clé AES = Argon2id(mot de passe, sel, paramètres stockés) ; AAD = `KEY_MAGIC`. Les paramètres Argon2 sont relus depuis le fichier (`excelcrypt.py:436`).
- Écriture via `.tmp` + `chmod 0600` (erreur ignorée) + `os.replace`.

**Format du coffre** (`Vault.save`, `excelcrypt.py:519`) : `b"XLCV1"` + nonce 12 o + `AESGCM(vault_key).encrypt(nonce, json, AAD=b"XLCV1")`. JSON v2 compact UTF-8 : `{"v":2,"entries":{hex:{"t":type,"v":valeur}},"aliases":{hex:"PREFIXE_0042"},"counters":{prefixe:n}}`. Format 1 (hérité) : le JSON est directement le dict `entries` (`excelcrypt.py:515-516`). Nouveau nonce aléatoire à chaque sauvegarde ; écriture atomique `.tmp` + `os.replace` (pas de chmod).

**Valeur typée** (`pack_value`, `excelcrypt.py:577`) : `t` ∈ `bool`, `int`, `float` (`repr`), `datetime`, `date`, `time` (ISO), `str` (défaut, `str(v)`).

## Sections

### Erreurs
- `class ExcelCryptError(Exception)` — `excelcrypt.py:95` — erreur utilisateur ; message français affiché tel quel par la CLI.
  - `__init__(self, message: str, code: str | None = None, **params)` — `excelcrypt.py:99` — stocke `code` et `params` pour la traduction côté GUI. Codes utilisés : `regex_invalid`, `key_invalid`, `key_missing`, `key_locked`, `key_bad_password`, `vault_invalid`, `vault_bad_key`, `collision`, `file_missing`, `xls_unsupported`, `format_unsupported`, `vault_missing`. Plusieurs erreurs n'ont pas de code (clé déjà existante, aucune clé trouvée, mots de passe différents, références non comprises, rien à masquer, détecteur inconnu).

### Sélection de cellules
- `@dataclass class SheetSelection` — `excelcrypt.py:108-109` — cellules à masquer (indices 1-based) : `cols: set[int]`, `rows: list[(a,b)]` (plages inclusives), `cells: set[(r,c)]`, `rects: list[(r1,c1,r2,c2)]`.
  - `__bool__(self)` — `excelcrypt.py:117` — vrai si l'un des quatre ensembles est non vide.
  - `has(self, r, c)` — `excelcrypt.py:120` — appartenance d'une cellule (colonne, cellule, plage de lignes ou rectangle).
  - `update(self, other)` — `excelcrypt.py:127` — fusion en place, retourne `self` (les listes peuvent contenir des doublons).
  - `from_dict(cls, d)` — `excelcrypt.py:134-135` — construit depuis un dict JSON (clés absentes tolérées) ; conversion `int`.
  - `to_dict(self)` — `excelcrypt.py:143` — sérialisation JSON (cols et cells triées).
- `parse_refs(text, header=None) -> (SheetSelection, list[str])` — `excelcrypt.py:151` — lit une liste séparée par `,` `;` ou saut de ligne. Ordre de priorité : nom d'en-tête (strip + casefold) > lignes `12`, `12-30`, `12:30` (0 refusé) > cellule `B5` > zone `A2:C40` (normalisée min/max) > colonnes `D` ou `D:F`. Retourne aussi les jetons non compris. Piège : un en-tête nommé comme une lettre (« A ») ou un nombre l'emporte sur l'interprétation Excel.
- `profile_selection(columns, header) -> SheetSelection` — `excelcrypt.py:186` — noms de colonnes d'un profil (casse et espaces ignorés) -> `cols`. Les noms absents sont ignorés silencieusement.

### Détecteurs
- `_digits(s)` — `excelcrypt.py:196` — ne garde que les chiffres.
- `_luhn(num)` — `excelcrypt.py:200` — somme de contrôle de Luhn (chaîne de chiffres).
- `_iban_ok(s)` — `excelcrypt.py:211` — longueur 15-34 après suppression des espaces, mod 97 == 1. Lève `ValueError` si caractère non alphanumérique (le regex en amont l'évite).
- `_card_ok(s)` — `excelcrypt.py:219` — 13-19 chiffres, premier chiffre 2-6, Luhn.
- `_steuer_id_ok(s)` — `excelcrypt.py:224` — Steuer-ID allemand : 11 chiffres, pas de 0 initial, ISO 7064 MOD 11,10.
- `_nir_ok(s)` — `excelcrypt.py:237` — NIR français 15 caractères, Corse 2A->19 / 2B->18, clé = 97 - (corps mod 97).
- `_rvnr_ok(s)` — `excelcrypt.py:248` — Rentenversicherungsnummer : `\d{8}[A-Z]\d{3}`, lettre convertie en rang sur 2 chiffres, poids `2,1,2,5,7,1,2,1,2,1,2,1`, somme des chiffres des produits mod 10.
- `_siret_ok(s)` — `excelcrypt.py:259` — 14 chiffres + Luhn.
- `@dataclass(frozen=True) class Detector` — `excelcrypt.py:264-265` — `key`, `prefix` (préfixe des jetons lisibles), `regex`, `check` optionnel.
  - `matches(self, text)` — `excelcrypt.py:271` — générateur des `re.Match` validés par `check`.
  - `sub(self, text, repl)` — `excelcrypt.py:276` — remplace chaque correspondance validée par `repl(valeur, prefix)` ; fonction interne `one(m)` — `excelcrypt.py:277`.
- `DETECTORS` — `excelcrypt.py:283-297` — ordre (important pour `detect_column`) : `email`/EMAIL, `phone_fr`/PHONE, `phone_de`/PHONE, `iban`/IBAN (+`_iban_ok`), `card`/CARD (+`_card_ok`), `vat`/VAT (DE, FR, ATU, IT, ES, NL, BE, LU, CHE ; sans somme de contrôle), `steuer_id`/TAXID, `nir`/SSN (IGNORECASE), `rvnr`/SSN, `siret`/SIRET.
- `build_detectors(keys=None, regexes=None) -> list[Detector]` — `excelcrypt.py:300` — clés connues + regex utilisateur (`Detector("regex","PATTERN",…)`). Lève `ExcelCryptError` si clé inconnue (sans code) ou regex invalide (`regex_invalid`).
- `build_patterns(regexes=None, emails=False, phones=False, phones_de=False)` — `excelcrypt.py:315` — ancienne signature conservée pour compatibilité ; délègue à `build_detectors`.
- `detect_column(values) -> str | None` — `excelcrypt.py:321` — sur les 100 premières valeurs non vides, retourne le premier détecteur dont une correspondance couvre ≥ 80 % de la valeur pour plus de la moitié des valeurs (bouton « Suggérer » de la GUI).

### Propagation
- `_trie_regex(words) -> str` — `excelcrypt.py:336` — regex compacte en arbre de préfixes (échappée) ; fonction interne récursive `build(node)` — `excelcrypt.py:345`.
- `class Propagation` — `excelcrypt.py:356` — valeurs des cellules masquées à masquer aussi dans le texte libre.
  - `__init__(self)` — `excelcrypt.py:359` — `prefix_of: dict[casefold -> préfixe]`, `regex = None`.
  - `add(self, value, prefix)` — `excelcrypt.py:363` — ignore les non-`str`, les valeurs (après strip) de moins de 3 caractères, les jetons `ENC_` et les formules ; premier préfixe conservé (`setdefault`). Seules les chaînes sont propagées (nombres/dates jamais).
  - `compile(self)` — `excelcrypt.py:371` — `(?<!\w)(?:trie)(?!\w)` IGNORECASE ; `regex=None` si aucun mot. Retourne `self`.
  - `__bool__(self)` — `excelcrypt.py:376` — vrai si compilée avec au moins un mot.

### Clés
- `_password_key(password, salt, params) -> bytes` — `excelcrypt.py:386` — Argon2id 32 octets, paramètres donnés.
- `class Keys` — `excelcrypt.py:391` — clé maître + deux sous-clés.
  - `__init__(self, master)` — `excelcrypt.py:394` — exige 32 octets (`key_invalid`) ; `token_key` = HKDF(info `excelcrypt/token`), `vault_key` = HKDF(info `excelcrypt/vault`).
  - `_derive(master, info)` (staticmethod) — `excelcrypt.py:401-402` — HKDF-SHA256, 32 octets, `salt=None`.
  - `from_text(cls, raw, password=None)` (classmethod) — `excelcrypt.py:405-406` — texte commençant par `KEY_MAGIC` -> `_unlock_key_text` ; sinon base64 strict (`key_invalid`).
  - `from_file(cls, path, password=None)` (classmethod) — `excelcrypt.py:416-417` — `key_missing` si absent, puis `from_text`.
- `key_is_protected(path) -> bool` — `excelcrypt.py:423` — le fichier commence-t-il par `KEY_MAGIC` ; `False` en cas d'`OSError`.
- `_unlock_key_text(raw, password) -> bytes` — `excelcrypt.py:430` — `key_locked` sans mot de passe, `key_invalid` si JSON illisible, `key_bad_password` sur `InvalidTag`.
- `write_key(path, master, password=None)` — `excelcrypt.py:445` — voir format plus haut ; écriture atomique, chmod 600.
- `generate_key(path, force=False, password=None)` — `excelcrypt.py:465` — refuse d'écraser sans `force` ; `os.urandom(32)`.
- `load_key(key_arg, password=None) -> Keys` — `excelcrypt.py:473` — résolution pour la CLI : (1) `key_arg` qui n'est pas un fichier existant est interprété comme texte de clé ; (2) sinon `$EXCELCRYPT_KEY` si pas d'argument ; (3) sinon fichier (`key_arg` ou `./excelcrypt.key`). Pour un fichier protégé : `$EXCELCRYPT_PASSWORD` puis saisie masquée si terminal interactif.

### Coffre
- `class Vault` — `excelcrypt.py:491` — coffre chiffré (jeton hex -> valeur typée, + alias lisibles).
  - `__init__(self, path, keys)` — `excelcrypt.py:492` — `entries`, `aliases` (hex -> alias), `counters` (préfixe -> dernier n), `by_alias` (alias -> hex), `dirty`. Charge si le fichier existe (sinon coffre vide, créé à la sauvegarde).
  - `_load(self)` — `excelcrypt.py:503` — vérifie `VAULT_MAGIC` (`vault_invalid`), déchiffre (`vault_bad_key` sur `InvalidTag`), gère v2 et v1, reconstruit `by_alias`.
  - `save(self)` — `excelcrypt.py:519` — ne fait rien si `dirty` est faux ; sinon réécrit tout le coffre (nouveau nonce), atomique.
  - `put(self, token_hex, value)` — `excelcrypt.py:530` — ajoute l'entrée ; si l'entrée existe avec une valeur différente -> `ExcelCryptError(code="collision")`.
  - `alias(self, token_hex, prefix, overlay=None) -> str` — `excelcrypt.py:540` — alias stable `PREFIXE_{n:04d}`. Alias existant retourné tel quel (le préfixe de la première attribution est définitif). Avec `overlay` (aperçu) : attribution provisoire dans le dict fourni, rien n'est écrit. Sinon incrémente le compteur en sautant les alias déjà pris, marque `dirty`.
  - `get(self, token_hex)` — `excelcrypt.py:560` — valeur typée ou `None` (hex mis en minuscules).
  - `resolve(self, token) -> (trouvé, valeur, reconnu_comme_jeton)` — `excelcrypt.py:564` — `ENC_…` : recherche hex ; alias : recherche `by_alias` en majuscules ; un `PREFIXE_0042` inconnu n'est signalé comme jeton que si son préfixe figure dans `counters`.
- `pack_value(v) -> dict` — `excelcrypt.py:577` — `bool` testé avant `int`, `datetime` avant `date`.
- `unpack_value(p) -> valeur` — `excelcrypt.py:593` — inverse ; type inconnu -> valeur brute.
- `value_as_text(v) -> str` — `excelcrypt.py:605` — `None` -> `""`, float entier -> `"12"`, datetime à minuit -> date ISO, date/time -> ISO, sinon `str`.
- `slug_prefix(header, letter) -> str` — `excelcrypt.py:618` — NFKD -> ASCII, non-alphanumériques -> `_`, majuscules, 20 caractères max ; vide -> `COL_<lettre>` ; commence par un chiffre -> préfixé `C`.
- `column_prefix(header, c, sel, mask_headers) -> str` — `excelcrypt.py:627` — `COL_<lettre>` si l'en-tête est masqué (pour ne pas le révéler), sinon `slug_prefix`.

### Tokenizer
- `class Tokenizer` — `excelcrypt.py:638` — calcule les jetons.
  - `__init__(self, keys, vault=None, readable=False, dry_run=False)` — `excelcrypt.py:645` — `keys=None` : aperçu sans clé ; `vault=None` : pas d'enregistrement ; `dry_run` : coffre lu, jamais modifié ; `overlay` pour alias provisoires ; `count` = nombre d'appels à `token`.
  - `token(self, value, prefix="VALUE") -> str` — `excelcrypt.py:653` — sans clé : `PREFIXE_••••` ou `ENC_••••…`. Sinon `h = HMAC-SHA256(token_key, f"{t}\x1f{v}")[:16]` sur la valeur typée ; `vault.put` si coffre et pas `dry_run` ; retourne `ENC_h`, ou un alias (overlay local si pas de coffre, `vault.alias` sinon, avec overlay si `dry_run`). `count` compte les occurrences, pas les valeurs uniques.
  - `mask_text(self, text, literals, detectors, propagation=None) -> str` — `excelcrypt.py:673` — ordre : propagation (préfixe de la valeur d'origine), littéraux (remplacement exact sensible à la casse, préfixe `VALUE`), détecteurs.
  - `mask_cell(self, value, masked, literals, detectors, propagation=None, prefix="VALUE")` — `excelcrypt.py:686` — laisse intacts `None`, `""`, formules et jetons `ENC_` ; cellule masquée -> jeton de la valeur (chaîne strippée) ; sinon masquage dans le texte si chaîne. Retourne l'objet d'origine s'il n'y a rien à faire (test `is not` en aval).
- `is_formula(v)` — `excelcrypt.py:697` — chaîne commençant par `=`.
- `is_token(v)` — `excelcrypt.py:701` — chaîne (strippée) qui est exactement un jeton `ENC_` (les alias lisibles ne sont pas reconnus).
- `resolve_columns(header, specs, sheet_name, strict) -> set[int]` — `excelcrypt.py:705` — nom d'en-tête (casefold, première occurrence) > lettre(s) 1-3 > numéro. Si `strict`, avertit sur stderr pour les colonnes introuvables.

### Lecture / écriture Excel/CSV
- `check_format(path) -> "excel" | "csv"` — `excelcrypt.py:730` — `file_missing`, `xls_unsupported` (.xls), `format_unsupported`.
- `read_csv(path) -> (rows, dialect, encodage)` — `excelcrypt.py:746` — essaie `utf-8-sig`, `cp1252`, `latin-1` ; `csv.Sniffer` sur 64 Kio (délimiteurs `,;\t|`), repli `csv.excel`. Toutes les valeurs sont des chaînes. Lecture via `splitlines()`.
- `write_csv(path, rows, dialect, enc)` — `excelcrypt.py:762` — réécrit avec le même dialecte et encodage (écriture non atomique ; `utf-8-sig` réécrit le BOM).
- `load_workbook(path)` — `excelcrypt.py:767` — `openpyxl.load_workbook`, `keep_vba` pour `.xlsm`. Formules conservées (pas `data_only`).
- `read_preview(path, header_row=1, max_rows=500) -> {feuille: {header, rows, total}}` — `excelcrypt.py:771` — CSV : feuille `(csv)` ; Excel : `read_only=True, data_only=True` (valeurs calculées), classeur fermé dans `finally`.
- `default_output(path, suffix) -> Path` — `excelcrypt.py:803` — `<nom>_<suffix><ext>` (`_chiffre`, `_dechiffre`).

### Chiffrement, scan et déchiffrement
- `as_selection(sel)` — `excelcrypt.py:811` — `None`/`SheetSelection` inchangés, sinon un ensemble d'index -> `SheetSelection(cols=…)`.
- `describe_selection(sel) -> str` — `excelcrypt.py:817` — texte de journal (« colonnes A, C ; lignes 2-5 ; 3 cellule(s) ; B2:D9 ») ou `-`.
- `class _Sheet` — `excelcrypt.py:830` — vue commune feuille Excel / CSV.
  - `__init__(self, name, header, sel, cells, header_cells)` — `excelcrypt.py:833` — `cells` : callable qui itère `(ligne, colonne, getter, setter)` ; `header_cells` : colonne -> `(getter, setter)`.
- `_sheets(fmt, doc, columns, hr)` — `excelcrypt.py:839` — générateur de `_Sheet`. CSV : une feuille `(csv)` dont la sélection `None` devient une sélection vide (pas d'exclusion) ; générateur interne `cells()` — `excelcrypt.py:843`. Excel : en-tête = ligne `hr` ; `cells(ws=ws)` — `excelcrypt.py:858` — parcourt les lignes après `hr` en sautant les formules (`data_type == "f"`) et les `MergedCell`.
- `_set_cell(cell, v)` — `excelcrypt.py:874` — affecte la valeur ; format `@` (texte) si la valeur est un jeton `ENC_…` ou un alias.
- `_process(path, keys, vault, columns, literals, detectors, header_row, progress, log, mask_headers, propagate, readable, scan)` — `excelcrypt.py:880` — passe commune. Littéraux dédupliqués et triés par longueur décroissante ; regex brutes enveloppées en `Detector`. Tokenizer avec clé aléatoire si `keys` est None, sans coffre et `dry_run` en scan. Feuilles avec sélection `None` exclues. Passe 1 (si `propagate` ou `scan`) : relevé des valeurs des cellules sélectionnées. Passe 2 : masquage des en-têtes (préfixe `HEADER`, hors scan) puis des cellules ; en scan, `_record_leaks` sur les cellules non masquées, en passant la propagation seulement si `propagate` est faux (sinon ces valeurs sont déjà masquées). Retour : scan -> liste de constats triée (compte décroissant, feuille, colonne) ; sinon `(fmt, doc, rows, dialect, enc, tk)`. Progression tous les 5000 (passe 1) / 2000 (passe 2) éléments ; le total est approximatif. Fonction interne `prefix_for(sh, c)` — `excelcrypt.py:906`.
- `_record_leaks(findings, sh, c, text, detectors, propagation)` — `excelcrypt.py:952` — agrège par (feuille, colonne, détecteur) : `{sheet, col, letter, header, detector, count, example}` ; clé `masked_value` pour la propagation ; ignore un `phone_de` déjà vu en `phone_fr` sur le même extrait.
- `encrypt_file(path, out, keys, vault_path, columns, literals=None, patterns=None, header_row=1, progress=None, log=…, mask_headers=False, propagate=False, readable=False) -> dict` — `excelcrypt.py:968` — ouvre/crée le coffre, `_process`, écrit la sortie (CSV ou `doc.save`) **puis** `vault.save()`. Retour `{masked, unique, output, vault}` (`unique` = taille totale du coffre, anciennes entrées comprises).
- `scan_file(path, columns, literals=None, patterns=None, header_row=1, progress=None, mask_headers=False, propagate=False) -> list[dict]` — `excelcrypt.py:990` — contrôle des fuites sans clé ni coffre. N'inspecte ni la ligne d'en-tête ni les formules.
- `decrypt_file(path, out, keys, vault_path, progress=None) -> dict` — `excelcrypt.py:1002` — `vault_missing` si le coffre est absent. Fonction interne `restore(value)` — `excelcrypt.py:1011` : cellule entière = jeton -> valeur typée ; sinon substitution dans le texte via `sub(m)` — `excelcrypt.py:1024` (`value_as_text`). Jetons inconnus collectés dans `stats["unknown"]`. CSV : valeurs non textuelles reconverties en texte, pas de progression. Excel : saute les `MergedCell` ; formats `yyyy-mm-dd[ hh:mm:ss]` pour les dates, `General` pour les nombres restaurés dans une cellule formatée `@`. Noms de feuilles : jetons restaurés via `title_sub(m)` — `excelcrypt.py:1063`, caractères interdits `[]:*?/\` -> `_`, tronqués à 31. Retour `{restored, unknown: set, output}`.

### Commandes CLI
- `cmd_inspect(args)` — `excelcrypt.py:1076` — affiche, par feuille, les colonnes (lettre, en-tête, 3 exemples tronqués à 60 caractères).
- `_cli_detectors(args) -> list[Detector]` — `excelcrypt.py:1085` — fusionne `--detect` et les raccourcis `--emails/--phones/--phones-de` (dédupliqués, ordre conservé) + `--regex`.
- `_cli_selector(args, path) -> (col_specs, select)` — `excelcrypt.py:1091` — construit le `ColumnSelector` ; `select(sheet, header)` — `excelcrypt.py:1096` — retourne `None` pour les feuilles hors `--sheets`, sinon colonnes `-c` (avertissements stricts si `--sheets` est donné ou s'il n'y a qu'une feuille) + `--select` via `parse_refs` (références non comprises -> erreur).
- `cmd_encrypt(args)` — `excelcrypt.py:1110` — si rien à masquer : erreur hors terminal, sinon affiche `inspect` et demande les colonnes via `input`. Sortie par défaut `_chiffre`. Affiche les compteurs et les chemins.
- `cmd_scan(args)` — `excelcrypt.py:1137` — affiche les constats ; `sys.exit(2)` s'il y en a au moins un.
- `cmd_decrypt(args)` — `excelcrypt.py:1151` — sortie par défaut `_dechiffre` ; liste jusqu'à 20 jetons inconnus sur stderr (code retour 0 malgré tout).
- `_ask_new_password() -> str | None` — `excelcrypt.py:1164` — saisie + confirmation ; vide = aucun mot de passe.
- `cmd_passwd(args)` — `excelcrypt.py:1171` — recharge la clé (demande l'ancien mot de passe si besoin) et la réécrit avec le nouveau (ou en clair) ; la clé maître et donc les jetons ne changent pas.

### main
- `main()` — `excelcrypt.py:1178` — argparse, parents `common` (`-k/--key`, `--vault`, `-o/--output`) et `select` (voir tableau) ; dispatch ; toute `ExcelCryptError` -> `sys.exit("Erreur : …")` (code 1). Point d'entrée `if __name__ == "__main__"` — `excelcrypt.py:1246`.

## Commandes CLI
| Commande | Options | Fonction appelée | Sortie produite | Codes retour |
|---|---|---|---|---|
| `keygen` | `-o/--output` (défaut `excelcrypt.key`), `--force`, `--password` | `generate_key` (+ `_ask_new_password`) | fichier clé (chmod 600) | 0 ; 1 si le fichier existe sans `--force` ou mots de passe différents |
| `passwd` | `-k/--key` | `cmd_passwd` | fichier clé réécrit | 0 ; 1 sur erreur de clé/mot de passe |
| `inspect` | `file`, `--header-row` | `cmd_inspect` -> `read_preview` | liste des colonnes sur stdout | 0 ; 1 sur format/fichier invalide |
| `scan` | `file` + options `select` : `-c/--columns`, `--select`, `-s/--sheets`, `--value` (répétable), `--regex` (répétable), `--detect`, `--emails`, `--phones`, `--phones-de`, `--propagate`, `--mask-headers`, `--header-row` | `cmd_scan` -> `scan_file` | rapport des fuites sur stdout | 0 si aucune fuite, **2** si fuites, 1 sur erreur |
| `encrypt` | `file` + `common` (`-k`, `--vault`, `-o`) + `select` + `--readable` | `cmd_encrypt` -> `encrypt_file` | `<nom>_chiffre.<ext>` + coffre mis à jour | 0 ; 1 sur erreur (dont collision) |
| `decrypt` | `file` + `common` | `cmd_decrypt` -> `decrypt_file` | `<nom>_dechiffre.<ext>` ; jetons inconnus sur stderr | 0 (même avec jetons inconnus) ; 1 sur erreur |

Les erreurs d'arguments argparse sortent aussi avec le code 2 (même code que `scan` avec fuites).

## Modèle de sécurité
- **Clé maître** : 32 octets aléatoires (`os.urandom`). Deux sous-clés indépendantes via HKDF-SHA256 sans sel, `info` = `excelcrypt/token` et `excelcrypt/vault` (`excelcrypt.py:398-403`).
- **Jetons** : `HMAC-SHA256(token_key, type + "\x1f" + valeur)` tronqué à 16 hex = 64 bits (`excelcrypt.py:659-660`). Déterministes (même valeur typée => même jeton, ce qui permet de grouper/joindre) mais non calculables sans la clé. Le **type fait partie de l'empreinte** : `12` (int), `12.0` (float) et `"12"` (str) donnent trois jetons différents.
- **Troncature 64 bits** : collision attendue autour de 2^32 valeurs distinctes ; `Vault.put` refuse net toute collision détectée (`excelcrypt.py:536-538`). Pas de vérification en scan ni en aperçu sans coffre.
- **Jetons lisibles** (`PREFIXE_0042`) : simples compteurs séquentiels stockés dans le coffre ; ils révèlent l'ordre d'apparition et le nombre de valeurs distinctes par préfixe, et le préfixe révèle le nom de colonne (sauf `--mask-headers`, qui force `COL_<lettre>`).
- **Coffre** : AES-256-GCM, nonce aléatoire de 12 octets à chaque sauvegarde, AAD = `XLCV1` ; authentifié (toute altération -> `vault_bad_key`). Contient les valeurs en clair une fois déchiffré en mémoire.
- **Clé protégée** : Argon2id (t=3, p=4, 64 Mio), sel 16 octets, puis AES-256-GCM avec AAD `EXCELCRYPT-KEY-2`. Changer le mot de passe ne change pas la clé maître.
- **Protégé** : le contenu des cellules sélectionnées, les valeurs trouvées par littéraux/détecteurs/regex, les valeurs propagées, les en-têtes masqués ; le coffre et la clé au repos.
- **Non protégé** : les cellules non sélectionnées et non détectées ; les formules (jamais modifiées, et leurs résultats en cache peuvent rester dans le fichier) ; les cellules fusionnées secondaires ; les noms de feuilles, commentaires, noms définis, métadonnées du classeur, graphiques ; la structure (nombre de lignes, fréquences via le déterminisme des jetons) ; les valeurs de moins de 3 caractères et les non-chaînes pour la propagation. Le coffre n'a pas de chmod 600 (seule la clé en a un). La clé en clair (base64) est lisible par quiconque accède au fichier ou à `$EXCELCRYPT_KEY`.

## Points d'attention / pièges
- **Compatibilité des jetons existants** : ne pas modifier `TOKEN_PREFIX`, `TOKEN_HEX_LEN`, les `info` HKDF, le séparateur `\x1f`, le format de `pack_value` (noms de types, `repr` des floats, `isoformat`) ni l'ordre `bool` avant `int` / `datetime` avant `date` : cela changerait tous les jetons et casserait les jointures entre fichiers déjà chiffrés. Le format de coffre v1 doit rester lisible.
- **Normalisation** : une cellule masquée est strippée avant hachage (`excelcrypt.py:691`), donc `" Jean"` et `"Jean"` donnent le même jeton. En revanche la casse est conservée : `"jean"` et `"Jean"` donnent deux jetons. La propagation recherche sans tenir compte de la casse mais hache le texte trouvé tel quel, donc une occurrence en casse différente produit un autre jeton (restauré correctement). Les littéraux (`--value`) sont sensibles à la casse et remplacés par sous-chaîne (sans bornes de mot).
- **Ordre de masquage dans le texte** : propagation, puis littéraux, puis détecteurs, appliqués sur un texte qui contient déjà des jetons ; un littéral ou une regex qui correspond à un morceau de jeton (`ENC`, hex, `_0042`…) le corromprait.
- **Alias** : le préfixe d'un alias est fixé à la première attribution et partagé entre colonnes ; `ALIAS_RE` reconnaît aussi du texte ordinaire (`ORDER_2024`) : au déchiffrement, un tel texte n'est remplacé que s'il existe réellement dans `by_alias`, et n'est signalé inconnu que si son préfixe est connu du coffre. `is_token` ne reconnaît que `ENC_` : une cellule contenant déjà un alias lisible sera re-tokenisée.
- **Formules** : jamais masquées ni lues (Excel) ; `is_formula` exclut aussi les chaînes CSV commençant par `=`. En sortie Excel, une colonne dont les valeurs sont masquées peut casser les formules qui en dépendent.
- **`_set_cell`** force le format texte `@` sur les cellules tokenisées ; `decrypt_file` rétablit `General` pour les nombres et un format date pour les dates.
- **Ordre d'écriture** dans `encrypt_file` : fichier de sortie puis coffre ; si la sauvegarde du coffre échoue, le fichier produit contient des jetons irrécupérables. Aucune protection contre `out == path` (écrasement de l'original).
- **CSV vs Excel** : un `ColumnSelector` qui retourne `None` exclut une feuille Excel mais pas le CSV (sélection vide). Tout est texte en CSV : `"12"` en CSV et `12` en Excel ne donnent pas le même jeton.
- **Clé** : `load_key` interprète un chemin de fichier inexistant comme du texte base64 (message « Clé invalide » en cas de faute de frappe). `$EXCELCRYPT_PASSWORD` n'est consulté que pour une clé fichier, pas pour une clé protégée passée par `$EXCELCRYPT_KEY`. `keygen --force` rend les anciens coffres illisibles.
- **Scan** utilise une clé aléatoire : les jetons qu'il génère ne sont pas les vrais. Il ignore la ligne d'en-tête.
- **Détecteurs** : l'ordre de `DETECTORS` détermine le résultat de `detect_column` ; `vat` n'a pas de somme de contrôle (faux positifs possibles).
- **Noms de feuilles** restaurés : tronqués à 31 caractères et nettoyés ; une collision avec un nom existant n'est pas gérée explicitement.

## Utilisé par
`gui.py` (`import excelcrypt as ec`, `gui.py:27`) utilise : `ec.CSV_EXT`, `ec.EXCEL_EXT`, `ec.DEFAULT_KEY`, `ec.DEFAULT_VAULT`, `ec.DETECTORS`, `ec.ExcelCryptError`, `ec.Keys` (`Keys.from_file`), `ec.Vault`, `ec.Tokenizer` (aperçu avec `dry_run=True`, `gui.py:353`), `ec.Propagation`, `ec.SheetSelection`, `ec.build_detectors`, `ec.check_format`, `ec.column_prefix`, `ec.decrypt_file`, `ec.default_output`, `ec.detect_column`, `ec.encrypt_file`, `ec.generate_key`, `ec.key_is_protected`, `ec.parse_refs`, `ec.profile_selection`, `ec.read_preview`, `ec.scan_file`, `ec.value_as_text`, `ec.write_key`. Non utilisés par la GUI : `build_patterns`, `load_key`, `resolve_columns`, les fonctions `cmd_*` et `main`.

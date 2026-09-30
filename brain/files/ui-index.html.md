# ui/index.html

> Interface complète d'ExcelCrypt (page unique HTML + CSS + JS inline) affichée par pywebview, qui délègue toute la logique de fichiers et de cryptographie à Python via `window.pywebview.api.*`. · Lignes : 2537 · Aucune dépendance externe (pas de CDN, pas de framework) ; seules ressources : `ui/logo.svg` (l.533) et les icônes Lucide copiées en `<symbol>` inline (l.743-787). Les polices « Inter » et « JetBrains Mono » sont citées dans les piles de polices mais ne sont pas chargées : repli sur les polices système.

## Vue d'ensemble

| Bloc | Lignes |
|---|---|
| `<head>` (meta, `<title>ExcelCrypt</title>`) | 3-528 |
| `<style>` | 7-527 |
| `<body>` | 529-2536 |
| En-tête `header.topbar` | 531-551 |
| `<main>` et ses 4 vues | 553-732 |
| Conteneurs globaux (modale, infobulle, toasts, voile de glisser-déposer) | 734-740 |
| Sprite SVG (icônes Lucide + drapeaux) | 743-787 |
| `<script>` (`"use strict"`) | 783-2535 |

Organisation du script, dans l'ordre : dictionnaire i18n (788-1291), état `S` et utilitaires (1293-1338), langue (1340-1401), démarrage (1403-1444), navigation (1446-1459), chargement de fichier et modèle de sélection (1461-1520), historique d'annulation (1522-1542), rendu (1544-1671), interactions de sélection (1673-1832), vue IA (1834-1852), chips valeurs/regex (1856-1902), chiffrement (1904-1936), restauration (1938-1990), clé et coffre (1992-2072), modales génériques (2074-2129), détecteurs (2131-2166), mot de passe (2168-2256), contrôle avant envoi (2258-2297), profils (2299-2402), lots (2404-2460), toasts et infobulles (2462-2498), glisser-déposer (2500-2519), clavier (2521-2533).

Vues de l'application (`section.view`, une seule `.active` à la fois, via `showView`) :

- **Protéger, accueil** `#v-protect-empty` (555-571) : zone de dépôt, bouton de lot, 3 étapes.
- **Protéger, espace de travail** `#v-protect-work` (574-702) : barre latérale de 340 px (fichier, profil, colonnes, lignes/cellules, détections, bouton de chiffrement) + zone principale (bandeau sans clé, barre d'outils, tableau d'aperçu, pied).
- **Restaurer, accueil** `#v-restore-empty` (705-717) : zone de dépôt, bouton de lot, checklist clé/coffre.
- **Restaurer, résultat** `#v-restore-result` (720-731) : en-tête de résultat, avertissement jetons inconnus, onglets de feuilles, aperçu du fichier restauré.

Toutes les boîtes de dialogue partagent un seul conteneur `#modal` / `#modal-box` dont le HTML est régénéré par chaque fonction `xxxModal()`.

## CSS

### Jetons `:root` (l. 11-49, thème clair uniquement, commentaire « Jetons DIVE Turbinen (design-system.md §2 à §4) »)

| Jeton | Valeur |
|---|---|
| `--color-primary` | `#004A99` |
| `--color-primary-hover` | `#003A78` |
| `--color-primary-light` | `#1E63B5` |
| `--color-primary-tint` | `#E8F0F9` |
| `--color-primary-wash` | `rgba(0, 74, 153, .045)` (fond des cellules protégées) |
| `--color-accent` | `#EE7F00` |
| `--color-accent-hover` | `#CC6E00` |
| `--color-accent-tint` | `#FFF3E6` |
| `--color-cta` | `#A85F00` (fond des `.btn.primary`) |
| `--color-cta-hover` | `#8C4E00` |
| `--color-neutral` | `#BCBDBF` |
| `--color-bg` | `#F5F7FA` |
| `--color-surface` | `#FFFFFF` |
| `--color-text` | `#1A2230` |
| `--color-text-secondary` | `#5B6676` |
| `--color-border` | `#E4E8EE` |
| `--color-border-strong` | `#BCBDBF` |
| `--color-success` / `-tint` | `#1E7B4F` / `#E7F4EE` |
| `--color-danger` / `-hover` / `-tint` | `#B42318` / `#911A12` / `#FDECEA` |
| `--color-focus-ring` | `#1E63B5` |
| `--radius-xs/sm/md/lg` | `4px / 8px / 12px / 16px` |
| `--shadow-sm` | `0 1px 2px rgba(16, 24, 40, .05)` |
| `--shadow-md` | `0 4px 12px rgba(16, 24, 40, .08)` |
| `--shadow-lg` | `0 12px 32px rgba(16, 24, 40, .10)` |
| `--ease` | `cubic-bezier(.16, 1, .3, 1)` |
| `--dur` | `170ms` |
| `--z-sticky / overlay / modal / toast / tooltip` | `1100 / 1200 / 1300 / 1400 / 1500` |
| `--z-dropdown` | `1000` (défini dans un second bloc `:root`, l.487) |
| `--font` | `"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI Variable", "Segoe UI", system-ui, sans-serif` |
| `--mono` | `"JetBrains Mono", ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace` |

Quelques couleurs sont codées en dur hors jetons : `#F1B9B3` (bordure `.pill.bad`), `#B8CDE6`, `#C9DAEE`, `#F6D3A8`, `#EDF1F6`, `#8A94A3`, `#C5CCD6`.

### Base et thème

- `body` (52-57) : 14px/20px, `overflow: hidden`, `user-select: none` (réactivé sur `input, textarea` l. 58). Pas de mode sombre.
- Focus : `:focus` sans contour, `:focus-visible` anneau 2px `--color-focus-ring` (65-66).
- `@media (prefers-reduced-motion: reduce)` (435-437) : animations/transitions ramenées à 1ms.
- `@media (max-width: 1180px)` (438-442) : barre latérale 300 px, sous-titres de marque masqués, pastilles rétrécies.
- `[hidden] { display: none !important; }` (445) : l'attribut `hidden` est la convention pour masquer.

### Conventions de nommage

Classes courtes et plates, sans préfixe BEM. États par classes modificatrices : `.on` (sélectionné/activé), `.m` (masqué/protégé, dans le tableau), `.pick` (cellule cochée à la main), `.drag` (zone en cours de glisser), `.tok` / `.t` (jeton), `.unk` (jeton inconnu), `.ok` / `.bad` / `.warn` / `.info` (statut), `.show` (visible), `.sm` / `.lg` / `.xl` (tailles). États ARIA stylés directement : `[aria-selected="true"]`, `[aria-checked="true"]`, `[aria-expanded="true"]`, `[aria-invalid="true"]`.

### Composants principaux

| Composant | Classes | Lignes |
|---|---|---|
| Icônes SVG | `svg.i`, `.sm`, `.lg`, `.xl` | 61-64 |
| Losange de marque | `.diamond`, `.outline` | 68-70 |
| Boutons | `.btn`, `.primary`, `.secondary`, `.ghost`, `.lg`, `.sm`, `.icon` | 72-92 |
| En-tête | `.topbar`, `.brand*` | 94-104 |
| Contrôle segmenté | `.seg`, `.seg.sm` | 106-114 |
| Pastilles clé/coffre | `.pill`, `.bad`, `.warn`, `.locked` (484) | 116-129 |
| Vues | `.view`, `.active`, `@keyframes fadeIn` | 131-135 |
| Accueil, zone de dépôt, étapes, checklist | `.welcome`, `.dropzone`, `.dz-icon`, `.formats`, `.kbd`, `.steps`, `.step`, `.checklist`, `.check` | 137-173 |
| Espace de travail, barre latérale | `.workspace`, `.sidebar`, `.sidebar-scroll`, `.file-card`, `.section-h`, `.badge` | 175-191 |
| Champs | `.search`, `.input` | 193-205 |
| Liste de colonnes | `.col-list`, `.col-item`, `.col-letter`, `.col-main`, `.tag-sug` | 207-224 |
| Interrupteur | `.switch` (activé par `.on > .switch`) | 226-229 |
| Lignes d'options | `.opt-list`, `.opt-row` | 231-243 |
| Chips | `.chips-field`, `.chips`, `.chip`, `.mono`, `.err`, `.help`, `.field-err` | 245-266 |
| Pied de barre latérale, résumé | `.sidebar-foot`, `.summary`, `.s-item` | 268-273 |
| Sélection manuelle | `.man-list`, `.range-row` | 275-281 |
| Barre d'outils, onglets, stepper | `.main`, `.toolbar`, `.tabs`, `.tab`, `.cnt`, `.stepper` | 283-301 |
| Tableau d'aperçu | `table.grid`, `th.rn`, `td.rn`, `.th-btn`, `.rn-btn`, `td.m`, `.tok`, `.t`, `.pick`, `.drag`, `.unk` | 303-336 |
| Pied de tableau, légende, bandeau sans clé | `.table-foot`, `.legend`, `.nokey-banner` | 338-344 |
| Infobulle | `.tooltip` | 346-353 |
| Vue restauration | `.restore-layout`, `.result-head`, `.warn-box` | 355-364 |
| Modales | `.overlay`, `.modal`, `.modal-h`, `.mi`, `.modal-b`, `.modal-f`, `.stats`, `.stat`, `.file-row`, `.key-path`, `.key-block`, `.note` | 366-404 |
| Progression | `.progress`, `.indet`, `.spinner` | 406-411 |
| Toasts | `.toasts`, `.toast`, `.out`, `.act` (482-483) | 413-425 |
| Voile de glisser-déposer | `.drag-veil` | 427-433 |
| Profils, lots, contrôle, mot de passe | `.profile-actions`, `.select-wrap`, `.batch-cta`, `.det-group`, `.field`, `.pw-wrap`, `.finding`, `.findings`, `.modal.wide`, `.batch-list`, `.batch-item`, `.scan-line` | 444-484 |
| Sélecteur de langue | `.top-right`, `.lang`, `.lang-btn`, `.flag`, `.menu`, `.lang-grid`, `.lang-choice` | 486-524 |
| Divers | `.th-tok`, `.opt-list.tight` | 525-526 |

## Structure HTML

### En-tête (531-551)
- Marque : `logo.svg` + « ExcelCrypt » + sous-titre `brandSub` (532-536).
- Onglets de mode `nav.seg` : `#tab-protect` (538), `#tab-restore` (539) → `setMode()`.
- Sélecteur de langue `#lang` (542-547) : `#lang-btn`, `#lang-flag`, `#lang-code`, menu `#lang-menu` rempli par `applyI18n`.
- Pastilles `#pill-key` (548, textes `#pill-key-t`, `#pill-key-s`) et `#pill-vault` (549, `#pill-vault-t`) → `openKeyModal()`.

### Protéger, accueil `#v-protect-empty` (555-571)
- `#dz-protect` (559) → `pickAndLoad()` ; `#kbd-open` (562) affiche ⌘O ou Ctrl+O.
- Bouton « Protéger tout un dossier… » (565) → `batchModal()`.

### Protéger, espace de travail `#v-protect-work` (574-702)
Barre latérale (575-669) :
- Carte fichier : `#f-name`, `#f-meta` (579), bouton « Changer » (580).
- Profil : `#profile-select` (586), boutons enregistrer (590), `#profile-batch` (591), `#profile-del` (592).
- Colonnes : `#sel-count` (598), `#col-filter` (602), `#btn-suggest` + `#sug-count` (605), Toutes/Aucune (606-607), `#col-list` (609), options `#opt-maskHeaders` (611), `#opt-propagate` (616).
- Lignes et cellules : `#man-count` (631), `#man-clear` (632), `#man-list` (634), `#in-range` (638), `#range-help` (641), `#range-err` (642).
- Détections : `#detector-list` (648), `#chips-values` / `#in-values` (651-652), `#chips-regex` / `#in-regex` (658-659), `#regex-err` (661).
- Pied : `#summary` (666), `#btn-encrypt` (667) → `doEncrypt()`.

Zone principale (671-701) : `#nokey-banner` (672), `#sheet-tabs` (678), `#btn-undo` (679), stepper de ligne d'en-têtes `#hdr-row` (680-687), bascule de vue `#view-orig` / `#view-ai` (688-691), `#tw-protect` + `#grid-protect` (693), `#rows-info` (695) et légende (696-699).

### Restaurer, accueil `#v-restore-empty` (705-717)
`#dz-restore` (709) → `doDecrypt()` ; bouton lot (715) → `batchRestoreModal()` ; `#restore-checks` (716).

### Restaurer, résultat `#v-restore-result` (720-731)
`#r-title`, `#r-sub` (723), `#r-reveal` (724, `onclick` affecté en JS), bouton « Restaurer un autre fichier » (725), `#r-warn` (727), `#r-tabs` (728), `#grid-restore` (729), `#r-rows` (730).

### Conteneurs globaux (734-740)
`#modal` (overlay `role="dialog"`) + `#modal-box` (735-737), `#tip` (738), `#toasts` (739, `aria-live="polite"`), `#veil` + `#veil-t` (740).

### Sprite SVG (743-787)
Icônes `#i-*` : shield, lock, unlock, key, db, sheet, upload, sparkles, search, eye, bot, check, x, alert, folder, arrow, plus, minus, info, mail, phone, type, code, rows, grid, undo, send, save, trash, folders, share, tag, card, bank, id, eye-off, chevron, heading. Drapeaux `#f-fr`, `#f-de`, `#f-en` (784-786). Utilisées via `<use href="#i-…">` ou les helpers `icon()` / `flag()`.

### Dialogues (générés en JS dans `#modal-box`)
Choix de langue (`langModal`), occupation/progression (`showBusy`), erreur (`errorModal`), succès du chiffrement (`successEncryptModal`), clé et coffre (`openKeyModal`), nouvelle clé (`confirmNewKey`), clé créée (dans `newKey`), clé requise (`keyRequiredModal`), déverrouillage (`unlockModal`), mot de passe (`passwordModal`), retrait du mot de passe (`removePasswordModal`), contrôle avant envoi (`leakModal`, classe `.wide`), enregistrement/suppression de profil (`saveProfileModal`, `deleteProfileModal`), lot (`batchModal`, `batchRestoreModal`, résultat dans `runBatch`, `.wide`).

## i18n

- Langues : `LANGS` (788-792) = fr (`fr-FR`), de (`de-DE`), en (`en-GB`).
- Pluriels : `fr_s(n)` (793, singulier pour 0 et 1) et `en_s(n)` (794). L'allemand écrit ses pluriels en ligne (`n === 1 ? … : …`).
- Dictionnaire `I18N` (796-1291) : `fr` 797-964, `de` 966-1127, `en` 1129-1290. Une valeur est une chaîne ou une fonction (paramètres, pluriels, ex. `vaultCount: (n) => …`). Certaines chaînes contiennent du HTML (`orBrowse`, `keyNote`, `newKeyWarn`, `unknownWarn`).
- `t(key, ...args)` (1329-1332) : cherche dans `I18N[LANG]`, sinon `I18N.fr`, sinon renvoie la clé ; appelle la fonction si besoin.
- Attributs déclaratifs traités par `applyI18n()` (1343-1362) : `data-i18n` (textContent), `data-i18n-html` (innerHTML), `data-i18n-ph` (placeholder), `data-i18n-title` (title), `data-i18n-aria` (aria-label). Les parties dynamiques sont re-rendues au changement de langue (pastilles, fichier, chips, détecteurs, profils, résultat de restauration).
- La langue choisie est persistée côté Python (`api.set_lang`, 1367) et relue au démarrage (`st.lang`, 1412) ; sinon déduite de `navigator.language` et le choix est imposé au premier lancement (`langModal`).
- **Ajouter une chaîne** : ajouter la même clé dans les trois blocs `fr`, `de`, `en`, puis l'utiliser via `data-i18n="clé"` dans le HTML ou `t("clé", …)` dans le JS. Le repli vers `fr` masque une clé manquante en de/en.
- **Codes d'erreur Python** : `errText(res)` (1334-1338) cherche `I18N[LANG]["err_" + res.code]` et l'appelle avec `res.params` si c'est une fonction ; sinon cherche dans `I18N.fr`, sinon affiche `res.error` (texte brut de Python). Codes traduits : `key_invalid`, `key_missing` (`path`), `vault_invalid` (`name`), `vault_bad_key`, `collision`, `regex_invalid` (`pattern`), `file_missing` (`path`), `xls_unsupported`, `format_unsupported` (`ext`), `vault_missing` (`name`), `no_key`, `no_file`, `same_output`, `file_exists` (`name`), `busy`, `write_denied` (`name`), `read_failed` / `encrypt_failed` / `decrypt_failed` (`detail`), `key_locked`, `key_bad_password`, `profile_name`, `profile_missing` (`name`), `batch_empty` (`name`). Pour ajouter un code : le renvoyer côté Python sous forme `{error, code, params}` et ajouter `err_<code>` dans les trois langues.
- Détecteurs : libellés `det_<clé>` (ex. `det_iban`) et groupes `grpContact`, `grpBank`, `grpIds`.
- `save` : libellé générique « Enregistrer » (bouton de `passwordModal`) ; `saveProfile` est réservé aux profils. `emailsEx` sert d'exemple du détecteur e-mail.

## État JS

Objet global `S` (1296-1311) :

| Champ | Contenu |
|---|---|
| `mode` | `"protect"` ou `"restore"` |
| `platform` | `sys.platform` renvoyé par Python (`"darwin"`, `"win32"`…) |
| `key` | objet d'état de clé venant de Python : `ok`, `locked`, `protected`, `exists`, `name`, `path` |
| `vault` | `ok`, `exists`, `count`, `path` |
| `file` | `{ path, name, bytes }` du fichier ouvert |
| `sheets` | tableau de feuilles : `{ name, columns: [{ idx, letter, name, example, suggested, unique, empty, filled }], rows: [[…]], total }` |
| `sheet` | index de la feuille courante |
| `headerRow` | ligne d'en-têtes (1-based, 1 à 100) |
| `selection` | `{ [nomFeuille]: { cols: Set<idxCol>, rows: Set<n°Ligne>, cells: Set<"r,c">, ranges: [{ rows: [[a,b]], rects: [[r1,c1,r2,c2]] }] } }`, numérotation Excel 1-based |
| `opts` | `{ detectors: [], maskHeaders: true, propagate: true, values: [], regexes: [] }` |
| `profiles`, `profile` | liste des profils (Python) et nom du profil actif |
| `scanClean` | `null` (pas de contrôle), `true` (propre ou tout corrigé), `false` (ignoré/partiel) |
| `view` | `"original"` ou `"ai"` |
| `aiRows`, `aiHeader` | lignes et en-têtes jetonisés renvoyés par `api.preview` |
| `regexErrors` | `{ motif: message }` |
| `restore`, `rSheet` | résultat de `api.decrypt` + `sheets` de l'aperçu, et index de feuille affichée |
| `busy` | opération Python en cours |
| `langRequired` | modale de langue obligatoire ouverte |
| `findings` | résultats du dernier contrôle avant envoi (rempli par `leakModal`) |

Autres variables globales : `LANG` (1312), `api` (1327), `regexSeq` (1872), `history` (1523, pile de snapshots JSON, max 100), `lastRow` (1699), `drag`, `lastCell` (1742), `grid` (1743), `aiTimer`, `aiSeq` (1835), `lastFocus` (2077), `unlockThen` (2197), `toastSeq`, `toastActions` (2465-2466), `tip`, `tipTimer` (2481-2482), `dragDepth`, `veil` (2503-2504). Constantes : `DETECTOR_GROUPS` (2134-2139), `TOKEN_ANY` (2165), `TOKEN_WHOLE` (2166).

Format envoyé à Python (`selectionPayload`) : `{ cols: [idx], rows: [[a,b]], cells: [[r,c]], rects: [[r1,c1,r2,c2]] }`, les `ranges` étant aplaties dans `rows`/`rects`.

Snapshot d'annulation : `JSON.stringify({ opts, sel: { feuille: { cols: [], rows: [], cells: [], ranges } } })`.

## Fonctions JS

### Utilitaires
- `fr_s(n)`, `en_s(n)` — `ui/index.html:793`, `:800` — suffixe pluriel.
- `$(s)` — `ui/index.html:1313` — alias de `document.querySelector`.
- `esc(s)` — `ui/index.html:1314` — échappement HTML de `& < > " '`.
- `locale()` — `ui/index.html:1315` — locale de `LANG`.
- `fmt(n)` — `ui/index.html:1316` — nombre formaté selon la locale.
- `fmtSize(b)` — `ui/index.html:1318` — taille de fichier (o/Ko/Mo en français, B/KB/MB sinon) ; « — » si inconnue (`null`, fichier disparu).
- `icon(id, cls)` — `ui/index.html:1325` — HTML `<svg><use href="#i-id">`.
- `flag(code, cls)` — `ui/index.html:1326` — HTML d'un drapeau.
- `t(key, ...args)` — `ui/index.html:1329` — traduction (voir i18n).
- `errText(res)` — `ui/index.html:1334` — traduction d'une erreur Python par code.

### Langue
- `applyI18n()` — `ui/index.html:1343` — applique toutes les traductions déclaratives, met à jour drapeau, code et menu de langue, re-rend les parties dynamiques.
- `setLang(code, silent)` — `ui/index.html:1363` — change `LANG`, ferme le menu, `applyI18n()`, appelle `api.set_lang(code)` ; si choix initial obligatoire, ferme la modale et enchaîne sur `unlockModal()` si la clé est verrouillée ; sinon toast.
- `toggleLangMenu()` — `ui/index.html:1371` — ouvre/ferme `#lang-menu`, met `aria-expanded`, focalise l'option cochée.
- `closeLangMenu()` — `ui/index.html:1377` — ferme le menu.
- Écouteurs : clic hors `#lang` ferme le menu (1378) ; navigation clavier ↑/↓/Échap dans le menu (1379-1385).
- `langModal()` — `ui/index.html:1388` — modale trilingue de premier lancement, met `S.langRequired = true` (bloque `closeModal`), propose la langue du navigateur.

### Démarrage et état
- `boot()` — `ui/index.html:1406` — une seule fois : `api = window.pywebview.api`, `api.get_state()`, libellé ⌘O/Ctrl+O, choix de langue, `applyState`, `applyI18n`, `syncOpts`, `loadProfiles` ; puis `langModal()` si aucune langue, sinon `unlockModal()` si clé verrouillée. Déclenché par l'événement `pywebviewready` (1424) ou immédiatement si l'API existe déjà (1425).
- `revealLabel()` — `ui/index.html:1427` — libellé « Afficher dans le Finder / l'Explorateur / Ouvrir le dossier » selon la plateforme.
- `applyState(st)` — `ui/index.html:1431` — copie `platform`, `key`, `vault` dans `S`, met à jour les pastilles (`.bad`, `.locked`, `.warn`), le bandeau `#nokey-banner`, puis `renderRestoreChecks()`.

### Navigation
- `showView(id)` — `ui/index.html:1449` — active une seule `.view`.
- `setMode(m)` — `ui/index.html:1452` — met à jour les onglets de mode et affiche la vue adaptée (accueil ou travail/résultat selon `S.file` / `S.restore`), masque l'infobulle.

### Chargement de fichier
- `pickAndLoad()` — `ui/index.html:1464` — `api.pick_file()` puis `loadFile(p, 1)`.
- `loadFile(path, headerRow)` — `ui/index.html:1468` — modale d'occupation (`S.busy` vrai pendant la lecture : Échap, clic sur le fond et dépôt de fichier sont ignorés), `api.load(path, headerRow)` ; en erreur `errorModal` ; sinon remplit `S.file`, `S.sheets`. Si c'est un nouveau fichier : réinitialise sélection, feuille, vue, profil, `scanClean`, historique. Met à jour carte fichier, passe en mode protéger, `renderAll()`, `renderProfiles()`, puis applique automatiquement `bestProfile()` s'il existe (nouveau fichier uniquement).
- `stepHeader(d)` — `ui/index.html:1489` — ligne d'en-têtes ±1 (bornée 1-100) et recharge le fichier via `loadFile`.

### Modèle de sélection
- `cur()` — `ui/index.html:1495` — feuille courante.
- `sel(name)` — `ui/index.html:1498` — sélection d'une feuille, créée à la demande (`??=`).
- `cellKey(r, c)` — `ui/index.html:1501` — clé `"r,c"`.
- `colLetter(n)` — `ui/index.html:1502` — numéro de colonne → lettres Excel.
- `inRange(g, r, c)` — `ui/index.html:1503` — cellule dans une plage saisie.
- `rowMasked(m, r)` — `ui/index.html:1504` — ligne protégée (ligne cochée ou plage de lignes).
- `isMasked(m, r, c)` — `ui/index.html:1505` — cellule protégée par colonne, ligne, cellule ou plage.
- `selSize(m)` — `ui/index.html:1506` — nombre d'éléments de sélection (compteur des onglets).
- `compressRows(set)` — `ui/index.html:1508` — ensemble de lignes → intervalles `[a,b]`.
- `selectionPayload(m)` — `ui/index.html:1516` — format envoyé à Python.

### Annulation
- `snapshot()` — `ui/index.html:1524` — sérialise `S.opts` + toutes les sélections.
- `pushHistory()` — `ui/index.html:1531` — empile (max 100), active `#btn-undo`.
- `resetHistory()` — `ui/index.html:1532` — vide la pile, désactive `#btn-undo`.
- `undo()` — `ui/index.html:1533` — dépile, reconstruit les `Set`, restaure `S.opts`, `syncOpts()`, `renderAll()`.

### Rendu de l'espace de travail
- `renderAll()` — `ui/index.html:1547` — `renderTabs`, `renderColumns`, `renderManual`, `renderTable`, `renderSummary`, `refreshAi`.
- `renderTabs()` — `ui/index.html:1549` — onglets de feuilles dans `#sheet-tabs` avec compteur `.cnt`.
- `selectSheet(i)` — `ui/index.html:1555` — change de feuille, réinitialise `aiRows`, `lastRow`, `lastCell`.
- `renderColumns()` — `ui/index.html:1557` — liste `#col-list` filtrée par `#col-filter` (nom contenu ou lettre exacte), marque « Sensible » pour `c.suggested`, infobulle d'exemple ; met à jour `#sel-count` et `#sug-count` (suggestions non cochées).
- `renderManual()` — `ui/index.html:1580` — chips des lignes (intervalles), des blocs de cellules (12 max puis « +N zones ») et des plages saisies dans `#man-list` ; `#man-count`, `#man-clear`.
- `renderTable()` — `ui/index.html:1600` — construit `#grid-protect` : en-têtes cliquables (`toggleCol`), numéros de ligne (`.rn-btn`, n° = `headerRow + 1 + index`), classes `.m`/`.pick`/`.empty`. En vue IA : cellules modifiées marquées `.tok` (jeton entier) ou jetons surlignés `<span class="t">`, infobulle avec la valeur réelle ; en-tête jetonisé avec infobulle du nom réel. Met à jour `#rows-info`.
- `renderSummary()` — `ui/index.html:1643` — résumé `#summary` (colonnes + estimation de valeurs extrapolée à `total`, noms de colonnes, lignes, cellules, propagation, détections, valeurs, regex) ; désactive `#btn-encrypt` si rien à faire ou `S.busy`.

### Sélection colonnes, lignes, cellules, plages
- `toggleCol(idx)` — `ui/index.html:1676` — bascule une colonne (avec historique).
- `setAll(on)` — `ui/index.html:1682` — toutes/aucune colonne de la feuille.
- `suggest()` — `ui/index.html:1688` — coche les colonnes `suggested` (calculées par Python), toast.
- `toggleRow(r, shift)` — `ui/index.html:1700` — bascule une ligne ; Maj+clic applique l'état à l'intervalle depuis `lastRow`.
- `removeRows(a, b)` — `ui/index.html:1710` — retire un intervalle de lignes.
- `removeBox(r1, c1, r2, c2)` — `ui/index.html:1711` — retire un bloc de cellules.
- `groupCells(set)` — `ui/index.html:1718` — regroupe les cellules en rectangles pleins pour l'affichage.
- `clearCells()` — `ui/index.html:1733` — retire toutes les cellules.
- `rangeLabel(g)` — `ui/index.html:1734` — libellé d'une plage saisie.
- `removeRange(i)` — `ui/index.html:1738` — retire une plage saisie.
- `clearManual()` — `ui/index.html:1739` — retire lignes, cellules et plages.
- Écouteurs du tableau : clic sur `.rn-btn` → `toggleRow` (1744-1747) ; `mousedown` sur `td[data-c]` démarre `drag` (mode ajout si Maj ou cellule non cochée ; Maj+clic termine immédiatement depuis `lastCell`) (1748-1758) ; `mouseover` étend la zone (1759-1765) ; `mouseup` global → `finishDrag` (1766).
- `dragBox()` — `ui/index.html:1767` — rectangle normalisé de la zone glissée.
- `paintDrag()` — `ui/index.html:1770` — applique `.drag` aux cellules visibles de la zone.
- `finishDrag()` — `ui/index.html:1779` — clic simple sur une cellule déjà protégée par colonne/ligne : toast informatif et rien d'autre ; sinon ajoute/retire les cellules de la zone, mémorise `lastCell`, `renderAll()`.
- `paintDragClear()` — `ui/index.html:1792` — retire `.drag`.
- `addRange()` — `ui/index.html:1795` — envoie `#in-range` à `api.parse_refs(feuille, texte)` ; affiche `#range-err` en cas d'erreur ; sinon ajoute colonnes, cellules, lignes seules (dans `rows`) et intervalles/rectangles (dans `ranges`). Entrée dans `#in-range` déclenche `addRange` (1819).

### Options et vue IA
- `toggleOpt(k)` — `ui/index.html:1821` — bascule `maskHeaders` / `propagate` (après `pushHistory()`, donc annulable par ⌘Z).
- `setView(v)` — `ui/index.html:1827` — bascule Original / Vue IA ; en vue IA sans données, `refreshAi(true)`.
- `refreshAi(now)` — `ui/index.html:1836` — invalide `S.aiRows` ; si vue IA, appelle après 120 ms (anti-rebond, 0 si `now`) `api.preview(feuille, sélectionsDeToutesLesFeuilles, S.opts)` ; ignore les réponses périmées via `aiSeq` ; stocke `aiRows`, `aiHeader`, `regexErrors` puis re-rend chips regex et tableau.

### Chips valeurs / regex
- `setupChips(key, inputId)` — `ui/index.html:1857` — Entrée ou virgule ajoute la valeur (sans doublon), Retour arrière sur champ vide retire la dernière ; chaque modification est historisée (`pushHistory`). Appelée l.2522-2533.
- `validateRegex()` — `ui/index.html:1873` — validation immédiate avec `new RegExp` (syntaxe JS), puis `api.check_regexes` (syntaxe Python, qui fait foi) remplace `S.regexErrors` ; compteur `regexSeq` (l.1862) pour ignorer les réponses obsolètes.
- `removeChip(key, i)` — `ui/index.html:1884` — retire une chip (historisé).
- `renderChips(key)` — `ui/index.html:1885` — reconstruit les chips avant le champ ; chips regex invalides en `.err`, message dans `#regex-err`.

### Chiffrement
- `doEncrypt(skipScan)` — `ui/index.html:1907` — `requireKey()`, refuse si regex invalides, construit la sélection des feuilles non vides ; sauf `skipScan`, lance `api.scan(selection, S.opts, S.headerRow)` et ouvre `leakModal` si des fuites sont trouvées ; puis `api.encrypt(selection, S.opts, S.headerRow)` ; gère `cancelled` / `error` ; `applyState(res.state)` et `successEncryptModal(res)`.
- `setBusy(b)` — `ui/index.html:1930` — `S.busy` + `renderSummary()`.
- `window.onTaskStart(kind, name)` — `ui/index.html:1932` — appelé par Python (`evaluate_js`) : modale de progression pour `encrypt` / `decrypt` / `scan`.
- `window.onTaskProgress(pct)` — `ui/index.html:1933` — appelé par Python : remplit `#busy-bar` et `#busy-pct`.

### Restauration
- `doDecrypt(path)` — `ui/index.html:1941` — `requireKey()`, exige un coffre existant (sinon erreur avec bouton « Choisir le coffre ») ; `api.decrypt(path)` (sélecteur Python si `path` nul) ; puis `api.load(res.output.path, 1, false)` pour l'aperçu ; remplit `S.restore`, `renderRestoreResult()`, passe en mode restaurer, toast.
- `renderRestoreChecks()` — `ui/index.html:1958` — checklist clé/coffre de `#restore-checks` avec boutons « Configurer » / « Choisir ».
- `renderRestoreResult()` — `ui/index.html:1971` — titre/sous-titre, `#r-reveal` → `api.reveal(output.path)`, avertissement des jetons inconnus (6 premiers), onglets `#r-tabs` (handler inline `S.rSheet=i`), tableau `#grid-restore` avec cellules/en-têtes `.unk` si elles contiennent un jeton inconnu, `#r-rows`.

### Clé et coffre
- `openKeyModal()` — `ui/index.html:1995` — modale clé + coffre : état, chemins, boutons choisir/générer une clé, section mot de passe (déverrouiller / définir / changer / retirer) si le fichier clé existe, choix d'un autre coffre, note explicative.
- `chooseKey()` — `ui/index.html:2026` — `api.choose_key()` ; erreur → `errorModal` ; clé verrouillée → `unlockModal(openKeyModal)` ; sinon rouvre la modale et toast.
- `confirmNewKey()` — `ui/index.html:2034` — confirmation de génération avec avertissement si une clé existe, champs mot de passe optionnels.
- `newKey()` — `ui/index.html:2048` — `readNewPassword(true)` puis `api.new_key(pw)` ; affiche le chemin de la nouvelle clé et un bouton `api.reveal(...)`.
- `chooseVault()` — `ui/index.html:2062` — `api.choose_vault()` ; `applyState`, rouvre la modale clé si une modale est affichée, toast.
- `keyRequiredModal()` — `ui/index.html:2066` — « Une clé secrète est nécessaire » : choisir ou créer.
- `requireKey()` — `ui/index.html:2171` — clé verrouillée → `unlockModal()` ; pas de clé → `keyRequiredModal()` ; renvoie un booléen.

### Mot de passe de clé
- `pwField(id, labelKey, autocomplete)` — `ui/index.html:2176` — HTML d'un champ mot de passe avec bouton afficher/masquer.
- `togglePw(id, btn)` — `ui/index.html:2181` — bascule `type` password/text, icône et aria-label.
- `readNewPassword(optional)` — `ui/index.html:2188` — lit `#pw-new` / `#pw-confirm` ; vide autorisé si `optional` ; 8 caractères minimum ; doit correspondre ; renvoie `null` en affichant `#pw-err`.
- `unlockModal(then)` — `ui/index.html:2198` — modale de déverrouillage, mémorise le rappel `unlockThen`, Entrée → `doUnlock`.
- `doUnlock()` — `ui/index.html:2209` — `api.unlock_key(mdp)` ; erreur affichée dans la modale ; sinon `applyState`, toast, `refreshAi()` si fichier ouvert, exécute `unlockThen`.
- `passwordModal()` — `ui/index.html:2226` — définir/changer le mot de passe.
- `savePassword()` — `ui/index.html:2239` — `api.set_key_password(pw)`, rouvre la modale clé, toast.
- `removePasswordModal()` — `ui/index.html:2246` — confirmation du retrait.
- `removePassword()` — `ui/index.html:2252` — `api.set_key_password("")`.

### Modales génériques
- `modal(html)` — `ui/index.html:2078` — mémorise le focus précédent (si aucune modale ouverte), réinitialise la classe de `#modal-box`, injecte le HTML, affiche `#modal`, focalise le bouton principal du pied (ou le premier bouton).
- `closeModal()` — `ui/index.html:2086` — ferme sauf si `S.langRequired`, restaure le focus.
- `showBusy(label, pct)` — `ui/index.html:2091` — modale spinner + barre (indéterminée si `pct === null`), ids `#busy-bar`, `#busy-pct`.
- `errorModal(title, msg, actions)` — `ui/index.html:2099` — modale d'erreur ; `actions` = `[[libellé, "codeJsInline"]]` + bouton OK.
- `successEncryptModal(r)` — `ui/index.html:2105` — résultat du chiffrement : ligne de contrôle avant envoi (propre / ignoré), statistiques `masked` / `unique`, fichier à envoyer (bouton `api.reveal`), clé et coffre à garder, bouton vers le mode restaurer.

### Détecteurs
- `DETECTOR_GROUPS` — `ui/index.html:2134` — groupes et détecteurs `[clé, icône, exemple]` : contact (`email`, `phone_fr`, `phone_de`), banque (`iban`, `card`), identifiants (`vat`, `steuer_id`, `nir`, `rvnr`, `siret`).
- `renderDetectors()` — `ui/index.html:2140` — génère `#detector-list` (interrupteurs `.opt-row`).
- `toggleDetector(k)` — `ui/index.html:2146` — ajoute/retire dans `S.opts.detectors` (historisé).
- `syncOpts()` — `ui/index.html:2153` — aligne les 3 interrupteurs d'options sur `S.opts`, re-rend détecteurs, valide les regex, re-rend les chips.

### Contrôle avant envoi
- `leakModal(findings)` — `ui/index.html:2261` — liste des constats (`detector`, `count`, `sheet`, `letter`, `header`, `example`) avec case à cocher et correctif proposé (activer le détecteur ou la propagation ; aucun correctif pour `regex`, case désactivée). Boutons Revenir / Envoyer quand même / Corriger et protéger.
- `fixLeaks()` — `ui/index.html:2283` — active les détecteurs ou la propagation cochés (avec historique), `scanClean = (aucune case décochée)`, relance `doEncrypt(true)` sans nouveau contrôle.
- `ignoreLeaks()` — `ui/index.html:2297` — `scanClean = false`, `doEncrypt(true)`.

### Profils
- `renderProfiles()` — `ui/index.html:2302` — options de `#profile-select`, visibilité de `#profile-del` et `#profile-batch`.
- `loadProfiles()` — `ui/index.html:2310` — `api.list_profiles()`.
- `headerIndex()` — `ui/index.html:2311` — ensemble des noms d'en-têtes (minuscules, trim) de toutes les feuilles.
- `bestProfile()` — `ui/index.html:2317` — profil dont toutes les colonnes existent dans le fichier, le plus complet d'abord.
- `applyProfile(p, auto)` — `ui/index.html:2322` — coche les colonnes par nom (insensible à la casse) sur toutes les feuilles, remplace `opts`, `values`, `regexes` (et retire l'option `readable` des anciens profils) ; toast (avec action « Annuler » de 7 s si automatique).
- `onProfileSelect(name)` — `ui/index.html:2338` — sélection dans la liste ; applique si un fichier est ouvert.
- `profileColumns()` — `ui/index.html:2344` — noms des colonnes cochées (dédoublonnés sans casse).
- `saveProfileModal()` — `ui/index.html:2352` — modale d'enregistrement : nom proposé (profil actif ou nom de fichier), aperçu du contenu, avertissement d'écrasement, note si des lignes/cellules manuelles ne seront pas sauvegardées.
- `saveProfile()` — `ui/index.html:2381` — `api.save_profile({ name, columns, headerRow, values, regexes, opts: { detectors, maskHeaders, propagate } })`.
- `deleteProfileModal()` — `ui/index.html:2391` — confirmation.
- `deleteProfile()` — `ui/index.html:2398` — `api.delete_profile(S.profile)`.

### Lots (dossier entier)
- `batchModal()` — `ui/index.html:2407` — exige une clé, choix du profil (bouton désactivé s'il n'y en a aucun) → `runBatch('encrypt', profil)`.
- `batchRestoreModal()` — `ui/index.html:2420` — exige clé et coffre → `runBatch('decrypt')`.
- `runBatch(kind, profile)` — `ui/index.html:2430` — `api.batch_encrypt(profile)` ou `api.batch_decrypt()` ; affiche la liste des résultats (ok / erreur traduite, valeurs masquées/restaurées, fuites possibles, jetons inconnus) et un bouton `api.reveal(res.folder)`.
- `window.onBatchProgress(i, n, name)` — `ui/index.html:2454` — appelé par Python : crée la modale de progression si absente, met à jour titre, nom de fichier et pourcentage.

### Toasts et infobulles
- `toast(msg, kind, action)` — `ui/index.html:2467` — toast `ok` / `bad` / `info` dans `#toasts`, 4 s (7 s avec action `{ label, fn }`).
- `runToastAction(id, btn)` — `ui/index.html:2476` — exécute l'action et retire le toast.
- Infobulle : écouteur global `mouseover` sur `[data-tip]` (2483-2496), délai 250 ms, positionnement sous l'élément ou au-dessus s'il manque de place ; titre `data-tip-title`.
- `hideTip()` — `ui/index.html:2497` — masque ; aussi sur tout `scroll` (2498).

### Glisser-déposer et clavier
- Écouteurs `dragenter` / `dragleave` / `dragover` / `drop` (2505-2514) : affichent seulement le voile `#veil` (texte selon le mode) ; le compteur `dragDepth` gère les entrées/sorties imbriquées.
- `window.onFileDropped(path)` — `ui/index.html:2515` — appelé par Python avec le chemin complet : `doDecrypt(path)` en mode restaurer, sinon `loadFile(path, 1)` ; ignoré si occupé ou choix de langue en cours.
- Écouteur `keydown` global (2524-2529) et clic sur l'overlay (2530) : voir section raccourcis.

## Appels vers Python

| Méthode | Lignes | Usage |
|---|---|---|
| `get_state()` | 1409 | État initial : plateforme, langue, clé, coffre |
| `set_lang(code)` | 1367 | Persiste la langue |
| `pick_file()` | 1465 | Sélecteur de fichier à protéger |
| `load(path, headerRow[, false])` | 1470, 1950 | Lecture/aperçu d'un fichier ; 3e argument `false` pour l'aperçu du fichier restauré |
| `parse_refs(sheet, text)` | 1799 | Analyse d'une plage saisie (B5, A2:C40, 12-30, D:F, nom) |
| `preview(sheet, selections, opts)` | 1844 | Vue IA : lignes et en-têtes jetonisés, erreurs regex |
| `scan(selection, opts, headerRow)` | 1914 | Contrôle avant envoi |
| `encrypt(selection, opts, headerRow)` | 1922 | Chiffrement et enregistrement |
| `decrypt(path)` | 1945 | Restauration (sélecteur si `path` nul) |
| `reveal(path)` | 1975, 2059, 2121, 2451 | Afficher un fichier/dossier dans le gestionnaire de fichiers |
| `choose_key()` | 2027 | Charger une clé existante |
| `new_key(password)` | 2051 | Générer une clé (mot de passe optionnel) |
| `choose_vault()` | 2063 | Choisir un autre coffre |
| `unlock_key(password)` | 2212 | Déverrouiller une clé protégée |
| `set_key_password(password)` | 2242, 2253 | Définir/changer (non vide) ou retirer (`""`) le mot de passe |
| `list_profiles()` | 2310 | Liste des profils |
| `save_profile(profile)` | 2385 | Enregistrer un profil |
| `delete_profile(name)` | 2399 | Supprimer un profil |
| `batch_encrypt(profile)` | 2433 | Protéger un dossier |
| `batch_decrypt()` | 2433 | Restaurer un dossier |
| `check_regexes(patterns)` | 1878 | Validation des regex par Python (`validateRegex`) |

Rappels Python → JS (via `evaluate_js` dans `gui.py`) : `window.onTaskStart` (1932), `window.onTaskProgress` (1933), `window.onBatchProgress` (2454), `window.onFileDropped` (2515). Convention de réponse Python : `{ error, code, params }` en erreur, `{ cancelled: true }` si l'utilisateur annule un sélecteur, `state` pour rafraîchir clé/coffre.

## Raccourcis clavier et interactions

- **⌘O / Ctrl+O** (2528) : `pickAndLoad()` en mode protéger, `doDecrypt()` en mode restaurer. Fonctionne même avec une modale ouverte.
- **⌘Z / Ctrl+Z** (2527) : `undo()`, uniquement en mode protéger, sans Maj, hors champ de saisie et sans modale ouverte.
- **Échap** (2525) : ferme la modale si rien n'est en cours (`!S.busy`) ; dans le menu de langue, le ferme (1384).
- **↑ / ↓** dans le menu de langue (1382-1383).
- **Entrée** : ajoute une plage (`#in-range`, 1819), une chip (`#in-values`, `#in-regex` ; aussi la virgule), valide le déverrouillage (2207) et l'enregistrement de profil (2378).
- **Retour arrière** sur un champ de chips vide : retire la dernière chip (1867).
- **Clic sur un en-tête de colonne** (tableau ou liste) : protège/libère la colonne.
- **Clic sur un n° de ligne** : protège/libère la ligne ; **Maj+clic** : intervalle depuis la dernière ligne cliquée.
- **Clic sur une cellule** : bascule la cellule ; **glisser** : zone rectangulaire ; **Maj+clic** : zone depuis la dernière cellule.
- **Glisser-déposer d'un fichier** sur la fenêtre : voile visuel côté JS, chemin réel fourni par Python (`onFileDropped`).
- **Clic sur le fond de l'overlay** : ferme la modale (2530) si rien n'est en cours.
- Toutes ces actions sont bloquées tant que la langue n'a pas été choisie au premier lancement (`S.langRequired`).

## Points d'attention / pièges

- **Aucune donnée sensible calculée côté JS** : la vue IA, le contrôle avant envoi et le chiffrement passent par Python ; la clé ne transite jamais dans la page (commentaire l.1824).
- **Handlers inline** : de nombreux `onclick="…"` dans le HTML et dans les chaînes générées supposent des fonctions globales (et `S`, `api`, `$` accessibles globalement). Renommer une fonction impose de chercher aussi dans les gabarits de chaînes. Les chemins passés à `api.reveal` sont injectés via `esc(JSON.stringify(path))` dans un attribut (2059, 2121, 2451).
- **`errorModal` actions** : le second élément est du code JS en chaîne, pas une fonction.
- **Annulation** : le snapshot contient la sélection **et** `S.opts` ; toute fonction qui modifie l'un ou l'autre doit appeler `pushHistory()` **avant** la modification.
- **`closeModal()` est sans effet quand `S.langRequired`** : toute modale ouverte pendant le choix de langue ne peut pas se fermer.
- **Numérotation de lignes** : tout est 1-based « comme Excel » ; dans l'aperçu de protection, n° = `headerRow + 1 + index` ; dans l'aperçu de restauration, le n° est codé en dur `ri + 2` (1984), car l'aperçu est chargé avec `headerRow = 1`.
- **L'aperçu est tronqué** : `s.rows` ne contient que les premières lignes (`s.total` = total). `renderSummary` extrapole le nombre de valeurs. Les lignes hors aperçu ne se sélectionnent que via le champ de plage.
- **Regex** : c'est Python qui les exécute ; la validation JS n'est qu'un premier retour instantané, remplacé par `api.check_regexes` (et par `api.preview` en vue IA). Ne pas se fier à `new RegExp` seul (`(?<nom>…)` est valide en JS, pas en Python).
- **Profils** : seules les colonnes (par nom, insensible à la casse), options, valeurs et regex sont sauvegardées ; `headerRow` est envoyé à Python mais n'est pas réappliqué par `applyProfile`. Le profil automatique ne s'applique qu'à l'ouverture d'un nouveau fichier.
- **Ordre de déclaration** : `TOKEN_ANY` / `TOKEN_WHOLE` (2165-2166), `lastRow` (1699), `lastCell` (1742) sont déclarés après les fonctions qui les utilisent ; cela fonctionne parce que ces fonctions ne sont appelées qu'après l'exécution complète du script (`boot` attend `api.get_state()`). Ne pas appeler de rendu de manière synchrone en haut du script.
- **`TOKEN_ANY` porte le drapeau `g`** : sûr avec `replace` et `matchAll`, mais un `.test()` direct dessus serait faussé par `lastIndex` (d'où `TOKEN_WHOLE` sans `g`). Il reconnaît aussi les jetons factices `ENC_••••…` affichés sans clé, et les alias `PREFIXE_0042` des anciennes versions (utile en restauration).
- **`errText`** retombe sur `fr` comme `t()` ; le texte brut de Python n'apparaît que pour un code absent des trois langues.
- **Thème clair uniquement**, pas de variables pour le mode sombre ; plusieurs couleurs codées en dur hors `:root`.
- **Polices non embarquées** : Inter et JetBrains Mono ne s'affichent que si elles sont installées sur la machine.
- **Bouton principal orange/brun** (`--color-cta`), et non bleu primaire : la couleur primaire sert aux états sélectionnés et protégés.

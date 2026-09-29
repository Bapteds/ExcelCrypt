# ExcelCrypt — instructions pour Claude

Outil de **pseudonymisation réversible** de fichiers Excel/CSV avant envoi à une IA (DIVE Turbinen). Python 3.14, sans framework front.
Code et documentation en **français** ; interface en fr/de/en.

## Commencer ici
- **`brain/INDEX.md`** : carte de tous les fichiers → une fiche détaillée par fichier dans `brain/files/` (fonctions, lignes, pièges).
- `brain/design/architecture.md` : couches et flux. `brain/design/security.md` : modèle crypto. `brain/design/ui.md` : charte.
- Lire la fiche d'un fichier **avant** de le modifier, plutôt que de relire tout le fichier.

## Structure
- `excelcrypt.py` : moteur + CLI. Toute logique métier ou crypto va ici.
- `gui.py` : pont pywebview (`class Api`), expose ses méthodes publiques à la page.
- `ui/index.html` : page unique HTML/CSS/JS, tokens CSS dans `:root`, textes dans `I18N`.

## Commandes
```bash
source .venv/bin/activate          # pip install -r requirements.txt
python gui.py [--debug]            # interface
python excelcrypt.py encrypt exemple_clients_DIVE.xlsx -c "Contact,E-mail"   # CLI
python excelcrypt.py decrypt exemple_clients_DIVE_chiffre.xlsx
```
Pas de suite de tests. Test de non-régression : chiffrer puis déchiffrer `exemple_clients_DIVE.xlsx`, puis comparer avec l'original.

## Règles impératives
1. **Secrets** : ne jamais lire, afficher, copier ni envoyer `*.key`, `*.vault`, ni la valeur de `EXCELCRYPT_KEY` ou `EXCELCRYPT_PASSWORD`.
2. **Compatibilité des jetons** : ne jamais modifier `TOKEN_PREFIX`, `TOKEN_HEX_LEN`, les `info` HKDF, le séparateur `\x1f`, `pack_value`, `VAULT_MAGIC` ni `KEY_MAGIC`, sinon tous les fichiers et coffres existants deviennent inutilisables. Un changement de format impose une nouvelle version, lue en rétrocompatibilité.
3. **La clé ne quitte jamais Python** : la page ne reçoit que des jetons. Aucun calcul crypto en JS.
4. **Erreurs** : lever `ExcelCryptError(msg_fr, code, **params)` ; côté page, ajouter `err_<code>` dans fr, de **et** en.
5. **Textes UI** : toujours via `I18N` (3 langues), jamais en dur.
6. **Style** : uniquement les tokens `:root` ; orange `--color-cta` réservé à l'action principale ; thème clair ; pas de dépendance externe (CDN, framework).
7. `product.md` et `design-system.md` viennent d'un autre projet DIVE : suivre `brain/design/product.md` et `brain/design/ui.md` en cas de contradiction.

## Tenir le brain à jour (à chaque modification)
- Ajouter une entrée dans `brain/CHANGELOG.md` (`[Non publié]`, date, fichiers).
- Mettre à jour la fiche `brain/files/<fichier>.md` : fonctions ajoutées ou modifiées, **numéros de ligne**, pièges.
- Nouveau fichier : créer sa fiche et l'ajouter à `brain/INDEX.md`.
- Changement d'architecture, de sécurité ou de design : mettre à jour le document concerné dans `brain/design/`.

# Index — ExcelCrypt

> Carte de tous les fichiers du projet. Chaque ligne renvoie à sa fiche détaillée dans `brain/files/`.
> Mettre à jour cet index à chaque ajout, suppression ou renommage de fichier.

## Code source
| Fichier | Lignes | Rôle | Fiche |
|---|---|---|---|
| `excelcrypt.py` | 1247 | Moteur de pseudonymisation + CLI (clés, coffre, jetons, détecteurs, lecture/écriture Excel/CSV) | [files/excelcrypt.py.md](files/excelcrypt.py.md) |
| `gui.py` | 605 | Application de bureau pywebview : classe `Api` exposée à la page, dialogues, profils, lots | [files/gui.py.md](files/gui.py.md) |
| `ui/index.html` | 2529 | Interface complète (HTML + CSS + JS inline), i18n fr/de/en | [files/ui-index.html.md](files/ui-index.html.md) |

## Documentation et configuration
| Fichier | Rôle | Fiche |
|---|---|---|
| `README.md` | Guide utilisateur (installation, GUI, CLI, sécurité) | [files/README.md.md](files/README.md.md) |
| `design-system.md` | Charte DIVE Turbinen (⚠️ écrite pour un autre projet) | [files/design-system.md.md](files/design-system.md.md) |
| `product.md` | Positionnement produit (⚠️ personas d'un autre projet) | [files/product.md.md](files/product.md.md) |
| `requirements.txt` | Dépendances : openpyxl, cryptography, pywebview | [files/requirements.txt.md](files/requirements.txt.md) |
| `.gitignore` | Exclut secrets et état local | [files/.gitignore.md](files/.gitignore.md) |
| `CLAUDE.md` | Instructions pour Claude Code | (ce fichier est la porte d'entrée) |

## Assets
| Fichier | Rôle | Fiche |
|---|---|---|
| `logo.svg` | Logo DIVE Turbinen (source) | [files/logo.svg.md](files/logo.svg.md) |
| `ui/logo.svg` | Copie identique affichée par l'interface | [files/ui-logo.svg.md](files/ui-logo.svg.md) |
| `exemple_clients_DIVE.xlsx` | Données fictives de test (Clients, Projets) | [files/exemples-xlsx.md](files/exemples-xlsx.md) |
| `exemple_clients_DIVE_chiffre.xlsx` | Même fichier protégé | [files/exemples-xlsx.md](files/exemples-xlsx.md) |
| `exemple_clients_DIVE_chiffre_dechiffre.xlsx` | Même fichier restauré (test aller-retour) | [files/exemples-xlsx.md](files/exemples-xlsx.md) |

## État local et secrets (ignorés par git)
| Fichier | Rôle | Fiche |
|---|---|---|
| `excelcrypt.key` 🔒 | Clé maître — ne jamais lire ni partager | [files/excelcrypt.key.md](files/excelcrypt.key.md) |
| `excelcrypt.vault` 🔒 | Coffre chiffré jeton → valeur | [files/excelcrypt.vault.md](files/excelcrypt.vault.md) |
| `excelcrypt_gui.json` | Préférences de l'interface (clé, coffre, langue) | [files/excelcrypt_gui.json.md](files/excelcrypt_gui.json.md) |
| `excelcrypt_profiles.json` | Profils de sélection (créé à la première sauvegarde) | [files/gui.py.md](files/gui.py.md) |

Non documentés (générés) : `.venv/`, `__pycache__/`, `.DS_Store`.

## Brain
| Fichier | Contenu |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Historique des modifications |
| [design/architecture.md](design/architecture.md) | Couches, pont Python↔JS, flux Protéger/Restaurer, contrat d'erreur, dette connue |
| [design/security.md](design/security.md) | Chaîne de clés, jetons, ce qui est protégé ou non, invariants |
| [design/product.md](design/product.md) | Problème, utilisateurs, promesses produit |
| [design/ui.md](design/ui.md) | Charte appliquée à l'interface, conventions, ajout de composants |

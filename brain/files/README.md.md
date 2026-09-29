# README.md
> Guide utilisateur : installation, interface graphique, CLI, fichiers secrets, sécurité. · 82 lignes

## Contenu
| Section | Ce qu'elle couvre |
|---|---|
| Installation | venv + `pip install -r requirements.txt` |
| Fichier d'exemple | `exemple_clients_DIVE.xlsx` (250 clients, 180 projets fictifs) |
| Charte graphique | renvoie à `design-system.md`, tokens CSS en tête de `ui/index.html`, logo `ui/logo.svg` |
| Interface graphique | `python gui.py` ; langue fr/de/en ; parcours **Protéger** (colonnes, lignes, cellules, plages, ⌘Z, en-têtes masqués, détections, Vue IA) ; contrôle avant envoi ; options (propagation, jetons lisibles) ; profils ; traitement par lot ; mot de passe sur la clé ; **Restaurer** |
| Ligne de commande | `keygen`, `inspect`, `encrypt`, `scan`, `passwd`, `decrypt` et leurs options |
| Fichiers à garder chez vous | `excelcrypt.key`, `excelcrypt.vault` |
| Sécurité | HMAC-SHA256 tronqué 64 bits, coffre AES-256-GCM (sous-clé HKDF), déterminisme, ce que l'IA voit encore |

## À maintenir
- Toute nouvelle option CLI ou fonction de l'interface doit y être ajoutée (et dans `brain/CHANGELOG.md`).
- Source de vérité **utilisateur** ; la source de vérité **développeur** est `brain/`.

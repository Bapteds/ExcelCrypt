# Design de l'interface

> Application de `design-system.md` (charte DIVE Turbinen, écrite pour un autre projet React/Tailwind) à ExcelCrypt, qui est une page HTML unique sans framework.

## Où vit le design
- **Tokens** : bloc `:root` en tête de `ui/index.html` (l. 11-49, plus `--z-dropdown` l. 487). **Aucune couleur en dur dans les composants** ; utiliser ou ajouter un token. (Quelques exceptions existantes sont listées dans `files/ui-index.html.md` § CSS.)
- **Icônes** : sprite SVG inline (Lucide + drapeaux), l. 743-787, `<svg class="i"><use href="#i-…"/></svg>`.
- **Logo** : `ui/logo.svg`.

## Règles reprises de `design-system.md`
| Règle | Application dans ExcelCrypt |
|---|---|
| §2 Couleurs verrouillées | `--color-primary #004A99` pour états sélectionnés/protégés, liens, titres ; `--color-cta #A85F00` **uniquement** pour le bouton principal (`.btn.primary`) de chaque zone (« Protéger et enregistrer », « Restaurer ») ; `--color-accent #EE7F00` jamais comme petit texte sur blanc. |
| §1 Filets et losange | Bordures 1 px `--color-border`, ombres rares ; `.diamond` pour la marque et les puces, jamais en orange plein. |
| §4 Mouvement | `--dur: 170ms`, `--ease` ; `prefers-reduced-motion` respecté (l. 435-437). |
| Accessibilité AA | `:focus-visible` anneau 2 px `--color-focus-ring` ; `aria-label` via `data-i18n-aria` sur les boutons-icônes. |
| §8 Anti-slop | pas de dégradés, pas de glassmorphism, pas d'emoji dans l'UI, une seule action orange par zone. |

Non applicables : §5 app-shell et §7 écrans (login/admin) de l'autre projet ; mentions de Tailwind, `tokens.css`, `lucide-react`.

## Conventions d'interface propres à ExcelCrypt
- **4 vues** (`section.view`, une seule `.active`) : Protéger accueil / espace de travail, Restaurer accueil / résultat. Navigation par `showView`.
- **Une seule modale** (`#modal-box`) régénérée par chaque `xxxModal()`.
- **Classes courtes sans BEM**, états par modificateurs : `.on`, `.m` (cellule protégée), `.pick`, `.drag`, `.unk` (jeton inconnu). Masquer = attribut `hidden`.
- **Thème clair uniquement** (choix de la charte).
- **Polices** : Inter / JetBrains Mono si installées, sinon police système (pas d'embarquement).
- **Textes** : toujours via `I18N` (fr/de/en) — jamais de texte en dur dans le HTML ou le JS. Voir `files/ui-index.html.md` § i18n.
- **Survol d'un jeton** en Vue IA : infobulle avec la valeur réelle (calculée par Python).

## Ajouter un écran ou un composant
1. Réutiliser un composant existant (tableau dans `files/ui-index.html.md` § Composants principaux).
2. Styles avec les tokens uniquement ; vérifier contraste AA.
3. Chaînes dans les 3 langues.
4. Si une action Python est nécessaire : méthode dans `Api` (gui.py) renvoyant un dict / `{error, code, params}`.

# design-system.md
> Contrat visuel et composants de la charte DIVE Turbinen. · 191 lignes

## Sections
| § | Ligne | Contenu |
|---|---|---|
| 0 | 14 | Lecture du design, curseurs (variance 3, motion 2, densité 4) |
| 1 | 28 | Idée signature : filets 1 px + « nœud losange » tiré du logo |
| 2 | 45 | Tokens couleur **verrouillés** (primary `#004A99`, CTA `#A85F00`, accent `#EE7F00`, neutral `#BCBDBF`, bg `#F5F7FA`…) |
| 3 | 85 | Typographie |
| 4 | 105 | Espacements, rayons, ombres, mouvement, z-index |
| 5 | 124 | Pattern app-shell |
| 6 | 135 | Inventaire des composants et états |
| 7 | 160 | Écrans (login, home, admin — **propres à l'autre projet**) |
| 8 | 179 | Checklist anti-slop |

## ⚠️ À savoir
- Écrit pour un autre projet DIVE (React + Tailwind v3 + `tokens.css` + lucide-react). ExcelCrypt n'utilise **ni React ni Tailwind** : les tokens sont des variables CSS en tête de `ui/index.html`.
- Les §2 (couleurs), §1 (filets, losange), §4 et §8 s'appliquent tels quels ; §5 et §7 non.
- Mapping vers ExcelCrypt : `brain/design/ui.md`.

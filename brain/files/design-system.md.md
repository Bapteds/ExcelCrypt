# design-system.md
> Contrat visuel et composants de la charte DIVE Turbinen. · 189 lignes

## Sections
| § | Ligne | Contenu |
|---|---|---|
| 0 | 12 | Lecture du design, curseurs (variance 3, motion 2, densité 4) |
| 1 | 26 | Idée signature : filets 1 px + « nœud losange » tiré du logo |
| 2 | 43 | Tokens couleur **verrouillés** (primary `#004A99`, CTA `#A85F00`, accent `#EE7F00`, neutral `#BCBDBF`, bg `#F5F7FA`…) |
| 3 | 83 | Typographie |
| 4 | 103 | Espacements, rayons, ombres, mouvement, z-index |
| 5 | 122 | Pattern app-shell |
| 6 | 133 | Inventaire des composants et états |
| 7 | 158 | Écrans (login, home, admin — **propres à l'autre projet**) |
| 8 | 177 | Checklist anti-slop |

## ⚠️ À savoir
- Écrit pour un autre projet DIVE (React + Tailwind v3 + `tokens.css` + lucide-react). ExcelCrypt n'utilise **ni React ni Tailwind** : les tokens sont des variables CSS en tête de `ui/index.html`.
- Les §2 (couleurs), §1 (filets, losange), §4 et §8 s'appliquent tels quels ; §5 et §7 non.
- Mapping vers ExcelCrypt : `brain/design/ui.md`.

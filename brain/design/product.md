# Produit — ExcelCrypt

> Version ExcelCrypt de `product.md` (racine), dont les personas et la description viennent d'un autre projet DIVE.

## Problème
Les équipes veulent confier des fichiers Excel/CSV à une IA (analyse, nettoyage, reporting) sans lui transmettre de données personnelles ou confidentielles (noms, e-mails, téléphones, IBAN, n° fiscaux…).

## Solution
Pseudonymisation **réversible** et **déterministe** :
1. **Protéger** : les valeurs choisies sont remplacées par des jetons (`ENC_9f3a…` ou `CONTACT_0042`). La correspondance reste dans un coffre chiffré local.
2. L'utilisateur envoie le fichier protégé à l'IA, qui peut regrouper, compter et joindre sur les jetons.
3. **Restaurer** : les jetons présents n'importe où dans le fichier renvoyé sont remplacés par les vraies valeurs, avec leur type d'origine.

## Utilisateurs
Personnel de **DIVE Turbinen GmbH & Co. KG**, pas forcément technique (commercial, administration, gestion de projet, ingénierie), sur un poste de bureau macOS ou Windows. Deux points d'entrée :
- **Interface graphique** (`gui.py`) pour l'usage courant ;
- **CLI** (`excelcrypt.py`) pour l'automatisation et les utilisateurs avancés.
Langues : français, allemand, anglais.

## Promesses (non négociables)
- La clé et les valeurs réelles **ne quittent jamais la machine** ; même la page web de l'interface ne reçoit que des jetons.
- **Ce que vous voyez dans « Vue IA » est exactement ce que l'IA recevra.**
- **Contrôle avant envoi** systématique : toute fuite probable hors des zones protégées est signalée.
- Aller-retour **sans perte** : `restaurer(protéger(f)) == f` (valeurs, types, formules, feuilles).
- Stabilité : un jeton émis reste valable pour toujours avec la même clé et le même coffre.

## Personnalité et principes
Repris de `product.md` (valables ici) : *Engineered, Precise, Trustworthy* ; l'outil s'efface derrière la tâche ; orange réservé à l'action principale ; tous les états sont explicites ; les actions irréversibles sont protégées (ex. écraser une clé existante).

## Hors périmètre
Anonymisation au sens RGPD (voir `security.md`), partage multi-utilisateur du coffre, stockage cloud.

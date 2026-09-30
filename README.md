# ExcelCrypt

Masque des colonnes ou des valeurs d'un fichier Excel/CSV avant de l'envoyer à une IA, puis restaure les vraies données dans le fichier que l'IA renvoie.

## Installation
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Fichier d'exemple
`exemple_clients_DIVE.xlsx` contient 250 clients et 180 projets fictifs, avec des noms, e-mails, téléphones allemands et français, des IBAN et des dates de naissance. Il sert à tester l'application sans données réelles.

## Charte graphique
L'interface suit la charte DIVE Turbinen décrite dans `design-system.md` : thème clair, bleu `#004A99`, orange `#A85F00` réservé à l'action principale, gris du logo et filets de 1 px. Toutes les couleurs sont définies une seule fois, en variables CSS, au début de `ui/index.html`. Le logo affiché est `ui/logo.svg`.

## Interface graphique
```bash
python gui.py
```
**Langue** : français, allemand ou anglais. Elle est demandée au premier lancement, puis se change avec le drapeau en haut à droite. Le choix est enregistré dans `excelcrypt_gui.json`.
Fenêtre native (WKWebView sur macOS, WebView2 sur Windows) qui affiche `ui/index.html`. La clé ne quitte jamais Python : la page ne reçoit que les jetons.

**Protéger**
1. Glissez un fichier dans la fenêtre (ou ⌘O / Ctrl+O).
2. Activez les colonnes à masquer dans la liste, ou cliquez sur leur en-tête dans le tableau. **Suggérer** coche les colonnes qui ressemblent à des données personnelles.
3. Protégez aussi des lignes ou des cellules précises :
   - clic sur un **numéro de ligne** pour la ligne entière, Maj+clic pour une série de lignes ;
   - clic sur une **cellule**, **glisser** pour une zone, Maj+clic pour étendre depuis la dernière cellule ;
   - champ **Ajouter une plage** : `B5`, `A2:C40`, `12-30`, `D:F` ou un nom de colonne, y compris au-delà des 500 lignes de l'aperçu ;
   - **⌘Z / Ctrl+Z** (ou le bouton ↶) annule la dernière modification de sélection.
   - **Masquer aussi les noms de colonnes** (activé par défaut) : l'en-tête des colonnes protégées devient lui aussi un jeton, restauré au retour.
4. Ajoutez si besoin une détection dans tout le texte : e-mails, téléphones, valeurs précises, regex.
5. **Vue IA** montre exactement ce que l'IA recevra. Survolez un jeton pour voir la valeur réelle.
6. **Protéger et enregistrer**.

**Contrôle avant envoi** : avant chaque enregistrement, le fichier complet est analysé. Tout ce qui ressemble encore à une donnée personnelle hors des zones protégées est listé (e-mail, téléphone, IBAN, carte, n° de TVA, Steuer-ID, n° de sécurité sociale FR/DE, SIRET, ou valeur protégée visible ailleurs). Un clic sur « Corriger et protéger » active les détections nécessaires.

**Options des colonnes protégées**
- *Masquer aussi les noms de colonnes* : l'en-tête devient un jeton.
- *Masquer aussi ces valeurs ailleurs* : un nom protégé dans « Contact » est aussi masqué s'il apparaît dans un commentaire, sur n'importe quelle feuille.

**Profils** : « Enregistrer » mémorise les colonnes (par leur nom), les détections et les options dans `excelcrypt_profiles.json`. À l'ouverture d'un fichier qui contient toutes les colonnes d'un profil, celui-ci s'applique tout seul, avec la possibilité d'annuler.

**Traitement par lot** : « Protéger tout un dossier… » applique un profil à chaque fichier Excel/CSV d'un dossier, et « Restaurer tout un dossier… » fait l'inverse. Un bilan est affiché par fichier.

**Mot de passe sur la clé** : depuis la pastille de la clé, choisissez « Définir un mot de passe ». La clé est alors chiffrée (Argon2id + AES-256-GCM) et demandée à chaque démarrage. Ni la clé ni les jetons ne changent : les coffres existants restent valables. Un mot de passe oublié ne peut pas être récupéré.

**Restaurer** : glissez le fichier renvoyé par l'IA. Un aperçu du résultat s'affiche, et les jetons inconnus du coffre sont signalés.

La clé et le coffre se gèrent depuis les pastilles en haut à droite.

## Ligne de commande
```bash
python excelcrypt.py keygen                          # 1 seule fois -> excelcrypt.key (SECRET)
python excelcrypt.py inspect clients.xlsx            # voir feuilles / colonnes
python excelcrypt.py encrypt clients.xlsx -c "Nom,Email,IBAN"   # -> clients_chiffre.xlsx
#   --select "B5,A2:C40,12-30,D:F" : cellules, zones, lignes, colonnes
#   --detect email,phone_fr,phone_de,iban,card,vat,steuer_id,nir,rvnr,siret
#   --propagate : masque aussi ailleurs les valeurs des cellules masquées
python excelcrypt.py scan clients.xlsx -c "Nom"      # contrôle des fuites (code retour 2 si fuite)
python excelcrypt.py keygen --password               # clé protégée par mot de passe
python excelcrypt.py passwd                          # ajouter / changer / retirer le mot de passe
#   mot de passe non interactif : variable EXCELCRYPT_PASSWORD
#   --mask-headers : masque aussi le nom des colonnes masquées
#   options : -s Feuille1  --value "ACME"  --regex "FR\d{12}"  --emails  --phones
#   sans -c : mode interactif (choix des colonnes)
# ... envoyer clients_chiffre.xlsx à l'IA, récupérer resultat.xlsx ...
python excelcrypt.py decrypt resultat.xlsx           # -> resultat_dechiffre.xlsx
```

## Fichiers à garder chez vous (ne jamais envoyer)
- `excelcrypt.key`: la clé secrète. Si vous la perdez, rien ne peut être déchiffré.
- `excelcrypt.vault`: le coffre chiffré (jeton -> valeur). Il grossit au fil des fichiers.

## Sécurité
- Jeton = HMAC-SHA256(clé, valeur), tronqué à 64 bits. Sans la clé, on ne peut pas le deviner par dictionnaire.
- Le coffre est chiffré en AES-256-GCM avec une sous-clé dérivée (HKDF).
- La même valeur donne toujours le même jeton, donc l'IA peut regrouper, compter et joindre sur les colonnes masquées.
- Ce que l'IA voit encore : les colonnes non masquées et la fréquence des valeurs masquées.

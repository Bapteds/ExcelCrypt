# Modèle de sécurité

## Chaîne de clés
```
excelcrypt.key (clé maître 256 bits, éventuellement chiffrée Argon2id + AES-256-GCM)
   ├── HKDF-SHA256 info="excelcrypt/token" → token_key → HMAC-SHA256 des valeurs
   └── HKDF-SHA256 info="excelcrypt/vault" → vault_key → AES-256-GCM du coffre
```
Sous-clés indépendantes : compromettre l'une ne révèle pas l'autre.

## Jeton
`hex = HMAC-SHA256(token_key, type ‖ 0x1F ‖ valeur)[:16 hex]` → `ENC_<hex>` (64 bits).
- **Déterministe**, sans sel par fichier : même valeur + même clé ⇒ même jeton, dans un fichier ou entre fichiers.
- Le **type** fait partie de l'empreinte : `12` (nombre) ≠ `"12"` (texte).
- **Sensible à la casse** ; espaces de début/fin retirés pour une cellule masquée en entier.
- Jetons lisibles (`PREFIXE_0042`) : alias attribués séquentiellement et stockés dans le coffre, donc stables d'un fichier à l'autre avec le même coffre.
- Collision (même hex pour deux valeurs) : détectée à l'écriture dans le coffre, le traitement s'arrête.

## Ce qui est protégé
- Retrouver une valeur à partir d'un jeton est impossible sans la clé (HMAC à clé secrète : pas d'attaque par dictionnaire, contrairement à un SHA-256 nu).
- Le coffre est illisible sans la clé et son intégrité est vérifiée (GCM).
- La clé peut être protégée par un mot de passe (Argon2id, 64 Mio, 3 itérations).

## Ce qui n'est PAS protégé (pseudonymisation ≠ anonymisation)
- **Liaison** : un destinataire peut suivre un même jeton à travers plusieurs fichiers et envois.
- **Fréquences** : le nombre d'occurrences de chaque jeton reste visible.
- **Quasi-identifiants** : les colonnes non masquées (ville, date, métier…) peuvent suffire à ré-identifier.
- **Jetons lisibles** : ils révèlent la catégorie et l'ordre de première apparition.
- Au sens du RGPD, les données restent des **données personnelles**.

## Recommandations
- Une clé (et un coffre) **par projet ou par destinataire** si la liaison entre fichiers est indésirable.
- Masquer aussi les quasi-identifiants ; utiliser le contrôle avant envoi (`scan`).
- Sauvegarder clé **et** coffre : la perte de l'un ou l'autre rend la restauration impossible.
- Ne jamais versionner `*.key` / `*.vault` (déjà dans `.gitignore`).

## Invariants à ne jamais casser
Changer l'un des éléments suivants rend **tous les jetons et coffres existants** inutilisables :
les chaînes `info` HKDF, le format `type\x1fvaleur`, `TOKEN_PREFIX`, `TOKEN_HEX_LEN`, `pack_value`, `VAULT_MAGIC`, `KEY_MAGIC`.
Tout changement de format passe par un nouveau numéro de version et une lecture rétrocompatible (comme `Vault._load` pour le format 1).

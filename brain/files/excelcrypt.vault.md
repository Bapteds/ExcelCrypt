# excelcrypt.vault — 🔒 SECRET
> Coffre chiffré jeton → valeur réelle (+ alias lisibles des anciennes versions). · Classe `Vault` de `excelcrypt.py` · Ignoré par git

**Ne jamais lire ni envoyer ce fichier.**

## Format binaire
`VAULT_MAGIC` (`b"XLCV1"`, `excelcrypt.py:82`) ‖ nonce 12 octets ‖ AES-256-GCM(`vault_key`, JSON, AAD = `VAULT_MAGIC`)

JSON format 2 : `{"v": 2, "entries": {hex: valeur typée}, "aliases": {hex: "CONTACT_0042"}, "counters": {préfixe: n}}`. Le format 1 (ancien) ne contenait que `entries` ; il est toujours lu (`Vault._load`). `aliases` et `counters` ne sont plus alimentés (jetons lisibles retirés) mais sont conservés à chaque sauvegarde pour restaurer les anciens fichiers.

## Comportement
- Grossit à chaque chiffrement (une entrée par valeur distincte) ; jamais purgé automatiquement.
- Écriture atomique : `.vault.tmp` puis `os.replace` (`Vault.save`), uniquement si `dirty`. Nouveau nonce aléatoire à chaque sauvegarde.
- Un même jeton pour deux valeurs différentes lève `ExcelCryptError(code="collision")`.
- Sans le coffre, le déchiffrement est impossible même avec la clé (le HMAC n'est pas réversible).

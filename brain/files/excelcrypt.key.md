# excelcrypt.key — 🔒 SECRET
> Clé maître de 256 bits. · Créée par `python excelcrypt.py keygen` · Ignorée par git · permissions 600

**Ne jamais lire, afficher, copier, commiter ni envoyer ce fichier.**

## Formats
- **Non protégée** : la clé maître encodée en base64, sur une ligne.
- **Protégée par mot de passe** : préfixe magique `KEY_MAGIC` (`"EXCELCRYPT-KEY-2"`, `excelcrypt.py:83`) suivi d'un JSON `{kdf: "argon2id", argon2: {iterations: 3, lanes: 4, memory_cost: 65536}, salt, nonce, ct}` (paramètres `ARGON2`, `excelcrypt.py:383` : 64 Mio) ; AAD = `KEY_MAGIC`. La clé maître est chiffrée en AES-256-GCM avec une clé dérivée du mot de passe par Argon2id (`write_key`, `_unlock_key_text` dans `excelcrypt.py`).

## Rôle
Deux sous-clés en sont dérivées par HKDF-SHA256 (`Keys`) :
- `token_key` (`info="excelcrypt/token"`) → HMAC des jetons ;
- `vault_key` (`info="excelcrypt/vault"`) → chiffrement du coffre.

Perdre la clé = impossible de déchiffrer le coffre et de recalculer les jetons. Changer de clé = tous les jetons changent. Ajouter/retirer un mot de passe (`passwd`) **ne change pas** la clé maître.
Source alternative : variable d'environnement `EXCELCRYPT_KEY`.

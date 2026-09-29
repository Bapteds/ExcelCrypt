# requirements.txt
> Dépendances Python. · 3 lignes

| Paquet | Contrainte | Utilisé pour |
|---|---|---|
| `openpyxl` | `>=3.1` | lecture/écriture `.xlsx` / `.xlsm` (VBA conservé) |
| `cryptography` | `>=44` | AES-GCM, HKDF-SHA256, Argon2id (`cryptography.hazmat.primitives.kdf.argon2`, nécessite une version récente) |
| `pywebview` | `>=6.0` | fenêtre native de `gui.py` (WKWebView macOS, WebView2 Windows) |

Le reste vient de la bibliothèque standard (`hmac`, `hashlib`, `csv`, `json`, `re`, `unicodedata`…).
Versions installées dans `.venv` (Python 3.14) : cryptography 50.0.1, openpyxl 3.1.5, pywebview 6.2.1.

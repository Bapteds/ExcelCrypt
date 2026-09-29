#!/usr/bin/env python3
"""
ExcelCrypt - Pseudonymisation réversible de fichiers Excel/CSV.

Principe
--------
Chaque valeur sensible est remplacée par un jeton court et déterministe :

    "Jean Dupont"  ->  ENC_9f3a1c0b7d2e4a68      (ou CONTACT_0042 en mode « jetons lisibles »)

* Le jeton dérive d'un HMAC-SHA256 de la valeur, calculé avec VOTRE clé secrète :
  sans la clé, impossible de le recalculer ou de le deviner.
* Même valeur => même jeton : l'IA peut toujours grouper, compter, joindre.
* La correspondance jeton -> valeur réelle est stockée dans un « coffre » (.vault)
  chiffré en AES-256-GCM avec la même clé. Il ne quitte jamais votre machine.
* La clé peut elle-même être protégée par un mot de passe (Argon2id + AES-256-GCM).
* Le déchiffrement retrouve les jetons PARTOUT dans le fichier renvoyé par l'IA
  et les remplace par les vraies valeurs, avec leur type d'origine.

Commandes
---------
    python excelcrypt.py keygen [--password]          # crée excelcrypt.key
    python excelcrypt.py passwd                       # ajoute / change / retire le mot de passe
    python excelcrypt.py inspect  fichier.xlsx
    python excelcrypt.py scan     fichier.xlsx -c "Nom"          # contrôle des fuites
    python excelcrypt.py encrypt  fichier.xlsx -c "Nom,Email,C" --detect email,iban --propagate
    python excelcrypt.py decrypt  fichier_retour_ia.xlsx

Interface graphique : python gui.py
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import getpass
import hashlib
import hmac
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

try:
    import openpyxl
    from openpyxl.utils import column_index_from_string, get_column_letter
except ImportError:  # pragma: no cover
    sys.exit("openpyxl manquant : pip install -r requirements.txt")

DEFAULT_KEY = "excelcrypt.key"
DEFAULT_VAULT = "excelcrypt.vault"
KEY_ENV = "EXCELCRYPT_KEY"
PASSWORD_ENV = "EXCELCRYPT_PASSWORD"

TOKEN_PREFIX = "ENC_"
TOKEN_HEX_LEN = 16  # 64 bits -> collisions négligeables même sur des millions de valeurs
TOKEN_RE = re.compile(rf"{TOKEN_PREFIX}([0-9a-fA-F]{{{TOKEN_HEX_LEN}}})(?![0-9a-fA-F])", re.IGNORECASE)
# Jeton lisible : PREFIXE_0042 (préfixe en majuscules, au moins 4 chiffres)
ALIAS_RE = re.compile(r"(?<![\w])([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)_(\d{4,})(?!\w)")
ANY_TOKEN_RE = re.compile(rf"{TOKEN_RE.pattern}|{ALIAS_RE.pattern}", re.IGNORECASE)

EMAIL_RE = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
# Numéro isolé (pas au milieu d'un IBAN ou d'une référence), même séparateur partout : 06 12 34 56 78, 06.12..., 0612345678
PHONE_FR_RE = r"(?<![\w+/-])(?:\+33\s?|0)[1-9]([\s.-]?)\d{2}(?:\1\d{2}){3}(?!\w)"
# Numéro allemand : +49 / 0049 / 0 + indicatif (2 à 5 chiffres) + abonné, ex. +49 151 12345678, 030 12345678, 0151/1234567.
# Refuse un numéro précédé ou suivi d'un autre groupe de chiffres (groupes d'un IBAN, références).
PHONE_DE_RE = (r"(?<![\w+/.-])(?<!\d[\s.-])(?:(?:\+|00)49[\s.-]?(?:\(0\)[\s.-]?)?|0)[1-9]\d{1,4}"
               r"[\s./-]?\d{3,8}(?:[\s-]\d{2,5})?(?![\s./-]?\d)(?!\w)")

VAULT_MAGIC = b"XLCV1"
KEY_MAGIC = "EXCELCRYPT-KEY-2"
EXCEL_EXT = {".xlsx", ".xlsm"}
CSV_EXT = {".csv", ".tsv", ".txt"}
CSV_SHEET = "(csv)"
PROPAGATE_MIN_LEN = 3  # valeurs plus courtes jamais propagées (trop de faux positifs)

# (feuille, en-têtes) -> cellules à masquer : SheetSelection, ou un simple set d'index de colonnes (1-based),
# ou None pour ignorer la feuille
ColumnSelector = Callable[[str, list], "SheetSelection | set[int] | None"]
Progress = Callable[[int, int], None]


class ExcelCryptError(Exception):
    """Erreur utilisateur. Le message (français) est affiché tel quel en ligne de commande ;
    `code` + `params` permettent à l'interface graphique de le traduire."""

    def __init__(self, message: str, code: str | None = None, **params):
        super().__init__(message)
        self.code = code
        self.params = params


# --------------------------------------------------------------------------- #
# Sélection de cellules
# --------------------------------------------------------------------------- #
@dataclass
class SheetSelection:
    """Cellules à masquer dans une feuille. Lignes et colonnes numérotées comme dans Excel (1-based)."""

    cols: set[int] = field(default_factory=set)
    rows: list[tuple[int, int]] = field(default_factory=list)              # plages de lignes inclusives
    cells: set[tuple[int, int]] = field(default_factory=set)               # (ligne, colonne)
    rects: list[tuple[int, int, int, int]] = field(default_factory=list)   # (ligne1, col1, ligne2, col2)

    def __bool__(self) -> bool:
        return bool(self.cols or self.rows or self.cells or self.rects)

    def has(self, r: int, c: int) -> bool:
        if c in self.cols or (r, c) in self.cells:
            return True
        if any(a <= r <= b for a, b in self.rows):
            return True
        return any(r1 <= r <= r2 and c1 <= c <= c2 for r1, c1, r2, c2 in self.rects)

    def update(self, other: "SheetSelection") -> "SheetSelection":
        self.cols |= other.cols
        self.rows += other.rows
        self.cells |= other.cells
        self.rects += other.rects
        return self

    @classmethod
    def from_dict(cls, d: dict) -> "SheetSelection":
        return cls(
            cols={int(c) for c in d.get("cols", [])},
            rows=[(int(a), int(b)) for a, b in d.get("rows", [])],
            cells={(int(r), int(c)) for r, c in d.get("cells", [])},
            rects=[tuple(int(x) for x in q) for q in d.get("rects", [])],
        )

    def to_dict(self) -> dict:
        return {"cols": sorted(self.cols), "rows": [list(x) for x in self.rows],
                "cells": [list(x) for x in sorted(self.cells)], "rects": [list(x) for x in self.rects]}


_REF_CELL = r"([A-Za-z]{1,3})(\d+)"


def parse_refs(text: str, header: list | None = None) -> tuple[SheetSelection, list[str]]:
    """
    Lit une liste de références à la Excel, séparées par des virgules ou points-virgules :
      B5 (cellule), A2:C40 (zone), 12 ou 12-30 ou 12:30 (lignes), D ou D:F (colonnes), Nom (en-tête).
    Retourne la sélection et la liste des références non comprises.
    """
    by_name = {str(h).strip().casefold(): i for i, h in enumerate(header or [], start=1) if h not in (None, "")}
    sel, errors = SheetSelection(), []
    for raw in re.split(r"[,;\n]+", text or ""):
        t = raw.strip()
        if not t:
            continue
        if t.casefold() in by_name:
            sel.cols.add(by_name[t.casefold()])
        elif m := re.fullmatch(r"(\d+)(?:\s*[-:]\s*(\d+))?", t):
            a, b = int(m[1]), int(m[2] or m[1])
            if min(a, b) < 1:
                errors.append(t)
            else:
                sel.rows.append((min(a, b), max(a, b)))
        elif m := re.fullmatch(_REF_CELL, t):
            sel.cells.add((int(m[2]), column_index_from_string(m[1].upper())))
        elif m := re.fullmatch(_REF_CELL + r"\s*:\s*" + _REF_CELL, t):
            c1, c2 = column_index_from_string(m[1].upper()), column_index_from_string(m[3].upper())
            r1, r2 = int(m[2]), int(m[4])
            sel.rects.append((min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)))
        elif m := re.fullmatch(r"([A-Za-z]{1,3})(?:\s*:\s*([A-Za-z]{1,3}))?", t):
            a = column_index_from_string(m[1].upper())
            b = column_index_from_string((m[2] or m[1]).upper())
            sel.cols.update(range(min(a, b), max(a, b) + 1))
        else:
            errors.append(t)
    return sel, errors


def profile_selection(columns: list[str], header: list) -> SheetSelection:
    """Colonnes d'un profil (noms d'en-tête, casse ignorée) -> sélection pour une feuille."""
    wanted = {str(c).strip().casefold() for c in columns if str(c).strip()}
    return SheetSelection(cols={i for i, h in enumerate(header or [], start=1)
                                if h not in (None, "") and str(h).strip().casefold() in wanted})


# --------------------------------------------------------------------------- #
# Détecteurs (avec validation par somme de contrôle quand elle existe)
# --------------------------------------------------------------------------- #
def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _luhn(num: str) -> bool:
    total, alt = 0, False
    for ch in reversed(num):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _iban_ok(s: str) -> bool:
    s = re.sub(r"\s", "", s).upper()
    if not 15 <= len(s) <= 34:
        return False
    num = "".join(str(int(ch, 36)) for ch in s[4:] + s[:4])
    return int(num) % 97 == 1


def _card_ok(s: str) -> bool:
    d = _digits(s)
    return 13 <= len(d) <= 19 and d[0] in "23456" and _luhn(d)


def _steuer_id_ok(s: str) -> bool:
    """Steuerliche Identifikationsnummer (DE) : 11 chiffres, clé ISO 7064 MOD 11,10."""
    d = _digits(s)
    if len(d) != 11 or d[0] == "0":
        return False
    product = 10
    for ch in d[:10]:
        total = (int(ch) + product) % 10 or 10
        product = (total * 2) % 11
    check = 11 - product
    return (0 if check == 10 else check) == int(d[10])


def _nir_ok(s: str) -> bool:
    """N° de sécurité sociale français : 13 caractères + clé = 97 - (numéro mod 97). Corse : 2A -> 19, 2B -> 18."""
    t = re.sub(r"\s", "", s).upper()
    if len(t) != 15:
        return False
    body = t[:13].replace("2A", "19", 1) if t[5:7] == "2A" else t[:13].replace("2B", "18", 1) if t[5:7] == "2B" else t[:13]
    if not body.isdigit() or not t[13:].isdigit():
        return False
    return 97 - int(body) % 97 == int(t[13:])


def _rvnr_ok(s: str) -> bool:
    """Rentenversicherungsnummer (DE) : 12 caractères dont une lettre, clé pondérée 2121212121 2 1..."""
    t = re.sub(r"\s", "", s).upper()
    if not re.fullmatch(r"\d{8}[A-Z]\d{3}", t):
        return False
    digits = t[:8] + f"{ord(t[8]) - 64:02d}" + t[9:11]
    weights = [2, 1, 2, 5, 7, 1, 2, 1, 2, 1, 2, 1]
    total = sum(sum(divmod(int(d) * w, 10)) for d, w in zip(digits, weights))
    return total % 10 == int(t[11])


def _siret_ok(s: str) -> bool:
    d = _digits(s)
    return len(d) == 14 and _luhn(d)


@dataclass(frozen=True)
class Detector:
    key: str
    prefix: str                       # préfixe des jetons lisibles
    regex: re.Pattern
    check: Callable[[str], bool] | None = None

    def matches(self, text: str):
        for m in self.regex.finditer(text):
            if self.check is None or self.check(m.group(0)):
                yield m

    def sub(self, text: str, repl: Callable[[str, str], str]) -> str:
        def one(m):
            v = m.group(0)
            return repl(v, self.prefix) if self.check is None or self.check(v) else v
        return self.regex.sub(one, text)


DETECTORS: dict[str, Detector] = {d.key: d for d in [
    Detector("email", "EMAIL", re.compile(EMAIL_RE)),
    Detector("phone_fr", "PHONE", re.compile(PHONE_FR_RE)),
    Detector("phone_de", "PHONE", re.compile(PHONE_DE_RE)),
    Detector("iban", "IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b"), _iban_ok),
    Detector("card", "CARD", re.compile(r"(?<![\w.,+(-])(?<!\d[ -])\d(?:[ -]?\d){12,18}(?![\w.,-])(?![ -]\d)"), _card_ok),
    Detector("vat", "VAT", re.compile(
        r"\b(?:DE ?\d{3} ?\d{3} ?\d{3}|FR ?[0-9A-HJ-NP-Z]{2} ?\d{3} ?\d{3} ?\d{3}|ATU ?\d{8}|IT ?\d{11}|"
        r"ES ?[0-9A-Z]\d{7}[0-9A-Z]|NL ?\d{9}B\d{2}|BE ?0?\d{9}|LU ?\d{8}|CHE[- ]?\d{3}\.?\d{3}\.?\d{3})\b")),
    Detector("steuer_id", "TAXID", re.compile(r"(?<![\w.,+(-])(?<!\d[ -])[1-9]\d ?\d{3} ?\d{3} ?\d{3}(?![\w.,-])(?![ -]\d)"),
             _steuer_id_ok),
    Detector("nir", "SSN", re.compile(r"\b[12] ?\d{2} ?\d{2} ?(?:\d{2}|2[AB]) ?\d{3} ?\d{3} ?\d{2}\b", re.IGNORECASE), _nir_ok),
    Detector("rvnr", "SSN", re.compile(r"\b\d{2} ?\d{6} ?[A-Z] ?\d{3}\b"), _rvnr_ok),
    Detector("siret", "SIRET", re.compile(r"(?<![\w.,+(-])(?<!\d[ -])\d{3} ?\d{3} ?\d{3} ?\d{5}(?![\w.,-])(?![ -]\d)"), _siret_ok),
]}


def build_detectors(keys: list[str] | None = None, regexes: list[str] | None = None) -> list[Detector]:
    """Détecteurs actifs (clés de DETECTORS) + motifs regex de l'utilisateur."""
    out = []
    for k in keys or []:
        if k not in DETECTORS:
            raise ExcelCryptError(f"Détecteur inconnu : {k} (disponibles : {', '.join(DETECTORS)})")
        out.append(DETECTORS[k])
    for r in regexes or []:
        try:
            out.append(Detector("regex", "PATTERN", re.compile(r)))
        except re.error as e:
            raise ExcelCryptError(f"Regex invalide '{r}' : {e}", "regex_invalid", pattern=r)
    return out


def build_patterns(regexes=None, emails=False, phones=False, phones_de=False) -> list[Detector]:
    """Compatibilité : ancienne signature."""
    keys = [k for k, on in (("email", emails), ("phone_fr", phones), ("phone_de", phones_de)) if on]
    return build_detectors(keys, regexes)


def detect_column(values: list[str]) -> str | None:
    """Détecteur qui reconnaît la majorité des valeurs d'une colonne (pour « Suggérer »)."""
    texts = [str(v).strip() for v in values if v not in (None, "")][:100]
    if not texts:
        return None
    for d in DETECTORS.values():
        hits = sum(1 for t in texts if any(len(m.group(0)) >= 0.8 * len(t) for m in d.matches(t)))
        if hits > len(texts) / 2:
            return d.key
    return None


# --------------------------------------------------------------------------- #
# Propagation : valeurs masquées -> recherche rapide dans le texte libre
# --------------------------------------------------------------------------- #
def _trie_regex(words: list[str]) -> str:
    """Construit une regex compacte (arbre de préfixes) qui reconnaît n'importe quel mot de la liste."""
    trie: dict = {}
    for w in words:
        node = trie
        for ch in w:
            node = node.setdefault(ch, {})
        node[""] = {}

    def build(node: dict) -> str:
        end = "" in node
        alts = [re.escape(ch) + build(sub) for ch, sub in sorted(node.items()) if ch != ""]
        if not alts:
            return ""
        body = alts[0] if len(alts) == 1 else "(?:" + "|".join(alts) + ")"
        return f"(?:{body})?" if end else body

    return build(trie)


class Propagation:
    """Valeurs des cellules masquées, à masquer aussi partout où elles apparaissent dans le texte."""

    def __init__(self):
        self.prefix_of: dict[str, str] = {}   # valeur (casefold) -> préfixe de jeton lisible
        self.regex: re.Pattern | None = None

    def add(self, value, prefix: str) -> None:
        if not isinstance(value, str):
            return
        v = value.strip()
        if len(v) < PROPAGATE_MIN_LEN or is_token(v) or is_formula(v):
            return
        self.prefix_of.setdefault(v.casefold(), prefix)

    def compile(self) -> "Propagation":
        words = sorted(self.prefix_of, key=len, reverse=True)
        self.regex = re.compile(r"(?<!\w)(?:" + _trie_regex(words) + r")(?!\w)", re.IGNORECASE) if words else None
        return self

    def __bool__(self) -> bool:
        return self.regex is not None


# --------------------------------------------------------------------------- #
# Clé (avec mot de passe optionnel)
# --------------------------------------------------------------------------- #
ARGON2 = {"iterations": 3, "lanes": 4, "memory_cost": 64 * 1024}  # 64 Mio


def _password_key(password: str, salt: bytes, params: dict) -> bytes:
    return Argon2id(salt=salt, length=32, iterations=params["iterations"], lanes=params["lanes"],
                    memory_cost=params["memory_cost"]).derive(password.encode("utf-8"))


class Keys:
    """Dérive deux sous-clés indépendantes depuis la clé maître."""

    def __init__(self, master: bytes):
        if len(master) != 32:
            raise ExcelCryptError("La clé doit faire 32 octets (256 bits).", "key_invalid")
        self.master = master
        self.token_key = self._derive(master, b"excelcrypt/token")
        self.vault_key = self._derive(master, b"excelcrypt/vault")

    @staticmethod
    def _derive(master: bytes, info: bytes) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)

    @classmethod
    def from_text(cls, raw: str, password: str | None = None) -> "Keys":
        raw = raw.strip()
        if raw.startswith(KEY_MAGIC):
            return cls(_unlock_key_text(raw, password))
        try:
            master = base64.b64decode(raw, validate=True)
        except Exception:
            raise ExcelCryptError("Clé invalide (attendu : 32 octets encodés en base64).", "key_invalid")
        return cls(master)

    @classmethod
    def from_file(cls, path: Path, password: str | None = None) -> "Keys":
        if not Path(path).exists():
            raise ExcelCryptError(f"Fichier clé introuvable : {path}", "key_missing", path=str(path))
        return cls.from_text(Path(path).read_text(), password)


def key_is_protected(path: Path) -> bool:
    try:
        return Path(path).read_text().lstrip().startswith(KEY_MAGIC)
    except OSError:
        return False


def _unlock_key_text(raw: str, password: str | None) -> bytes:
    if not password:
        raise ExcelCryptError("La clé est protégée par un mot de passe.", "key_locked")
    try:
        data = json.loads(raw[len(KEY_MAGIC):].strip())
        salt, nonce, ct = (base64.b64decode(data[k]) for k in ("salt", "nonce", "ct"))
        params = data["argon2"]
    except Exception:
        raise ExcelCryptError("Fichier clé illisible.", "key_invalid")
    try:
        return AESGCM(_password_key(password, salt, params)).decrypt(nonce, ct, KEY_MAGIC.encode())
    except InvalidTag:
        raise ExcelCryptError("Mot de passe incorrect.", "key_bad_password")


def write_key(path: Path, master: bytes, password: str | None = None) -> None:
    """Écrit la clé maître, en clair (base64) ou chiffrée par un mot de passe. Écriture atomique."""
    path = Path(path)
    if password:
        salt, nonce = os.urandom(16), os.urandom(12)
        ct = AESGCM(_password_key(password, salt, ARGON2)).encrypt(nonce, master, KEY_MAGIC.encode())
        text = KEY_MAGIC + "\n" + json.dumps({
            "kdf": "argon2id", "argon2": ARGON2, "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(), "ct": base64.b64encode(ct).decode()}) + "\n"
    else:
        text = base64.b64encode(master).decode() + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def generate_key(path: Path, force: bool = False, password: str | None = None) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise ExcelCryptError(f"'{path}' existe déjà. Utilisez --force pour l'écraser "
                              "(ATTENTION : les fichiers chiffrés avec l'ancienne clé deviendront irrécupérables).")
    write_key(path, os.urandom(32), password)


def load_key(key_arg: str | None, password: str | None = None) -> Keys:
    """Clé pour la ligne de commande. Mot de passe : argument, $EXCELCRYPT_PASSWORD, ou saisie masquée."""
    if key_arg and not Path(key_arg).exists():
        return Keys.from_text(key_arg, password)
    if not key_arg and os.environ.get(KEY_ENV):
        return Keys.from_text(os.environ[KEY_ENV], password)
    path = Path(key_arg) if key_arg else Path(DEFAULT_KEY)
    if not path.exists():
        raise ExcelCryptError(f"Aucune clé trouvée. Lancez 'keygen', passez -k <fichier.key> "
                              f"ou définissez la variable {KEY_ENV}.")
    if key_is_protected(path) and not password:
        password = os.environ.get(PASSWORD_ENV) or (getpass.getpass("Mot de passe de la clé : ") if sys.stdin.isatty() else None)
    return Keys.from_file(path, password)


# --------------------------------------------------------------------------- #
# Coffre chiffré (jeton -> valeur d'origine typée, + jetons lisibles)
# --------------------------------------------------------------------------- #
class Vault:
    def __init__(self, path: Path, keys: Keys):
        self.path = Path(path)
        self.aes = AESGCM(keys.vault_key)
        self.entries: dict[str, dict] = {}   # hex -> valeur typée
        self.aliases: dict[str, str] = {}    # hex -> jeton lisible (PREFIXE_0042)
        self.counters: dict[str, int] = {}   # préfixe -> dernier numéro attribué
        self.by_alias: dict[str, str] = {}   # jeton lisible -> hex
        self.dirty = False
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        blob = self.path.read_bytes()
        if not blob.startswith(VAULT_MAGIC):
            raise ExcelCryptError(f"'{self.path}' n'est pas un coffre ExcelCrypt.", "vault_invalid", name=self.path.name)
        nonce = blob[len(VAULT_MAGIC):len(VAULT_MAGIC) + 12]
        try:
            data = self.aes.decrypt(nonce, blob[len(VAULT_MAGIC) + 12:], VAULT_MAGIC)
        except InvalidTag:
            raise ExcelCryptError("Impossible d'ouvrir le coffre : mauvaise clé ou fichier corrompu.", "vault_bad_key")
        doc = json.loads(data.decode("utf-8"))
        if doc.get("v") == 2:
            self.entries, self.aliases, self.counters = doc["entries"], doc["aliases"], doc["counters"]
        else:  # format 1 : uniquement les entrées
            self.entries = doc
        self.by_alias = {a: h for h, a in self.aliases.items()}

    def save(self) -> None:
        if not self.dirty:
            return
        nonce = os.urandom(12)
        doc = {"v": 2, "entries": self.entries, "aliases": self.aliases, "counters": self.counters}
        data = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_bytes(VAULT_MAGIC + nonce + self.aes.encrypt(nonce, data, VAULT_MAGIC))
        os.replace(tmp, self.path)  # écriture atomique : pas de coffre à moitié écrit
        self.dirty = False

    def put(self, token_hex: str, value) -> None:
        packed = pack_value(value)
        existing = self.entries.get(token_hex)
        if existing is None:
            self.entries[token_hex] = packed
            self.dirty = True
        elif existing != packed and unpack_value(existing) != value:
            # Deux valeurs différentes -> même jeton : quasi impossible, mais on refuse net.
            raise ExcelCryptError(f"Collision de jeton détectée ({token_hex}). Abandon.", "collision", token=token_hex)

    def alias(self, token_hex: str, prefix: str, overlay: dict | None = None) -> str:
        """Jeton lisible stable pour une valeur. overlay : attribution provisoire (aperçu), rien n'est écrit."""
        if token_hex in self.aliases:
            return self.aliases[token_hex]
        if overlay is not None:
            if token_hex in overlay["aliases"]:
                return overlay["aliases"][token_hex]
            n = overlay["counters"].get(prefix, self.counters.get(prefix, 0)) + 1
            overlay["counters"][prefix] = n
            overlay["aliases"][token_hex] = a = f"{prefix}_{n:04d}"
            return a
        n = self.counters.get(prefix, 0) + 1
        while f"{prefix}_{n:04d}" in self.by_alias:
            n += 1
        self.counters[prefix] = n
        a = f"{prefix}_{n:04d}"
        self.aliases[token_hex], self.by_alias[a] = a, token_hex
        self.dirty = True
        return a

    def get(self, token_hex: str):
        packed = self.entries.get(token_hex.lower())
        return None if packed is None else unpack_value(packed)

    def resolve(self, token: str):
        """Valeur d'un jeton (ENC_… ou lisible). (trouvé, valeur, reconnu_comme_jeton)."""
        if m := TOKEN_RE.fullmatch(token):
            v = self.get(m.group(1))
            return v is not None, v, True
        h = self.by_alias.get(token.upper())
        if h is not None:
            return True, self.get(h), True
        m = ALIAS_RE.fullmatch(token)
        # un PREFIXE_0042 inconnu n'est signalé que si le préfixe a bien été utilisé par ce coffre
        return False, None, bool(m and m.group(1).upper() in self.counters)


def pack_value(v) -> dict:
    if isinstance(v, bool):
        return {"t": "bool", "v": v}
    if isinstance(v, int):
        return {"t": "int", "v": v}
    if isinstance(v, float):
        return {"t": "float", "v": repr(v)}
    if isinstance(v, dt.datetime):
        return {"t": "datetime", "v": v.isoformat()}
    if isinstance(v, dt.date):
        return {"t": "date", "v": v.isoformat()}
    if isinstance(v, dt.time):
        return {"t": "time", "v": v.isoformat()}
    return {"t": "str", "v": str(v)}


def unpack_value(p: dict):
    t, v = p["t"], p["v"]
    return {
        "bool": lambda: v,
        "int": lambda: v,
        "float": lambda: float(v),
        "datetime": lambda: dt.datetime.fromisoformat(v),
        "date": lambda: dt.date.fromisoformat(v),
        "time": lambda: dt.time.fromisoformat(v),
    }.get(t, lambda: v)()


def value_as_text(v) -> str:
    """Représentation texte lisible d'une valeur (restauration dans un texte, aperçu)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, dt.datetime) and v.time() == dt.time():
        return v.date().isoformat()
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    return str(v)


def slug_prefix(header, letter: str) -> str:
    """Préfixe de jeton lisible tiré d'un en-tête : « Date de naissance » -> DATE_DE_NAISSANCE."""
    s = unicodedata.normalize("NFKD", str(header or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()[:20].rstrip("_")
    if not s:
        return f"COL_{letter}"
    return s if s[0].isalpha() else f"C{s}"


def column_prefix(header: list, c: int, sel: SheetSelection, mask_headers: bool) -> str:
    """Préfixe des jetons lisibles d'une colonne. Si son en-tête est masqué, on ne le révèle pas : COL_C."""
    letter = get_column_letter(c)
    if mask_headers and c in sel.cols:
        return f"COL_{letter}"
    return slug_prefix(header[c - 1] if c - 1 < len(header) else None, letter)


# --------------------------------------------------------------------------- #
# Pseudonymisation
# --------------------------------------------------------------------------- #
class Tokenizer:
    """
    Calcule les jetons.
    vault=None : aperçu sans coffre. dry_run=True : le coffre est lu mais jamais modifié.
    readable=True : jetons lisibles PREFIXE_0042 au lieu de ENC_….
    """

    def __init__(self, keys: Keys | None, vault: Vault | None = None, readable: bool = False, dry_run: bool = False):
        self.key = keys.token_key if keys else None
        self.vault = vault
        self.readable = readable
        self.dry_run = dry_run
        self.overlay = {"aliases": {}, "counters": {}}
        self.count = 0

    def token(self, value, prefix: str = "VALUE") -> str:
        self.count += 1
        if self.key is None:  # aperçu sans clé
            return f"{prefix}_••••" if self.readable else TOKEN_PREFIX + "•" * TOKEN_HEX_LEN
        # Le type fait partie de l'empreinte : 12 (nombre) et "12" (texte) restent distincts.
        packed = pack_value(value)
        material = f"{packed['t']}\x1f{packed['v']}".encode("utf-8")
        h = hmac.new(self.key, material, hashlib.sha256).hexdigest()[:TOKEN_HEX_LEN]
        if self.vault is not None and not self.dry_run:
            self.vault.put(h, value)
        if not self.readable:
            return TOKEN_PREFIX + h
        if self.vault is None:
            if h not in self.overlay["aliases"]:
                n = self.overlay["counters"].get(prefix, 0) + 1
                self.overlay["counters"][prefix] = n
                self.overlay["aliases"][h] = f"{prefix}_{n:04d}"
            return self.overlay["aliases"][h]
        return self.vault.alias(h, prefix, self.overlay if self.dry_run else None)

    def mask_text(self, text: str, literals: list[str], detectors: list[Detector],
                  propagation: Propagation | None = None) -> str:
        """Remplace, à l'intérieur d'un texte, les valeurs/motifs ciblés par des jetons."""
        if propagation:
            text = propagation.regex.sub(
                lambda m: self.token(m.group(0), propagation.prefix_of.get(m.group(0).casefold(), "VALUE")), text)
        for lit in literals:
            if lit and lit in text:
                text = text.replace(lit, self.token(lit, "VALUE"))
        for d in detectors:
            text = d.sub(text, lambda v, p: self.token(v, p))
        return text

    def mask_cell(self, value, masked: bool, literals: list[str], detectors: list[Detector],
                  propagation: Propagation | None = None, prefix: str = "VALUE"):
        if value is None or value == "" or is_formula(value) or is_token(value):
            return value
        if masked:
            return self.token(value.strip() if isinstance(value, str) else value, prefix)
        if isinstance(value, str) and (literals or detectors or propagation):
            return self.mask_text(value, literals, detectors, propagation)
        return value


def is_formula(v) -> bool:
    return isinstance(v, str) and v.startswith("=")


def is_token(v) -> bool:
    return isinstance(v, str) and TOKEN_RE.fullmatch(v.strip()) is not None


def resolve_columns(header: list, specs: list[str], sheet_name: str, strict: bool) -> set[int]:
    """Transforme 'Nom', 'Email', 'C'... en index de colonnes (1-based)."""
    by_name = {}
    for idx, h in enumerate(header, start=1):
        if h is not None:
            by_name.setdefault(str(h).strip().casefold(), idx)
    cols = set()
    for spec in specs:
        s = spec.strip()
        if not s:
            continue
        if s.casefold() in by_name:
            cols.add(by_name[s.casefold()])
        elif re.fullmatch(r"[A-Za-z]{1,3}", s):
            cols.add(column_index_from_string(s.upper()))
        elif re.fullmatch(r"\d+", s):
            cols.add(int(s))
        elif strict:
            print(f"  [!] Colonne '{s}' introuvable dans la feuille '{sheet_name}'.", file=sys.stderr)
    return cols


# --------------------------------------------------------------------------- #
# Lecture / écriture
# --------------------------------------------------------------------------- #
def check_format(path: Path) -> str:
    path = Path(path)
    if not path.exists():
        raise ExcelCryptError(f"Fichier introuvable : {path}", "file_missing", path=str(path))
    ext = path.suffix.lower()
    if ext in EXCEL_EXT:
        return "excel"
    if ext in CSV_EXT:
        return "csv"
    if ext == ".xls":
        raise ExcelCryptError("Format .xls (Excel 97-2003) : ouvrez-le dans Excel et enregistrez-le en .xlsx.",
                              "xls_unsupported")
    raise ExcelCryptError(f"Format non supporté : {ext} (supportés : .xlsx, .xlsm, .csv, .tsv, .txt)",
                          "format_unsupported", ext=ext)


def read_csv(path: Path) -> tuple[list[list[str]], csv.Dialect, str]:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:64 * 1024], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(text.splitlines(), dialect))
    return rows, dialect, enc


def write_csv(path: Path, rows: list[list], dialect, enc: str) -> None:
    with open(path, "w", newline="", encoding=enc) as f:
        csv.writer(f, dialect).writerows(rows)


def load_workbook(path: Path):
    return openpyxl.load_workbook(path, keep_vba=Path(path).suffix.lower() == ".xlsm")


def read_preview(path: Path, header_row: int = 1, max_rows: int = 500) -> dict[str, dict]:
    """
    Lecture rapide pour affichage : {feuille: {"header": [...], "rows": [[...]], "total": n}}.
    Les valeurs sont celles calculées (pas les formules).
    """
    path = Path(path)
    fmt = check_format(path)
    result = {}
    if fmt == "csv":
        rows, _, _ = read_csv(path)
        result[CSV_SHEET] = {
            "header": rows[header_row - 1] if len(rows) >= header_row else [],
            "rows": rows[header_row:header_row + max_rows],
            "total": max(0, len(rows) - header_row),
        }
        return result
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            chunk = [list(r) for r in ws.iter_rows(min_row=header_row, max_row=header_row + max_rows,
                                                   values_only=True)]
            total = (ws.max_row or 0) - header_row
            result[ws.title] = {
                "header": chunk[0] if chunk else [],
                "rows": chunk[1:],
                "total": max(0, total if ws.max_row else len(chunk) - 1),
            }
    finally:
        wb.close()
    return result


def default_output(path: Path, suffix: str) -> Path:
    path = Path(path)
    return path.with_name(f"{path.stem}_{suffix}{path.suffix}")


# --------------------------------------------------------------------------- #
# Chiffrement / contrôle des fuites
# --------------------------------------------------------------------------- #
def as_selection(sel) -> SheetSelection | None:
    if sel is None or isinstance(sel, SheetSelection):
        return sel
    return SheetSelection(cols=set(sel))


def describe_selection(sel: SheetSelection) -> str:
    parts = []
    if sel.cols:
        parts.append("colonnes " + ", ".join(get_column_letter(c) for c in sorted(sel.cols)))
    if sel.rows:
        parts.append("lignes " + ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in sel.rows))
    if sel.cells:
        parts.append(f"{len(sel.cells)} cellule(s)")
    for r1, c1, r2, c2 in sel.rects:
        parts.append(f"{get_column_letter(c1)}{r1}:{get_column_letter(c2)}{r2}")
    return " ; ".join(parts) or "-"


class _Sheet:
    """Vue commune d'une feuille Excel ou d'un CSV pour les passes de traitement."""

    def __init__(self, name: str, header: list, sel: SheetSelection | None, cells, header_cells):
        self.name, self.header, self.sel = name, header, sel
        self.cells = cells                  # itérable -> (ligne, colonne, getter, setter)
        self.header_cells = header_cells    # colonne -> (getter, setter)


def _sheets(fmt: str, doc, columns: ColumnSelector, hr: int):
    if fmt == "csv":
        rows = doc

        def cells():
            for r_idx, row in enumerate(rows, start=1):
                if r_idx > hr:
                    for c_idx in range(len(row)):
                        yield r_idx, c_idx + 1, (lambda row=row, i=c_idx: row[i]), \
                            (lambda v, row=row, i=c_idx: row.__setitem__(i, v))

        header = rows[hr - 1] if len(rows) >= hr else []
        hcells = {c + 1: ((lambda i=c: header[i]), (lambda v, i=c: header.__setitem__(i, v))) for c in range(len(header))}
        yield _Sheet(CSV_SHEET, header, as_selection(columns(CSV_SHEET, header)) or SheetSelection(), cells, hcells)
        return
    for ws in doc.worksheets:
        header = [c.value for c in ws[hr]] if ws.max_row >= hr else []
        sel = as_selection(columns(ws.title, header))

        def cells(ws=ws):
            for row in ws.iter_rows(min_row=hr + 1):
                for cell in row:
                    if cell.data_type == "f" or type(cell).__name__ == "MergedCell":
                        continue
                    yield cell.row, cell.column, (lambda cell=cell: cell.value), \
                        (lambda v, cell=cell: _set_cell(cell, v))

        hcells = {}
        if ws.max_row >= hr:
            for cell in ws[hr]:
                if cell.data_type != "f" and type(cell).__name__ != "MergedCell":
                    hcells[cell.column] = ((lambda cell=cell: cell.value), (lambda v, cell=cell: _set_cell(cell, v)))
        yield _Sheet(ws.title, header, sel, cells, hcells)


def _set_cell(cell, v) -> None:
    cell.value = v
    if isinstance(v, str) and (v.startswith(TOKEN_PREFIX) or ALIAS_RE.fullmatch(v)):
        cell.number_format = "@"  # sinon une colonne date afficherait mal le jeton


def _process(path: Path, keys: Keys | None, vault: Vault | None, columns: ColumnSelector,
             literals, detectors, header_row: int, progress, log, mask_headers: bool,
             propagate: bool, readable: bool, scan: bool):
    """
    Passe commune au chiffrement et au contrôle des fuites.
    1re passe (si propagate) : relève les valeurs des cellules masquées.
    2e passe : masque. En mode scan, rien n'est écrit et on relève ce qui reste visible.
    """
    path = Path(path)
    fmt = check_format(path)
    hr = max(1, int(header_row))
    literals = sorted(set(literals or []), key=len, reverse=True)
    detectors = [d if isinstance(d, Detector) else Detector("regex", "PATTERN", d) for d in (detectors or [])]
    tk = Tokenizer(keys or Keys(os.urandom(32)), None if scan else vault, readable, dry_run=scan)
    if fmt == "csv":
        rows, dialect, enc = read_csv(path)
        doc, total = rows, len(rows)
    else:
        doc = load_workbook(path)
        rows = dialect = enc = None
        total = sum(ws.max_row for ws in doc.worksheets) or 1
    sheets = [s for s in _sheets(fmt, doc, columns, hr) if s.sel is not None]
    passes = 2 if (propagate or scan) else 1
    total *= passes
    done = 0

    def prefix_for(sh: _Sheet, c: int) -> str:
        return column_prefix(sh.header, c, sh.sel, mask_headers)

    propagation = Propagation()
    if propagate or scan:  # en contrôle, on relève toujours les valeurs masquées pour repérer celles restées visibles
        for sh in sheets:
            if not sh.sel:
                continue
            for r, c, get, _ in sh.cells():
                if sh.sel.has(r, c):
                    propagation.add(get(), prefix_for(sh, c))
                done += 1
                if progress and done % 5000 == 0:
                    progress(done, total)
        propagation.compile()
    active_propagation = propagation if (propagate and propagation) else None

    findings: dict[tuple, dict] = {}
    all_detectors = list(DETECTORS.values())
    for sh in sheets:
        if not scan and not sh.sel and not literals and not detectors and not active_propagation:
            continue
        if not scan:
            log(f"Feuille '{sh.name}' : {describe_selection(sh.sel)}")
            if mask_headers:
                for c in sorted(sh.sel.cols):
                    if c in sh.header_cells:
                        get, put = sh.header_cells[c]
                        put(tk.mask_cell(get(), True, [], [], None, "HEADER"))
        for r, c, get, put in sh.cells():
            v = get()
            masked = sh.sel.has(r, c)
            new = tk.mask_cell(v, masked, literals, detectors, active_propagation, prefix_for(sh, c))
            if scan:
                if not masked and isinstance(new, str) and new:
                    _record_leaks(findings, sh, c, new, all_detectors, None if propagate else propagation)
            elif new is not v:
                put(new)
            done += 1
            if progress and done % 2000 == 0:
                progress(done, total)
    if scan:
        return sorted(findings.values(), key=lambda f: (-f["count"], f["sheet"], f["col"]))
    return fmt, doc, rows, dialect, enc, tk


def _record_leaks(findings, sh: _Sheet, c: int, text: str, detectors: list[Detector], propagation) -> None:
    hits = [(d.key, m.group(0)) for d in detectors for m in d.matches(text)]
    if propagation:
        hits += [("masked_value", m.group(0)) for m in propagation.regex.finditer(text)]
    seen = set()
    for key, example in hits:
        if key == "phone_de" and ("phone_fr", example) in seen:
            continue
        seen.add((key, example))
        k = (sh.name, c, key)
        f = findings.setdefault(k, {"sheet": sh.name, "col": c, "letter": get_column_letter(c),
                                    "header": value_as_text(sh.header[c - 1]) if c - 1 < len(sh.header) else "",
                                    "detector": key, "count": 0, "example": example})
        f["count"] += 1


def encrypt_file(path: Path, out: Path, keys: Keys, vault_path: Path, columns: ColumnSelector,
                 literals: list[str] | None = None, patterns: list | None = None,
                 header_row: int = 1, progress: Progress | None = None,
                 log: Callable[[str], None] = lambda s: None, mask_headers: bool = False,
                 propagate: bool = False, readable: bool = False) -> dict:
    """
    mask_headers : remplace aussi l'en-tête des colonnes entièrement masquées par un jeton.
    propagate    : masque aussi, partout dans le texte, les valeurs des cellules masquées.
    readable     : jetons lisibles (CONTACT_0042) au lieu de ENC_….
    """
    vault = Vault(Path(vault_path), keys)
    fmt, doc, rows, dialect, enc, tk = _process(path, keys, vault, columns, literals, patterns, header_row,
                                                progress, log, mask_headers, propagate, readable, scan=False)
    out = Path(out)
    if fmt == "csv":
        write_csv(out, rows, dialect, enc)
    else:
        doc.save(out)
    vault.save()
    return {"masked": tk.count, "unique": len(vault.entries), "output": out, "vault": vault.path}


def scan_file(path: Path, columns: ColumnSelector, literals: list[str] | None = None,
              patterns: list | None = None, header_row: int = 1, progress: Progress | None = None,
              mask_headers: bool = False, propagate: bool = False) -> list[dict]:
    """
    Contrôle avant envoi : simule le masquage puis cherche ce qui ressemble encore à une donnée personnelle
    (e-mail, téléphone, IBAN, carte…, ou valeur d'une cellule masquée restée visible ailleurs).
    Retourne une liste de {sheet, col, letter, header, detector, count, example}.
    """
    return _process(path, None, None, columns, literals, patterns, header_row, progress,
                    lambda s: None, mask_headers, propagate, False, scan=True)


def decrypt_file(path: Path, out: Path, keys: Keys, vault_path: Path,
                 progress: Progress | None = None) -> dict:
    path, out = Path(path), Path(out)
    fmt = check_format(path)
    if not Path(vault_path).exists():
        raise ExcelCryptError(f"Coffre introuvable : {vault_path}", "vault_missing", name=Path(vault_path).name)
    vault = Vault(Path(vault_path), keys)
    stats = {"restored": 0, "unknown": set()}

    def restore(value):
        if not isinstance(value, str) or not ANY_TOKEN_RE.search(value):
            return value
        whole = value.strip()
        if ANY_TOKEN_RE.fullmatch(whole):  # la cellule entière est un jeton -> on remet la valeur avec son type
            found, v, is_tok = vault.resolve(whole)
            if found:
                stats["restored"] += 1
                return v
            if is_tok:
                stats["unknown"].add(whole)
            return value

        def sub(m):
            found, v, is_tok = vault.resolve(m.group(0))
            if found:
                stats["restored"] += 1
                return value_as_text(v)
            if is_tok:
                stats["unknown"].add(m.group(0))
            return m.group(0)

        return ANY_TOKEN_RE.sub(sub, value)

    if fmt == "csv":
        rows, dialect, enc = read_csv(path)
        rows = [[value_as_text(x) if not isinstance(x := restore(c), str) else x for c in row] for row in rows]
        write_csv(out, rows, dialect, enc)
    else:
        wb = load_workbook(path)
        total = sum(ws.max_row for ws in wb.worksheets) or 1
        done = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if type(cell).__name__ == "MergedCell":
                        continue
                    v = cell.value
                    new = restore(v)
                    if new is not v:
                        cell.value = new
                        if isinstance(new, dt.datetime):
                            cell.number_format = "yyyy-mm-dd hh:mm:ss" if new.time() != dt.time() else "yyyy-mm-dd"
                        elif isinstance(new, dt.date):
                            cell.number_format = "yyyy-mm-dd"
                        elif isinstance(new, (int, float)) and cell.number_format == "@":
                            cell.number_format = "General"
                done += 1
                if progress and done % 2000 == 0:
                    progress(done, total)
            # noms de feuilles : l'IA peut en créer à partir de valeurs masquées
            if ANY_TOKEN_RE.search(ws.title):
                def title_sub(m):
                    found, v, _ = vault.resolve(m.group(0))
                    return value_as_text(v) if found else m.group(0)
                ws.title = re.sub(r"[\[\]:*?/\\]", "_", ANY_TOKEN_RE.sub(title_sub, ws.title))[:31]
        wb.save(out)

    stats["output"] = out
    return stats


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_inspect(args) -> None:
    for name, sheet in read_preview(Path(args.file), args.header_row, max_rows=3).items():
        print(f"\n=== Feuille : {name}  (~{sheet['total']} lignes)")
        for i, h in enumerate(sheet["header"], start=1):
            ex = ", ".join(value_as_text(r[i - 1]) for r in sheet["rows"]
                           if i - 1 < len(r) and r[i - 1] not in (None, ""))
            print(f"  {get_column_letter(i):>3} | {str(h) if h is not None else '':<30} | ex: {ex[:60]}")


def _cli_detectors(args) -> list[Detector]:
    keys = [k.strip() for k in (args.detect or "").split(",") if k.strip()]
    keys += [k for k, on in (("email", args.emails), ("phone_fr", args.phones), ("phone_de", args.phones_de)) if on]
    return build_detectors(list(dict.fromkeys(keys)), args.regex)


def _cli_selector(args, path: Path):
    col_specs = [c for c in (args.columns or "").split(",") if c.strip()]
    only_sheets = {s.strip() for s in args.sheets.split(",")} if args.sheets else None
    n_sheets = len(read_preview(path, args.header_row, max_rows=0))

    def select(sheet: str, header: list):
        if only_sheets and sheet not in only_sheets:
            return None
        sel = SheetSelection(cols=resolve_columns(header, col_specs, sheet,
                                                  strict=only_sheets is not None or n_sheets == 1))
        if args.select:
            extra, errors = parse_refs(args.select, header)
            if errors:
                raise ExcelCryptError(f"Références non comprises : {', '.join(errors)}")
            sel.update(extra)
        return sel
    return col_specs, select


def cmd_encrypt(args) -> None:
    path = Path(args.file)
    check_format(path)
    keys = load_key(args.key)
    literals = args.value or []
    detectors = _cli_detectors(args)
    col_specs, select = _cli_selector(args, path)

    if not col_specs and not args.select and not literals and not detectors:
        if not sys.stdin.isatty():
            raise ExcelCryptError("Rien à masquer : utilisez -c, --select, --value, --regex ou --detect.")
        print("Aucune colonne indiquée. Colonnes disponibles :")
        cmd_inspect(argparse.Namespace(file=str(path), header_row=args.header_row))
        args.columns = input("\nColonnes à masquer (noms ou lettres, séparés par des virgules) : ")
        col_specs, select = _cli_selector(args, path)
        if not col_specs:
            raise ExcelCryptError("Rien à masquer.")

    out = Path(args.output) if args.output else default_output(path, "chiffre")
    res = encrypt_file(path, out, keys, Path(args.vault), select, literals, detectors, args.header_row,
                       log=lambda s: print("  " + s), mask_headers=args.mask_headers,
                       propagate=args.propagate, readable=args.readable)
    print(f"\n{res['masked']} valeurs masquées ({res['unique']} valeurs uniques dans le coffre).")
    print(f"Fichier à envoyer à l'IA : {res['output']}")
    print(f"Coffre (à garder avec la clé, NE PAS envoyer) : {res['vault']}")


def cmd_scan(args) -> None:
    path = Path(args.file)
    _, select = _cli_selector(args, path)
    found = scan_file(path, select, args.value or [], _cli_detectors(args), args.header_row,
                      mask_headers=args.mask_headers, propagate=args.propagate)
    if not found:
        print("Aucune donnée personnelle détectée hors des zones masquées.")
        return
    print(f"{len(found)} fuite(s) possible(s) :")
    for f in found:
        print(f"  [{f['detector']:>12}] {f['sheet']} › {f['letter']} ({f['header']}) : {f['count']} × ex. {f['example']}")
    sys.exit(2)


def cmd_decrypt(args) -> None:
    path = Path(args.file)
    out = Path(args.output) if args.output else default_output(path, "dechiffre")
    res = decrypt_file(path, out, load_key(args.key), Path(args.vault))
    print(f"{res['restored']} jetons restaurés.")
    if res["unknown"]:
        print(f"[!] {len(res['unknown'])} jetons inconnus du coffre (autre clé/coffre, ou jeton modifié par l'IA) :",
              file=sys.stderr)
        for t in sorted(res["unknown"])[:20]:
            print(f"    {t}", file=sys.stderr)
    print(f"Fichier déchiffré : {res['output']}")


def _ask_new_password() -> str | None:
    pw = getpass.getpass("Nouveau mot de passe (vide = aucun) : ")
    if pw and pw != getpass.getpass("Confirmez : "):
        raise ExcelCryptError("Les mots de passe ne correspondent pas.")
    return pw or None


def cmd_passwd(args) -> None:
    path = Path(args.key or DEFAULT_KEY)
    keys = load_key(str(path))
    write_key(path, keys.master, _ask_new_password())
    print(f"Clé réenregistrée : {path} (la clé elle-même et les jetons ne changent pas).")


def main() -> None:
    p = argparse.ArgumentParser(
        prog="excelcrypt",
        description="Masque des colonnes/valeurs d'un Excel par des jetons réversibles (HMAC-SHA256 + AES-256-GCM).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-k", "--key", help=f"fichier clé ou clé base64 (défaut : ${KEY_ENV} ou ./{DEFAULT_KEY})")
    common.add_argument("--vault", default=DEFAULT_VAULT, help=f"coffre chiffré (défaut : ./{DEFAULT_VAULT})")
    common.add_argument("-o", "--output", help="fichier de sortie")

    select = argparse.ArgumentParser(add_help=False)
    select.add_argument("-c", "--columns", help='colonnes à masquer : noms ou lettres, ex. "Nom,Email,C"')
    select.add_argument("--select", help='lignes/cellules/zones à masquer, ex. "B5,A2:C40,12-30,D:F"')
    select.add_argument("-s", "--sheets", help="limiter à ces feuilles (séparées par des virgules)")
    select.add_argument("--value", action="append", help="valeur à masquer partout (répétable)")
    select.add_argument("--regex", action="append", help="motif regex à masquer partout (répétable)")
    select.add_argument("--detect", help=f"détecteurs, ex. email,iban (disponibles : {', '.join(DETECTORS)})")
    select.add_argument("--emails", action="store_true", help="= --detect email")
    select.add_argument("--phones", action="store_true", help="= --detect phone_fr")
    select.add_argument("--phones-de", action="store_true", help="= --detect phone_de")
    select.add_argument("--propagate", action="store_true", help="masquer aussi ailleurs les valeurs des cellules masquées")
    select.add_argument("--mask-headers", action="store_true", help="masquer aussi le nom des colonnes masquées")
    select.add_argument("--header-row", type=int, default=1, help="ligne des en-têtes (défaut : 1)")

    g = sub.add_parser("keygen", help="génère une nouvelle clé secrète")
    g.add_argument("-o", "--output", default=DEFAULT_KEY)
    g.add_argument("--force", action="store_true")
    g.add_argument("--password", action="store_true", help="protéger la clé par un mot de passe (saisi au clavier)")

    pw = sub.add_parser("passwd", help="ajoute, change ou retire le mot de passe de la clé")
    pw.add_argument("-k", "--key", help=f"fichier clé (défaut : ./{DEFAULT_KEY})")

    i = sub.add_parser("inspect", help="liste les feuilles et colonnes d'un fichier")
    i.add_argument("file")
    i.add_argument("--header-row", type=int, default=1)

    sc = sub.add_parser("scan", parents=[select], help="contrôle avant envoi : cherche les données encore visibles")
    sc.add_argument("file")

    e = sub.add_parser("encrypt", parents=[common, select], help="masque les données sensibles")
    e.add_argument("file")
    e.add_argument("--readable", action="store_true", help="jetons lisibles (CONTACT_0042) au lieu de ENC_…")

    d = sub.add_parser("decrypt", parents=[common], help="restaure les vraies valeurs")
    d.add_argument("file")

    args = p.parse_args()
    try:
        if args.cmd == "keygen":
            generate_key(Path(args.output), args.force, _ask_new_password() if args.password else None)
            print(f"Clé générée : {args.output}")
            print("-> Gardez-la SECRÈTE et SAUVEGARDÉE : sans elle, aucun déchiffrement possible.")
        elif args.cmd == "passwd":
            cmd_passwd(args)
        elif args.cmd == "inspect":
            cmd_inspect(args)
        elif args.cmd == "scan":
            cmd_scan(args)
        elif args.cmd == "encrypt":
            cmd_encrypt(args)
        elif args.cmd == "decrypt":
            cmd_decrypt(args)
    except ExcelCryptError as e:
        sys.exit(f"Erreur : {e}")


if __name__ == "__main__":
    main()

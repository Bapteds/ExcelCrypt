#!/usr/bin/env python3
"""
ExcelCrypt - interface graphique.

    python gui.py

L'interface est une page HTML (ui/index.html) affichée dans une fenêtre native
via pywebview (WKWebView sur macOS, WebView2 sur Windows). Toute la logique
cryptographique reste en Python (excelcrypt.py) : la page ne voit jamais la clé.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import webview
from openpyxl.utils import get_column_letter
from webview.dom import DOMEventHandler

import excelcrypt as ec

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
UI_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "ui"
SETTINGS = APP_DIR / "excelcrypt_gui.json"
PROFILES = APP_DIR / "excelcrypt_profiles.json"
PREVIEW_ROWS = 500
LANGS = ("fr", "de", "en")
SUPPORTED = ec.EXCEL_EXT | ec.CSV_EXT
# Libellés des dialogues natifs (format imposé par pywebview : lettres et espaces uniquement)
DIALOG_TEXT = {
    "fr": {"sheets": "Excel ou CSV", "all": "Tous les fichiers", "key": "Clé ExcelCrypt", "vault": "Coffre ExcelCrypt",
           "enc": "chiffre", "dec": "dechiffre"},
    "de": {"sheets": "Excel oder CSV", "all": "Alle Dateien", "key": "ExcelCrypt Schlüssel", "vault": "ExcelCrypt Tresor",
           "enc": "geschuetzt", "dec": "wiederhergestellt"},
    "en": {"sheets": "Excel or CSV", "all": "All files", "key": "ExcelCrypt key", "vault": "ExcelCrypt vault",
           "enc": "protected", "dec": "restored"},
}

# En-têtes qui ressemblent à des données personnelles (pour « Suggérer »)
SENSITIVE_HINTS = re.compile(
    r"nom|pr[ée]nom|name|e-?mail|courriel|t[ée]l|phone|mobile|portable|adresse|address|rue|"
    r"iban|bic|rib|siret|siren|s[ée]cu|nir|ssn|passeport|passport|naissance|birth|dob|"
    r"contact|login|identifiant|carte|card|\bip\b|"
    r"geburt|anschrift|stra(?:ss|ß)e|kontakt|ansprechpartner|steuer|personal|ust|tva|vat|"
    r"sozialversicherung|rentenversicherung|kreditkarte",
    re.IGNORECASE,
)


def error(code: str, message: str, **params) -> dict:
    """Erreur renvoyée à la page : `code` + `params` sont traduits côté interface, `error` sert de repli."""
    return {"error": message, "code": code, "params": params}


def from_exc(e: ec.ExcelCryptError) -> dict:
    return {"error": str(e), "code": e.code, "params": e.params}


def file_info(p: Path) -> dict:
    return {"name": p.name, "path": str(p), "dir": str(p.parent), "bytes": p.stat().st_size}


class Api:
    """Méthodes appelées depuis JavaScript via window.pywebview.api.*

    Les attributs sont préfixés par _ : pywebview expose sinon tout attribut public à la page.
    """

    def __init__(self):
        self._window: webview.Window | None = None
        self._keys: ec.Keys | None = None
        self._key_path = APP_DIR / ec.DEFAULT_KEY
        self._vault_path = APP_DIR / ec.DEFAULT_VAULT
        self._file: Path | None = None
        self._sheets: dict[str, dict] = {}  # valeurs brutes (typées) de l'aperçu
        self._header_row = 1
        self._lang: str | None = None       # None = premier lancement : la page demande la langue
        self._preview_vault: ec.Vault | None = None
        self._busy = threading.Lock()
        self._load_settings()
        self._load_key()

    # ---------------------------------------------------------------- état --
    def _load_settings(self):
        try:
            data = json.loads(SETTINGS.read_text())
            self._key_path = Path(data.get("key", self._key_path))
            self._vault_path = Path(data.get("vault", self._vault_path))
            self._lang = data.get("lang") if data.get("lang") in LANGS else None
        except (OSError, ValueError):
            pass

    def _save_settings(self):
        data = {"key": str(self._key_path), "vault": str(self._vault_path)}
        if self._lang:
            data["lang"] = self._lang
        try:
            SETTINGS.write_text(json.dumps(data, indent=2))
        except OSError:
            pass

    def _load_key(self, password: str | None = None) -> ec.ExcelCryptError | None:
        """Charge la clé. Une clé protégée sans mot de passe reste verrouillée (pas une erreur)."""
        self._keys = None
        self._preview_vault = None
        if not self._key_path.exists():
            return None
        if ec.key_is_protected(self._key_path) and not password:
            return None
        try:
            self._keys = ec.Keys.from_file(self._key_path, password)
        except ec.ExcelCryptError as e:
            return e
        return None

    @property
    def _t(self) -> dict:
        return DIALOG_TEXT[self._lang or "fr"]

    def _file_types(self, kind: str = "sheets") -> tuple:
        if kind == "sheets":
            return (f"{self._t['sheets']} (*.xlsx;*.xlsm;*.csv;*.tsv;*.txt)", f"{self._t['all']} (*.*)")
        ext = "key" if kind == "key" else "vault"
        return (f"{self._t[kind]} (*.{ext})",) + ((f"{self._t['all']} (*.*)",) if kind == "key" else ())

    def set_lang(self, lang: str) -> dict:
        if lang not in LANGS:
            return {"ok": False}
        self._lang = lang
        self._save_settings()
        return {"ok": True}

    def get_state(self) -> dict:
        protected = self._key_path.exists() and ec.key_is_protected(self._key_path)
        vault = {"name": self._vault_path.name, "path": str(self._vault_path), "exists": self._vault_path.exists(),
                 "count": 0, "ok": True}
        if self._keys and vault["exists"]:
            try:
                vault["count"] = len(ec.Vault(self._vault_path, self._keys).entries)
            except ec.ExcelCryptError:
                vault["ok"] = False
        return {
            "platform": sys.platform,
            "lang": self._lang,
            "key": {"name": self._key_path.name, "path": str(self._key_path), "ok": self._keys is not None,
                    "exists": self._key_path.exists(), "protected": protected,
                    "locked": protected and self._keys is None},
            "vault": vault,
            "detectors": list(ec.DETECTORS),
        }

    # ------------------------------------------------------------ dialogues --
    def _open_dialog(self, file_types=None, directory="") -> Path | None:
        res = self._window.create_file_dialog(webview.FileDialog.OPEN, directory=directory,
                                              file_types=file_types or self._file_types())
        return Path(res[0]) if res else None

    def _save_dialog(self, filename: str, directory: str = "", file_types=None) -> Path | None:
        res = self._window.create_file_dialog(webview.FileDialog.SAVE, directory=directory,
                                              save_filename=filename, file_types=file_types or self._file_types())
        if not res:
            return None
        return Path(res if isinstance(res, str) else res[0])

    def _folder_dialog(self, directory: str = "") -> Path | None:
        res = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=directory)
        if not res:
            return None
        return Path(res if isinstance(res, str) else res[0])

    def pick_file(self) -> str | None:
        p = self._open_dialog()
        return str(p) if p else None

    def reveal(self, path: str) -> None:
        p = Path(path)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", str(p)] if p.is_file() else ["open", str(p)])
            elif os.name == "nt":
                subprocess.run(["explorer", "/select,", str(p)] if p.is_file() else ["explorer", str(p)])
            else:
                subprocess.run(["xdg-open", str(p.parent if p.is_file() else p)])
        except OSError:
            pass

    # ---------------------------------------------------------- clé & coffre --
    def choose_key(self) -> dict:
        p = self._open_dialog(self._file_types("key"), str(self._key_path.parent))
        if not p:
            return {"cancelled": True}
        old = self._key_path
        self._key_path = p
        err = self._load_key()
        if err:
            self._key_path = old
            self._load_key()
            return from_exc(err)
        self._save_settings()
        return {"ok": True, "state": self.get_state()}

    def unlock_key(self, password: str) -> dict:
        err = self._load_key(password or None)
        if err or not self._keys:
            return from_exc(err) if err else error("key_locked", "La clé est protégée par un mot de passe.")
        return {"ok": True, "state": self.get_state()}

    def set_key_password(self, password: str) -> dict:
        """Ajoute, change ou retire (mot de passe vide) le mot de passe. La clé elle-même ne change pas."""
        if not self._keys:
            return error("no_key", "Aucune clé chargée.")
        ec.write_key(self._key_path, self._keys.master, password or None)
        return {"ok": True, "state": self.get_state()}

    def new_key(self, password: str = "") -> dict:
        p = self._save_dialog(ec.DEFAULT_KEY, str(self._key_path.parent), self._file_types("key")[:1])
        if not p:
            return {"cancelled": True}
        if p.suffix != ".key":
            p = p.with_suffix(".key")
        ec.generate_key(p, force=True, password=password or None)
        self._key_path = p
        if self._vault_path.exists():
            # un coffre existant appartient à l'ancienne clé : on en crée un nouveau à côté
            self._vault_path = p.with_suffix(".vault")
        self._load_key(password or None)
        self._save_settings()
        return {"ok": True, "state": self.get_state()}

    def choose_vault(self) -> dict:
        p = self._save_dialog(self._vault_path.name, str(self._vault_path.parent), self._file_types("vault"))
        if not p:
            return {"cancelled": True}
        self._vault_path = p if p.suffix == ".vault" else p.with_suffix(".vault")
        self._preview_vault = None
        self._save_settings()
        return {"ok": True, "state": self.get_state()}

    # -------------------------------------------------------------- profils --
    def _profiles(self) -> list[dict]:
        try:
            return json.loads(PROFILES.read_text()).get("profiles", [])
        except (OSError, ValueError):
            return []

    def _write_profiles(self, profiles: list[dict]) -> None:
        PROFILES.write_text(json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2))

    def list_profiles(self) -> list[dict]:
        return sorted(self._profiles(), key=lambda p: p["name"].casefold())

    def save_profile(self, profile: dict) -> dict:
        name = str(profile.get("name", "")).strip()
        if not name:
            return error("profile_name", "Donnez un nom au profil.")
        profile = {**profile, "name": name, "updated": time.strftime("%Y-%m-%d %H:%M")}
        others = [p for p in self._profiles() if p["name"].casefold() != name.casefold()]
        try:
            self._write_profiles(others + [profile])
        except OSError:
            return error("write_denied", f"Impossible d'écrire {PROFILES.name}.", name=PROFILES.name)
        return {"ok": True, "profiles": self.list_profiles()}

    def delete_profile(self, name: str) -> dict:
        self._write_profiles([p for p in self._profiles() if p["name"] != name])
        return {"ok": True, "profiles": self.list_profiles()}

    # --------------------------------------------------------- lecture ------
    def load(self, path: str, header_row: int = 1, remember: bool = True) -> dict:
        """Lit l'aperçu d'un fichier. remember=False : simple consultation (résultat restauré)."""
        try:
            p = Path(path)
            raw = ec.read_preview(p, max(1, int(header_row)), PREVIEW_ROWS)
        except ec.ExcelCryptError as e:
            return from_exc(e)
        except Exception as e:  # fichier corrompu, protégé par mot de passe...
            return error("read_failed", f"Lecture impossible : {e}", detail=str(e))
        if remember:
            self._file = p
            self._sheets = raw
            self._header_row = max(1, int(header_row))
        sheets = []
        for name, s in raw.items():
            header, rows = s["header"], s["rows"]
            ncols = max([len(header)] + [len(r) for r in rows] or [0])
            columns = []
            for i in range(1, ncols + 1):
                vals = [r[i - 1] if i - 1 < len(r) else None for r in rows]
                filled = [v for v in vals if v not in (None, "")]
                label = header[i - 1] if i - 1 < len(header) and header[i - 1] is not None else ""
                detected = ec.detect_column(filled) if remember else None
                columns.append({
                    "idx": i,
                    "letter": get_column_letter(i),
                    "name": str(label),
                    "unique": len({ec.value_as_text(v) for v in filled}),
                    "empty": len(vals) - len(filled),
                    "filled": len(filled),
                    "example": ec.value_as_text(filled[0])[:60] if filled else "",
                    "detected": detected,
                    "suggested": bool(SENSITIVE_HINTS.search(str(label))) or detected is not None,
                })
            sheets.append({
                "name": name,
                "total": s["total"],
                "columns": columns,
                "rows": [[ec.value_as_text(r[i] if i < len(r) else None) for i in range(ncols)] for r in rows],
            })
        return {"file": file_info(p) | {"ext": p.suffix.lower()}, "sheets": sheets}

    def parse_refs(self, sheet: str, text: str) -> dict:
        """Valide une saisie de plages (B5, A2:C40, 12-30, D:F, nom de colonne) pour la feuille donnée."""
        header = self._sheets.get(sheet, {}).get("header", [])
        sel, errors = ec.parse_refs(text, header)
        return {"selection": sel.to_dict(), "errors": errors}

    @staticmethod
    def _mask_options(opts: dict):
        literals = [v for v in opts.get("values", []) if v]
        valid, errors = [], {}
        for r in opts.get("regexes", []):
            try:
                re.compile(r)
                valid.append(r)
            except re.error as e:
                errors[r] = str(e)
        keys = [k for k in opts.get("detectors", []) if k in ec.DETECTORS]
        return literals, ec.build_detectors(keys, valid), errors

    def _vault_for_preview(self) -> ec.Vault | None:
        if self._keys and self._preview_vault is None:
            try:
                self._preview_vault = ec.Vault(self._vault_path, self._keys)
            except ec.ExcelCryptError:
                return None
        return self._preview_vault

    def preview(self, sheet: str, selections: dict, opts: dict) -> dict:
        """Lignes de l'aperçu telles que l'IA les verra (vrais jetons, sans rien écrire dans le coffre)."""
        s = self._sheets.get(sheet)
        if s is None:
            return {"rows": []}
        literals, detectors, errors = self._mask_options(opts)
        readable, mask_headers = bool(opts.get("readable")), bool(opts.get("maskHeaders"))
        vault = self._vault_for_preview() if readable else None
        tk = ec.Tokenizer(self._keys, vault, readable, dry_run=True)
        sels = {name: ec.SheetSelection.from_dict(selections.get(name, {})) for name in self._sheets}
        sel = sels[sheet]

        header = None
        if mask_headers:
            header = [ec.value_as_text(tk.mask_cell(h, True, [], [], None, "HEADER") if i in sel.cols else h)
                      for i, h in enumerate(s["header"], start=1)]

        propagation = None
        if opts.get("propagate"):
            propagation = ec.Propagation()
            for name, other in self._sheets.items():
                osel = sels[name]
                for ri, r in enumerate(other["rows"]):
                    for i, v in enumerate(r, start=1):
                        if osel.has(self._header_row + 1 + ri, i):
                            propagation.add(v, ec.column_prefix(other["header"], i, osel, mask_headers))
            propagation = propagation.compile() or None

        ncols = max([len(s["header"])] + [len(r) for r in s["rows"]] or [0])
        out = []
        for ri, r in enumerate(s["rows"]):
            excel_row = self._header_row + 1 + ri
            row = []
            for i in range(1, ncols + 1):
                v = r[i - 1] if i - 1 < len(r) else None
                prefix = ec.column_prefix(s["header"], i, sel, mask_headers)
                v = tk.mask_cell(v, sel.has(excel_row, i), literals, detectors, propagation, prefix)
                row.append(ec.value_as_text(v))
            out.append(row)
        return {"rows": out, "header": header, "regexErrors": errors, "hasKey": self._keys is not None}

    # ------------------------------------------------ chiffrer / déchiffrer --
    def _progress_cb(self):
        last = [0.0]

        def cb(done, total):
            now = time.monotonic()
            if now - last[0] > 0.1:
                last[0] = now
                self._window.evaluate_js(f"window.onTaskProgress({done / max(total, 1) * 100:.1f})")
        return cb

    def _run_options(self, selection: dict, opts: dict):
        literals, detectors, errors = self._mask_options(opts)
        sel = {k: ec.SheetSelection.from_dict(v) for k, v in selection.items()}
        return literals, detectors, errors, (lambda s, h: sel.get(s, ec.SheetSelection()))

    def scan(self, selection: dict, opts: dict, header_row: int = 1) -> dict:
        """Contrôle avant envoi sur le fichier complet (rien n'est écrit)."""
        if not self._file:
            return error("no_file", "Aucun fichier ouvert.")
        literals, detectors, errors, select = self._run_options(selection, opts)
        if errors:
            return error("regex_invalid", "Regex invalide : " + ", ".join(errors), pattern=", ".join(errors))
        if not self._busy.acquire(blocking=False):
            return error("busy", "Une opération est déjà en cours.")
        try:
            self._window.evaluate_js(f"window.onTaskStart('scan', {json.dumps(self._file.name)})")
            found = ec.scan_file(self._file, select, literals, detectors, max(1, int(header_row)),
                                 progress=self._progress_cb(), mask_headers=bool(opts.get("maskHeaders")),
                                 propagate=bool(opts.get("propagate")))
        except ec.ExcelCryptError as e:
            return from_exc(e)
        except Exception as e:
            return error("read_failed", f"Lecture impossible : {e}", detail=str(e))
        finally:
            self._busy.release()
        return {"ok": True, "findings": found}

    def encrypt(self, selection: dict, opts: dict, header_row: int = 1) -> dict:
        if not self._keys:
            return error("no_key", "Aucune clé chargée.")
        if not self._file:
            return error("no_file", "Aucun fichier ouvert.")
        src = self._file
        out = self._save_dialog(ec.default_output(src, self._t["enc"]).name, str(src.parent))
        if not out:
            return {"cancelled": True}
        if out.suffix.lower() != src.suffix.lower():
            out = out.with_suffix(src.suffix)
        if out.resolve() == src.resolve():
            return error("same_output", "Choisissez un fichier de sortie différent de l'original.")
        literals, detectors, errors, select = self._run_options(selection, opts)
        if errors:
            return error("regex_invalid", "Regex invalide : " + ", ".join(errors), pattern=", ".join(errors))
        if not self._busy.acquire(blocking=False):
            return error("busy", "Une opération est déjà en cours.")
        try:
            self._window.evaluate_js(f"window.onTaskStart('encrypt', {json.dumps(src.name)})")
            res = ec.encrypt_file(src, out, self._keys, self._vault_path, select, literals, detectors,
                                  max(1, int(header_row)), progress=self._progress_cb(),
                                  mask_headers=bool(opts.get("maskHeaders")), propagate=bool(opts.get("propagate")),
                                  readable=bool(opts.get("readable")))
        except ec.ExcelCryptError as e:
            return from_exc(e)
        except PermissionError:
            return error("write_denied", f"Impossible d'écrire {out.name} : le fichier est peut-être ouvert dans Excel.",
                         name=out.name)
        except Exception as e:
            return error("encrypt_failed", f"Échec du chiffrement : {e}", detail=str(e))
        finally:
            self._preview_vault = None
            self._busy.release()
        return {"ok": True, "masked": res["masked"], "unique": res["unique"],
                "output": file_info(out), "key": str(self._key_path), "vault": str(self._vault_path),
                "state": self.get_state()}

    def decrypt(self, path: str | None = None) -> dict:
        if not self._keys:
            return error("no_key", "Aucune clé chargée.")
        if not self._vault_path.exists():
            return error("vault_missing", f"Coffre introuvable : {self._vault_path.name}.", name=self._vault_path.name)
        src = Path(path) if path else self._open_dialog()
        if not src:
            return {"cancelled": True}
        try:
            ec.check_format(src)
        except ec.ExcelCryptError as e:
            return from_exc(e)
        out = self._save_dialog(ec.default_output(src, self._t["dec"]).name, str(src.parent))
        if not out:
            return {"cancelled": True}
        if out.suffix.lower() != src.suffix.lower():
            out = out.with_suffix(src.suffix)
        if not self._busy.acquire(blocking=False):
            return error("busy", "Une opération est déjà en cours.")
        try:
            self._window.evaluate_js(f"window.onTaskStart('decrypt', {json.dumps(src.name)})")
            res = ec.decrypt_file(src, out, self._keys, self._vault_path, progress=self._progress_cb())
        except ec.ExcelCryptError as e:
            return from_exc(e)
        except PermissionError:
            return error("write_denied", f"Impossible d'écrire {out.name} : le fichier est peut-être ouvert dans Excel.",
                         name=out.name)
        except Exception as e:
            return error("decrypt_failed", f"Échec du déchiffrement : {e}", detail=str(e))
        finally:
            self._busy.release()
        return {"ok": True, "restored": res["restored"], "unknown": sorted(res["unknown"])[:50],
                "unknownCount": len(res["unknown"]), "source": file_info(src), "output": file_info(out)}

    # ------------------------------------------------------ traitement par lot --
    def _pick_batch_folders(self):
        src = self._folder_dialog(str(self._file.parent) if self._file else "")
        if not src:
            return None, None, []
        files = sorted(p for p in src.iterdir()
                       if p.is_file() and p.suffix.lower() in SUPPORTED - {".txt"} and not p.name.startswith(("~$", ".")))
        if not files:
            return src, None, []
        dst = self._folder_dialog(str(src))
        return src, dst, files

    def batch_encrypt(self, profile_name: str) -> dict:
        """Protège tous les fichiers d'un dossier avec un profil (colonnes retrouvées par leur nom)."""
        if not self._keys:
            return error("no_key", "Aucune clé chargée.")
        profile = next((p for p in self._profiles() if p["name"] == profile_name), None)
        if not profile:
            return error("profile_missing", f"Profil introuvable : {profile_name}", name=profile_name)
        src, dst, files = self._pick_batch_folders()
        if not src or (files and not dst):
            return {"cancelled": True}
        if not files:
            return error("batch_empty", "Aucun fichier Excel ou CSV dans ce dossier.", name=src.name)
        opts = profile.get("opts", {})
        literals, detectors, _ = self._mask_options(opts)
        cols = profile.get("columns", [])
        hr = max(1, int(profile.get("headerRow", 1)))
        mh, prop, readable = bool(opts.get("maskHeaders")), bool(opts.get("propagate")), bool(opts.get("readable"))

        def select(sheet, header):
            return ec.profile_selection(cols, header)

        if not self._busy.acquire(blocking=False):
            return error("busy", "Une opération est déjà en cours.")
        results = []
        try:
            for i, f in enumerate(files):
                self._window.evaluate_js(f"window.onBatchProgress({i}, {len(files)}, {json.dumps(f.name)})")
                out = dst / ec.default_output(f, self._t["enc"]).name
                try:
                    leaks = ec.scan_file(f, select, literals, detectors, hr, mask_headers=mh, propagate=prop)
                    res = ec.encrypt_file(f, out, self._keys, self._vault_path, select, literals, detectors, hr,
                                          mask_headers=mh, propagate=prop, readable=readable)
                    results.append({"name": f.name, "ok": True, "masked": res["masked"], "output": out.name,
                                    "leaks": sum(x["count"] for x in leaks)})
                except ec.ExcelCryptError as e:
                    results.append({"name": f.name, "ok": False} | from_exc(e))
                except Exception as e:
                    results.append({"name": f.name, "ok": False} | error("encrypt_failed", str(e), detail=str(e)))
            self._window.evaluate_js(f"window.onBatchProgress({len(files)}, {len(files)}, '')")
        finally:
            self._preview_vault = None
            self._busy.release()
        return {"ok": True, "kind": "encrypt", "results": results, "folder": str(dst), "state": self.get_state()}

    def batch_decrypt(self) -> dict:
        """Restaure tous les fichiers d'un dossier."""
        if not self._keys:
            return error("no_key", "Aucune clé chargée.")
        if not self._vault_path.exists():
            return error("vault_missing", f"Coffre introuvable : {self._vault_path.name}.", name=self._vault_path.name)
        src, dst, files = self._pick_batch_folders()
        if not src or (files and not dst):
            return {"cancelled": True}
        if not files:
            return error("batch_empty", "Aucun fichier Excel ou CSV dans ce dossier.", name=src.name)
        if not self._busy.acquire(blocking=False):
            return error("busy", "Une opération est déjà en cours.")
        results = []
        try:
            for i, f in enumerate(files):
                self._window.evaluate_js(f"window.onBatchProgress({i}, {len(files)}, {json.dumps(f.name)})")
                out = dst / ec.default_output(f, self._t["dec"]).name
                try:
                    res = ec.decrypt_file(f, out, self._keys, self._vault_path)
                    results.append({"name": f.name, "ok": True, "restored": res["restored"], "output": out.name,
                                    "unknown": len(res["unknown"])})
                except ec.ExcelCryptError as e:
                    results.append({"name": f.name, "ok": False} | from_exc(e))
                except Exception as e:
                    results.append({"name": f.name, "ok": False} | error("decrypt_failed", str(e), detail=str(e)))
            self._window.evaluate_js(f"window.onBatchProgress({len(files)}, {len(files)}, '')")
        finally:
            self._busy.release()
        return {"ok": True, "kind": "decrypt", "results": results, "folder": str(dst)}


def main():
    api = Api()
    window = webview.create_window(
        "ExcelCrypt", url=str(UI_DIR / "index.html"), js_api=api,
        width=1320, height=840, min_size=(1024, 660), background_color="#F5F7FA",
    )
    api._window = window

    def on_drop(event):
        files = event.get("dataTransfer", {}).get("files", [])
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if paths:
            window.evaluate_js(f"window.onFileDropped({json.dumps(paths[0])})")

    def bind(win):
        win.dom.document.events.drop += DOMEventHandler(on_drop, True, True)

    webview.start(bind, window, debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()

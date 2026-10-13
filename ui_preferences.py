"""Versioned, offline GUI preferences.

A packaged Windows app writes to its own LocalState; the unpackaged build
uses %LOCALAPPDATA%/<product>. No data is automatically uploaded.
Only the explicitly allowlisted user preferences are stored, never input files.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import tempfile
from pathlib import Path

MAX_BYTES = 65536
MAX_VALUE = 4096
VERSION = 1
_PRODUCT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,63}$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def package_family_name() -> str | None:
    """Return actual Windows packaged process identity; never infer from env text."""
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True).GetCurrentPackageFamilyName
        api.argtypes = [ctypes.POINTER(wintypes.UINT), ctypes.c_wchar_p]
        api.restype = ctypes.c_long
        count = wintypes.UINT(0)
        result = api(ctypes.byref(count), None)
        if result == 15700:  # APPMODEL_ERROR_NO_PACKAGE
            return None
        if result != 122 or not (1 < count.value <= 512):
            raise OSError(f"Windows package identity lookup failed: {result}")
        buffer = ctypes.create_unicode_buffer(count.value)
        result = api(ctypes.byref(count), buffer)
        if result != 0 or not buffer.value:
            raise OSError(f"Windows package identity read failed: {result}")
        return buffer.value
    except (AttributeError, OSError):
        raise


def preference_path(product: str, *, override_dir: Path | None = None) -> Path:
    if not _PRODUCT_RE.fullmatch(product):
        raise ValueError("Invalid product identifier")
    if override_dir is not None:
        root = Path(override_dir)
    else:
        local = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home() / "AppData" / "Local"
        family = package_family_name()
        root = (local / "Packages" / family / "LocalState" / product) if family else (local / product)
    return root / "preferences.json"


def _validate_fields(fields: tuple[str, ...]) -> None:
    if not fields or len(fields) > 24 or len(set(fields)) != len(fields):
        raise ValueError("Invalid preference allowlist")
    if any(not _KEY_RE.fullmatch(name) for name in fields):
        raise ValueError("Invalid preference key")


def load_preferences(product: str, fields: tuple[str, ...], *,
                     override_dir: Path | None = None) -> dict[str, str]:
    _validate_fields(fields)
    path = preference_path(product, override_dir=override_dir)
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Preferences are unsafe or exceed size limit")
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Preferences JSON is damaged; original file was not changed") from exc
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != VERSION:
        raise ValueError("Unsupported preferences version; keeping original intact")
    stored = data.get("values")
    if not isinstance(stored, dict) or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > MAX_VALUE for k, v in stored.items()):
        raise ValueError("Malformed preferences; keeping original intact")
    return {name: stored[name] for name in fields if name in stored}


def save_preferences(product: str, values: dict[str, str], fields: tuple[str, ...], *,
                     override_dir: Path | None = None) -> Path:
    _validate_fields(fields)
    if (not isinstance(values, dict)
        or any(key not in fields or not isinstance(value, str) or len(value) > MAX_VALUE for key, value in values.items())):
        raise ValueError("Invalid or unapproved preferences")
    path = preference_path(product, override_dir=override_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Reject newer/corrupted preferences rather than silently destroying them.
    if path.exists():
        if path.is_symlink():
            raise ValueError("Refusing to overwrite a symlink")
        load_preferences(product, fields, override_dir=override_dir)
    payload = json.dumps({"schema_version": VERSION, "values": values},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Preference document exceeds size limit")
    temp_name = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".preferences-", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        temp_name = None
        return path
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)

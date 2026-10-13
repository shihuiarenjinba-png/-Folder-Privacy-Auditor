"""Synthetic installed-GUI test of REAL user preference save/reload functionality.

Runs in packaged process through Windows AUMID activation, not standalone EXE.
No real user data or customer paths. Test writes only synthetic settings.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from tkinter import ttk

from ui_preferences import load_preferences, preference_path


def _save_button(app):
    found = []
    def visit(node):
        for child in node.winfo_children():
            if isinstance(child, ttk.Button) and "設定を保存" in child.cget("text"):
                found.append(child)
            visit(child)
    visit(app)
    if len(found) != 1:
        raise AssertionError(f"Expected one genuine settings save button, got {len(found)}")
    return found[0]


def run(gui_type, product: str, expected: dict[str, str]) -> None:
    if len(sys.argv) != 4 or sys.argv[1] != "--preferences-ci" or sys.argv[2] not in ("write", "verify"):
        raise SystemExit("Usage: --preferences-ci write|verify <proof-path>")
    mode, proof_path = sys.argv[2], Path(sys.argv[3]).resolve()
    settings_path = preference_path(product)
    # Require real MSIX package identity, not environment supplied by caller.
    from ui_preferences import package_family_name
    family = package_family_name()
    if not family or not family.startswith("QA.") or ".Prototype_" not in family:
        raise RuntimeError("Preferences CI is allowed only inside synthetic QA MSIX")
    if not settings_path.is_relative_to(proof_path.parent):
        raise AssertionError("Preferences are outside synthetic MSIX LocalState")
    app = gui_type()
    try:
        app.withdraw()
        app.update()
        for name, value in expected.items():
            variable = getattr(app, name)
            if mode == "write":
                variable.set(value)
            else:
                if str(variable.get()) != value:
                    raise AssertionError(f"Persisted GUI preference did not restore: {name}")
        if mode == "write":
            _save_button(app).invoke()
            app.update()
        actual = load_preferences(product, tuple(expected))
        if actual != expected:
            raise AssertionError("Persisted preferences differ from GUI values")
        settings_hash = hashlib.sha256(settings_path.read_bytes()).hexdigest()
        with proof_path.open("x", encoding="utf-8") as handle:
            json.dump({"status": "GUI_REAL_PREFERENCES_OK", "mode": mode, "product": product,
                       "schema_version": 1, "preferences_sha256": settings_hash,
                       "fields": sorted(expected),
                       "synthetic_data_only": True, "human_gui_test": False},
                      handle, ensure_ascii=False, sort_keys=True)
    finally:
        app.destroy()

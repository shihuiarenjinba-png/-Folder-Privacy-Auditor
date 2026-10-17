"""Compiled storage analyzer GUI E2E using small synthetic folders only."""
from __future__ import annotations
import json
import sys
import tempfile
import time
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from unittest.mock import patch


def buttons(app, name):
    found=[]
    def visit(node):
        for child in node.winfo_children():
            if isinstance(child,ttk.Button) and child.cget("text")==name:
                found.append(child)
            visit(child)
    visit(app)
    return found


def await_idle(app, timeout=20):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.update()
        if not app.busy:
            app.update()
            return
        time.sleep(0.06)
    raise AssertionError("Storage GUI scan timed out")


def run(GUI):
    if len(sys.argv)!=3 or sys.argv[1]!="--e2e-test":
        raise ValueError("Usage: --e2e-test <proof.json>")
    proof=Path(sys.argv[2]).resolve()
    with tempfile.TemporaryDirectory(prefix="storage_gui_e2e_") as directory:
        root=Path(directory)
        scan=root/"scan"
        reports=root/"reports"
        nm=scan/"project"/"node_modules"
        venv=scan/"py"/".venv"
        nm.mkdir(parents=True)
        venv.mkdir(parents=True)
        (nm/"lib.js").write_bytes(b"x"*110)
        (venv/"lib.dat").write_bytes(b"y"*40)
        app=GUI()
        errors=[]
        try:
            app.withdraw()
            app.update()
            browse=buttons(app,"参照")
            assert len(browse)==3
            with patch.object(filedialog,"askdirectory",return_value=str(scan)):
                browse[0].invoke()
            with patch.object(filedialog,"askdirectory",return_value=str(reports)):
                browse[1].invoke()
            assert app.scan.get()==str(scan) and app.reports.get()==str(reports)
            start=buttons(app,"スキャン開始（読み取りのみ）")
            assert len(start)==1
            with patch.object(messagebox,"showerror",side_effect=lambda *args: errors.append(args)):
                start[0].invoke()
                await_idle(app)
                files=list(reports.glob("storage_cause_*/storage_report.json"))
                assert len(files)==1
                first=json.loads(files[0].read_text(encoding="utf-8"))
                assert first["total_logical_bytes"]==150
                assert first["category_bytes"]["node_dependencies"]==110
                assert first["category_bytes"]["python_environment"]==40
                assert first["status"]=="COMPLETE_FOR_REGULAR_FILES"
                (nm/"lib.js").write_bytes(b"x"*160)
                # No manual baseline selected: second scan must compare automatically.
                assert not app.baseline.get()
                start[0].invoke()
                await_idle(app)
                second_files=[p for p in reports.glob("storage_cause_*/storage_report.json") if p not in files]
                assert len(second_files)==1
                second=json.loads(second_files[0].read_text(encoding="utf-8"))
                assert second["growth_total_logical_bytes"]==50
                assert second["growth_by_category"]["node_dependencies"]==50
                assert second["comparison_source"]=="automatic_previous"
                assert (venv/"lib.dat").read_bytes()==b"y"*40
                assert (nm/"lib.js").read_bytes()==b"x"*160
                assert not errors, errors
                # Negative UI path: absent scan root must not create a new report.
                app.scan.set(str(root/"missing-source"))
                start[0].invoke()
                await_idle(app)
                assert errors, "Missing scan root must produce a GUI error"
                assert len(list(reports.glob("storage_cause_*/storage_report.json")))==2
            with proof.open("x",encoding="utf-8") as output:
                json.dump({"status":"GUI_E2E_OK","scenario":"browse -> scan -> report -> baseline growth",
                           "actual_output_verified":True,"input_unchanged":True,
                           "negative_case_verified":True,"interactive_human_test":False},output,ensure_ascii=False,indent=2)
        finally:
            app.destroy()

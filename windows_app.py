from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from tkinter import BOTH, END, LEFT, Button, Frame, Label, Listbox, Tk, filedialog, messagebox

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?81[- ]?)?0?\d{1,4}[- ]?\d{1,4}[- ]?\d{3,4}(?!\d)")
TEXTLIKE = {".txt", ".md", ".csv", ".json", ".log", ".yaml", ".yml"}
RISKY_EXT = {".csv", ".xlsx", ".xls", ".json", ".sql", ".db", ".sqlite", ".bak"}
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "utf-16")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_text(raw: bytes) -> str:
    last_error: UnicodeError | None = None
    for enc in TEXT_ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeError as exc:
            last_error = exc
    raise UnicodeError(f"Unsupported or undecodable text encoding; supported encodings: {', '.join(TEXT_ENCODINGS)}") from last_error


def sample_text(path: Path, limit: int = 1_000_000) -> str:
    with path.open("rb") as fh:
        return decode_text(fh.read(limit))


def audit_folder(root: Path) -> list[dict]:
    records: list[dict] = []
    hashes: dict[str, list[int]] = defaultdict(list)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        try:
            size = path.stat().st_size
        except OSError:
            continue
        rec = {
            "path": rel,
            "extension": path.suffix.lower(),
            "bytes": size,
            "hidden": any(part.startswith(".") for part in path.relative_to(root).parts),
            "risky_data_type": path.suffix.lower() in RISKY_EXT,
            "email_candidate": False,
            "phone_candidate": False,
            "duplicate_group": "",
            "sha256": "",
            "notes": [],
        }
        if rec["hidden"]:
            rec["notes"].append("hidden file/path")
        if rec["risky_data_type"]:
            rec["notes"].append("data-bearing file type")
        if size <= 50 * 1024 * 1024:
            try:
                digest = sha256_file(path)
                rec["sha256"] = digest
                hashes[digest].append(len(records))
            except OSError as exc:
                rec["notes"].append(f"hash failed: {exc}")
        else:
            rec["notes"].append("hash skipped >50MB")
        if path.suffix.lower() in TEXTLIKE and size <= 2 * 1024 * 1024:
            try:
                text = sample_text(path)
                rec["email_candidate"] = bool(EMAIL_RE.search(text))
                rec["phone_candidate"] = bool(PHONE_RE.search(text))
                if rec["email_candidate"]:
                    rec["notes"].append("email candidate")
                if rec["phone_candidate"]:
                    rec["notes"].append("phone candidate")
            except (OSError, UnicodeError) as exc:
                rec["notes"].append(f"content scan failed (manual review required): {exc}")
        elif path.suffix.lower() in TEXTLIKE and size > 2 * 1024 * 1024:
            rec["notes"].append("content scan skipped >2MB (manual review required)")
        records.append(rec)

    group_num = 1
    for digest, indices in hashes.items():
        if len(indices) > 1:
            label = f"DUP-{group_num:04d}"
            group_num += 1
            for idx in indices:
                records[idx]["duplicate_group"] = label
                records[idx]["notes"].append("duplicate content")
    return records


def export_reports(records: list[dict], output_base: Path) -> tuple[Path, Path]:
    csv_path = output_base.with_suffix(".csv")
    json_path = output_base.with_suffix(".json")
    fields = ["path", "extension", "bytes", "hidden", "risky_data_type", "email_candidate", "phone_candidate", "duplicate_group", "sha256", "notes"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            row = dict(rec)
            row["notes"] = "; ".join(row["notes"])
            writer.writerow(row)
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Folder Privacy Auditor — Windows")
        self.root.geometry("960x650")
        self.folder: Path | None = None
        self.records: list[dict] = []

        head = Frame(root, padx=12, pady=12)
        head.pack(fill="x")
        Label(head, text="Folder Privacy Auditor", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        Label(head, text="Audit a folder locally for data-bearing files, PII candidates, hidden files and duplicates.").pack(anchor="w")
        controls = Frame(root, padx=12)
        controls.pack(fill="x")
        Button(controls, text="Choose folder", width=16, command=self.choose).pack(side=LEFT)
        Button(controls, text="Run audit", width=16, command=self.audit).pack(side=LEFT, padx=8)
        Button(controls, text="Export CSV + JSON", width=18, command=self.export).pack(side=LEFT)
        self.listbox = Listbox(root, font=("Consolas", 9))
        self.listbox.pack(fill=BOTH, expand=True, padx=12, pady=12)

    def choose(self):
        p = filedialog.askdirectory(title="Choose folder to audit")
        if p:
            self.folder = Path(p)
            self.listbox.delete(0, END)
            self.listbox.insert(END, f"Folder: {self.folder}")

    def audit(self):
        if not self.folder:
            return messagebox.showinfo("Folder Privacy Auditor", "Choose a folder first.")
        try:
            self.records = audit_folder(self.folder)
            self.listbox.delete(0, END)
            flagged = 0
            for r in self.records:
                flags = ", ".join(r["notes"])
                if flags:
                    flagged += 1
                self.listbox.insert(END, f"{r['path']} | {r['bytes']:,} bytes | {flags or 'no flag'}")
            self.listbox.insert(END, f"--- Files: {len(self.records):,} / flagged: {flagged:,} ---")
        except Exception as exc:
            messagebox.showerror("Folder Privacy Auditor", str(exc))

    def export(self):
        if not self.records:
            self.audit()
        if not self.records:
            return
        p = filedialog.asksaveasfilename(title="Report base name", defaultextension=".csv", initialfile="folder_privacy_audit.csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        try:
            csv_path, json_path = export_reports(self.records, Path(p))
            messagebox.showinfo("Folder Privacy Auditor", f"Saved:\n{csv_path}\n{json_path}")
        except Exception as exc:
            messagebox.showerror("Folder Privacy Auditor", str(exc))


def main():
    root = Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()

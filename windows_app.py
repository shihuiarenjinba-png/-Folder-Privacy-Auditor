from __future__ import annotations

import csv
import hashlib
import json
import os
import queue
import threading
import re
import stat
from collections import defaultdict
from pathlib import Path
from tkinter import BOTH, END, LEFT, Button, Frame, Label, Listbox, StringVar, Tk, OptionMenu, filedialog, messagebox

EMAIL_RE = re.compile(
    r"(?<![A-Z0-9._%+-])"
    r"[A-Z0-9_%+-]+(?:\.[A-Z0-9_%+-]+)*"
    r"@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+"
    r"(?![A-Z0-9._-])",
    re.I,
)
PHONE_RE = re.compile(
    r"(?<![\d+])(?<!\+81-)(?<!\+81 )(?:"
    r"\+81(?:[- ]?(?:70|80|90)[- ]?\d{4}[- ]?\d{4}|[- ]?(?!0)\d{1,4}[- ]\d{1,4}[- ]\d{3,4})"
    r"|0(?:70|80|90)(?:[- ]?\d{4}){2}"
    r"|0(?![789]0[- ])\d{1,4}[- ]\d{1,4}[- ]\d{3,4}"
    r")(?!\d)"
)
LONG_ID_RE = re.compile(r"(?<!\d)\d{10,16}(?!\d)")
TEXTLIKE = {
    ".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".log",
    ".yaml", ".yml", ".ini", ".conf", ".cfg", ".toml",
}
RISKY_EXT = {
    ".csv", ".tsv", ".xlsx", ".xls", ".docx", ".pdf", ".json", ".xml",
    ".yaml", ".yml", ".log", ".sql", ".db", ".sqlite", ".bak",
}
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "utf-16")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_decoded_text(text: str) -> str:
    if "\x00" in text:
        raise UnicodeError("Decoded text contains NUL bytes and appears binary.")
    if text:
        controls = sum(ord(ch) < 32 and ch not in "\t\n\r\f" for ch in text)
        if controls / len(text) > 0.01:
            raise UnicodeError("Decoded text contains too many control characters and appears binary.")
    return text


def decode_text(raw: bytes) -> str:
    last_error: UnicodeError | None = None
    for enc in TEXT_ENCODINGS:
        try:
            return validate_decoded_text(raw.decode(enc))
        except UnicodeError as exc:
            last_error = exc
    raise UnicodeError(
        f"Unsupported or undecodable text encoding; supported encodings: {', '.join(TEXT_ENCODINGS)}"
    ) from last_error


def sample_text(path: Path, limit: int = 1_000_000) -> str:
    with path.open("rb") as fh:
        return decode_text(fh.read(limit))


def _valid_email_match(text: str, match: re.Match[str]) -> bool:
    candidate = match.group(0)
    local, domain = candidate.rsplit("@", 1)
    if len(candidate) > 254 or len(local) > 64:
        return False
    labels = domain.split(".")
    if not (2 <= len(labels) and labels[-1].isalpha() and len(labels[-1]) >= 2):
        return False
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        return False
    if not any(char.isalpha() for char in labels[0]):
        return False

    token_start = max(text.rfind(" ", 0, match.start()), text.rfind("\t", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
    prefix = text[token_start:match.start()].lower()
    if "://" in prefix and not prefix.endswith("mailto:"):
        return False
    context = text[max(0, token_start - 12):match.start()].lower()
    if context.rstrip().endswith(("filename=", "file=", "path=")):
        return False
    return True


def find_email_candidates(text: str) -> list[re.Match[str]]:
    return [match for match in EMAIL_RE.finditer(text) if _valid_email_match(text, match)]


def is_hidden_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part.startswith(".") for part in rel.parts):
        return True
    try:
        attrs = getattr(path.stat(), "st_file_attributes", 0)
        hidden_flag = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0)
        return bool(hidden_flag and attrs & hidden_flag)
    except OSError:
        return False


MAX_FILES = 150_000
HASH_LIMIT_BYTES = 50 * 1024 * 1024
TEXT_SCAN_LIMIT_BYTES = 1_000_000


def _reparse_or_symlink(path: Path) -> bool:
    """Never follow symlinks, junctions or any Windows reparse point."""
    try:
        info = path.lstat()
        return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def _record(path: str, *, note: str, status: str = "UNINSPECTED") -> dict:
    return {
        "path": path, "extension": Path(path).suffix.lower(), "bytes": 0,
        "hidden": False, "risky_data_type": False,
        "email_candidate": False, "phone_candidate": False, "long_id_candidate": False,
        "duplicate_group": "", "sha256": "",
        "status": status, "checked": [], "unchecked": [note], "notes": [note],
    }


def audit_folder(root: Path) -> list[dict]:
    """Read-only inventory with explicit per-file coverage and traversal failures."""
    if _reparse_or_symlink(root):
        raise ValueError("Cannot audit through a symlink, junction or reparse root.")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Choose a directory.")
    records: list[dict] = []
    hashes: dict[str, list[int]] = defaultdict(list)
    stack = [root]
    counted = 0
    truncated = False

    while stack and not truncated:
        folder = stack.pop()
        try:
            with os.scandir(folder) as iterator:
                children = list(iterator)
        except OSError as exc:
            records.append(_record(str(folder.relative_to(root)),
                                   note=f"directory not inspected: {type(exc).__name__}",
                                   status="FAILED"))
            continue
        for item in children:
            path = Path(item.path)
            rel = str(path.relative_to(root))
            try:
                if _reparse_or_symlink(path):
                    records.append(_record(rel, note="link/reparse target not inspected"))
                    continue
                info = item.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    stack.append(path)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    records.append(_record(rel, note="not a regular file; content not inspected"))
                    continue
                counted += 1
                if counted > MAX_FILES:
                    records.append(_record("(limit)", note=f"scan capped at {MAX_FILES} files"))
                    truncated = True
                    break
                size = int(info.st_size)
                ext = path.suffix.lower()
                rec = _record(rel, note="content not inspected")
                rec.update({
                    "bytes": size,
                    "extension": ext,
                    "hidden": is_hidden_path(path, root),
                    "risky_data_type": ext in RISKY_EXT,
                    "status": "UNINSPECTED",
                    "checked": ["file name, size and hidden/path indicators"],
                    "unchecked": [],
                    "notes": [],
                })
                if rec["hidden"]:
                    rec["notes"].append("hidden file/path")
                if rec["risky_data_type"]:
                    rec["notes"].append("data-bearing file type")
                if size <= HASH_LIMIT_BYTES:
                    try:
                        digest = sha256_file(path)
                        rec["sha256"] = digest
                        hashes[digest].append(len(records))
                        rec["checked"].append("SHA256 byte hash")
                    except OSError as exc:
                        rec["unchecked"].append(f"hash failed: {type(exc).__name__}")
                else:
                    rec["unchecked"].append("hash skipped >50MB")
                if ext in TEXTLIKE:
                    if size <= 2 * 1024 * 1024:
                        try:
                            text = sample_text(path, limit=TEXT_SCAN_LIMIT_BYTES)
                            rec["checked"].append("text-pattern sample, up to first 1MB")
                            if size > TEXT_SCAN_LIMIT_BYTES:
                                rec["unchecked"].append("text beyond first 1MB not scanned")
                            rec["email_candidate"] = bool(find_email_candidates(text))
                            rec["phone_candidate"] = bool(PHONE_RE.search(text))
                            rec["long_id_candidate"] = bool(LONG_ID_RE.search(text))
                            if rec["email_candidate"]:
                                rec["notes"].append("email candidate")
                            if rec["phone_candidate"]:
                                rec["notes"].append("phone candidate")
                            if rec["long_id_candidate"]:
                                rec["notes"].append("long numeric identifier candidate (warning only)")
                        except (OSError, UnicodeError) as exc:
                            rec["unchecked"].append(f"content scan failed (manual review required): {type(exc).__name__}")
                            rec["notes"].append("content scan failed (manual review required)")
                    else:
                        rec["unchecked"].append("content scan skipped >2MB (manual review required)")
                else:
                    rec["unchecked"].append("format-specific content not inspected")
                if rec["risky_data_type"] or rec["hidden"] or rec["email_candidate"] or rec["phone_candidate"] or rec["long_id_candidate"]:
                    rec["status"] = "REVIEW"
                elif rec["unchecked"]:
                    rec["status"] = "UNINSPECTED"
                else:
                    # Pattern checks cannot certify privacy even when no match.
                    rec["status"] = "LIMITED"
                rec["unchecked"].append("privacy not certified; undiscovered personal data may remain")
                records.append(rec)
            except (OSError, ValueError) as exc:
                records.append(_record(rel, note=f"file access/scan failed: {type(exc).__name__}",
                                       status="FAILED"))

    group_num = 1
    for digest, indices in hashes.items():
        if len(indices) > 1:
            label = f"DUP-{group_num:04d}"
            group_num += 1
            for idx in indices:
                records[idx]["duplicate_group"] = label
                records[idx]["notes"].append("duplicate content")
                records[idx]["status"] = "REVIEW"
    return records


def summarize_audit(records: list[dict]) -> dict:
    """One-screen summary; skipped files must not disappear from totals."""
    regular = [r for r in records if "file name, size and hidden/path indicators" in r["checked"]]
    return {
        "files": len(regular),
        "logical_bytes": sum(r["bytes"] for r in regular),
        "review": sum(r["status"] == "REVIEW" for r in regular),
        "limited": sum(r["status"] == "LIMITED" for r in regular),
        "uninspected": sum(r["status"] == "UNINSPECTED" for r in records),
        "failed": sum(r["status"] == "FAILED" for r in records),
        "duplicated": sum(bool(r["duplicate_group"]) for r in regular),
        "scope": "Read-only, pattern-based, partial by design; no automatic deletions",
    }


def filter_audit_records(records: list[dict], status: str) -> list[dict]:
    """Status selector changes only displayed rows, never the full report."""
    if status == "ALL":
        return list(records)
    if status not in {"REVIEW", "LIMITED", "UNINSPECTED", "FAILED"}:
        raise ValueError("Unknown audit status filter")
    return [r for r in records if r["status"] == status]


def _safe_csv_report_cell(value):
    """Protect the audit CSV from formula evaluation when opened in Excel."""
    if isinstance(value, str):
        leading = value.lstrip(" \t\r\n")
        if leading.startswith(("=", "+", "-", "@")) or value[:1] in ("\t", "\r", "\n"):
            return "'" + value
    return value


def export_reports(records: list[dict], output_base: Path,
                   scanned_root: Path | None = None) -> tuple[Path, Path]:
    """Export new reports only, never replace files or write into a scanned tree."""
    csv_path = output_base.with_suffix(".csv")
    json_path = output_base.with_suffix(".json")
    if scanned_root is not None:
        root = scanned_root.resolve(strict=True)
        if csv_path.resolve().is_relative_to(root) or json_path.resolve().is_relative_to(root):
            raise ValueError("Report output must be outside the scanned folder.")
    if csv_path.exists() or json_path.exists() or csv_path.is_symlink() or json_path.is_symlink():
        raise FileExistsError("One or both report filenames already exist; choose another name.")
    fields = [
        "path", "extension", "bytes", "hidden", "risky_data_type",
        "email_candidate", "phone_candidate", "long_id_candidate",
        "duplicate_group", "sha256", "status", "checked", "unchecked", "notes",
    ]
    csv_escaped_cells = 0
    for record in records:
        for field in fields:
            value = record[field]
            if field in ("checked", "unchecked", "notes"):
                value = "; ".join(value)
            if _safe_csv_report_cell(value) != value:
                csv_escaped_cells += 1
    created_csv = False
    created_json = False
    try:
        with csv_path.open("x", encoding="utf-8-sig", newline="") as fh:
            created_csv = True
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for rec in records:
                row = dict(rec)
                for field in ("checked", "unchecked", "notes"):
                    row[field] = "; ".join(row[field])
                writer.writerow({field: _safe_csv_report_cell(row[field]) for field in fields})
        with json_path.open("x", encoding="utf-8") as fh:
            created_json = True
            json.dump(
                {"schema_version": 2, "summary": summarize_audit(records),
                 "csv_escaped_formula_cells": csv_escaped_cells,
                 "records": records}, fh, ensure_ascii=False, indent=2,
            )
    except BaseException:
        if created_csv:
            csv_path.unlink(missing_ok=True)
        if created_json:
            json_path.unlink(missing_ok=True)
        raise
    return csv_path, json_path


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Folder Privacy Auditor — Windows")
        self.root.geometry("960x650")
        self.folder: Path | None = None
        self.records: list[dict] = []
        self.busy = False
        self.results_queue = queue.Queue()
        self.status_text = StringVar(value="Choose a folder. Audit does not modify input files.")
        self.filter_status = StringVar(value="ALL")

        head = Frame(root, padx=12, pady=12)
        head.pack(fill="x")
        Label(head, text="Folder Privacy Auditor", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        Label(head, text="Choose folder → inspect → export report. Read-only; never deletes anything.").pack(anchor="w")

        controls = Frame(root, padx=12)
        controls.pack(fill="x")
        self.choose_button = Button(controls, text="Choose folder", width=16, command=self.choose)
        self.choose_button.pack(side=LEFT)
        self.audit_button = Button(controls, text="Run audit", width=16, command=self.audit)
        self.audit_button.pack(side=LEFT, padx=8)
        self.export_button = Button(controls, text="Export CSV + JSON", width=18, command=self.export)
        self.export_button.pack(side=LEFT)

        filters = Frame(root, padx=12)
        filters.pack(fill="x", pady=(10, 0))
        Label(filters, text="Show results:").pack(side=LEFT)
        OptionMenu(filters, self.filter_status, "ALL", "REVIEW", "LIMITED", "UNINSPECTED", "FAILED",
                   command=lambda _value: self.render_filtered_results()).pack(side=LEFT)
        Label(filters, text="The CSV/JSON report always contains ALL records.").pack(side=LEFT, padx=(8, 0))
        self.listbox = Listbox(root, font=("Consolas", 9))
        self.listbox.pack(fill=BOTH, expand=True, padx=12, pady=12)
        Label(root, textvariable=self.status_text, anchor="w").pack(fill="x", padx=12, pady=(0, 10))
        self.root.after(150, self.poll_results)

    def choose(self):
        if self.busy:
            return
        p = filedialog.askdirectory(parent=self.root, title="Choose folder to audit")
        if p:
            self.folder = Path(p)
            self.records = []
            self.filter_status.set("ALL")
            self.status_text.set("Choose Run audit to begin. Results will be read-only.")
            self.listbox.delete(0, END)
            self.listbox.insert(END, f"Folder: {self.folder}")

    def audit(self):
        if self.busy:
            return
        if not self.folder:
            return messagebox.showinfo("Folder Privacy Auditor", "Choose a folder first.")
        self.busy = True
        self.records = []
        self.choose_button.configure(state="disabled")
        self.audit_button.configure(state="disabled")
        self.export_button.configure(state="disabled")
        self.status_text.set("Auditing locally... this may take time for large folders.")
        selected = self.folder

        def scan_worker():
            try:
                result = audit_folder(selected)
                self.results_queue.put((True, result))
            except Exception as exc:
                self.results_queue.put((False, str(exc)))

        threading.Thread(target=scan_worker, daemon=True).start()

    def poll_results(self):
        try:
            while True:
                ok, payload = self.results_queue.get_nowait()
                self.busy = False
                self.choose_button.configure(state="normal")
                self.audit_button.configure(state="normal")
                self.export_button.configure(state="normal")
                if not ok:
                    self.records = []
                    self.status_text.set("Audit failed; no report created.")
                    messagebox.showerror("Folder Privacy Auditor", payload)
                    continue
                self.records = payload
                self.render_filtered_results()
                self.status_text.set("Audit finished. No files were deleted. Review all uninspected areas.")
        except queue.Empty:
            pass
        self.root.after(150, self.poll_results)

    def render_filtered_results(self):
        if not self.records:
            return
        summary = summarize_audit(self.records)
        visible = filter_audit_records(self.records, self.filter_status.get())
        self.listbox.delete(0, END)
        self.listbox.insert(END,
            f"Total files {summary['files']} | Review {summary['review']} | "
            f"Limited {summary['limited']} | Uninspected {summary['uninspected']} | "
            f"Failed {summary['failed']} | {summary['logical_bytes']/(1024**2):.1f} MiB")
        self.listbox.insert(END,
            "Partial text/pattern scan only: LIMITED and zero findings never mean a folder is safe.")
        self.listbox.insert(END,
            f"Filter: {self.filter_status.get()} | displayed {min(len(visible), 2000)} / "
            f"{len(visible)} matching; full report {len(self.records)} records.")
        self.listbox.insert(END, "---")
        for record in visible[:2000]:
            flags = ", ".join(record["notes"]) or "No candidate in checked portion"
            self.listbox.insert(END, f"[{record['status']}] {record['path']} "
                f"| {record['bytes']:,} bytes | {flags}")
            if record["unchecked"]:
                self.listbox.insert(END, "    Not checked: " + ", ".join(record["unchecked"]))
        if len(visible) > 2000:
            self.listbox.insert(END, "Further results are available in the full CSV/JSON report.")

    def export(self):
        if self.busy:
            return messagebox.showinfo("Folder Privacy Auditor", "Audit is still running.")
        if not self.folder or not self.records:
            return messagebox.showinfo("Folder Privacy Auditor", "Run the audit before exporting.")
        p = filedialog.asksaveasfilename(
            parent=self.root,
            title="Report base name",
            defaultextension=".csv",
            initialfile="folder_privacy_audit.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not p:
            return
        try:
            csv_path, json_path = export_reports(self.records, Path(p), scanned_root=self.folder)
            messagebox.showinfo("Folder Privacy Auditor", f"Saved:\n{csv_path}\n{json_path}")
        except Exception as exc:
            messagebox.showerror("Folder Privacy Auditor", str(exc))


def main():
    from i18n import install_bilingual_ui

    root = Tk()
    App(root)
    install_bilingual_ui(root)
    root.mainloop()


if __name__ == "__main__":
    main()

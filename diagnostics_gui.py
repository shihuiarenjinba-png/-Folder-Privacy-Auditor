"""Optional read-only diagnostics dialog for the existing Folder Privacy Auditor UI."""
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from czkawka_bridge import SCAN_MODES, ScanCancelled, scan
from i18n import get_language
from storage_cause_analyzer import analyze


class DiagnosticsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, selected_folder: Path | None = None):
        super().__init__(parent)
        self.jp = get_language() == "ja"
        self.title(self.t("容量・重複診断（読み取り専用）", "Storage and duplicate diagnostics (read-only)"))
        self.geometry("880x600")
        self.minsize(760, 510)
        self.transient(parent)
        self.folder = tk.StringVar(value=str(selected_folder or ""))
        self.report_folder = tk.StringVar(value=str(Path.home() / "Documents" / "FolderPrivacyAuditorReports"))
        self.previous = tk.StringVar()
        self.scan_mode = tk.StringVar(value="duplicates")
        self.status = tk.StringVar(value=self.t("監視・スキャンは停止しています", "Scan is idle"))
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.running = False
        self.current_kind = ""

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self.path_row(frame, 0, self.t("調査フォルダ", "Folder to inspect"), self.folder)
        self.path_row(frame, 1, self.t("レポート保存先（調査フォルダ外）", "Report location (outside scan folder)"),
                      self.report_folder)
        notebook = ttk.Notebook(frame)
        notebook.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(12, 8))
        frame.rowconfigure(2, weight=1)
        duplicate_tab = ttk.Frame(notebook, padding=12)
        capacity_tab = ttk.Frame(notebook, padding=12)
        notebook.add(duplicate_tab, text=self.t("重複・ファイル検査", "Duplicate / file checks"))
        notebook.add(capacity_tab, text=self.t("容量・増加原因", "Storage / growth causes"))
        ttk.Label(duplicate_tab, text=self.t(
            "Czkawka Coreによる高速検査。削除・移動・修復は一切しません。",
            "Fast Czkawka Core scans. No deletion, moving or repair."),
            wraplength=780).pack(anchor="w", pady=(0, 12))
        choices = [(self.t(ja, en), key) for key, ja, en in (
            ("duplicates", "重複ファイル（サイズ＋内容ハッシュ）", "Duplicates (size and hash)"),
            ("similar_images", "類似画像", "Similar images"),
            ("large_files", "大容量ファイル", "Largest files"),
            ("empty_folders", "空フォルダ", "Empty folders"),
            ("empty_files", "空ファイル", "Empty files"),
            ("temporary_files", "一時ファイル候補", "Temporary file candidates"),
            ("bad_extensions", "拡張子の不整合候補", "Bad extension candidates"),
            ("broken_files", "破損ファイル候補", "Broken file candidates"),
        )]
        self.mode_names = {name: key for name, key in choices}
        self.mode_display = tk.StringVar(value=choices[0][0])
        selector = ttk.Combobox(duplicate_tab, textvariable=self.mode_display, state="readonly",
                                values=[a for a, _ in choices], width=46)
        selector.pack(anchor="w", pady=5)
        ttk.Button(duplicate_tab, text=self.t("検査を開始", "Start scan"),
                   command=self.start_fast).pack(anchor="w", pady=8)
        ttk.Label(duplicate_tab, text=self.t(
            "外部通信なし。調査結果にはファイル名が含まれるため、共有時は注意してください。",
            "No uploads. Reports contain file names; review them before sharing."),
            wraplength=750).pack(anchor="w")
        ttk.Label(capacity_tab, text=self.t(
            "フォルダ別・キャッシュ等の容量と前回からの増減を比較します。値は論理サイズです。",
            "Inspect folder/cache sizes and compare growth. Values are logical bytes."),
            wraplength=760).pack(anchor="w", pady=(0, 12))
        self.path_row(capacity_tab, 0, self.t("前回のJSON（任意）", "Previous JSON (optional)"),
                      self.previous, report=True, pack_layout=True)
        ttk.Button(capacity_tab, text=self.t("容量診断を開始", "Analyze storage"),
                   command=self.start_storage).pack(anchor="w", pady=10)
        controls = ttk.Frame(frame)
        controls.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.cancel_button = ttk.Button(controls, text=self.t("キャンセル", "Cancel"),
                                        command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left")
        self.progress = ttk.Progressbar(controls, mode="indeterminate")
        self.progress.pack(side="left", padx=12, fill="x", expand=True)
        self.details = tk.Text(frame, height=8, wrap="word", state="disabled")
        self.details.grid(row=4, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(4, weight=1)
        ttk.Label(frame, textvariable=self.status, wraplength=820).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.after(150, self.poll)

    def t(self, ja: str, en: str) -> str:
        return ja if self.jp else en

    def path_row(self, parent, row, title, variable, report=False, pack_layout=False):
        if pack_layout:
            line = ttk.Frame(parent)
            line.pack(fill="x", pady=5)
            ttk.Label(line, text=title).pack(anchor="w")
            ttk.Entry(line, textvariable=variable).pack(side="left", fill="x", expand=True)
            ttk.Button(line, text="...", command=lambda: self.choose(variable, report)).pack(side="left")
        else:
            ttk.Label(parent, text=title).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
            ttk.Button(parent, text="...", command=lambda: self.choose(variable, report)).grid(
                row=row, column=2, padx=4)

    def choose(self, variable, report):
        value = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json")]) if report else (
            filedialog.askdirectory(parent=self))
        if value:
            variable.set(value)

    def _start(self, kind: str, worker):
        if self.running:
            return
        if not self.folder.get().strip() or not self.report_folder.get().strip():
            messagebox.showwarning(self.title(), self.t("フォルダと保存先を指定してください",
                                                       "Select a folder and report location"), parent=self)
            return
        self.running = True
        self.current_kind = kind
        self.cancel_event = threading.Event()
        self.cancel_button.configure(state="normal")
        self.progress.start(20)  # indeterminate; Czkawka CLI does not expose percent
        self.status.set(self.t("処理中（正確な進捗率は取得不可）", "Working (percent unavailable)"))
        folder, reports = self.folder.get().strip(), self.report_folder.get().strip()
        cancel = self.cancel_event

        def thread_main():
            try:
                path = worker(folder, reports, cancel)
                self.events.put(("done", path))
            except (ScanCancelled, RuntimeError) as exc:
                if cancel.is_set():
                    self.events.put(("cancelled", str(exc)))
                else:
                    self.events.put(("error", str(exc)))
            except Exception as exc:
                self.events.put(("error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=thread_main, daemon=True).start()

    def start_fast(self):
        mode = self.mode_names.get(self.mode_display.get(), "duplicates")
        self._start("fast", lambda root, reports, cancel: scan(
            root, mode, report_directory=reports, cancel_event=cancel))

    def start_storage(self):
        prior = self.previous.get().strip() or None
        self._start("storage", lambda root, reports, cancel: analyze(
            root, reports, prior, cancel_event=cancel) / "storage_report.json")

    def cancel(self):
        if self.running:
            self.cancel_event.set()
            self.status.set(self.t("中断処理中です…", "Cancelling..."))

    def _display(self, text: str):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                self.running = False
                self.cancel_button.configure(state="disabled")
                self.progress.stop()
                if kind == "done":
                    try:
                        raw = json.loads(Path(data).read_text(encoding="utf-8-sig"))
                        if self.current_kind == "storage":
                            summary = [
                                self.t("論理サイズ（MiB）", "Logical MiB") +
                                f": {raw['total_logical_bytes'] / (1024 * 1024):,.1f}",
                                self.t("検査したファイル", "Files scanned") +
                                f": {raw['scanned_files']}",
                                "Status: " + str(raw["status"]),
                                self.t("容量が大きい場所", "Largest top-level directories") + ":",
                            ]
                            summary += [f"  {k}: {v / (1024 * 1024):,.1f} MiB"
                                        for k, v in list(raw.get("top_level_bytes", {}).items())[:12]]
                            if "growth_total_logical_bytes" in raw:
                                summary += [self.t("前回比", "Change from previous") +
                                            f": {raw['growth_total_logical_bytes'] / (1024 * 1024):+,.1f} MiB"]
                            preview = "\n".join(summary)
                        else:
                            preview = self.t("Czkawkaの生データ（先頭のみ）:", "Original Czkawka JSON (excerpt):") + "\n" + (
                                json.dumps(raw, ensure_ascii=False, indent=2)[:8000])
                        self._display(preview)
                        self.status.set(self.t("完了（削除なし）。レポート: ", "Done (no deletion). Report: ") + str(data))
                    except Exception as exc:
                        self.status.set(self.t("表示に失敗: ", "Display failed: ") + str(exc))
                elif kind == "cancelled":
                    self.status.set(self.t("キャンセルしました。削除なし。", "Cancelled; no input files modified"))
                else:
                    self.status.set(self.t("検査失敗: ", "Scan failed: ") + str(data))
        except queue.Empty:
            pass
        try:
            if self.winfo_exists():
                self.after(150, self.poll)
        except tk.TclError:
            pass

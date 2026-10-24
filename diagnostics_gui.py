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
from pc_load import LocalMonitor, save_history, delete_history


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
        self.exclusion = tk.StringVar()
        self.extension_filter = tk.StringVar()
        self.status = tk.StringVar(value=self.t("監視・スキャンは停止しています", "Scan is idle"))
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.running = False
        self.current_kind = ""
        self.pc_monitor = LocalMonitor(Path.home(), interval=2)
        self.pc_monitor.on_sample = lambda snapshot: self.events.put(("pc", snapshot))
        self.pc_running = False
        self.high_cpu_seconds = 0.0
        self.cpu_threshold = tk.IntVar(value=90)
        self.protocol("WM_DELETE_WINDOW", self.close_dialog)

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
        pc_tab = ttk.Frame(notebook, padding=12)
        notebook.add(duplicate_tab, text=self.t("重複・ファイル検査", "Duplicate / file checks"))
        notebook.add(capacity_tab, text=self.t("容量・増加原因", "Storage / growth causes"))
        notebook.add(pc_tab, text=self.t("PC負荷（任意）", "PC load (optional)"))
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
        advanced = ttk.LabelFrame(duplicate_tab, text=self.t("絞り込み（任意）", "Optional filters"), padding=6)
        advanced.pack(fill="x", pady=4)
        ttk.Label(advanced, text=self.t("除外フォルダ（1件）", "Excluded folder (one)")).grid(
            row=0, column=0, sticky="w")
        ttk.Entry(advanced, textvariable=self.exclusion).grid(row=0, column=1, sticky="ew")
        ttk.Button(advanced, text="...", command=lambda: self.choose(self.exclusion, False)).grid(
            row=0, column=2, padx=4)
        ttk.Label(advanced, text=self.t("拡張子（例: jpg,png）", "Extensions (e.g. jpg,png)")).grid(
            row=1, column=0, sticky="w")
        ttk.Entry(advanced, textvariable=self.extension_filter).grid(row=1, column=1, sticky="ew")
        advanced.columnconfigure(1, weight=1)
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
        ttk.Label(pc_tab, text=self.t(
            "初期状態OFF。CPU・RAM・ディスクと負荷の高いプロセスを2秒間隔でローカル表示します。",
            "OFF by default. Locally sample CPU, RAM, disk and top processes every 2 seconds."),
            wraplength=760).pack(anchor="w", pady=(0, 8))
        pc_actions = ttk.Frame(pc_tab)
        pc_actions.pack(fill="x")
        self.pc_start_button = ttk.Button(pc_actions, text=self.t("監視ON", "Start monitoring"),
                                           command=self.start_pc)
        self.pc_start_button.pack(side="left")
        self.pc_stop_button = ttk.Button(pc_actions, text=self.t("監視OFF", "Stop monitoring"),
                                          command=self.stop_pc, state="disabled")
        self.pc_stop_button.pack(side="left", padx=8)
        ttk.Label(pc_actions, text=self.t("CPU警告しきい値(%)", "CPU alert (%)")).pack(side="left", padx=5)
        ttk.Spinbox(pc_actions, from_=50, to=100, textvariable=self.cpu_threshold, width=4).pack(side="left")
        self.pc_text = tk.StringVar(value=self.t(
            "停止中。GPU/VRAM/CPU温度: 取得不可（未対応）。CPU高負荷だけではAI利用と判定しません。",
            "Stopped. GPU/VRAM/CPU temperature: unavailable. High CPU never proves AI use."))
        ttk.Label(pc_tab, textvariable=self.pc_text, wraplength=750, justify="left").pack(
            anchor="w", pady=(10, 6))
        self.pc_graph = tk.Canvas(pc_tab, height=90, background="#eef2f6", highlightthickness=0)
        self.pc_graph.pack(fill="x", pady=5)
        save_delete = ttk.Frame(pc_tab)
        save_delete.pack(anchor="w", pady=7)
        ttk.Button(save_delete, text=self.t("履歴を保存", "Save local history"),
                   command=self.save_pc_history).pack(side="left")
        ttk.Button(save_delete, text=self.t("保存履歴を削除", "Delete saved history"),
                   command=self.delete_pc_history).pack(side="left", padx=8)
        ttk.Label(pc_tab, text=self.t(
            "既知の実行ファイル名のみAI関連プロセス候補として表示。ChatGPT等のブラウザ利用は検出できません。",
            "Only known process names are AI-related candidates. Browser/cloud AI usage cannot be detected."),
            wraplength=760).pack(anchor="w", pady=4)
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
        excluded = tuple(x.strip() for x in self.exclusion.get().split(";") if x.strip())
        extensions = tuple(x.strip() for x in self.extension_filter.get().split(",") if x.strip())
        self._start("fast", lambda root, reports, cancel: scan(
            root, mode, report_directory=reports, cancel_event=cancel,
            excluded=excluded, extensions=extensions))

    def start_storage(self):
        prior = self.previous.get().strip() or None
        self._start("storage", lambda root, reports, cancel: analyze(
            root, reports, prior, cancel_event=cancel) / "storage_report.json")

    def cancel(self):
        if self.running:
            self.cancel_event.set()
            self.status.set(self.t("中断処理中です…", "Cancelling..."))

    def start_pc(self):
        if self.pc_running:
            return
        self.pc_running = True
        self.pc_start_button.configure(state="disabled")
        self.pc_stop_button.configure(state="normal")
        self.pc_monitor.start()
        self.pc_text.set(self.t("監視中（保存データの外部送信なし）",
                                "Monitoring locally (no uploads)"))

    def stop_pc(self):
        if not self.pc_running:
            return
        self.pc_monitor.stop()
        self.pc_running = False
        self.pc_start_button.configure(state="normal")
        self.pc_stop_button.configure(state="disabled")
        self.pc_text.set(self.t("監視停止。履歴はローカル保存できます。",
                                "Monitoring stopped. You may save history locally."))

    def save_pc_history(self):
        try:
            path = save_history(list(self.pc_monitor.history))
            self.pc_text.set(self.t("保存先: ", "Saved at: ") + str(path))
        except Exception as exc:
            self.pc_text.set(self.t("保存失敗: ", "Save failed: ") + str(exc))

    def delete_pc_history(self):
        if self.pc_running:
            self.pc_text.set(self.t("監視を停止してから履歴を削除してください。",
                                    "Stop monitoring before deleting history."))
            return
        try:
            delete_history()
            self.pc_monitor.history.clear()
            self.pc_graph.delete("all")
            self.pc_text.set(self.t("保存済み・表示中の履歴を削除しました。",
                                    "Saved and displayed history removed."))
        except Exception as exc:
            self.pc_text.set(self.t("削除失敗: ", "Delete failed: ") + str(exc))

    def render_pc(self, data):
        if not self.pc_running:
            return
        cpu = data["cpu_percent"]
        try:
            threshold = max(50, min(100, int(self.cpu_threshold.get())))
        except (ValueError, tk.TclError):
            threshold = 90
        self.high_cpu_seconds = self.high_cpu_seconds + self.pc_monitor.interval if cpu >= threshold else 0
        warning = self.t(" CPU高負荷が継続しています。", " Sustained high CPU observed.") if self.high_cpu_seconds >= 10 else ""
        candidates = data["local_ai_related_process_candidates"]
        ai = (self.t("AI関連プロセスを検出（候補のみ）: ", "AI-related process candidate: ") +
              ", ".join(p["name"] for p in candidates)) if candidates else self.t(
                  "AI関連プロセス: 検出なし（利用していない証明ではありません）",
                  "No known AI process observed (not proof of non-use)")
        top = ", ".join(p["name"] + " " + str(round(p["cpu_percent"], 1)) + "%"
                        for p in data["top_processes"][:3])
        self.pc_text.set(
            f"CPU {cpu:.1f}%  RAM {data['ram_percent']:.1f}%  Disk {data['disk_percent']:.1f}%" +
            warning + "\n" + ai + "\n" +
            self.t("高負荷プロセス: ", "Top processes: ") + top + "\n" +
            self.t("GPU / VRAM / 温度: 取得不可（未測定）", "GPU / VRAM / temperature: unavailable (not measured)"))
        values = [s["cpu_percent"] for s in list(self.pc_monitor.history)[-60:]]
        self.pc_graph.delete("all")
        width = max(300, self.pc_graph.winfo_width())
        height = max(60, self.pc_graph.winfo_height())
        if len(values) >= 2:
            points = []
            for index, value in enumerate(values):
                points.extend((index * (width - 4) / (len(values) - 1) + 2,
                               height - 2 - min(100, max(0, value)) * (height - 4) / 100))
            self.pc_graph.create_line(*points, fill="#305e96", width=2)

    def close_dialog(self):
        self.cancel_event.set()
        self.stop_pc()
        self.destroy()

    def _display(self, text: str):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "pc":
                    self.render_pc(data)
                    continue
                self.running = False
                self.cancel_button.configure(state="disabled")
                self.progress.stop()
                if kind == "done":
                    try:
                        raw = json.loads(Path(data).read_text(encoding="utf-8-sig")) if self.current_kind == "storage" else None
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
                            with Path(data).open("r", encoding="utf-8-sig") as stream:
                                excerpt = stream.read(8000)
                            preview = self.t("Czkawkaの生データ（先頭のみ）:", "Original Czkawka JSON (excerpt):") + "\n" + excerpt
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

"""Windows read-only storage cause GUI with background analysis."""
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from storage_cause_analyzer import analyze
from ui_preferences import load_preferences, save_preferences


class StorageCauseGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ストレージ容量原因分析（削除なし）")
        self.geometry("880x650")
        self.minsize(750, 540)
        self.scan = tk.StringVar()
        self.reports = tk.StringVar(value=str(Path.home() / "Documents"))
        self.baseline = tk.StringVar()
        self.status = tk.StringVar(value="スキャン対象を選択。ファイルを移動・削除することはありません。")
        self.messages = queue.Queue()
        self.busy = False
        try:
            self.reports.set(load_preferences("StorageCauseAnalyzer", ("reports",)).get("reports", self.reports.get()))
        except (OSError, ValueError) as exc:
            self.status.set("保存設定を読み込めませんでした: " + str(exc))
        parent = ttk.Frame(self, padding=18)
        parent.pack(fill="both", expand=True)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(6, weight=1)
        ttk.Label(parent, text="容量不足の原因分析", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))
        self._file(parent, 1, "調査フォルダ", self.scan, "dir")
        self._file(parent, 2, "レポート保存先", self.reports, "dir")
        self._file(parent, 3, "前回のレポート（任意）", self.baseline, "json")
        ttk.Label(parent, text="Python仮想環境、node_modules、ビルド成果物、キャッシュ等を分類。"
                  "ディスク上の実使用容量ではなく論理的なファイルサイズを集計します。",
                  wraplength=820).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 10))
        self.run_button = ttk.Button(parent, text="スキャン開始（読み取りのみ）", command=self.start)
        self.run_button.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self.report = tk.Text(parent, wrap="none", height=20, state="disabled")
        self.report.grid(row=6, column=0, columnspan=3, sticky="nsew")
        ttk.Label(parent, textvariable=self.status, wraplength=830).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(parent, text="設定を保存", command=self.save_user_preferences).grid(row=8, column=0, columnspan=3, sticky="w", pady=5)
        self.after(150, self.poll)

    def save_user_preferences(self) -> None:
        try:
            save_preferences("StorageCauseAnalyzer", {"reports": self.reports.get()}, ("reports",))
            self.status.set("レポート保存先の設定を保存しました。")
        except (OSError, ValueError) as exc:
            self.status.set(f"設定保存失敗: {exc}")
            messagebox.showerror("設定保存失敗", str(exc))

    def _file(self, parent, row, label, var, kind):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=5)
        def choose():
            p = filedialog.askdirectory() if kind == "dir" else filedialog.askopenfilename(
                filetypes=[("JSON", "*.json")])
            if p:
                var.set(p)
        ttk.Button(parent, text="参照", command=choose).grid(row=row, column=2, padx=8)

    def start(self) -> None:
        if self.busy:
            return
        folder = self.scan.get().strip()
        output = self.reports.get().strip()
        if not folder or not output:
            messagebox.showwarning("入力不足", "調査フォルダとレポート保存先を指定してください。")
            return
        self.busy = True
        self.run_button.configure(state="disabled")
        self.status.set("スキャン中。大きなフォルダでは時間がかかります...")
        baseline = self.baseline.get().strip() or None
        def worker():
            try:
                path = analyze(folder, output, baseline)
                data = json.loads((path / "storage_report.json").read_text(encoding="utf-8"))
                self.messages.put((True, path, data))
            except Exception as exc:
                self.messages.put((False, None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self) -> None:
        try:
            while True:
                ok, path, data = self.messages.get_nowait()
                self.busy = False
                self.run_button.configure(state="normal")
                if not ok:
                    self.status.set(f"失敗: {data}")
                    messagebox.showerror("分析失敗", data)
                    continue
                result = [
                    f"状態: {data['status']}",
                    f"対象ファイル: {data['scanned_files']:,}",
                    f"論理サイズ合計: {data['total_logical_bytes'] / (1024**3):.3f} GiB",
                    f"スキップした再解析ポイント: {data['skipped_reparse_entries']}",
                    f"検査エラー: {data['errors_count']}",
                    "",
                    "カテゴリ別容量（GiB）:",
                ]
                result += [f"  {key:<30} {val / (1024**3):.3f}"
                           for key, val in sorted(data["category_bytes"].items(), key=lambda x: -x[1])]
                if "growth_by_category" in data:
                    result += ["", "前回との差分（GiB）:"]
                    result += [f"  {k:<30} {v / (1024**3):+.3f}"
                               for k, v in sorted(data["growth_by_category"].items(), key=lambda x: -x[1])]
                result += ["", "大きなファイル（最大50件）:"]
                result += [f"  {entry['bytes'] / (1024**2):>10.1f} MiB   {entry['path']}"
                           for entry in data["largest_files"]]
                self.report.configure(state="normal")
                self.report.delete("1.0", "end")
                self.report.insert("1.0", "\n".join(result))
                self.report.configure(state="disabled")
                self.status.set(f"レポート: {path / 'storage_report.json'}（削除操作は行っていません）")
        except queue.Empty:
            pass
        self.after(150, self.poll)



def _validation_smoke() -> None:
    """Noninteractive Tk widget construction smoke; not user-click testing."""
    import json
    import sys
    from pathlib import Path
    if len(sys.argv) != 4 or sys.argv[1] != "--smoke-test" or sys.argv[2] != "--smoke-output":
        raise SystemExit(2)
    app = StorageCauseGUI()
    try:
        app.update_idletasks()
        app.update()
        assert app.winfo_exists() and app.title() and len(app.winfo_children()) > 0
        result = {"status": "GUI_PROCESS_SMOKE_OK", "title": app.title(),
                  "scope": "Tk initialization and event pump only; no simulated clicks"}
        with Path(sys.argv[3]).open("x", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False)
    finally:
        app.destroy()


if __name__ == "__main__":
    import sys
    if "--smoke-test" in sys.argv:
        _validation_smoke()
    elif "--e2e-test" in sys.argv:
        from gui_e2e_harness import run
        run(StorageCauseGUI)
    elif "--preferences-ci" in sys.argv:
        from preferences_ci import run
        run(StorageCauseGUI, "StorageCauseAnalyzer", {"reports":"C:\\QA\\容量分析レポート"})
    else:
        StorageCauseGUI().mainloop()

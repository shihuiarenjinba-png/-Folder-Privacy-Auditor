from __future__ import annotations

import locale
import os
import tkinter as tk
from tkinter import filedialog, messagebox

_LANGUAGE = "ja" if any((x or "").lower().startswith("ja") for x in (locale.getlocale()[0], os.environ.get("LANG"))) else "en"
_CONTROLLERS = []
_PATCHED = False

TEXTS = {
    "1  Choose folder": ("1  Choose folder", "1  フォルダを選択"),
    "2  Run audit": ("2  Run audit", "2  監査を実行"),
    "3  Save report (CSV + JSON)": ("3  Save report (CSV + JSON)", "3  レポートを保存 (CSV + JSON)"),
    "① Choose folder  →  ② Run audit  →  ③ Review flagged items  →  ④ Save report": ("① Choose folder  →  ② Run audit  →  ③ Review flagged items  →  ④ Save report", "① フォルダを選択  →  ② 監査を実行  →  ③ 要確認項目を見る  →  ④ レポートを保存"),
    "Folder Privacy Auditor": ("Folder Privacy Auditor", "フォルダプライバシー監査"),
    "Folder Privacy Auditor — Windows": ("Folder Privacy Auditor — Windows", "フォルダプライバシー監査 — Windows"),
    "Choose folder → inspect → export report. Read-only; never deletes anything.": ("Choose folder → inspect → export report. Read-only; never deletes anything.", "フォルダ選択 → 点検 → レポート出力。読み取り専用で削除はしません。"),
    "Run the audit before exporting.": ("Run the audit before exporting.", "先にフォルダの監査を実行してください。"),

    "Audit a folder locally for data-bearing files, PII candidates, hidden files and duplicates.": ("Audit a folder locally for data-bearing files, PII candidates, hidden files and duplicates.", "フォルダをローカル監査し、データファイル・個人情報候補・隠しファイル・重複を確認します。"),
    "Choose folder": ("Choose folder", "フォルダを選択"),
    "Run audit": ("Run audit", "監査を実行"),
    "Export CSV + JSON": ("Export CSV + JSON", "CSV + JSONを出力"),
    "Choose folder to audit": ("Choose folder to audit", "監査するフォルダを選択"),
    "Choose a folder first.": ("Choose a folder first.", "先にフォルダを選択してください。"),
    "Report base name": ("Report base name", "レポートの基本名"),
    "CSV": ("CSV", "CSV"),
}

PHRASES = (
    ("hidden file/path", "隠しファイル/パス"),
    ("Not checked:", "未検査:"),
    ("Auditing locally... this may take time for large folders.", "ローカルで監査中です。大きなフォルダでは時間がかかります。"),
    ("Audit finished. No files were deleted. Review all uninspected areas.", "監査完了。ファイル削除なし。未検査の範囲を確認してください。"),
    ("Choose Run audit to begin. Results will be read-only.", "「監査を実行」で開始します。読み取り専用です。"),
    ("More records in exported CSV/JSON", "残りの記録は出力CSV/JSONで確認できます"),
    ("Audit is still running.", "監査を実行中です。"),
    ("Audit failed; no report created.", "監査失敗。レポートは作成していません。"),

    ("Uninspected", "未検査"), ("UNINSPECTED", "未検査"),
    ("Failed", "失敗"), ("FAILED", "失敗"),
    ("Review", "要確認"), ("REVIEW", "要確認"),
    ("LIMITED", "限定的な検査"),
    ("link/reparse target not inspected", "リンク/再解析ポイントの参照先は未検査"),
    ("format-specific content not inspected", "形式に応じた内容検査は未実施"),
    ("text beyond first 1MB not scanned", "先頭1MBを超えるテキストは未検査"),
    ("privacy not certified; undiscovered personal data may remain", "プライバシー安全性は未保証。未検出の個人情報が残る可能性"),
    ("Limited pattern scan only. Uninspected does NOT mean safe.", "限定的なパターン検査のみ。未検査は安全を意味しません。"),
    ("Report output must be outside the scanned folder.", "レポート出力先は監査対象フォルダの外に指定してください。"),
    ("One or both report filenames already exist; choose another name.", "レポートファイルが既に存在します。別の名前を指定してください。"),

    ("data-bearing file type", "データを含む可能性がある形式"),
    ("hash failed", "ハッシュ失敗"),
    ("hash skipped >50MB", "50MB超のためハッシュ省略"),
    ("email candidate", "メールアドレス候補"),
    ("phone candidate", "電話番号候補"),
    ("long numeric identifier candidate", "長い数値識別子候補"),
    ("content scan failed", "内容スキャン失敗"),
    ("content scan skipped >2MB", "2MB超のため内容スキャン省略"),
    ("manual review required", "手動確認が必要"),
    ("duplicate content", "重複内容"),
    ("Unsupported or undecodable text encoding", "未対応またはデコード不能な文字コード"),
    ("Decoded text contains NUL bytes and appears binary.", "デコード結果にNUL文字が含まれ、バイナリデータの可能性があります。"),
    ("Decoded text contains too many control characters and appears binary.", "制御文字が多すぎるため、バイナリデータの可能性があります。"),
    ("Folder:", "フォルダ:"),
    ("Files:", "ファイル数:"),
    ("flagged:", "要確認:"),
    ("no flag", "フラグなし"),
    ("Saved:", "保存しました:"),
    ("ERROR", "エラー"),
)


def get_language() -> str:
    return _LANGUAGE


def translate(text):
    if not isinstance(text, str): return text
    if text in TEXTS: return TEXTS[text][1 if _LANGUAGE == "ja" else 0]
    if _LANGUAGE == "ja":
        for en, ja in PHRASES: text = text.replace(en, ja)
    return text


def set_language(lang: str):
    global _LANGUAGE
    if lang not in {"en", "ja"}: raise ValueError("language must be 'en' or 'ja'")
    _LANGUAGE = lang
    for c in tuple(_CONTROLLERS): c.refresh()


def _patch():
    global _PATCHED
    if _PATCHED: return
    _PATCHED=True
    oi=tk.Listbox.insert
    tk.Listbox.insert=lambda self,index,*items: oi(self,index,*(translate(x) for x in items))
    for name in ("showinfo","showwarning","showerror"):
        original=getattr(messagebox,name)
        setattr(messagebox,name,lambda title,message,*a,_f=original,**k:_f(translate(title),translate(message),*a,**k))
    for name in ("askopenfilename","askopenfilenames","asksaveasfilename","askdirectory"):
        original=getattr(filedialog,name)
        def wrapper(*a,_f=original,**k):
            if "title" in k: k["title"]=translate(k["title"])
            if "filetypes" in k: k["filetypes"]=[(translate(label),pattern) for label,pattern in k["filetypes"]]
            return _f(*a,**k)
        setattr(filedialog,name,wrapper)


class LanguageController:
    def __init__(self,root):
        self.root=root; self.original_title=root.title(); existing=list(root.winfo_children()); self._snapshot(root)
        f=tk.Frame(root,padx=12,pady=5)
        if existing: f.pack(fill="x", before=existing[0])
        else: f.pack(fill="x")
        tk.Label(f,text="Language / 言語").pack(side="right",padx=(0,8))
        self.button=tk.Button(f,width=10,command=self.toggle); self.button.pack(side="right")
        _CONTROLLERS.append(self); self.refresh()
    def _snapshot(self,w):
        try: w._i18n_original_text=w.cget("text")
        except Exception: pass
        for c in w.winfo_children(): self._snapshot(c)
    def _refresh(self,w):
        if w is not self.button and hasattr(w,"_i18n_original_text"):
            try: w.configure(text=translate(w._i18n_original_text))
            except Exception: pass
        for c in w.winfo_children(): self._refresh(c)
    def refresh(self):
        self.root.title(translate(self.original_title)); self._refresh(self.root); self.button.configure(text="English" if _LANGUAGE=="ja" else "日本語")
    def toggle(self): set_language("en" if _LANGUAGE=="ja" else "ja")


def install_bilingual_ui(root):
    _patch(); return LanguageController(root)

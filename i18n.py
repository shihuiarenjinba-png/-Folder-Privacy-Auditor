from __future__ import annotations

import locale
import os
import tkinter as tk
from tkinter import filedialog, messagebox

_LANGUAGE = "ja" if any((x or "").lower().startswith("ja") for x in (locale.getlocale()[0], os.environ.get("LANG"))) else "en"
_CONTROLLERS = []
_PATCHED = False
TEXTS = {
    "Folder Privacy Auditor": ("Folder Privacy Auditor", "フォルダプライバシー監査"),
    "Audit a folder locally for data-bearing files, PII candidates, hidden files and duplicates.": ("Audit a folder locally for data-bearing files, PII candidates, hidden files and duplicates.", "フォルダをローカル監査し、データファイル・個人情報候補・隠しファイル・重複を確認します。"),
    "Choose folder": ("Choose folder", "フォルダを選択"), "Run audit": ("Run audit", "監査を実行"), "Export CSV + JSON": ("Export CSV + JSON", "CSV + JSONを出力"),
    "Choose folder to audit": ("Choose folder to audit", "監査するフォルダを選択"), "Choose a folder first.": ("Choose a folder first.", "先にフォルダを選択してください。"), "Report base name": ("Report base name", "レポートの基本名"),
}
PHRASES = (("hidden file/path", "隠しファイル/パス"), ("data-bearing file type", "データを含む可能性がある形式"), ("hash failed", "ハッシュ失敗"), ("hash skipped >50MB", "50MB超のためハッシュ省略"), ("email candidate", "メールアドレス候補"), ("phone candidate", "電話番号候補"), ("content scan failed", "内容スキャン失敗"), ("content scan skipped >2MB", "2MB超のため内容スキャン省略"), ("manual review required", "手動確認が必要"), ("duplicate content", "重複内容"), ("Unsupported or undecodable text encoding", "未対応またはデコード不能な文字コード"), ("Folder:", "フォルダ:"), ("Files:", "ファイル数:"), ("flagged:", "要確認:"), ("no flag", "フラグなし"), ("Saved:", "保存しました:"), ("ERROR", "エラー"))

def translate(text):
    if not isinstance(text, str): return text
    if text in TEXTS: return TEXTS[text][1 if _LANGUAGE == "ja" else 0]
    if _LANGUAGE == "ja":
        for en, ja in PHRASES: text=text.replace(en, ja)
    return text

def set_language(lang):
    global _LANGUAGE; _LANGUAGE=lang
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
        self.root=root; self.original_title=root.title(); self._snapshot(root)
        f=tk.Frame(root,padx=12,pady=6); f.pack(fill="x"); self.button=tk.Button(f,width=12,command=self.toggle); self.button.pack(side="right")
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

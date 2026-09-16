from __future__ import annotations
import json, locale, os, tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk
SUPPORTED={"ja","en"}
def _default_language():
    try: current=locale.getlocale()[0] or ""
    except Exception: current=""
    return "ja" if current.lower().startswith("ja") else "en"
def _path(app_id):
    local=os.getenv("LOCALAPPDATA","").strip(); base=Path(local) if local else Path.home()/".local"/"share"
    return base/"PrivateAutomation"/"ui"/f"{app_id}.json"
def _load(app_id):
    override=os.getenv("PRIVATE_AUTOMATION_UI_LANGUAGE","").strip().lower()
    if override in SUPPORTED: return override
    try:
        raw=json.loads(_path(app_id).read_text(encoding="utf-8")); value=str(raw.get("language","")).lower() if isinstance(raw,dict) else ""
        return value if value in SUPPORTED else _default_language()
    except (OSError,json.JSONDecodeError): return _default_language()
def _save(app_id,language):
    if language not in SUPPORTED: raise ValueError("language must be 'ja' or 'en'")
    path=_path(app_id); path.parent.mkdir(parents=True,exist_ok=True); payload=json.dumps({"language":language},ensure_ascii=False,indent=2)+"\n"
    fd,temp_name=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent); temp=Path(temp_name)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as fh: fh.write(payload); fh.flush(); os.fsync(fh.fileno())
        os.replace(temp,path)
    finally: temp.unlink(missing_ok=True)
def apply_language_standard(i18n_module,app_id):
    i18n_module._LANGUAGE=_load(app_id); controllers=getattr(i18n_module,"_CONTROLLERS",None)
    if not isinstance(controllers,list): controllers=[]; i18n_module._CONTROLLERS=controllers
    def set_language(language):
        if language not in SUPPORTED: raise ValueError("language must be 'ja' or 'en'")
        i18n_module._LANGUAGE=language; _save(app_id,language)
        for controller in tuple(controllers): controller.refresh()
    class ExplicitLanguageController:
        def __init__(self,root):
            self.root=root; self.original_title=root.title() if hasattr(root,"title") else ""; self._snapshot(root)
            frame=tk.Frame(root,padx=12,pady=6); frame.pack(fill="x"); tk.Label(frame,text="言語 / Language",font=("Segoe UI",9,"bold")).pack(side="right",padx=(0,6))
            self.value=tk.StringVar(value="日本語" if i18n_module._LANGUAGE=="ja" else "English"); self.combo=ttk.Combobox(frame,textvariable=self.value,values=("日本語","English"),state="readonly",width=10); self.combo.pack(side="right"); self.combo.bind("<<ComboboxSelected>>",self._changed)
            controllers.append(self); self.refresh()
        def _snapshot(self,w):
            try: setattr(w,"_i18n_original_text",w.cget("text"))
            except Exception: pass
            for c in w.winfo_children(): self._snapshot(c)
        def _refresh_widget(self,w):
            original=getattr(w,"_i18n_original_text",None)
            if original is not None:
                try: w.configure(text=i18n_module.translate(original))
                except Exception: pass
            for c in w.winfo_children(): self._refresh_widget(c)
        def refresh(self):
            if hasattr(self.root,"title"): self.root.title(i18n_module.translate(self.original_title))
            self._refresh_widget(self.root); self.value.set("日本語" if i18n_module._LANGUAGE=="ja" else "English")
        def _changed(self,_event=None): set_language("en" if self.value.get()=="English" else "ja")
    i18n_module.LanguageController=ExplicitLanguageController; i18n_module.set_language=set_language; i18n_module.get_language=lambda:i18n_module._LANGUAGE

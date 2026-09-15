import i18n

original = getattr(i18n, "get_language", lambda: getattr(i18n, "_LANGUAGE", "en"))()
try:
    i18n.set_language("ja")
    assert i18n.translate("Choose folder") == "フォルダを選択"
    assert i18n.translate("Run audit") == "監査を実行"
    i18n.set_language("en")
    assert i18n.translate("Choose folder") == "Choose folder"
    assert i18n.translate("Run audit") == "Run audit"
finally:
    i18n.set_language(original)

print("Folder Privacy Auditor bilingual UI smoke test: OK")

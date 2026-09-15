from i18n import get_language, set_language, translate

original = get_language()
try:
    set_language("ja")
    assert translate("Add files") == "ファイルを追加"
    assert translate("Scan") == "スキャン"
    assert translate("Unsupported format: .abc").startswith("未対応形式")
    set_language("en")
    assert translate("Add files") == "Add files"
    assert translate("Scan") == "Scan"
finally:
    set_language(original)

print("Bilingual UI smoke test: OK")

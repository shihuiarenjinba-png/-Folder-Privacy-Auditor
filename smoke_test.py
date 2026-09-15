from pathlib import Path
import tempfile

from windows_app import audit_folder, export_reports

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    a = root / "a.txt"
    b = root / "b.txt"
    a.write_text("contact test@example.com", encoding="utf-8")
    b.write_text("contact test@example.com", encoding="utf-8")
    records = audit_folder(root)
    assert len(records) == 2
    assert any(r["email_candidate"] for r in records)
    assert all(r["duplicate_group"] for r in records)
    csv_path, json_path = export_reports(records, root / "audit")
    assert csv_path.exists() and json_path.exists()
print("Folder Privacy Auditor smoke test: OK")

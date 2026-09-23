from pathlib import Path
import tempfile

from windows_app import audit_folder, export_reports


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)

    a = root / "a.txt"
    b = root / "b.txt"
    a.write_text("contact test@example.com / 090-1234-5678 / 123456789012", encoding="utf-8")
    b.write_text("contact test@example.com / 090-1234-5678 / 123456789012", encoding="utf-8")

    xml = root / "設定.xml"
    xml.write_text("<user>日本語 user@example.jp 987654321012</user>", encoding="utf-8")

    hidden = root / ".hidden.txt"
    hidden.write_text("secret", encoding="utf-8")

    binary = root / "binary.log"
    binary.write_bytes(b"\x00\x00\x01\x02")

    arbitrary = root / "archive.bin"
    arbitrary.write_bytes(b"\x01\x02\x03\x04")

    compact = root / "compact.txt"
    compact.write_text("09012345678 / +819012345678", encoding="utf-8")

    phone_negative = root / "phone-negative.txt"
    phone_negative.write_text(
        "2026-09-23 / 〒901-1234 / JPY 12,345 / ORDER-123456 / "
        "978-4-1234-5678-X / 192.0.2.10 / 090-123-456",
        encoding="utf-8",
    )

    records = audit_folder(root)
    assert len(records) == 8

    duplicates = [r for r in records if r["path"] in {"a.txt", "b.txt"}]
    assert all(r["duplicate_group"] for r in duplicates)
    assert all(r["email_candidate"] for r in duplicates)
    assert all(r["phone_candidate"] for r in duplicates)
    assert all(r["long_id_candidate"] for r in duplicates)

    xml_record = next(r for r in records if r["path"] == "設定.xml")
    assert xml_record["email_candidate"]
    assert xml_record["long_id_candidate"]

    hidden_record = next(r for r in records if r["path"] == ".hidden.txt")
    assert hidden_record["hidden"]

    binary_record = next(r for r in records if r["path"] == "binary.log")
    assert any("manual review required" in note for note in binary_record["notes"])

    arbitrary_record = next(r for r in records if r["path"] == "archive.bin")
    assert arbitrary_record["sha256"]
    assert not arbitrary_record["email_candidate"]

    compact_record = next(r for r in records if r["path"] == "compact.txt")
    assert compact_record["phone_candidate"]

    negative_record = next(r for r in records if r["path"] == "phone-negative.txt")
    assert not negative_record["phone_candidate"], negative_record

    csv_path, json_path = export_reports(records, root / "audit")
    assert csv_path.exists() and json_path.exists()
    csv_text = csv_path.read_text(encoding="utf-8-sig")
    assert "long_id_candidate" in csv_text
    assert "設定.xml" in csv_text

print("Folder Privacy Auditor smoke test: OK")

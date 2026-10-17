"""Read-only file inventory: report omissions rather than silently assuming safety."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from windows_app import audit_folder, export_reports, summarize_audit


class ReadOnlyCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "audit_root"
        self.root.mkdir()

    def test_file_unchanged_and_coverage_explicit(self):
        candidate = self.root / "顧客.csv"
        candidate.write_text("contact,phone\nuser@example.com,090-1234-5678\n", encoding="utf-8")
        original = candidate.read_bytes()
        binary = self.root / "archive.bin"
        binary.write_bytes(b"\x01\x02\x03")
        records = audit_folder(self.root)
        self.assertEqual(len(records), 2)
        self.assertEqual(candidate.read_bytes(), original)
        rec = next(r for r in records if r["path"] == "顧客.csv")
        self.assertEqual(rec["status"], "REVIEW")
        self.assertTrue(rec["email_candidate"])
        self.assertTrue(rec["phone_candidate"])
        self.assertTrue(rec["sha256"])
        self.assertTrue(rec["unchecked"])
        unknown = next(r for r in records if r["path"] == "archive.bin")
        self.assertEqual(unknown["status"], "UNINSPECTED")
        self.assertTrue(any("format-specific" in item for item in unknown["unchecked"]))
        self.assertEqual(summarize_audit(records)["files"], 2)

    def test_text_after_first_megabyte_explicitly_uninspected(self):
        src = self.root / "large.txt"
        src.write_bytes(b"a" * 1_000_100 + b" confidential@example.com")
        rec = next(r for r in audit_folder(self.root) if r["path"] == "large.txt")
        self.assertFalse(rec["email_candidate"])
        self.assertTrue(any("beyond first 1MB" in item for item in rec["unchecked"]))

    def test_symbolic_link_is_not_followed(self):
        private = self.base / "outside-secret.txt"
        private.write_text("hidden@example.org", encoding="utf-8")
        link = self.root / "link.txt"
        try:
            link.symlink_to(private)
        except (OSError, NotImplementedError):
            self.skipTest("This Windows runner does not allow creating a symlink")
        records = audit_folder(self.root)
        link_rec = next(r for r in records if r["path"] == "link.txt")
        self.assertEqual(link_rec["status"], "UNINSPECTED")
        self.assertEqual(link_rec["sha256"], "")
        self.assertFalse(link_rec["email_candidate"])
        self.assertIn("reparse", " ".join(link_rec["unchecked"]))
        self.assertEqual(private.read_text(encoding="utf-8"), "hidden@example.org")

    def test_report_schema_and_non_overwrite(self):
        (self.root / "a.txt").write_text("Hello", encoding="utf-8")
        records = audit_folder(self.root)
        reports = self.base / "reports"
        reports.mkdir()
        out = reports / "audit"
        csv_path, json_path = export_reports(records, out, scanned_root=self.root)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["summary"]["files"], 1)
        self.assertIn("unchecked", data["records"][0])
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            self.assertIn("status", next(csv.DictReader(handle)))
        old_csv = csv_path.read_bytes()
        old_json = json_path.read_bytes()
        with self.assertRaises(FileExistsError):
            export_reports(records, out, scanned_root=self.root)
        self.assertEqual(csv_path.read_bytes(), old_csv)
        self.assertEqual(json_path.read_bytes(), old_json)

    def test_export_into_scanned_folder_is_rejected(self):
        (self.root / "file.txt").write_text("hello", encoding="utf-8")
        records = audit_folder(self.root)
        with self.assertRaises(ValueError):
            export_reports(records, self.root / "report", scanned_root=self.root)
        self.assertFalse((self.root / "report.csv").exists())


if __name__ == "__main__":
    unittest.main()

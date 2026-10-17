"""Read-only automatic prior-snapshot comparison regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from storage_cause_analyzer import analyze
from storage_history import find_previous_snapshot


class StorageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.reports = self.base / "reports"
        self.source.mkdir()
        self.reports.mkdir()

    def _read(self, folder):
        return json.loads((folder / "storage_report.json").read_text(encoding="utf-8"))

    def test_first_then_second_scan_auto_compares_without_changing_source(self):
        target = self.source / "example.dat"
        target.write_bytes(b"A" * 100)
        first = analyze(self.source, self.reports, auto_history=True)
        first_data = self._read(first)
        self.assertEqual(first_data["comparison_status"], "NOT_COMPARED")
        self.assertNotIn("growth_total_logical_bytes", first_data)
        self.assertEqual(target.read_bytes(), b"A" * 100)

        target.write_bytes(b"B" * 150)
        second = analyze(self.source, self.reports, auto_history=True)
        second_data = self._read(second)
        self.assertEqual(second_data["comparison_status"], "COMPARED")
        self.assertEqual(second_data["comparison_source"], "automatic_previous")
        self.assertEqual(second_data["growth_total_logical_bytes"], 50)
        self.assertEqual(second_data["baseline_report"], str(first / "storage_report.json"))
        self.assertEqual(target.read_bytes(), b"B" * 150)
        self.assertTrue((first / "storage_report.json").is_file())

    def test_different_root_and_corrupt_history_are_ignored(self):
        other = self.base / "different"
        other.mkdir()
        (other / "different.txt").write_text("123", encoding="utf-8")
        analyze(other, self.reports)
        garbage = self.reports / "storage_cause_garbage"
        garbage.mkdir()
        (garbage / "storage_report.json").write_text("{not-json", encoding="utf-8")
        self.assertIsNone(find_previous_snapshot(self.reports, self.source))
        result = self._read(analyze(self.source, self.reports, auto_history=True))
        self.assertEqual(result["comparison_status"], "NOT_COMPARED")

    def test_explicit_previous_snapshot_has_priority(self):
        target = self.source / "a.bin"
        target.write_bytes(b"z" * 3)
        first = analyze(self.source, self.reports)
        target.write_bytes(b"y" * 6)
        analyze(self.source, self.reports)
        target.write_bytes(b"x" * 10)
        latest = self._read(analyze(self.source, self.reports,
                                    first / "storage_report.json", auto_history=True))
        self.assertEqual(latest["comparison_source"], "selected_baseline")
        self.assertEqual(latest["growth_total_logical_bytes"], 7)

    def test_partial_scan_warning_is_kept(self):
        (self.source / "data.bin").write_bytes(b"z")
        first = analyze(self.source, self.reports)
        baseline_path = first / "storage_report.json"
        data = self._read(first)
        data["status"] = "PARTIAL"
        baseline_path.write_text(json.dumps(data), encoding="utf-8")
        result = self._read(analyze(self.source, self.reports, auto_history=True))
        self.assertEqual(result["comparison_status"], "COMPARED")
        self.assertIn("growth_warning", result)

    def test_symlink_snapshot_is_not_followed(self):
        external = self.base / "external"
        external.mkdir()
        (self.source / "test.txt").write_text("test", encoding="utf-8")
        real = analyze(self.source, external)
        shortcut = self.reports / "storage_cause_link"
        try:
            shortcut.symlink_to(real, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating directory links is not allowed on this Windows account")
        self.assertIsNone(find_previous_snapshot(self.reports, self.source))


if __name__ == "__main__":
    unittest.main()

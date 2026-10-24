"""Synthetic storage inventory regression tests (no real disks scanned)."""
import json
import tempfile
import unittest
from pathlib import Path

from storage_cause_analyzer import analyze, classify


class StorageCauseTest(unittest.TestCase):
    def test_developer_categories_and_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tree = base / "source"
            (tree / "project" / "node_modules").mkdir(parents=True)
            (tree / "python_project" / ".venv").mkdir(parents=True)
            (tree / "project" / "node_modules" / "bundle.js").write_bytes(b"x" * 200)
            (tree / "python_project" / ".venv" / "lib.bin").write_bytes(b"a" * 120)
            old = analyze(tree, base / "reports")
            snapshot = json.loads((old / "storage_report.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot["total_logical_bytes"], 320)
            self.assertEqual(snapshot["category_bytes"]["node_dependencies"], 200)
            self.assertEqual(snapshot["category_bytes"]["python_environment"], 120)
            (tree / "project" / "node_modules" / "bundle.js").write_bytes(b"x" * 300)
            newer = analyze(tree, base / "reports", old / "storage_report.json")
            report = json.loads((newer / "storage_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["growth_total_logical_bytes"], 100)
            self.assertEqual(report["growth_by_category"]["node_dependencies"], 100)
            self.assertTrue((tree / "python_project" / ".venv" / "lib.bin").exists())

    def test_no_reports_inside_scanned_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "src").mkdir()
            with self.assertRaises(ValueError):
                analyze(base / "src", base / "src" / "reports")

    def test_wrong_baseline_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a, b = base / "a", base / "b"
            a.mkdir()
            b.mkdir()
            old = analyze(a, base / "out")
            with self.assertRaises(ValueError):
                analyze(b, base / "out", old / "storage_report.json")

    def test_category_names_are_heuristics(self):
        self.assertEqual(classify(("a", ".venv", "lib", "package.py")), "python_environment")
        self.assertEqual(classify(("a", "obj", "bin.dat")), "build_outputs")
        self.assertEqual(classify(("a", "report.pdf")), "other")


if __name__ == "__main__":
    unittest.main()

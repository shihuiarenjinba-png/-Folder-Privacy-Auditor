import json
import tempfile
import unittest
from pathlib import Path

from ui_preferences import load_preferences, save_preferences, preference_path


class PreferencesTests(unittest.TestCase):
    def test_roundtrip_japanese_and_versioned_format(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            values = {"reports": "C:\\QA\\日本語プロジェクト\\001"}
            target = save_preferences("StorageCauseAnalyzer", values, ("reports",), override_dir=root)
            self.assertEqual(target, root / "preferences.json")
            self.assertEqual(load_preferences("StorageCauseAnalyzer", ("reports",), override_dir=root), values)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_unknown_field_rejected_without_mutating_saved_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = save_preferences("StorageCauseAnalyzer", {"reports": "C:\\a"}, ("reports",), override_dir=root)
            previous = target.read_bytes()
            with self.assertRaises(ValueError):
                save_preferences("StorageCauseAnalyzer", {"password": "secret"}, ("reports",), override_dir=root)
            self.assertEqual(target.read_bytes(), previous)

    def test_corruption_and_newer_schema_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = preference_path("StorageCauseAnalyzer", override_dir=root)
            target.write_text("{not-valid", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_preferences("StorageCauseAnalyzer", {"reports": "C:\\a"}, ("reports",), override_dir=root)
            self.assertEqual(target.read_text(encoding="utf-8"), "{not-valid")
            target.write_text('{"schema_version":2,"values":{"reports":"new"}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                save_preferences("StorageCauseAnalyzer", {"reports": "C:\\a"}, ("reports",), override_dir=root)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["schema_version"], 2)

    def test_data_limit_and_invalid_product(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                save_preferences("StorageCauseAnalyzer", {"reports": "a" * 5000}, ("reports",), override_dir=Path(folder))
            with self.assertRaises(ValueError):
                preference_path("../other", override_dir=Path(folder))


if __name__ == "__main__":
    unittest.main()

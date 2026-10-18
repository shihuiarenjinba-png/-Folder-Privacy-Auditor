import csv
import json
import tempfile
import unittest
from pathlib import Path
from windows_app import _record, _safe_csv_report_cell, export_reports


class AuditorCsvSafetyTests(unittest.TestCase):
    def test_formula_prefix_escaped(self):
        self.assertEqual(_safe_csv_report_cell('=HYPERLINK("x")'), "'=HYPERLINK(\"x\")")
        self.assertEqual(_safe_csv_report_cell(' \t+CMD'), "' \t+CMD")
        self.assertEqual(_safe_csv_report_cell('ordinary.txt'), 'ordinary.txt')
    def test_filename_escaped_only_in_csv_and_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = '=HYPERLINK("https://bad.example")'
            csv_path, json_path = export_reports([_record(original, note="not fully inspected")], folder/'report')
            with csv_path.open(encoding='utf-8-sig', newline='') as stream:
                entry = next(csv.DictReader(stream))
            self.assertTrue(entry['path'].startswith("'="))
            raw = json.loads(json_path.read_text(encoding='utf-8'))
            self.assertEqual(raw['records'][0]['path'], original)
            self.assertEqual(raw['csv_escaped_formula_cells'], 1)
    def test_existing_reports_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'report'
            export_reports([_record('good.txt', note='not inspected')], target)
            with self.assertRaises(FileExistsError):
                export_reports([_record('new.txt', note='not inspected')], target)


if __name__=='__main__':
    unittest.main()

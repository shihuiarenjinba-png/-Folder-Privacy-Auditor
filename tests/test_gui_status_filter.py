"""Filtering the UI must never truncate stored audit evidence."""
import unittest
from windows_app import filter_audit_records, summarize_audit


def finding(status):
    return {
        "path": "/example/file", "extension": ".txt", "bytes": 3, "hidden": False,
        "risky_data_type": False, "email_candidate": False,
        "phone_candidate": False, "long_id_candidate": False,
        "duplicate_group": "", "sha256": "",
        "status": status,
        "checked": ["file name, size and hidden/path indicators"],
        "unchecked": ["contents not scanned"], "notes": []}


class StatusFilterTests(unittest.TestCase):
    def test_filtered_results_and_original_records(self):
        data = [finding("LIMITED"), finding("REVIEW"),
                finding("UNINSPECTED"), finding("FAILED")]
        original = [dict(row) for row in data]
        self.assertEqual(filter_audit_records(data, "ALL"), data)
        self.assertEqual(len(filter_audit_records(data, "REVIEW")), 1)
        self.assertEqual(len(filter_audit_records(data, "UNINSPECTED")), 1)
        self.assertEqual(len(filter_audit_records(data, "FAILED")), 1)
        self.assertEqual(data, original)
        self.assertEqual(summarize_audit(data)["failed"], 1)

    def test_unknown_filter_is_an_error(self):
        with self.assertRaises(ValueError):
            filter_audit_records([finding("REVIEW")], "SILENTLY_HIDE")


if __name__ == "__main__":
    unittest.main()

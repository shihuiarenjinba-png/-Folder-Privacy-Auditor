"""Static contract for the Store MSIX builder.

This does not claim a Windows build passed. It protects the fail-closed packaging
rules so later edits cannot silently restore guessed versions or remove source/
manifest evidence.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "store/build-msix.ps1").read_text(encoding="utf-8")

class StoreMsixBuilderContractTests(unittest.TestCase):
    def test_source_gate_is_fail_closed(self):
        for token in ("get-url", "fetch", "origin", "rev-parse", "--porcelain"):
            self.assertIn(token, SCRIPT)

    def test_source_commit_is_embedded(self):
        self.assertIn("SOURCE_GIT_COMMIT.txt", SCRIPT)

    def test_manifest_contract_is_checked(self):
        for token in ("ProcessorArchitecture", "PublisherDisplayName", "VisualElements"):
            self.assertIn(token, SCRIPT)

    def test_no_implicit_store_version_default(self):
        self.assertNotIn("$Version = '1.0.0.0'", SCRIPT)
        self.assertNotIn('$Version = "1.0.0.0"', SCRIPT)

if __name__ == "__main__":
    unittest.main()

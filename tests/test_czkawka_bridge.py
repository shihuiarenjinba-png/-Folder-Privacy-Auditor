"""Safety regression tests for read-only Czkawka Core / CLI adapter."""
import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from czkawka_bridge import (SCAN_MODES, ScanCancelled, build_command, scan,
                            verify_cli)


class CzkawkaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "対象-日本語"
        self.root.mkdir()
        (self.root / "exclude").mkdir()
        self.report = self.base / "reports"

    def test_no_delete_or_repair_in_any_mode(self):
        for mode, command in SCAN_MODES.items():
            with self.subTest(mode=mode):
                argv = build_command("czkawka_cli.exe", mode, self.root,
                                     self.report / "result.json")
                self.assertEqual(argv[1], command)
                self.assertNotIn("-D", argv)
                self.assertNotIn("-y", argv)
                self.assertNotIn("-F", argv)
                self.assertNotIn("-o", argv)
                self.assertIn("-W", argv)
                self.assertIn("-H", argv)
                self.assertIn("-p", argv)

    def test_hash_mode_and_filters(self):
        argv = build_command("exe", "duplicates", self.root,
                             self.report / "test.json", excluded=(self.root / "exclude",),
                             extensions=(".png",))
        self.assertEqual(argv[argv.index("-s") + 1], "HASH")
        self.assertEqual(argv[argv.index("-t") + 1], "BLAKE3")
        self.assertEqual(argv[argv.index("-m") + 1], "1")
        self.assertIn(str((self.root / "exclude").resolve()), argv)
        self.assertIn("png", argv)

    def test_reject_unsafe_choices(self):
        with self.assertRaises(ValueError):
            build_command("exe", "delete", self.root, self.report / "out.json")
        with self.assertRaises(ValueError):
            build_command("exe", "duplicates", self.root, self.root / "out.json")
        with self.assertRaises(ValueError):
            build_command("exe", "duplicates", self.root, self.report / "out.json",
                          excluded=(self.base,))
        with self.assertRaises(ValueError):
            build_command("exe", "duplicates", self.root, self.report / "out.json",
                          extensions=(".exe --delete",))

    def test_reparse_root_rejected(self):
        link = self.base / "link"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks is not supported")
        with self.assertRaises(ValueError):
            build_command("exe", "duplicates", link, self.report / "out.json")

    def test_binary_sha_mismatch_rejected(self):
        bad = self.base / "czkawka_cli.exe"
        bad.write_bytes(b"untrusted")
        with self.assertRaises(ValueError):
            verify_cli(bad)

    def test_cancelled_before_start_creates_no_json(self):
        event = Event()
        event.set()
        with patch("czkawka_bridge.verify_cli", return_value=Path("safe-cli.exe")):
            with self.assertRaises(ScanCancelled):
                scan(self.root, report_directory=self.report, cancel_event=event)
        self.assertEqual(list(self.report.rglob("*.json")), [])

    def test_success_preserves_upstream_json(self):
        record = {"upstream": {"groups": [["同じ内容A", "same-content-B"]]}}
        class CompletedProcess:
            returncode = 11
            def poll(self):
                return 11
        def factory(argv, **_):
            Path(argv[argv.index("-p") + 1]).write_text(
                json.dumps(record, ensure_ascii=False), encoding="utf-8")
            return CompletedProcess()
        with patch("czkawka_bridge.verify_cli", return_value=Path("verified.exe")):
            with patch("czkawka_bridge.subprocess.Popen", side_effect=factory):
                path = scan(self.root, report_directory=self.report)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), record)

    def test_corrupt_json_is_not_kept(self):
        class CompletedProcess:
            returncode = 0
            def poll(self):
                return 0
        def factory(argv, **_):
            Path(argv[argv.index("-p") + 1]).write_text("not-json", encoding="utf-8")
            return CompletedProcess()
        with patch("czkawka_bridge.verify_cli", return_value=Path("verified.exe")):
            with patch("czkawka_bridge.subprocess.Popen", side_effect=factory):
                with self.assertRaises(json.JSONDecodeError):
                    scan(self.root, report_directory=self.report)
        self.assertEqual(list(self.report.rglob("*.json")), [])


if __name__ == "__main__":
    unittest.main()

"""Opt-in PC load monitor must never infer AI merely from resource load."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pc_load import LocalMonitor, delete_history, sample, save_history


class MonitorSafetyTests(unittest.TestCase):
    def test_starts_off_and_stops_cleanly(self):
        monitor = LocalMonitor(Path.cwd(), interval=1)
        self.assertIsNone(monitor.worker)
        with patch("pc_load.sample", return_value={"cpu_percent": 1.0}):
            monitor.start()
            monitor.stop()
        self.assertTrue(monitor.stop_event.is_set())
        self.assertFalse(monitor.worker.is_alive())

    def test_game_load_is_not_ai_detection(self):
        proc = SimpleNamespace(
            info={"name": "game.exe", "pid": 42,
                  "memory_info": SimpleNamespace(rss=12345)},
            cpu_percent=lambda interval=None: 99.0)
        mock_psutil = Mock()
        mock_psutil.cpu_percent.return_value = 99.0
        mock_psutil.virtual_memory.return_value = SimpleNamespace(
            percent=70.0, used=1000, total=2000)
        mock_psutil.disk_usage.return_value = SimpleNamespace(percent=50.0)
        mock_psutil.process_iter.return_value = [proc]
        with patch("pc_load.psutil", mock_psutil):
            snapshot = sample(Path.cwd())
        self.assertEqual(snapshot["local_ai_detection"], "NOT_OBSERVED")
        self.assertIsNone(snapshot["gpu_percent"])
        self.assertEqual(snapshot["gpu_status"], "UNAVAILABLE")
        self.assertEqual(snapshot["top_processes"][0]["name"], "game.exe")

    def test_known_local_ai_is_only_candidate(self):
        proc = SimpleNamespace(
            info={"name": "ollama.exe", "pid": 8,
                  "memory_info": SimpleNamespace(rss=123)},
            cpu_percent=lambda interval=None: 0.0)
        mock_psutil = Mock()
        mock_psutil.cpu_percent.return_value = 0.0
        mock_psutil.virtual_memory.return_value = SimpleNamespace(
            percent=30.0, used=300, total=1000)
        mock_psutil.disk_usage.return_value = SimpleNamespace(percent=11.0)
        mock_psutil.process_iter.return_value = [proc]
        with patch("pc_load.psutil", mock_psutil):
            snapshot = sample(Path.cwd())
        self.assertEqual(snapshot["local_ai_detection"], "PROCESS_NAME_CANDIDATES")
        self.assertEqual(snapshot["local_ai_related_process_candidates"][0]["name"], "ollama.exe")

    def test_history_is_local_and_deletable(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "history.json"
            save_history([{"cpu_percent": 12}], destination=dest)
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))["samples"][0]["cpu_percent"], 12)
            self.assertTrue(delete_history(destination=dest))
            self.assertFalse(dest.exists())
            self.assertFalse(delete_history(destination=dest))

    def test_invalid_interval(self):
        for n in (0, 0.5, 31):
            with self.assertRaises(ValueError):
                LocalMonitor(Path.cwd(), interval=n)


if __name__ == "__main__":
    unittest.main()

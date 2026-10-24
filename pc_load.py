"""Opt-in local PC load sampler. No network, prompts, chats, or file contents.
CPU/RAM/process information comes from psutil (BSD-3-Clause).
GPU and temperature remain unavailable until a tested sensor backend is added.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread

try:
    import psutil
except ImportError:
    psutil = None

AI_PROCESSES = frozenset({
    "ollama.exe", "ollama", "lm studio.exe", "lmstudio.exe", "lm studio",
    "llama-server.exe", "llama-cli.exe", "llama-server", "llama-cli",
})
MAX_HISTORY = 900


def sample(path: str | Path) -> dict:
    """Single on-demand snapshot. Process names are indicators, not proof of AI usage."""
    if psutil is None:
        raise RuntimeError("PC load optional dependency psutil is unavailable")
    cpu = float(psutil.cpu_percent(interval=None))
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(path))
    rows = []
    detected = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = proc.info
            name = str(info.get("name") or "")
            if not name:
                continue
            cpu_process = float(proc.cpu_percent(interval=None))
            rss = info.get("memory_info")
            row = {"pid": int(info["pid"]), "name": name,
                   "cpu_percent": cpu_process,
                   "memory_bytes": int(rss.rss) if rss is not None else None}
            rows.append(row)
            if name.casefold() in AI_PROCESSES:
                detected.append({"pid": row["pid"], "name": name})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess,
                PermissionError, OSError):
            continue
    rows.sort(key=lambda p: (p["cpu_percent"], p["memory_bytes"] or 0), reverse=True)
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": cpu, "ram_percent": float(mem.percent),
        "ram_used_bytes": int(mem.used), "ram_total_bytes": int(mem.total),
        "disk_percent": float(disk.percent),
        "top_processes": rows[:8],
        "local_ai_related_process_candidates": detected,
        "local_ai_detection": "PROCESS_NAME_CANDIDATES" if detected else "NOT_OBSERVED",
        "gpu_percent": None, "vram_used_bytes": None, "cpu_temp_c": None,
        "gpu_status": "UNAVAILABLE", "temperature_status": "UNAVAILABLE",
        "limitations": (
            "Process names can be renamed/spoofed; candidate does not prove an active AI workload. "
            "Cloud AI browser usage cannot be inferred from resource load. "
            "GPU usage, VRAM and CPU temperature have not been measured."
        ),
    }


def history_path() -> Path:
    """Local only: no history is collected until monitoring is explicitly started."""
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return root / "FolderPrivacyAuditor" / "pc_load_history.json"


def save_history(data: list[dict], *, destination: Path | None = None) -> Path:
    """Atomically save limited resource-only snapshots, no file or chat content."""
    target = destination or history_path()
    if target.exists() and target.is_symlink():
        raise ValueError("Refusing to overwrite a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pc-load-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"schema": 1, "samples": data[-MAX_HISTORY:]}, f,
                      ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return target


def delete_history(*, destination: Path | None = None) -> bool:
    target = destination or history_path()
    if target.is_symlink():
        raise ValueError("Refusing to follow history symlink")
    if target.exists():
        target.unlink()
        return True
    return False


class LocalMonitor:
    """Starts OFF, samples every 2 seconds when explicitly enabled."""
    def __init__(self, disk: str | Path, interval: float = 2):
        if not 1 <= interval <= 30:
            raise ValueError("Interval must be 1-30 seconds")
        self.disk = Path(disk)
        self.interval = interval
        self.stop_event = Event()
        self.worker: Thread | None = None
        self.history: deque[dict] = deque(maxlen=MAX_HISTORY)
        self.errors: deque[str] = deque(maxlen=12)
        self.on_sample = None

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.stop_event.clear()
        def run():
            while not self.stop_event.is_set():
                try:
                    result = sample(self.disk)
                    self.history.append(result)
                    if self.on_sample is not None:
                        self.on_sample(result)
                except (OSError, ValueError, RuntimeError) as exc:
                    self.errors.append(type(exc).__name__ + ": " + str(exc))
                if self.stop_event.wait(self.interval):
                    break
        self.worker = Thread(target=run, daemon=True, name="fpa-local-pc-sampler")
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=3)

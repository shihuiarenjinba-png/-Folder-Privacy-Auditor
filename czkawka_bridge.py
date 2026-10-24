"""Safe, read-only Czkawka CLI bridge. CLI uses MIT-licensed czkawka_core.
Czkawka CLI 12.0.2 Windows asset pinned by upstream release SHA-256.
No delete/repair flags and no user-provided command strings are accepted.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from threading import Event

UPSTREAM_VERSION = "12.0.2"
UPSTREAM_SHA256 = "eb7c2009d2dd49cf5202acbd65370caece0a3f819b9515e727cedb1ec088ed1a"
SCAN_MODES = {
    "duplicates": "dup", "similar_images": "image",
    "large_files": "big", "empty_folders": "empty-folders",
    "empty_files": "empty-files", "temporary_files": "temp",
    "bad_extensions": "ext", "broken_files": "broken",
}


class ScanCancelled(Exception):
    pass


def _reparse(p: Path) -> bool:
    try:
        return p.is_symlink() or bool(getattr(p.lstat(), "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def _root(directory: str | Path) -> Path:
    p = Path(directory).expanduser()
    if _reparse(p):
        raise ValueError("Symlink/reparse scan roots are not supported")
    root = p.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Choose a directory")
    return root


def bundled_cli() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "czkawka_cli.exe"


def verify_cli(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if _reparse(candidate):
        raise ValueError("Unsafe Czkawka executable path")
    p = candidate.resolve(strict=True)
    if not p.is_file():
        raise ValueError("Missing Czkawka executable")
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest().lower() != UPSTREAM_SHA256:
        raise ValueError("Czkawka binary SHA-256 mismatch")
    return p


def build_command(binary: str | Path, mode: str, root: str | Path, output: str | Path,
                  *, excluded: tuple[str | Path, ...] = (),
                  extensions: tuple[str, ...] = ()) -> list[str]:
    if mode not in SCAN_MODES:
        raise ValueError("Unsupported scan mode")
    target = _root(root)
    dest = Path(output).resolve()
    if dest.is_relative_to(target):
        raise ValueError("Reports must be outside scan root")
    argv = [str(binary), SCAN_MODES[mode], "-d", str(target), "-p", str(dest),
            "-W", "-N", "-M", "-H", "-T", "2"]
    if mode == "duplicates":
        argv.extend(["-s", "HASH", "-t", "BLAKE3", "-m", "1"])
    for entry in excluded:
        p = _root(entry)
        if p == target or not p.is_relative_to(target):
            raise ValueError("Exclude directory must be within the scan folder")
        argv.extend(["-e", str(p)])
    for extension in extensions:
        clean = extension.lstrip(".")
        if not (clean.isalnum() and len(clean) <= 16):
            raise ValueError("Invalid extension filter")
        argv.extend(["-x", clean])
    return argv


def scan(root: str | Path, mode: str = "duplicates", *,
         report_directory: str | Path, cli_path: str | Path | None = None,
         excluded: tuple[str | Path, ...] = (),
         extensions: tuple[str, ...] = (),
         cancel_event: Event | None = None,
         timeout_seconds: float = 900) -> Path:
    """Run Czkawka read-only, saving official JSON. Returns its new JSON path."""
    target = _root(root)
    reports = Path(report_directory).expanduser().resolve()
    if reports == target or reports.is_relative_to(target):
        raise ValueError("Reports must be outside scan root")
    if reports.exists() and _reparse(reports):
        raise ValueError("Unsafe report location")
    if timeout_seconds <= 0:
        raise ValueError("Invalid timeout")
    binary = verify_cli(cli_path if cli_path is not None else bundled_cli())
    reports.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="czkawka_", dir=reports))
    dest = work / (mode + ".json")
    proc = None
    try:
        argv = build_command(binary, mode, target, dest,
                             excluded=excluded, extensions=extensions)
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled("Cancelled")
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                shell=False)
        start = time.monotonic()
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                raise ScanCancelled("Cancelled")
            if time.monotonic() - start > timeout_seconds:
                raise TimeoutError("Scan timed out")
            time.sleep(0.2)
        if proc.returncode not in (0, 11):
            raise RuntimeError("Czkawka failed with exit code " + str(proc.returncode))
        if not dest.is_file() or dest.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("Czkawka JSON report missing or oversized")
        with dest.open(encoding="utf-8-sig") as stream:
            json.load(stream)  # schema belongs to upstream; do not invent statistics
        return dest
    except BaseException:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        if dest.exists():
            dest.unlink()
        try:
            work.rmdir()
        except OSError:
            pass
        raise

"""Bounded, read-only discovery of previous local storage snapshots.

Only well-formed reports for exactly the same resolved scan root qualify.
Never visit symlink/reparse report directories or files.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

MAX_REPORTS_TO_CHECK = 2000
MAX_REPORT_BYTES = 1_000_000


def find_previous_snapshot(reports_dir: str | Path, resolved_root: str | Path,
                           *, format_version: str,
                           is_reparse: Callable[[Path], bool]) -> Path | None:
    reports = Path(reports_dir)
    root = str(Path(resolved_root).resolve(strict=True))
    if is_reparse(reports) or not reports.is_dir():
        return None
    matching: list[tuple[int, str, Path]] = []
    try:
        with os.scandir(reports) as it:
            for index, entry in enumerate(it):
                if index >= MAX_REPORTS_TO_CHECK:
                    break
                if not entry.name.startswith("storage_cause_"):
                    continue
                folder = Path(entry.path)
                if is_reparse(folder) or not entry.is_dir(follow_symlinks=False):
                    continue
                report = folder / "storage_report.json"
                if is_reparse(report) or not report.is_file():
                    continue
                try:
                    info = report.stat()
                    if not (0 < info.st_size <= MAX_REPORT_BYTES):
                        continue
                    data = json.loads(report.read_text(encoding="utf-8"))
                    size = data.get("total_logical_bytes")
                    if (data.get("format") != format_version or data.get("root") != root
                            or type(size) is not int or size < 0
                            or not isinstance(data.get("category_bytes"), dict)
                            or data.get("status") not in {"PARTIAL", "COMPLETE_FOR_REGULAR_FILES"}):
                        continue
                    matching.append((info.st_mtime_ns, entry.name, report))
                except (OSError, ValueError, UnicodeError, TypeError):
                    continue
    except OSError:
        return None
    if not matching:
        return None
    matching.sort(reverse=True)
    return matching[0][2]

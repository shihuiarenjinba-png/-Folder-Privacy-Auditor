"""Read-only disk usage cause analyzer; additive to Folder Privacy Auditor.

No cleanup/deletion. Inventory is based on metadata (logical bytes) rather than
physical allocation, compression, cloud placeholders or NTFS hardlink identity.
Does not follow symlinks/junctions. Skips inaccessible entries and reports them.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

MAX_FILES = 300000
MAX_TOP = 50
VERSION = "storage_cause_snapshot_v1"


def reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    # Windows junctions and other reparse points (Python 3.11 compatible).
    try:
        st = path.lstat()
        return bool(getattr(st, "st_file_attributes", 0) & 0x400)
    except OSError:
        return True


def classify(parts: tuple[str, ...]) -> str:
    segs = [x.casefold() for x in parts]
    if any(x in {".venv", "venv", "virtualenvs", "__pypackages__"} for x in segs):
        return "python_environment"
    if "node_modules" in segs:
        return "node_dependencies"
    if any(x in {".git", ".svn"} for x in segs):
        return "version_control"
    if any(x in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for x in segs):
        return "python_cache"
    if any(x in {"dist", "build", "target", "bin", "obj", ".next", ".nuxt"} for x in segs):
        return "build_outputs"
    if any(x in {"cache", "caches", ".cache", "tmp", "temp"} for x in segs):
        return "caches_or_temporary"
    if any(x in {"downloads", "download"} for x in segs):
        return "downloads"
    return "other"


def analyze(root_dir: str | Path, reports_dir: str | Path,
            baseline_file: str | Path | None = None, *, auto_history: bool = False) -> Path:
    requested = Path(root_dir).expanduser()
    if reparse(requested):
        raise ValueError("Root symlink/reparse location not supported")
    root = requested.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Source must be a directory")
    reports = Path(reports_dir).expanduser().resolve()
    if reports == root or reports.is_relative_to(root):
        raise ValueError("Reports must be outside scan root")
    automatic_baseline = False
    if auto_history and baseline_file is None:
        from storage_history import find_previous_snapshot
        baseline_file = find_previous_snapshot(reports, root, format_version=VERSION, is_reparse=reparse)
        automatic_baseline = baseline_file is not None
    category_bytes: dict[str, int] = defaultdict(int)
    category_files: dict[str, int] = defaultdict(int)
    first_level_bytes: dict[str, int] = defaultdict(int)
    top_files: list[dict] = []
    errors: list[dict[str, str]] = []
    scanned = 0
    skipped_links = 0
    truncated = False
    stack: list[Path] = [root]
    while stack and not truncated:
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                entries = list(it)
        except OSError as exc:
            errors.append({"location": str(folder.relative_to(root)), "error": type(exc).__name__})
            continue
        for entry in entries:
            path = Path(entry.path)
            rel = path.relative_to(root)
            try:
                if reparse(path):
                    skipped_links += 1
                    continue
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    stack.append(path)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                n = int(info.st_size)
                scanned += 1
                if scanned > MAX_FILES:
                    truncated = True
                    break
                category = classify(rel.parts)
                first = rel.parts[0] if len(rel.parts) > 1 else "(files at root)"
                category_bytes[category] += n
                category_files[category] += 1
                first_level_bytes[first] += n
                candidate = {"path": rel.as_posix(), "bytes": n, "category": category}
                if len(top_files) < MAX_TOP:
                    top_files.append(candidate)
                    top_files.sort(key=lambda x: x["bytes"], reverse=True)
                elif n > top_files[-1]["bytes"]:
                    top_files[-1] = candidate
                    top_files.sort(key=lambda x: x["bytes"], reverse=True)
            except (OSError, ValueError) as exc:
                errors.append({"location": rel.as_posix(), "error": type(exc).__name__})
                continue
    snapshot = {
        "format": VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "total_logical_bytes": sum(category_bytes.values()),
        "scanned_files": min(scanned, MAX_FILES),
        "skipped_reparse_entries": skipped_links,
        "truncated": truncated,
        "errors_count": len(errors),
        "errors_sample": errors[:50],
        "category_bytes": dict(sorted(category_bytes.items())),
        "category_file_count": dict(sorted(category_files.items())),
        "top_level_bytes": dict(sorted(first_level_bytes.items(), key=lambda x: x[1], reverse=True)),
        "largest_files": top_files,
        "status": "PARTIAL" if truncated or errors or skipped_links else "COMPLETE_FOR_REGULAR_FILES",
        "limitations": [
            "Sizes are logical file sizes, not allocated disk clusters.",
            "Hardlinks may be counted more than once; compression and deduplication are not resolved.",
            "Symlinks, junctions and other reparse points are skipped; inaccessible items are not counted.",
            "Categories are path-name heuristics, not permission to delete anything.",
            "This tool never deletes, moves, repairs or cleans files.",
        ],
    }
    snapshot["comparison_status"] = "NOT_COMPARED"
    if baseline_file:
        baseline = json.loads(Path(baseline_file).read_text(encoding="utf-8"))
        if baseline.get("format") != VERSION or baseline.get("root") != str(root):
            raise ValueError("Baseline format/root mismatch")
        if type(baseline.get("total_logical_bytes")) is not int:
            raise ValueError("Baseline is missing total logical bytes")
        if not isinstance(baseline.get("category_bytes"), dict):
            raise ValueError("Baseline category breakdown is invalid")
        if any(type(v) is not int or v < 0 for v in baseline["category_bytes"].values()):
            raise ValueError("Baseline category breakdown has invalid values")
        snapshot["comparison_status"] = "COMPARED"
        snapshot["comparison_source"] = "automatic_previous" if automatic_baseline else "selected_baseline"
        snapshot["baseline_report"] = str(Path(baseline_file).resolve())
        categories = set(baseline.get("category_bytes", {})) | set(snapshot["category_bytes"])
        snapshot["growth_by_category"] = {
            k: snapshot["category_bytes"].get(k, 0) - baseline["category_bytes"].get(k, 0)
            for k in sorted(categories)
        }
        previous = baseline.get("total_logical_bytes")
        if type(previous) is not int:
            raise ValueError("Baseline is missing total logical bytes")
        snapshot["growth_total_logical_bytes"] = snapshot["total_logical_bytes"] - previous
        if snapshot["status"] != "COMPLETE_FOR_REGULAR_FILES" or baseline.get("status") != "COMPLETE_FOR_REGULAR_FILES":
            snapshot["growth_warning"] = "At least one scan incomplete: growth estimates may be misleading"
    reports.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="storage_cause_", dir=reports))
    (out / "storage_report.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only local storage cause analyzer")
    p.add_argument("scan_folder")
    p.add_argument("report_folder")
    p.add_argument("--baseline", help="Previous storage_report.json from same root")
    p.add_argument("--compare-previous", action="store_true", help="Find previous same-root local report automatically")
    args = p.parse_args()
    output = analyze(args.scan_folder, args.report_folder, args.baseline,
                     auto_history=args.compare_previous)
    print(output / "storage_report.json")


if __name__ == "__main__":
    main()

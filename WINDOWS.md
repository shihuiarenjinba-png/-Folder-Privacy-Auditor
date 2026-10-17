# Folder Privacy Auditor — read-only Windows improvement

## Product UX
1. Select a folder.
2. Run a read-only audit. First line shows file count, logical bytes, REVIEW/UNINSPECTED/FAILED counts.
3. Examine individual risks, skipped areas and duplicate indicators.
4. Export CSV and JSON reports to **new filenames outside** the scanned directory.

## Checks and limitations
- File type, extension, logical bytes and hidden-path indicators.
- Up to 50 MB file SHA256 hashing, with duplicate grouping for hashed bytes.
- Known text-like extensions: pattern checking up to first 1 MB, only for files up to 2 MB. Content past the sample is explicitly UNINSPECTED.
- Email, Japanese telephone and ambiguous long numeric identifier candidates. Long IDs are warning-only; no automatic removal.
- All non-text formats show **format-specific content not inspected**; no unsupported scan is advertised.
- Symlinks, junctions, reparse points and special files are NOT followed. Inaccessible entries are reported as FAILED when observable.
- Scan capped at 150,000 regular files; exceeding cap marks inventory incomplete.
- Output contains file names, paths and candidate flags and can itself be sensitive. Protect reports and do not share without review.
- **No deletion, cleaning or move operation exists in this branch.**

## Relationship to Storage Cause Analyzer
`main` contains separate `storage_cause_analyzer.py`, `storage_cause_gui.py` and Windows QA tooling. This independent branch derives from `windows-mvp-20260915`; it must not overwrite/merge the storage analytics changes by mistake. Future integration should preserve both modules, with a simple launcher and independent testing.

## Test
```powershell
py -3 -m compileall -q windows_app.py i18n.py smoke_test.py tests
py -3 .\smoke_test.py
py -3 -m unittest discover -s tests -p 'test_*.py' -v
py -3 .\bilingual_smoke_test.py
```

Development portable build: `build-windows-portable.ps1`. Portable EXE is **not** an official Store MSIX.

## Store gate — HOLD
Pending executed CI, 150k-file and large-file tests, inaccessible paths/Windows symlink permissions and reparse-point E2E, clean Windows 10/11 GUI/DPI testing, report confidentiality review, correct Partner Center identity, formal MSIX packaging, install/update/uninstall and certification, licensing/third-party notices, verified egress, pricing and screenshots. No "folder fully safe" claim is permitted.

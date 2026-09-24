# Folder Privacy Auditor — Windows MVP

## Implemented

- Recursive local folder scan
- File type, size and hidden-path inspection
- Risky data-bearing extension flags
- Validated email/phone candidate scan for small text-like files. Email checks reject malformed syntax, URL user-info, and filename-like addresses whose first domain label contains no letter.
- Japanese international phone notation accepts `+81` without a domestic trunk `0`; invalid `+81-090-...` lookalikes are not reported as embedded domestic numbers.
- SHA256 hashing for files up to 50 MB
- Duplicate-content grouping by SHA256
- CSV + JSON audit report export

No file content is uploaded by this implementation.

## Run

```powershell
py -3 .\windows_app.py
```

## Build

```powershell
powershell -ExecutionPolicy Bypass -File .\build-windows-portable.ps1
```

Output: `dist\FolderPrivacyAuditor.exe`

## Sales note

The PII scan is intentionally conservative and limited to supported text-like formats; it is not a legal/compliance certification. Before sale test inaccessible folders, symlinks/junctions, very large trees, duplicates, Japanese paths, Windows 10/11, malware scan, Authenticode signing and SHA256.

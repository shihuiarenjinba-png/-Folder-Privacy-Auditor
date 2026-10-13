# Windows QA evidence and human acceptance

This is for **unsigned development builds only**. It does not approve a Microsoft Store release or make a malware-free claim.

## On your Windows 10/11 test computer

Clone this repository (or update your existing checkout), open PowerShell at the repo root and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build-windows-validation.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-acceptance.ps1 -Mode Local
```

The first command runs automated regression tests and creates an **unsigned local EXE** under `dist-validation\`. It installs build dependencies and therefore may require internet access at build time; the app itself is intended for offline use.

The second command checks the executable SHA-256 against `validation-manifest.json`, inventories distribution-file hashes, inspects Authenticode signature status and reads Defender availability. It writes new, non-overwriting files:

- `dist-validation\<PRODUCT-GUID>\qa-evidence-<RUN-ID>\acceptance.json`
- `dist-validation\<PRODUCT-GUID>\qa-evidence-<RUN-ID>\distribution-sha256.json`

Run a **human-observed GUI check** using *only synthetic test data*:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-acceptance.ps1 -Mode Local -Interactive
```

The script requests explicit confirmation before launching the GUI and prompts for PASS / FAIL / SKIP for each case from `docs/WINDOWS_MANUAL_ACCEPTANCE.md`. Do not record personal, customer or confidential data in the notes. Where there are multiple builds in `dist-validation`, specify `-ManifestPath "C:\path\to\validation-manifest.json"` so the intended EXE is checked.

Optional local Microsoft Defender custom scan (not run by default):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qa\windows-acceptance.ps1 -Mode Local -RunDefenderScan
```

Defender may be unavailable or blocked by organizational policies; it may quarantine suspicious test files. Do not bypass security warnings or treat a completed scan as a safety certificate. Review Windows Security detection history yourself.

## CI results and release constraints

- Passing Windows GitHub Actions validation: https://github.com/shihuiarenjinba-png/-Folder-Privacy-Auditor/actions/runs/38401043707
- CI verifies EXE compilation, startup, synthetic GUI-to-file behavior and QA evidence generation, **not** human visual inspection.
- `release_approved` is always `false` in the QA output; this is deliberate.
- GitHub Actions artifact-storage quota prevents preserving the generated EXE as a downloadable artifact.
- Windows 10 and 11 physical/manual tests, Japanese PDF glyph rendering (where applicable), Windows Security review, offline egress inspection, signed installer/MSIX and Store certification **remain pending**.
- Keep all personal QA records local; this script does not upload screenshots, files or reports.

**Status: AUTOMATED_QA_PASS / HUMAN_ACCEPTANCE_PENDING / RELEASE_BLOCKED.**

# Real GUI preferences and installed MSIX update — 2026-10-14

- Product: `StorageCauseAnalyzer`
- Passing Windows CI: https://github.com/shihuiarenjinba-png/-Folder-Privacy-Auditor/actions/runs/38477462623
- Regression tests: 8 passed
- Saved GUI preferences: 容量分析レポートの保存先（reports）.

A button labeled **設定を保存** writes an explicitly allowlisted UTF-8 JSON `schema_version=1` setting using an exclusive temporary file, fsync and atomic replace. Existing corrupt or newer format settings are NOT silently destroyed. No personal scan file contents are stored.

MSIX packaged: `%LOCALAPPDATA%\Packages\<ActualPackageFamilyName>\LocalState\StorageCauseAnalyzer\preferences.json`; unpackaged EXE: `%LOCALAPPDATA%\StorageCauseAnalyzer\preferences.json`.

CI proves actual GUI setting save at 1.0.0.0, same-package MSIX update to 1.0.1.0, byte-for-byte SHA-256 preservation, and GUI reload of saved synthetic Japanese-text path.

**Not tested**: historic real-world settings migrations, true disk logical/physical allocation differences, human GUI, Windows 10/11 hardware matrix, Defender/security audit, production MS Store identity or uninstall retention.

**Status: REAL_GUI_PREFERENCES_CI_PASS / RELEASE_BLOCKED.**

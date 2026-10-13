# Windows validation record — 2026-10-13

## Confirmed CI result

- Repository: `-Folder-Privacy-Auditor`
- Test-only branch: `validation/windows-20261013`
- Tested commit: `b50e43d67362e49ee96d85838ecb0b9f5a916e2d`
- Windows GitHub Actions run: https://github.com/shihuiarenjinba-png/-Folder-Privacy-Auditor/actions/runs/38386330294
- Runner environment: `windows-latest`, Python 3.11
- Automated unit tests run: **4, passing**
- PyInstaller Windows one-directory executable: **built successfully**
- Generated executable name: `StorageCauseAnalyzer.exe`
- EXE SHA-256 (ephemeral CI build): `6F278260E6D603166D24FEB2994E8F1690DD4A33D4DB3823C7A4A58DDF7E1710`
- Workflow conclusion: **success**

## Restrictions / release gates

- **NOT A SALES RELEASE.** EXE is unsigned and no manual GUI/window interaction tests were run.
- GitHub Actions artifact quota was exceeded. Binary upload was disabled; no downloadable build is preserved by this run. SHA-256 alone is not an EXE download.
- Windows host integration and actual GUI interactions, malware/Defender checks, signing, installer/MSIX, privacy review and Microsoft Store certification remain pending.
- Current automated tests are focused regression fixtures; they do not certify every file format, filesystem edge case, encoding, performance, security behavior, or real user dataset.
- `main` retains manually triggered `windows-validation.yml`; the push trigger exists only on the isolated validation branch.
- A future build from the same sources might not reproduce this hash unless the toolchain and dependencies are pinned.
- Do not merge the validation-only push trigger or claim full release approval.

## Next steps

1. Run the existing PowerShell validation script on a controlled Windows 10/11 test PC.
2. Perform explicit GUI open/import/output/safety tests, including negative and non-ASCII cases.
3. Audit compiled binaries, dependencies, egress, filesystem writes, uninstall, Defender results.
4. Sign release candidates and inspect manifest/AV results before creating an MSIX or selling.

Status: `AUTOMATED_WINDOWS_TEST_AND_BUILD_PASS / RELEASE_BLOCKED`.

# Group C | MSIX candidate handoff | 2026-10-23

**Product:** `-Folder-Privacy-Auditor`  
**Store ID:** `9PKMCT98XQF5` — OWNER_CONFIRMED_IN_CHAT; NOT_LIVE_VERIFIED_IN_PARTNER_CENTER.  
**Designated source:** `fix/store-identity-json-20261023`, SHA `11f64af55fb4e25e5d7e7f43a09d1669bc564d89` (verified at branch creation).  
**Isolated work branch:** `codex/store-p1-folder-privacy-20261023`.  
**Portable EXE:** `dist/FolderPrivacyAuditor.exe` (planned output, NOT confirmed built).  
**Existing MSIX builder:** `store/build-msix.ps1` (unchanged).

## Already prepared
- Isolated work branch based on the exact designated source SHA.
- Added only `.github/workflows/group-c-portable-prerequisite.yml`, which invokes the existing portable EXE builder, then runs the existing Python regressions, verifies the named EXE, records SHA-256 and uploads a short-lived EXE prerequisite artifact on success.
- The workflow does **not** build/sign/upload a Microsoft Store package and does not authorize sales or publication.
- At creation, GitHub Actions returned `failure` with **0 executed steps** and no verified build artifact. This means RUNNER/EXECUTION_UNVERIFIED, not a unit-test failure.

## Hard MSIX gates still requiring independent real evidence
1. Partner Center: confirm this product's Store ID, **Package Identity Name**, Publisher, PublisherDisplayName, Package Family Name and exact reserved display name; do not copy another app's values.
2. Owner-approved `A.B.C.0` MSIX package version and historical version collision check; the builder's `1.0.0.0` default is **not approval**.
3. Product-owned `StoreLogo.png` (50x50), `Square44x44Logo.png` (44x44) and `Square150x150Logo.png` (150x150). No invented/mock assets.
4. Windows Actions regression and portable EXE SHA-256 with **actual runner, steps, logs, exit codes and artifact**; source SHA must match the intended release.
5. Run the existing `store/build-msix.ps1` only with verified exact values, approved EXE and assets, on a clean Windows x64 environment with Windows SDK MakeAppx. Preserve previous artifacts.
6. Unpack and inspect the actual MSIX AppxManifest.xml (Identity Name/Publisher, x64, Version, Properties DisplayName, VisualElements DisplayName, PublisherDisplayName), compare EXE hashes and publish exact MSIX SHA-256. Test a properly signed build's install/launch/real data/write/update/uninstall separately. Check Store upload errors separately. **No upload, certification submission or publication without explicit owner approval.**

## Product-specific constraints
Canonical schema v2 exists at store/partner-center-identity.json. The Store ID, Publisher, PFN and SID carry OWNER_PROVIDED_UNVERIFIED evidence, not Partner Center live verification. Identity Name, PublisherDisplayName and approved package version remain UNKNOWN. Use -ValidateOnly on the existing builder; do not bypass identity_manifest.py.

**Current status:** `MSIX=NOT_CREATED_AND_NOT_VERIFIED`, `WINDOWS_E2E=NOT_VERIFIED`, `WACK=NOT_VERIFIED`, `CERTIFICATION=NOT_AUTHORIZED`, `SALES=HOLD`.

Do not change an existing app source file or existing PowerShell script just to suppress a red check. Work on this branch only, with reviewed changes.

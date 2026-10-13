# Storage Cause Analyzer — MSIX QA preflight

Run `build-windows-validation.ps1`, then `qa/build-msix-preflight.ps1 -TestIdentity` on Windows with Python and Windows SDK MakeAppx installed.

This creates a **test-only, unsigned MSIX** using a synthetic identity and temporary placeholder icons. It packs, unpacks, and checks the original executable SHA-256. The result is NOT a release, cannot be claimed Store-certified, and has not been installed or signed.

Before publishing: finish manual Windows acceptance, verify Defender and dependency risks, obtain exact identity/publisher in Partner Center, replace logos and QA labeling, run Windows App Certification Kit, and test installation, upgrade, removal, and payment/licensing. Never upload a synthetic-identity package to Partner Center.

Official references:
- https://learn.microsoft.com/en-us/windows/apps/distribute-through-store/how-to-distribute-your-win32-app-through-microsoft-store
- https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-manual-conversion

**Status: RELEASE_BLOCKED.**

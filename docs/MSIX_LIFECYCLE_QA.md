# Windows MSIX install/upgrade/uninstall — QA record 2026-10-13

Product: `StorageCauseAnalyzer` in existing repository `-Folder-Privacy-Auditor`.
Windows-hosted GitHub Actions: https://github.com/shihuiarenjinba-png/-Folder-Privacy-Auditor/actions/runs/38409241168
Automated lifecycle result: **MSIX_INSTALL_UPDATE_REMOVE_PASS**.

Tested on a temporary GitHub-hosted Windows runner:
1. Self-signed disposable test certificate; temporary LocalMachine/TrustedPeople import.
2. Synthetic QA identity version 1.0.0.0: signed and installed.
3. Version 1.0.1.0 with same package family: signed and successfully updated.
4. QA app unregistered; test cert removed from LocalMachine and CurrentUser stores.
5. Exit status passed only if upgrade, uninstall and certificate cleanup all succeed.

Safe execution restriction: `qa/msix-install-lifecycle-ci.ps1 -EphemeralRunner` refuses ordinary Windows PCs and self-hosted runners. CI workflow uses `windows-latest`, and user data, actual Store identity and production signing certificates are NOT used.

**Still untested**: launch through installed Start Menu entry, interactive GUI, real file editing, Windows 10/11 physical machines, upgrade data persistence, uninstall user data handling, production identity and icons, security/Defender clearance, Microsoft Store certification and licensing. Built QA MSIX is not preserved as a downloadable artifact due to repository storage quota.

No sale or Store submission is authorized by this test. Store-submitted MSIX packages can be signed by Microsoft at publication. See https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements.

Status: `AUTOMATED_INSTALL_UPDATE_UNINSTALL_PASS / RELEASE_BLOCKED`.

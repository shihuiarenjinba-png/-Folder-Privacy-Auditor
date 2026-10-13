# Windows installed MSIX GUI launch and LocalState persistence — 2026-10-14

- Existing product: `StorageCauseAnalyzer`; repo: `-Folder-Privacy-Auditor`
- Windows CI result: https://github.com/shihuiarenjinba-png/-Folder-Privacy-Auditor/actions/runs/38419707858 (**SUCCESS**)
- Synthetic QA package 1.0.0.0: installed and launched by Windows shell AUMID using `IApplicationActivationManager.ActivateApplication`
- App created a JSON Tk startup verification file inside `%LOCALAPPDATA%\Packages\<PackageFamilyName>\LocalState`
- Same-package-family upgrade to 1.0.1.0 retained the test file byte-for-byte (SHA-256), and new packaged GUI activation succeeded after update
- QA app unregistered, disposable test certificate removed
- No store submission, no production identity, no end-user PC installation

**Important limits**: This checks an app-generated synthetic QA marker, not actual user settings, application saves, invoice records, documents, or database upgrade compatibility. Visual Japanese PDF rendering, real human GUI operation, Windows 10/11 physical hardware, security, signing and Store certification remain NOT TESTED.

CI-only helper is restricted to disposable GitHub-hosted Windows runners. The main workflow remains manual-only.

**Status: INSTALLED_APP_ACTIVATION_AND_SYNTHETIC_STATE_PASS / RELEASE_BLOCKED.**

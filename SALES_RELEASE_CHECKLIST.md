# Sales release checklist / 販売直前チェック

## Code gates / コード側
- [x] Folder-audit logic remains independent from UI-language state
- [x] Packaged build enters through `desktop_entry.py`
- [x] Explicit **`言語 / Language`** selector with persisted `日本語 / English`
- [x] Existing translations remain in use

## Real Windows / fixture gates / 実機確認
- [ ] Windows 10 / Windows 11 smoke tests
- [ ] 日本語 → English → 日本語 switching and restart persistence
- [ ] 100%, 125%, 150% display scaling
- [ ] Run existing smoke/regression tests
- [ ] Test large/deep directory trees and long paths supported by Windows configuration
- [ ] Test permission-denied, unreadable, disappearing, and locked files/folders
- [ ] Verify audit is read-only and never modifies audited files
- [ ] Verify findings are deterministic and paths are displayed safely
- [ ] Verify documented local-only/network-egress boundary at runtime
- [ ] Build one-file EXE from a path with spaces/non-ASCII characters
- [ ] Windows Defender/AV scan; record SHA-256
- [ ] Prepare LICENSE/NOTICE/SBOM; lock dependencies
- [ ] Authenticode-sign final commercial artifact

Do not mark sales-ready until all applicable unchecked items are complete.
未チェック項目が残っている間は販売完成扱いにしません。

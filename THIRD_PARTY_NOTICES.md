# THIRD-PARTY NOTICES — Folder Privacy Auditor (QA)
 
## Czkawka CLI / czkawka_core (Rust)
- Upstream: https://github.com/qarmin/czkawka
- Pinned release: 12.0.2 (2026-09-09)
- Shipped file: windows_czkawka_cli.exe renamed czkawka_cli.exe inside the self-extracting Windows package
- Upstream release SHA-256: eb7c2009d2dd49cf5202acbd65370caece0a3f819b9515e727cedb1ec088ed1a
- License: MIT for CLI and Core. Copyright and permission notice reproduced below.
- Czkawka logos / images / sounds / Krokiet GUI are NOT used.
- CLI is used only for read-only scans; cleanup/repair features are not exposed.
- Recheck the complete transitive dependency license inventory before commercial release.

## MIT license text from upstream Czkawka CLI 12.0.2

MIT License

Copyright (c) 2020-2026 Rafał Mikrut

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## LibreHardwareMonitor
Referenced for possible future sensor integration only. No source/binary linked or bundled in this stage. It is under MPL-2.0, with additional notices for dependencies. Any future integration requires separate review and sensor privilege testing.

## Distribution hold
This is an engineering notice, not final clearance. Review all Cargo transitive dependency licenses and Python/PyInstaller/psutil (if bundled later) licenses prior to Store/Stripe publication.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' is required." }
$Venv = Join-Path $Root ".venv-build"
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
py -3 -m venv $Venv
$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $Python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "dependency installation failed." }
& $Python .\bilingual_smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "bilingual_smoke_test.py failed." }
& $Python .\language_standard_smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "language_standard_smoke_test.py failed." }
& $Python .\smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "smoke_test.py failed." }
& $Python .\dialog_parent_smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "dialog_parent_smoke_test.py failed." }
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name "FolderPrivacyAuditor" desktop_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
Copy-Item -LiteralPath (Join-Path $Root "START_HERE.html") -Destination (Join-Path $Root "dist\START_HERE.html") -Force
Write-Host "Built: $Root\dist\FolderPrivacyAuditor.exe"
Write-Host "Before sale: run SALES_RELEASE_CHECKLIST.md, large-folder tests, permission-error tests, JA/EN UI smoke, malware scan, Authenticode signing and SHA256."

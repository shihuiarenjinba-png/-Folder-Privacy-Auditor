$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher 'py' is required." }
$Venv = Join-Path $Root ".venv-build"
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
py -3 -m venv $Venv
$Python = Join-Path $Venv "Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install pyinstaller
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name "FolderPrivacyAuditor" desktop_entry.py
Write-Host "Built: $Root\dist\FolderPrivacyAuditor.exe"
Write-Host "Before sale: run SALES_RELEASE_CHECKLIST.md, large-folder tests, permission-error tests, JA/EN UI smoke, malware scan, Authenticode signing and SHA256."

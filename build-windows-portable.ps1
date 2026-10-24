$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
. (Join-Path $Root "build_python.ps1")
$BasePython = Resolve-BuildPython
$Venv = Join-Path $Root ".venv-build"
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
& $BasePython -m venv $Venv
$Python = Join-Path $Venv "Scripts\python.exe"
$LockFile = Join-Path $Root "requirements-windows.lock.txt"
if (-not (Test-Path -LiteralPath $LockFile -PathType Leaf)) { throw "Dependency lock is missing: $LockFile" }
& $Python -m pip install --requirement $LockFile
if ($LASTEXITCODE -ne 0) { throw "locked dependency installation failed." }
& $Python .\bilingual_smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "bilingual_smoke_test.py failed." }
& $Python .\language_standard_smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "language_standard_smoke_test.py failed." }
& $Python .\smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "smoke_test.py failed." }
& $Python .\dialog_parent_smoke_test.py
if ($LASTEXITCODE -ne 0) { throw "dialog_parent_smoke_test.py failed." }
# Pin the official MIT Czkawka CLI 12.0.2 binary. It embeds czkawka_core.
# Never fetch a moving 'latest' binary, or ship an unchecked executable.
$CliVersion = '12.0.2'
$CliSha256 = 'EB7C2009D2DD49CF5202ACBD65370CAECE0A3F819B9515E727CEDB1EC088ED1A'
$CliDir = Join-Path $Root 'vendor-bin'
New-Item -ItemType Directory -Path $CliDir -Force | Out-Null
$CliPath = Join-Path $CliDir 'czkawka_cli.exe'
$CliUrl = "https://github.com/qarmin/czkawka/releases/download/$CliVersion/windows_czkawka_cli.exe"
if (-not (Test-Path -LiteralPath $CliPath)) {
    Invoke-WebRequest -Uri $CliUrl -OutFile $CliPath -UseBasicParsing
}
$CliActualHash = (Get-FileHash -LiteralPath $CliPath -Algorithm SHA256).Hash
if ($CliActualHash -cne $CliSha256) {
    throw "Czkawka CLI checksum mismatch; refusing to build"
}
Write-Host "CZKAWKA_CORE_VIA_CLI=$CliVersion SHA256=$CliActualHash"
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name "FolderPrivacyAuditor" --add-binary "$CliPath;." desktop_entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
Copy-Item -LiteralPath (Join-Path $Root "START_HERE.html") -Destination (Join-Path $Root "dist\START_HERE.html") -Force
Write-Host "Built: $Root\dist\FolderPrivacyAuditor.exe"
Write-Host "Before sale: run SALES_RELEASE_CHECKLIST.md, large-folder tests, permission-error tests, JA/EN UI smoke, malware scan, Authenticode signing and SHA256."

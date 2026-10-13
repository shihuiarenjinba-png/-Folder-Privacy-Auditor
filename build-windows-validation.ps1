# Test-first Windows packaging, never a signed or approved store release.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot
$stamp = [Guid]::NewGuid().ToString("N")
$venv = Join-Path $env:TEMP ("StorageCauseAnalyzer-validation-" + $stamp)
$python = Join-Path $venv "Scripts\\python.exe"
$out = Join-Path $PSScriptRoot ("dist-validation\\StorageCauseAnalyzer-" + $stamp)
function CheckCode { if ($LASTEXITCODE -ne 0) { throw "Process exit $LASTEXITCODE" } }
function P([string[]]$argsList) { & $python @argsList; CheckCode }
try {
    py -3 -m venv $venv
    CheckCode
    P @("-m","pip","install","--upgrade","pip")
    P @("-m","pip","install","pyinstaller>=6.10,<7")
    P @("-m","unittest","discover","-s","tests","-p","test_*.py","-v")
    P @("-m","PyInstaller","--clean","--noconfirm","--onedir","--windowed",
        "--name","StorageCauseAnalyzer","--distpath",$out,
        "--workpath",(Join-Path $venv "pyinstaller-work"),
        "--specpath",(Join-Path $venv "pyinstaller-spec"),"storage_cause_gui.py")
    $exe = Join-Path $out "StorageCauseAnalyzer\\StorageCauseAnalyzer.exe"
    if (-not (Test-Path -LiteralPath $exe)) { throw "Missing EXE: $exe" }
    $sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash
    $manifest = [ordered]@{
        product="StorageCauseAnalyzer"; sha256=$sha; validation_only=$true; sales_release=$false
        signed=$false; windows_gui_runtime_tested=$false; defender_checked=$false
        created_utc=(Get-Date).ToUniversalTime().ToString("o")
    }
    $manifest | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $out "validation-manifest.json")
    Write-Host "UNSIGNED validation build only: $exe / sha256 $sha"
} finally {
    if (Test-Path -LiteralPath $venv) { Remove-Item -LiteralPath $venv -Force -Recurse }
}

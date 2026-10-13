# CI only. Smoke-check a Windows EXE GUI startup; does not simulate real user actions.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$manifestFile = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "dist-validation") -Recurse -Filter validation-manifest.json | Select-Object -First 1
if (-not $manifestFile) { throw "Missing validation manifest" }
$manifest = Get-Content -LiteralPath $manifestFile.FullName -Raw | ConvertFrom-Json
$exe = Join-Path $manifestFile.DirectoryName "$($manifest.product)\$($manifest.product).exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "EXE missing: $exe" }
$probe = Join-Path $manifestFile.DirectoryName "gui_process_smoke.json"
if (Test-Path -LiteralPath $probe) { throw "Smoke result already exists" }
$proc = Start-Process -FilePath $exe -ArgumentList @("--smoke-test", "--smoke-output", $probe) -PassThru
try {
    if (-not $proc.WaitForExit(30000)) {
        & taskkill.exe /F /T /PID $proc.Id | Out-Null
        throw "GUI process smoke timed out"
    }
    if ($proc.ExitCode -ne 0) { throw "GUI process exited with code $($proc.ExitCode)" }
    if (-not (Test-Path -LiteralPath $probe)) { throw "GUI did not write smoke result" }
    $check = Get-Content -LiteralPath $probe -Raw | ConvertFrom-Json
    if ($check.status -ne "GUI_PROCESS_SMOKE_OK") { throw "Invalid smoke result" }
    $manifest | Add-Member -NotePropertyName gui_process_smoke_tested -NotePropertyValue $true -Force
    $manifest | Add-Member -NotePropertyName interactive_gui_tested -NotePropertyValue $false -Force
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestFile.FullName -Encoding UTF8
    Write-Host "GUI_PROCESS_SMOKE_OK: $($check.title)"
} finally {
    if (-not $proc.HasExited) { & taskkill.exe /F /T /PID $proc.Id | Out-Null }
}

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

# Exercise the compiled GUI through actual programmatic button invocations and
# verify that output bytes exist, then exercise a safe error case.
$e2eProof = Join-Path $manifestFile.DirectoryName "gui_e2e_result.json"
if (Test-Path -LiteralPath $e2eProof) { throw "E2E proof already exists" }
$e2eProc = Start-Process -FilePath $exe -ArgumentList @("--e2e-test", $e2eProof) -PassThru
try {
    if (-not $e2eProc.WaitForExit(60000)) {
        & taskkill.exe /F /T /PID $e2eProc.Id | Out-Null
        throw "GUI end-to-end fixture timed out"
    }
    if ($e2eProc.ExitCode -ne 0) { throw "GUI end-to-end fixture exit $($e2eProc.ExitCode)" }
    if (-not (Test-Path -LiteralPath $e2eProof)) { throw "E2E proof not created" }
    $e2eResult = Get-Content -LiteralPath $e2eProof -Raw | ConvertFrom-Json
    if ($e2eResult.status -ne "GUI_E2E_OK" -or
        $e2eResult.actual_output_verified -ne $true -or
        $e2eResult.input_unchanged -ne $true -or
        $e2eResult.negative_case_verified -ne $true) {
        throw "GUI end-to-end proof invalid"
    }
    $manifest | Add-Member -NotePropertyName automated_gui_e2e_pass -NotePropertyValue $true -Force
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestFile.FullName -Encoding UTF8
    Write-Host "GUI_E2E_OK: $($e2eResult.scenario)"
} finally {
    if (-not $e2eProc.HasExited) { & taskkill.exe /F /T /PID $e2eProc.Id | Out-Null }
}

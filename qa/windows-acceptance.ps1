<#
Local Windows QA evidence collector for UNSIGNED validation builds.
Never approves sales releases, signs code, deletes files, or uploads evidence.
CI mode is noninteractive. Local -Interactive mode requires a human observer.
#>
[CmdletBinding()]
param(
    [ValidateSet("CI","Local")][string]$Mode = "Local",
    [string]$ManifestPath = "",
    [switch]$Interactive,
    [switch]$RunDefenderScan
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") { throw "Windows is required" }
if ($Mode -eq "CI" -and ($Interactive -or $RunDefenderScan)) {
    throw "CI cannot claim human approval or perform a requested local Defender scan"
}
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $location = Join-Path $repo "dist-validation"
    if (-not (Test-Path -LiteralPath $location)) { throw "First run build-windows-validation.ps1" }
    $candidates = @(Get-ChildItem -LiteralPath $location -Recurse -File -Filter "validation-manifest.json" |
        Sort-Object LastWriteTimeUtc -Descending)
    if ($candidates.Count -eq 0) { throw "No validation manifest found" }
    if ($candidates.Count -gt 1 -and $Mode -eq "Local") {
        throw "Multiple builds exist; specify the desired -ManifestPath"
    }
    $mfile = $candidates[0]
} else {
    $mfile = Get-Item -LiteralPath $ManifestPath -ErrorAction Stop
}
if ($mfile.Name -ne "validation-manifest.json") { throw "Wrong manifest filename" }
$manifest = Get-Content -LiteralPath $mfile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not ($manifest.product -is [string]) -or $manifest.product -notmatch '^[A-Za-z0-9_-]+$') {
    throw "Invalid product"
}
if ($manifest.validation_only -ne $true -or $manifest.sales_release -ne $false) {
    throw "This collector accepts non-release validation builds only"
}
$dist = Join-Path $mfile.DirectoryName $manifest.product
$exe = Join-Path $dist ($manifest.product + ".exe")
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "EXE missing: $exe" }
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if ($hash.ToUpperInvariant() -ne ([string]$manifest.sha256).ToUpperInvariant()) {
    throw "RELEASE BLOCKED: executable hash differs from the build manifest"
}
$signature = Get-AuthenticodeSignature -LiteralPath $exe
$osDetails = [ordered]@{caption="Unknown";version="Unknown";build="Unknown"}
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $osDetails = [ordered]@{caption=[string]$os.Caption;version=[string]$os.Version;build=[string]$os.BuildNumber}
} catch {}
$files = @()
$prefix = (Get-Item -LiteralPath $dist).FullName.TrimEnd('\')
foreach ($file in @(Get-ChildItem -LiteralPath $dist -File -Recurse -Force | Sort-Object FullName)) {
    $files += [ordered]@{
        relative_path=$file.FullName.Substring($prefix.Length).TrimStart('\')
        size_bytes=[long]$file.Length
        sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
}
if ($files.Count -lt 1) { throw "Empty distribution folder" }
$defender = [ordered]@{available=$false;status="UNAVAILABLE";scan_requested=[bool]$RunDefenderScan}
try {
    $mp = Get-MpComputerStatus -ErrorAction Stop
    $defender.available = $true
    $defender.status = "STATUS_READ_ONLY"
    $defender["real_time_protection_enabled"] = [bool]$mp.RealTimeProtectionEnabled
    $defender["antivirus_enabled"] = [bool]$mp.AntivirusEnabled
} catch {}
if ($RunDefenderScan) {
    if (-not $defender.available) {
        $defender.status = "SCAN_UNAVAILABLE"
    } else {
        try {
            Start-MpScan -ScanType CustomScan -ScanPath $dist -ErrorAction Stop
            $defender.status = "SCAN_COMMAND_COMPLETED_CHECK_WINDOWS_SECURITY_HISTORY"
        } catch {
            $defender.status = "SCAN_FAILED_MANUAL_REVIEW_REQUIRED"
        }
    }
}
$cases = @()
$checklist = Join-Path $repo "docs\WINDOWS_MANUAL_ACCEPTANCE.md"
foreach ($line in @(Get-Content -LiteralPath $checklist -Encoding UTF8)) {
    if ($line -match '^\d+\.\s+\[\s*\]\s+(.+)$') {
        $cases += [ordered]@{title=$Matches[1];result="PENDING";note=""}
    }
}
if ($cases.Count -eq 0) { throw "Manual acceptance checklist not found or empty" }
if ($Interactive) {
    Write-Host "Use only disposable synthetic test data. This does not authorize security warning bypasses."
    $answer = Read-Host "Type YES to launch the unsigned test GUI and record actual observations"
    if ($answer -eq "YES") {
        Start-Process -FilePath $exe | Out-Null
        for ($i=0;$i -lt $cases.Count;$i++) {
            Write-Host ("Case {0}/{1}: {2}" -f ($i+1),$cases.Count,$cases[$i].title)
            $status = (Read-Host "Result: PASS / FAIL / SKIP").Trim().ToUpperInvariant()
            if ($status -notin @("PASS","FAIL","SKIP")) { $status = "SKIP" }
            $cases[$i].result = $status
            $cases[$i].note = Read-Host "Sanitized evidence note (no personal data)"
        }
    }
}
$allManualPass = $Interactive -and (@($cases | Where-Object {$_.result -ne "PASS"}).Count -eq 0)
$evidenceDir = Join-Path $mfile.DirectoryName "qa-evidence"
if (-not (Test-Path -LiteralPath $evidenceDir)) {
    New-Item -ItemType Directory -Path $evidenceDir -ErrorAction Stop | Out-Null
}
$signerSubject = $null
if ($signature.SignerCertificate) { $signerSubject = [string]$signature.SignerCertificate.Subject }
$report = [ordered]@{
    schema="windows_qa_evidence_v1"
    created_utc=(Get-Date).ToUniversalTime().ToString("o")
    product=$manifest.product
    mode=$Mode
    os=$osDetails
    exe_hash_matches_build_manifest=$true
    exe_sha256=$hash
    executable_signature_status=[string]$signature.Status
    signature_subject=$signerSubject
    distribution_file_count=$files.Count
    defender=$defender
    manual_checks=$cases
    manual_all_pass=[bool]$allManualPass
    gui_automated_e2e_pass=($manifest.PSObject.Properties.Name -contains "automated_gui_e2e_pass" -and $manifest.automated_gui_e2e_pass -eq $true)
    release_approved=$false
    release_gate="BLOCKED_MANUAL_SECURITY_PACKAGING_AND_STORE_REVIEW"
    note="No malware-free, visual quality, or store approval is implied by CI or a Defender scan command."
}
$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $evidenceDir "acceptance.json") -Encoding UTF8
ConvertTo-Json -InputObject $files -Depth 6 | Set-Content -LiteralPath (Join-Path $evidenceDir "distribution-sha256.json") -Encoding UTF8
Write-Host ("QA_EVIDENCE_OK product={0} files={1} manual_all_pass={2} release_approved=false" -f $manifest.product,$files.Count,$allManualPass)
Write-Host ("QA evidence at {0}" -f (Join-Path $evidenceDir "acceptance.json"))

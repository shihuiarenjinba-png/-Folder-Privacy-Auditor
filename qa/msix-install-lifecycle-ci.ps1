<#
Disposable GitHub-hosted runner only. NOT safe for ordinary PC or shared runner.
Test local self-signed code-signing and current-user MSIX install/update/uninstall.
This test never uses a Store identity or production credentials.
#>
[CmdletBinding()]
param([switch]$EphemeralRunner)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (-not $EphemeralRunner -or $env:GITHUB_ACTIONS -ne "true" -or
    $env:RUNNER_ENVIRONMENT -ne "github-hosted" -or $env:OS -ne "Windows_NT") {
    throw "Refuse deployment outside an explicitly opted-in disposable Windows Actions runner"
}
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$builds = @(Get-ChildItem -LiteralPath (Join-Path $repo "dist-validation") -Recurse -File -Filter validation-manifest.json)
if ($builds.Count -ne 1) { throw "Expected one validation build" }
$record = Get-Content -LiteralPath $builds[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
if ($record.validation_only -ne $true -or $record.sales_release -ne $false) { throw "QA build required" }
$product = [string]$record.product
if ($product -notmatch '^[A-Za-z0-9_-]+$') { throw "Unsafe product identifier" }
$identity = "QA.$product.Prototype"
$reports = @(Get-ChildItem -LiteralPath $builds[0].DirectoryName -File -Recurse -Filter msix-preflight-report.json)
if ($reports.Count -ne 1) { throw "Expected exactly one initial MSIX report" }
$initial = Get-Content -LiteralPath $reports[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
if ($initial.test_identity -ne $true -or $initial.identity -ne $identity -or
    $initial.version -ne "1.0.0.0" -or $initial.release_approved -ne $false -or
    $initial.status -ne "MSIX_PACK_UNPACK_HASH_PASS") { throw "Wrong initial identity/version" }
if (-not (Test-Path -LiteralPath $initial.msix_path -PathType Leaf) -or
    (Get-FileHash -LiteralPath $initial.msix_path -Algorithm SHA256).Hash -ne $initial.msix_sha256) {
    throw "Initial MSIX missing or hash mismatch"
}
if (@(Get-AppxPackage -Name $identity -ErrorAction Stop).Count -ne 0) {
    throw "Preexisting QA application detected: refusing update"
}
$cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
$signTool = if ($cmd) { $cmd.Source } else { "" }
if (-not $signTool) {
    $sdk = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
    $found = @(Get-ChildItem -LiteralPath $sdk -File -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending)
    if ($found.Count -lt 1) { throw "SignTool missing from Windows SDK" }
    $signTool = $found[0].FullName
}
$certificate = $null
$signedOld = $false
$installedOld = $false
$signedNew = $false
$updated = $false
$removed = $false
$certRemoved = $false
$problem = ""
$cleanupIssues = @()
$family = ""
$packagedLaunchBefore = $false
$packagedLaunchAfter = $false
$qaStatePersisted = $false
$realPreferencesSaved = $false
$realPreferencesRestored = $false
$realPreferenceHash = ""
$initialProofHash = ""
try {
    $params = @{
        Type = "Custom"
        KeyUsage = "DigitalSignature"
        Subject = "CN=Untrusted QA Prototype"
        CertStoreLocation = "Cert:\CurrentUser\My"
        TextExtension = @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
        FriendlyName = "Temporary GitHub Windows MSIX test"
        ErrorAction = "Stop"
    }
    $certificate = New-SelfSignedCertificate @params
    if (-not $certificate -or $certificate.Subject -ne "CN=Untrusted QA Prototype") {
        throw "Unexpected code-signing certificate"
    }
    $cerPath = Join-Path $env:RUNNER_TEMP ("msix-qa-" + [guid]::NewGuid().ToString("N") + ".cer")
    try {
        Export-Certificate -Cert $certificate -FilePath $cerPath -ErrorAction Stop | Out-Null
        Import-Certificate -FilePath $cerPath -CertStoreLocation "Cert:\CurrentUser\TrustedPeople" -ErrorAction Stop | Out-Null
        $machineTrustPath = "Cert:\LocalMachine\TrustedPeople\$($certificate.Thumbprint)"
        if (Test-Path -LiteralPath $machineTrustPath) { throw "QA certificate unexpectedly already trusted in machine store" }
        Import-Certificate -FilePath $cerPath -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" -ErrorAction Stop | Out-Null
        if (-not (Test-Path -LiteralPath $machineTrustPath)) { throw "Machine-level trust could not be established" }
    } finally {
        if (Test-Path -LiteralPath $cerPath) { Remove-Item -LiteralPath $cerPath -Force }
    }
    & $signTool sign /fd SHA256 /sha1 $certificate.Thumbprint /s My $initial.msix_path
    if ($LASTEXITCODE -ne 0) { throw "Initial package signing failed" }
    $signedOld = $true
    Add-AppxPackage -Path $initial.msix_path -ErrorAction Stop
    $installed = @(Get-AppxPackage -Name $identity -ErrorAction Stop)
    if ($installed.Count -ne 1 -or [string]$installed[0].Version -ne "1.0.0.0") {
        throw "Package 1.0.0.0 installation not registered"
    }
    $family = [string]$installed[0].PackageFamilyName
    $installedOld = $true
    Write-Host ("QA_MSIX_INSTALLED version={0} family={1}" -f $installed[0].Version,$family)
    # Run through Windows' registered application activation contract, not directly from dist.
    $stateFolder = Join-Path $env:LOCALAPPDATA ("Packages\" + $family + "\LocalState")
    $proofBefore = Join-Path $stateFolder "qa_msix_before_upgrade.json"
    & (Join-Path $PSScriptRoot "msix-packaged-launch-ci.ps1") -PackageFamilyName $family -MarkerPath $proofBefore -EphemeralRunner
    if (-not (Test-Path -LiteralPath $proofBefore)) { throw "App-generated LocalState marker missing before upgrade" }
    $initialProofHash = (Get-FileHash -LiteralPath $proofBefore -Algorithm SHA256).Hash
    $packagedLaunchBefore = $true
    $prefWrite = Join-Path $stateFolder "qa_prefs_write.json"
    & (Join-Path $PSScriptRoot "msix-packaged-launch-ci.ps1") -PackageFamilyName $family -MarkerPath $prefWrite -EphemeralRunner -PreferenceMode write
    $actualPreferences = Join-Path $stateFolder (Join-Path $product "preferences.json")
    if (-not (Test-Path -LiteralPath $actualPreferences)) { throw "Real GUI preferences file not created" }
    $realPreferenceHash = (Get-FileHash -LiteralPath $actualPreferences -Algorithm SHA256).Hash
    $realPreferencesSaved = $true
    & (Join-Path $PSScriptRoot "build-msix-preflight.ps1") -TestIdentity -Version "1.0.1.0" -ManifestPath $builds[0].FullName
    if ($LASTEXITCODE -ne 0) { throw "MSIX upgrade package creation failed" }
    $newReports = @(Get-ChildItem -LiteralPath $builds[0].DirectoryName -File -Recurse -Filter msix-preflight-report.json |
        Where-Object { $_.FullName -ne $reports[0].FullName })
    if ($newReports.Count -ne 1) { throw "Expected exactly one upgrade package" }
    $next = Get-Content -LiteralPath $newReports[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($next.identity -ne $identity -or $next.version -ne "1.0.1.0" -or $next.test_identity -ne $true) {
        throw "Upgrade identity or version mismatch"
    }
    & $signTool sign /fd SHA256 /sha1 $certificate.Thumbprint /s My $next.msix_path
    if ($LASTEXITCODE -ne 0) { throw "Upgrade package signing failed" }
    $signedNew = $true
    Add-AppxPackage -Path $next.msix_path -ErrorAction Stop
    $upgraded = @(Get-AppxPackage -Name $identity -ErrorAction Stop)
    if ($upgraded.Count -ne 1 -or [string]$upgraded[0].Version -ne "1.0.1.0" -or
        [string]$upgraded[0].PackageFamilyName -ne $family) { throw "In-place upgrade validation failed" }
    $updated = $true
    Write-Host ("QA_MSIX_UPDATED version={0} family_stable=true" -f $upgraded[0].Version)
    if (-not (Test-Path -LiteralPath $proofBefore) -or
        (Get-FileHash -LiteralPath $proofBefore -Algorithm SHA256).Hash -ne $initialProofHash) {
        throw "App-generated LocalState test data missing/modified after update"
    }
    $qaStatePersisted = $true
    $proofAfter = Join-Path $stateFolder "qa_msix_after_upgrade.json"
    & (Join-Path $PSScriptRoot "msix-packaged-launch-ci.ps1") -PackageFamilyName $family -MarkerPath $proofAfter -EphemeralRunner
    if (-not (Test-Path -LiteralPath $proofAfter)) { throw "Packaged GUI marker missing after upgrade" }
    $packagedLaunchAfter = $true
    if (-not (Test-Path -LiteralPath $actualPreferences) -or
        (Get-FileHash -LiteralPath $actualPreferences -Algorithm SHA256).Hash -ne $realPreferenceHash) {
        throw "Saved user preference JSON was lost or changed during MSIX update"
    }
    $prefVerify = Join-Path $stateFolder "qa_prefs_verify.json"
    & (Join-Path $PSScriptRoot "msix-packaged-launch-ci.ps1") -PackageFamilyName $family -MarkerPath $prefVerify -EphemeralRunner -PreferenceMode verify
    $verifyState = Get-Content -LiteralPath $prefVerify -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($verifyState.preferences_sha256 -ne $realPreferenceHash) { throw "GUI restored unexpected preference bytes" }
    $realPreferencesRestored = $true
    Write-Host "QA_MSIX_REAL_PREFERENCES_RESTORED sha256_match=true release=false"
    Write-Host "QA_MSIX_LOCALSTATE_PRESERVED sha256_match=true release=false"
} catch {
    $problem = $_.Exception.Message
    Write-Warning ("QA_MSIX_LIFECYCLE_ERROR: " + $problem)
} finally {
    try {
        $current = @(Get-AppxPackage -Name $identity -ErrorAction Stop)
        foreach ($pkg in $current) {
            if ($pkg.Name -ne $identity -or $pkg.Publisher -ne "CN=Untrusted QA Prototype") {
                throw "Unrecognized package encountered during cleanup"
            }
            Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop
        }
        if (@(Get-AppxPackage -Name $identity -ErrorAction Stop).Count -ne 0) {
            throw "Package still registered after removal"
        }
        $removed = $true
    } catch {
        $cleanupIssues += "app removal: $($_.Exception.Message)"
    }
    if ($certificate) {
        try {
            $thumbprint = $certificate.Thumbprint
            foreach ($loc in @("Cert:\LocalMachine\TrustedPeople\$thumbprint",
                               "Cert:\CurrentUser\TrustedPeople\$thumbprint",
                               "Cert:\CurrentUser\My\$thumbprint")) {
                if (Test-Path -LiteralPath $loc) {
                    Remove-Item -LiteralPath $loc -Force -ErrorAction Stop
                }
            }
            foreach ($loc in @("Cert:\LocalMachine\TrustedPeople\$thumbprint", "Cert:\CurrentUser\TrustedPeople\$thumbprint", "Cert:\CurrentUser\My\$thumbprint")) {
                if (Test-Path -LiteralPath $loc) { throw "Test certificate still present" }
            }
            $certRemoved = $true
        } catch {
            $cleanupIssues += "cert removal: $($_.Exception.Message)"
        }
    }
}
$passed = $signedOld -and $installedOld -and $signedNew -and $updated -and
    $packagedLaunchBefore -and $packagedLaunchAfter -and $qaStatePersisted -and
    $realPreferencesSaved -and $realPreferencesRestored -and
    $removed -and $certRemoved -and $cleanupIssues.Count -eq 0
$report = [ordered]@{
    schema = "msix_ephemeral_lifecycle_v1"
    status = if ($passed) { "MSIX_INSTALL_UPDATE_REMOVE_PASS" } else { "REVIEW_OR_BLOCKED" }
    product = $product
    qa_identity = $identity
    signed_initial = $signedOld
    installed_initial = $installedOld
    signed_upgrade = $signedNew
    upgraded_same_family = $updated
    removed_test_app = $removed
    deleted_test_certificate = $certRemoved
    error = $problem
    cleanup_issues = @($cleanupIssues)
    packaged_gui_launch_before_update = $packagedLaunchBefore
    packaged_gui_launch_after_update = $packagedLaunchAfter
    qa_generated_localstate_persisted = $qaStatePersisted
    real_gui_preferences_saved = $realPreferencesSaved
    real_gui_preferences_restored = $realPreferencesRestored
    preferences_schema_version = 1
    actual_product_config_migration = "NOT_TESTED"
    user_interactive_gui = "NOT_TESTED"
    user_interaction = "NOT_TESTED"
    original_store_identity_used = $false
    release_approved = $false
}
$folder = Join-Path $builds[0].DirectoryName ("msix-lifecycle-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $folder | Out-Null
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $folder "lifecycle-report.json") -Encoding UTF8
if (-not $passed) { throw "MSIX lifecycle failed or cleanup incomplete" }
Write-Host ("MSIX_REAL_GUI_PREFERENCES_SURVIVE_UPDATE_PASS product={0} release=false" -f $product)

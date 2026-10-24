# Windows-only Store candidate builder. Identity fields are read exclusively from
# store/partner-center-identity.json by identity_manifest.py.
# This script never reserves an app name, signs, uploads, or publishes.
[CmdletBinding()]
param(
    [string]$ExePath = "",
    [string]$AssetsDirectory = "",
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$ExpectedBranch = 'codex/store-p1-folder-privacy-20261023'
$IdentityPath = Join-Path $PSScriptRoot 'partner-center-identity.json'
$IdentityHelper = Join-Path $PSScriptRoot 'identity_manifest.py'
if (-not (Test-Path -LiteralPath $IdentityPath -PathType Leaf)) {
    throw "Canonical identity JSON is missing: $IdentityPath"
}
if (-not (Test-Path -LiteralPath $IdentityHelper -PathType Leaf)) {
    throw "Identity manifest helper is missing: $IdentityHelper"
}

function Invoke-GitText {
    param([string[]]$GitArguments)
    $Output = & git @GitArguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Git command failed (exit $LASTEXITCODE): git $($GitArguments -join ' '); output: $Output" }
    return ($Output | Out-String).Trim()
}
Set-Location -LiteralPath $Root
$RemoteUrl = Invoke-GitText -GitArguments @('remote','get-url','origin')
if ($RemoteUrl -notmatch '(?i)github[.]com[:/]shihuiarenjinba-png/-Folder-Privacy-Auditor(?:[.]git)?$') {
    throw 'Wrong origin repository; stopped before validation or packaging.'
}
Invoke-GitText -GitArguments @('fetch','origin') | Out-Null
$Branch = Invoke-GitText -GitArguments @('branch','--show-current')
$SourceSha = Invoke-GitText -GitArguments @('rev-parse','HEAD')
$RemoteSha = Invoke-GitText -GitArguments @('rev-parse',('origin/' + $ExpectedBranch))
$DirtyState = Invoke-GitText -GitArguments @('status','--porcelain','--untracked-files=all')
if ($Branch -cne $ExpectedBranch) { throw "Wrong working branch: $Branch" }
if ($SourceSha -notmatch '^[0-9a-f]{40}$' -or $RemoteSha -cne $SourceSha) { throw 'Local and remote HEAD must be identical.' }
if ($DirtyState) { throw 'Uncommitted or untracked changes exist; stopped before validation or packaging.' }

$PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -eq $PythonCommand) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
}
$UsePyLauncher = $false
if ($null -eq $PythonCommand) {
    $PythonCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -eq $PythonCommand) { $PythonCommand = Get-Command py -ErrorAction SilentlyContinue }
    if ($null -eq $PythonCommand) {
        throw 'Python 3 is required to validate the canonical Identity JSON; no Python launcher was found.'
    }
    $UsePyLauncher = $true
}
$PythonPath = $PythonCommand.Source
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    throw 'Could not resolve the Python executable path.'
}

function Invoke-IdentityHelper {
    param([string[]]$HelperArguments)
    if ($script:UsePyLauncher) {
        & $script:PythonPath -3 $script:IdentityHelper @HelperArguments
    } else {
        & $script:PythonPath $script:IdentityHelper @HelperArguments
    }
    $HelperExitCode = $LASTEXITCODE
    if ($HelperExitCode -ne 0) {
        throw "Identity gate stopped the MSIX build (identity helper exit code $HelperExitCode)."
    }
}

if ($ValidateOnly) {
    Invoke-IdentityHelper -HelperArguments @('--validate-only')
    Write-Host 'VALIDATION_ONLY=TRUE; no EXE, manifest, or MSIX was created.'
    Write-Host 'A structurally valid JSON may still correctly report FORMAL_MSIX=BLOCKED.'
    return
}

# Release readiness is checked before touching the EXE, assets, output, or MakeAppx.
# There are deliberately no IdentityName/Publisher/DisplayName overrides.
Invoke-IdentityHelper -HelperArguments @('--check-release-ready')

$IdentityDocument = Get-Content -LiteralPath $IdentityPath -Raw -Encoding UTF8 | ConvertFrom-Json
$PackageVersion = [string]$IdentityDocument.package_version.value
$AppExe = 'FolderPrivacyAuditor.exe'

if ([string]::IsNullOrWhiteSpace($ExePath) -or
    -not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
    throw 'Provide the validated FolderPrivacyAuditor.exe path with -ExePath.'
}
$ExePath = (Resolve-Path -LiteralPath $ExePath).Path
if ([string]::IsNullOrWhiteSpace($AssetsDirectory) -or
    -not (Test-Path -LiteralPath $AssetsDirectory -PathType Container)) {
    throw 'Provide the approved brand assets directory with -AssetsDirectory.'
}
$AssetsDirectory = (Resolve-Path -LiteralPath $AssetsDirectory).Path

$MakeAppxCommand = Get-Command MakeAppx.exe -ErrorAction SilentlyContinue
if ($null -eq $MakeAppxCommand) {
    $Kits = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Windows Kits\10\bin'
    if (Test-Path -LiteralPath $Kits) {
        $Found = @(Get-ChildItem -LiteralPath $Kits -Recurse -File -Filter 'MakeAppx.exe' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
            Sort-Object FullName -Descending)
        if ($Found.Count -gt 0) {
            $MakeAppxPath = $Found[0].FullName
        } else {
            throw 'Windows SDK MakeAppx.exe was not found.'
        }
    } else {
        throw 'Windows SDK MakeAppx.exe was not found.'
    }
} else {
    $MakeAppxPath = $MakeAppxCommand.Source
}

$Output = Join-Path $Root 'dist-store'
$PackagePath = Join-Path $Output ("FolderPrivacyAuditor_QA_UNSIGNED_" + $PackageVersion + '_x64.msix')
if (Test-Path -LiteralPath $PackagePath) {
    throw "Refusing to overwrite an existing package. Use an owner-approved new package_version: $PackagePath"
}

$Stage = Join-Path $env:TEMP ('FolderPrivacyAuditor-stage-' + [guid]::NewGuid().ToString('N'))
$Roundtrip = Join-Path $env:TEMP ('FolderPrivacyAuditor-verify-' + [guid]::NewGuid().ToString('N'))
$PackageProducedByThisRun = $false
try {
    New-Item -ItemType Directory -Path $Stage -Force | Out-Null
    Copy-Item -LiteralPath $ExePath -Destination (Join-Path $Stage $AppExe) -ErrorAction Stop
    Set-Content -LiteralPath (Join-Path $Stage 'SOURCE_GIT_COMMIT.txt') -Value $SourceSha -Encoding ASCII
    $StageAssets = Join-Path $Stage 'Assets'
    New-Item -ItemType Directory -Path $StageAssets -Force | Out-Null

    foreach ($Item in @(
        @('StoreLogo.png', 50, 50),
        @('Square44x44Logo.png', 44, 44),
        @('Square150x150Logo.png', 150, 150)
    )) {
        $Filename = [string]$Item[0]
        $Original = Join-Path $AssetsDirectory $Filename
        if (-not (Test-Path -LiteralPath $Original -PathType Leaf)) {
            throw "Missing approved product asset: $Filename"
        }
        $Bytes = [IO.File]::ReadAllBytes($Original)
        if ($Bytes.Length -lt 24 -or $Bytes[0] -ne 137 -or $Bytes[1] -ne 80 -or
            $Bytes[2] -ne 78 -or $Bytes[3] -ne 71 -or $Bytes[12] -ne 73 -or
            $Bytes[13] -ne 72 -or $Bytes[14] -ne 68 -or $Bytes[15] -ne 82) {
            throw "Invalid PNG signature/IHDR: $Filename"
        }
        $Width = 0; $Height = 0
        for ($i = 16; $i -lt 20; $i++) { $Width = ($Width * 256) + [int]$Bytes[$i] }
        for ($i = 20; $i -lt 24; $i++) { $Height = ($Height * 256) + [int]$Bytes[$i] }
        if ($Width -ne [int]$Item[1] -or $Height -ne [int]$Item[2]) {
            throw "Wrong PNG dimensions for $Filename : $Width x $Height"
        }
        Copy-Item -LiteralPath $Original -Destination (Join-Path $StageAssets $Filename) -ErrorAction Stop
    }

    $ManifestPath = Join-Path $Stage 'AppxManifest.xml'
    Invoke-IdentityHelper -HelperArguments @('--render-manifest', $ManifestPath)

    function Assert-ManifestMatchesIdentity {
        param([string]$Path, [object]$Expected)
        [xml]$ManifestXml = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        $Namespaces = New-Object System.Xml.XmlNamespaceManager($ManifestXml.NameTable)
        $Namespaces.AddNamespace('f', 'http://schemas.microsoft.com/appx/manifest/foundation/windows10')
        $Namespaces.AddNamespace('uap', 'http://schemas.microsoft.com/appx/manifest/uap/windows10')
        $IdNode = $ManifestXml.SelectSingleNode('/f:Package/f:Identity', $Namespaces)
        $PropsNode = $ManifestXml.SelectSingleNode('/f:Package/f:Properties', $Namespaces)
        $VisualNode = $ManifestXml.SelectSingleNode('/f:Package/f:Applications/f:Application/uap:VisualElements', $Namespaces)
        if ($null -eq $IdNode -or $null -eq $PropsNode -or $null -eq $VisualNode) {
            throw "Manifest is missing a required identity/display element: $Path"
        }
        if ($IdNode.GetAttribute('Name') -cne [string]$Expected.identity_name.value -or
            $IdNode.GetAttribute('Publisher') -cne [string]$Expected.publisher.value -or
            $IdNode.GetAttribute('Version') -cne [string]$Expected.package_version.value -or
            $IdNode.GetAttribute('ProcessorArchitecture') -cne 'x64') {
            throw "Manifest Identity does not match the canonical identity JSON: $Path"
        }
        $DisplayNode = $PropsNode.SelectSingleNode('f:DisplayName', $Namespaces)
        $PublisherNode = $PropsNode.SelectSingleNode('f:PublisherDisplayName', $Namespaces)
        if ($null -eq $DisplayNode -or $DisplayNode.InnerText -cne [string]$Expected.display_name.value) {
            throw "Manifest Properties/DisplayName doesn't match the canonical JSON: $Path"
        }
        if ($null -eq $PublisherNode -or $PublisherNode.InnerText -cne [string]$Expected.publisher_display_name.value) {
            throw "Manifest Properties/PublisherDisplayName doesn't match the canonical JSON: $Path"
        }
        if ($VisualNode.GetAttribute('DisplayName') -cne [string]$Expected.display_name.value) {
            throw "Manifest VisualElements.DisplayName doesn't match the canonical JSON: $Path"
        }
    }
    Assert-ManifestMatchesIdentity -Path $ManifestPath -Expected $IdentityDocument

    if (-not (Test-Path -LiteralPath $Output)) {
        New-Item -ItemType Directory -Path $Output | Out-Null
    }
    & $MakeAppxPath pack /d $Stage /p $PackagePath
    $PackExitCode = $LASTEXITCODE
    if ($PackExitCode -ne 0 -or -not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
        throw "MakeAppx packaging failed (exit code $PackExitCode). Any partial output, if present, was preserved for review."
    }
    $PackageProducedByThisRun = $true

    New-Item -ItemType Directory -Path $Roundtrip | Out-Null
    & $MakeAppxPath unpack /p $PackagePath /d $Roundtrip
    $UnpackExitCode = $LASTEXITCODE
    if ($UnpackExitCode -ne 0) {
        throw "MSIX unpack verification failed (exit code $UnpackExitCode)."
    }

    $OriginalHash = (Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash
    $UnpackedExe = Join-Path $Roundtrip $AppExe
    if (-not (Test-Path -LiteralPath $UnpackedExe -PathType Leaf)) {
        throw 'Unpacked MSIX executable is missing.'
    }
    $UnpackedHash = (Get-FileHash -LiteralPath $UnpackedExe -Algorithm SHA256).Hash
    if ($OriginalHash -cne $UnpackedHash) {
        throw 'MSIX roundtrip executable SHA-256 mismatch.'
    }
    Assert-ManifestMatchesIdentity -Path (Join-Path $Roundtrip 'AppxManifest.xml') -Expected $IdentityDocument

    $PackageHash = (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash
    Write-Host "QA_UNSIGNED_MSIX=$PackagePath"
    Write-Host "MSIX_SHA256=$PackageHash"
    Write-Host "SOURCE_EXE_SHA256=$OriginalHash"
    Write-Host "SOURCE_SHA=$SourceSha"
    Write-Host "MANIFEST_IDENTITY_MATCH=PASS"
    Write-Host 'PACKAGE_SIGNATURE=NOT_ADDED'
    Write-Host 'STORE_SUBMISSION=NOT_PERFORMED'
    Write-Host 'IMPORTANT: QA_UNSIGNED package only. It was not installed, signed, submitted, or certified.'
} catch {
    if ($PackageProducedByThisRun -and (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
        Remove-Item -LiteralPath $PackagePath -Force -ErrorAction SilentlyContinue
    }
    throw
} finally {
    if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
    if (Test-Path -LiteralPath $Roundtrip) { Remove-Item -LiteralPath $Roundtrip -Recurse -Force }
}

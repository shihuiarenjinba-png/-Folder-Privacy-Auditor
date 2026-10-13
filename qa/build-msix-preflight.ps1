<#
Unsigned MSIX preflight from validated PyInstaller onedir. No install, signing,
Store upload, Defender clearance, release approval or user-data deletion.
Use -TestIdentity for synthetic QA only; Partner Center identity otherwise.
#>
[CmdletBinding()]
param(
    [string]$ManifestPath = "",
    [switch]$TestIdentity,
    [string]$IdentityName = "",
    [string]$Publisher = "",
    [string]$PublisherDisplayName = "",
    [string]$Version = "1.0.0.0",
    [ValidateSet("x64","x86","arm64")][string]$Architecture = "x64"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") { throw "Windows required" }
if ($Version -notmatch '^\d{1,5}\.\d{1,5}\.\d{1,5}\.0$') {
    throw "Store package version must be 1.0.0.0 style, fourth part 0"
}
$parts = @($Version.Split('.') | ForEach-Object { [int]$_ })
if ($parts[0] -lt 1 -or @($parts | Where-Object { $_ -gt 65535 }).Count -gt 0) {
    throw "Out-of-range version"
}
if ($TestIdentity) {
    if ($IdentityName -or $Publisher -or $PublisherDisplayName) {
        throw "Test identity cannot be combined with production values"
    }
} elseif (-not $IdentityName -or -not $Publisher -or -not $PublisherDisplayName) {
    throw "Explicit Partner Center identity, publisher and display name are required"
}
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not $ManifestPath) {
    $dist = Join-Path $root "dist-validation"
    $found = @(Get-ChildItem -LiteralPath $dist -Recurse -File -Filter "validation-manifest.json" -ErrorAction Stop)
    if ($found.Count -ne 1) { throw "Specify -ManifestPath when there are zero or multiple builds" }
    $mfile = $found[0]
} else { $mfile = Get-Item -LiteralPath $ManifestPath -ErrorAction Stop }
if ($mfile.Name -ne "validation-manifest.json") { throw "Expected validation-manifest.json" }
$record = Get-Content -LiteralPath $mfile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
if ($record.validation_only -ne $true -or $record.sales_release -ne $false) {
    throw "Only non-release validation EXE builds can be staged"
}
$product = [string]$record.product
if ($product -notmatch '^[A-Za-z0-9_-]{3,60}$') { throw "Unexpected product name" }
if ($TestIdentity) {
    $IdentityName = "QA.$product.Prototype"
    $Publisher = "CN=Untrusted QA Prototype"
    $PublisherDisplayName = "QA TEST - NOT FOR DISTRIBUTION"
}
if ($IdentityName -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]{2,48}$') { throw "Invalid identity" }
if ($Publisher -notmatch '^CN=.{1,120}$') { throw "Publisher must be a full certificate identity" }
$exeDir = Join-Path $mfile.Directory.FullName $product
$exe = Join-Path $exeDir "$product.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Missing EXE" }
$sha = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
if ($sha.ToUpperInvariant() -ne ([string]$record.sha256).ToUpperInvariant()) {
    throw "EXE differs from validated build; refusing packaging"
}
$tool = Get-Command makeappx.exe -ErrorAction SilentlyContinue
$makeappx = if ($tool) { $tool.Source } else { "" }
if (-not $makeappx) {
    $kits = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kits) {
        $found = @(Get-ChildItem -LiteralPath $kits -Recurse -File -Filter "makeappx.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\makeappx\.exe$' } |
            Sort-Object FullName -Descending)
        if ($found.Count -gt 0) { $makeappx = $found[0].FullName }
    }
}
if (-not $makeappx) { throw "Windows SDK makeappx.exe not installed; nothing packaged" }
$token = [Guid]::NewGuid().ToString("N")
$outDir = Join-Path $mfile.Directory.FullName ("msix-preflight-" + $token)
$layout = Join-Path $outDir "layout"
$unpacked = Join-Path $outDir "unpacked"
New-Item -ItemType Directory -Path $layout -Force | Out-Null
$app = Join-Path $layout "App"
Copy-Item -LiteralPath $exeDir -Destination $app -Recurse -ErrorAction Stop
if (-not (Test-Path -LiteralPath (Join-Path $app "$product.exe"))) { throw "EXE copy failed" }
$assets = Join-Path $layout "Assets"
New-Item -ItemType Directory -Path $assets -Force | Out-Null
& py -3 (Join-Path $PSScriptRoot "msix-placeholder-icons.py") $assets
if ($LASTEXITCODE -ne 0) { throw "Placeholder assets generation failed" }
function EscapeXml([string]$v) { [System.Security.SecurityElement]::Escape($v) }
$xmlName = EscapeXml $IdentityName
$xmlPublisher = EscapeXml $Publisher
$xmlBrand = EscapeXml $PublisherDisplayName
$xmlProduct = EscapeXml $product
$xmlVersion = EscapeXml $Version
$xmlArch = EscapeXml $Architecture
$xml = @"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
 xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
 xmlns:uap10="http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
 xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities">
 <Identity Name="$xmlName" Publisher="$xmlPublisher" Version="$xmlVersion" ProcessorArchitecture="$xmlArch"/>
 <Properties>
  <DisplayName>$xmlProduct QA Prototype</DisplayName>
  <PublisherDisplayName>$xmlBrand</PublisherDisplayName>
  <Description>Unsigned MSIX preflight; NOT FOR DISTRIBUTION</Description>
  <Logo>Assets\StoreLogo.png</Logo>
 </Properties>
 <Resources><Resource Language="ja-JP"/><Resource Language="en-US"/></Resources>
 <Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0" MaxVersionTested="10.0.22621.0"/></Dependencies>
 <Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities>
 <Applications>
  <Application Id="App" Executable="App\$xmlProduct.exe"
   uap10:RuntimeBehavior="packagedClassicApp" uap10:TrustLevel="mediumIL">
   <uap:VisualElements DisplayName="$xmlProduct" Description="QA only"
    BackgroundColor="transparent" Square150x150Logo="Assets\Square150x150Logo.png"
    Square44x44Logo="Assets\Square44x44Logo.png"/>
  </Application>
 </Applications>
</Package>
"@
[xml]$parsed = $xml
if ($parsed.Package.Identity.Name -ne $IdentityName) { throw "XML parse failed" }
[System.IO.File]::WriteAllText((Join-Path $layout "AppxManifest.xml"),$xml,(New-Object System.Text.UTF8Encoding($false)))
$package = Join-Path $outDir ("$product-$Version-$Architecture-QA-UNSIGNED.msix")
& $makeappx pack /d $layout /p $package /o
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $package)) { throw "MakeAppx pack failed" }
& $makeappx unpack /p $package /d $unpacked /o
if ($LASTEXITCODE -ne 0) { throw "MakeAppx unpack failed" }
$extractedExe = Join-Path (Join-Path $unpacked "App") "$product.exe"
if (-not (Test-Path -LiteralPath $extractedExe)) { throw "Extracted EXE missing" }
$after = (Get-FileHash -LiteralPath $extractedExe -Algorithm SHA256).Hash
if ($after.ToUpperInvariant() -ne $sha.ToUpperInvariant()) { throw "MSIX roundtrip altered EXE" }
$report = [ordered]@{
 schema="unsigned_msix_preflight_v1"
 status="MSIX_PACK_UNPACK_HASH_PASS"
 product=$product
 identity=$IdentityName
 publisher=$Publisher
 architecture=$Architecture
 version=$Version
 test_identity=[bool]$TestIdentity
 exe_sha256=$sha
 extracted_exe_sha256=$after
 msix_sha256=(Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash
 msix_path=$package
 signed=$false
 installed_or_launched=$false
 store_certification="NOT_RUN"
 production_icons=$false
 release_approved=$false
 manual_gui_acceptance="PENDING"
 disclaimers=@("No valid production identity or certificate verified",
               "Placeholder icons are not commercial artwork",
               "Windows App Certification Kit and physical install tests NOT performed")
}
$path = Join-Path $outDir "msix-preflight-report.json"
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $path -Encoding UTF8
Write-Host ("MSIX_PREFLIGHT_OK product={0} identity_test={1} sha256={2} release=false" -f $product,[bool]$TestIdentity,$report.msix_sha256)
Write-Host "Report: $path"

<#
CI-only packaged-app activation probe. Runs in disposable GitHub-hosted Windows
session, never registers certificates or installs packages by itself.
Using the official IApplicationActivationManager Windows Shell COM interface,
not launching an unpackaged PyInstaller EXE directly.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PackageFamilyName,
    [Parameter(Mandatory=$true)][string]$MarkerPath,
    [switch]$EphemeralRunner,
    [ValidateSet("","write","verify")][string]$PreferenceMode = ""
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (-not $EphemeralRunner -or $env:GITHUB_ACTIONS -ne "true" -or
    $env:RUNNER_ENVIRONMENT -ne "github-hosted" -or $env:OS -ne "Windows_NT") {
    throw "Packaged GUI launch probe is restricted to disposable GitHub-hosted Windows"
}
if ($PackageFamilyName -notmatch '^QA\.[A-Za-z0-9_-]+\.Prototype_[A-Za-z0-9]+$') {
    throw "Refusing non-QA package family"
}
$target = @(Get-AppxPackage -ErrorAction Stop | Where-Object {
    $_.PackageFamilyName -eq $PackageFamilyName -and $_.Name -match '^QA\..+\.Prototype$'
})
if ($target.Count -ne 1) { throw "Expected exactly one installed synthetic QA app" }
$pkg = $target[0]
if ($pkg.Publisher -ne "CN=Untrusted QA Prototype") { throw "Unexpected QA package publisher" }
$root = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA ("Packages\" + $PackageFamilyName + "\LocalState")))
$marker = [IO.Path]::GetFullPath($MarkerPath)
if (-not $marker.StartsWith($root + [IO.Path]::DirectorySeparatorChar,
                           [StringComparison]::OrdinalIgnoreCase) -or
    $marker -notmatch '\\(qa_msix_(before|after)_upgrade|qa_prefs_(write|verify))\.json$') {
    throw "Marker path must be a QA-only file inside the installed app LocalState"
}
if (Test-Path -LiteralPath $marker) { throw "Marker already exists; refusing overwrite" }
if (-not (Test-Path -LiteralPath $root)) {
    New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
}
$manifest = Get-AppxPackageManifest -Package $pkg.PackageFullName
$appIds = @($manifest.Package.Applications.Application | ForEach-Object { [string]$_.Id })
if ($appIds.Count -ne 1 -or $appIds[0] -ne "App") { throw "Unexpected package AppUserModelID suffix" }
$aumid = "$PackageFamilyName!App"

# COM contract: https://learn.microsoft.com/windows/win32/api/shobjidl_core/nf-shobjidl_core-iapplicationactivationmanager-activateapplication
$interop = @'
using System;
using System.Runtime.InteropServices;
namespace QaShell {
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager {
        [PreserveSig]
        int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    public class ApplicationActivationManager : IApplicationActivationManager {
        [System.Runtime.CompilerServices.MethodImpl(
          System.Runtime.CompilerServices.MethodImplOptions.InternalCall,
          MethodCodeType = System.Runtime.CompilerServices.MethodCodeType.Runtime),
          PreserveSig]
        public extern int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
}
'@
Add-Type -TypeDefinition $interop -ErrorAction Stop
$manager = [QaShell.IApplicationActivationManager](New-Object QaShell.ApplicationActivationManager)
$pidOut = [uint32]0
$argsText = if ($PreferenceMode) { '--preferences-ci ' + $PreferenceMode + ' "' + $marker + '"' } else { '--smoke-test --smoke-output "' + $marker + '"' }
# NoErrorUI is a testing option, not a bypass of app trust or security.
$hr = $manager.ActivateApplication($aumid, $argsText, [uint32]2, [ref]$pidOut)
if ($hr -ne 0 -or $pidOut -eq 0) {
    throw ("Packaged Start-menu activation failed: hresult={0}; PID={1}" -f $hr, $pidOut)
}
$deadline = [DateTime]::UtcNow.AddSeconds(35)
while (-not (Test-Path -LiteralPath $marker) -and [DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 200
}
if (-not (Test-Path -LiteralPath $marker)) {
    throw "Packaged GUI process did not write smoke marker in LocalState"
}
$proof = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
if ($PreferenceMode) {
    if ($proof.status -ne "GUI_REAL_PREFERENCES_OK" -or $proof.mode -ne $PreferenceMode -or
        $proof.schema_version -ne 1 -or -not $proof.preferences_sha256) {
        throw "Packaged app did not validate real user preferences"
    }
} elseif ($proof.status -ne "GUI_PROCESS_SMOKE_OK" -or -not $proof.title) {
    throw "Packaged GUI marker did not confirm widget initialization"
}
$verify = @(Get-AppxPackage -Name $pkg.Name -ErrorAction Stop)
if ($verify.Count -ne 1 -or $verify[0].PackageFamilyName -ne $PackageFamilyName) {
    throw "Package registration changed during activation"
}
Write-Host ("QA_MSIX_PACKAGED_GUI_LAUNCH_OK family={0} pid={1} marker={2}" -f $PackageFamilyName,$pidOut,$marker)
) {
    throw "Marker path must be a QA-only file inside the installed app LocalState"
}
if (Test-Path -LiteralPath $marker) { throw "Marker already exists; refusing overwrite" }
if (-not (Test-Path -LiteralPath $root)) {
    New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
}
$manifest = Get-AppxPackageManifest -Package $pkg.PackageFullName
$appIds = @($manifest.Package.Applications.Application | ForEach-Object { [string]$_.Id })
if ($appIds.Count -ne 1 -or $appIds[0] -ne "App") { throw "Unexpected package AppUserModelID suffix" }
$aumid = "$PackageFamilyName!App"

# COM contract: https://learn.microsoft.com/windows/win32/api/shobjidl_core/nf-shobjidl_core-iapplicationactivationmanager-activateapplication
$interop = @'
using System;
using System.Runtime.InteropServices;
namespace QaShell {
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager {
        [PreserveSig]
        int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    public class ApplicationActivationManager : IApplicationActivationManager {
        [System.Runtime.CompilerServices.MethodImpl(
          System.Runtime.CompilerServices.MethodImplOptions.InternalCall,
          MethodCodeType = System.Runtime.CompilerServices.MethodCodeType.Runtime),
          PreserveSig]
        public extern int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
}
'@
Add-Type -TypeDefinition $interop -ErrorAction Stop
$manager = [QaShell.IApplicationActivationManager](New-Object QaShell.ApplicationActivationManager)
$pidOut = [uint32]0
$argsText = '--smoke-test --smoke-output "' + $marker + '"'
# NoErrorUI is a testing option, not a bypass of app trust or security.
$hr = $manager.ActivateApplication($aumid, $argsText, [uint32]2, [ref]$pidOut)
if ($hr -ne 0 -or $pidOut -eq 0) {
    throw ("Packaged Start-menu activation failed: hresult={0}; PID={1}" -f $hr, $pidOut)
}
$deadline = [DateTime]::UtcNow.AddSeconds(35)
while (-not (Test-Path -LiteralPath $marker) -and [DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 200
}
if (-not (Test-Path -LiteralPath $marker)) {
    throw "Packaged GUI process did not write smoke marker in LocalState"
}
$proof = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
if ($proof.status -ne "GUI_PROCESS_SMOKE_OK" -or -not $proof.title) {
    throw "Packaged GUI marker did not confirm widget initialization"
}
$verify = @(Get-AppxPackage -Name $pkg.Name -ErrorAction Stop)
if ($verify.Count -ne 1 -or $verify[0].PackageFamilyName -ne $PackageFamilyName) {
    throw "Package registration changed during activation"
}
Write-Host ("QA_MSIX_PACKAGED_GUI_LAUNCH_OK family={0} pid={1} marker={2}" -f $PackageFamilyName,$pidOut,$marker)
) {
    throw "Marker path must be a QA-only file inside the installed app LocalState"
}
if (Test-Path -LiteralPath $marker) { throw "Marker already exists; refusing overwrite" }
if (-not (Test-Path -LiteralPath $root)) {
    New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
}
$manifest = Get-AppxPackageManifest -Package $pkg.PackageFullName
$appIds = @($manifest.Package.Applications.Application | ForEach-Object { [string]$_.Id })
if ($appIds.Count -ne 1 -or $appIds[0] -ne "App") { throw "Unexpected package AppUserModelID suffix" }
$aumid = "$PackageFamilyName!App"

# COM contract: https://learn.microsoft.com/windows/win32/api/shobjidl_core/nf-shobjidl_core-iapplicationactivationmanager-activateapplication
$interop = @'
using System;
using System.Runtime.InteropServices;
namespace QaShell {
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager {
        [PreserveSig]
        int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    public class ApplicationActivationManager : IApplicationActivationManager {
        [System.Runtime.CompilerServices.MethodImpl(
          System.Runtime.CompilerServices.MethodImplOptions.InternalCall,
          MethodCodeType = System.Runtime.CompilerServices.MethodCodeType.Runtime),
          PreserveSig]
        public extern int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
}
'@
Add-Type -TypeDefinition $interop -ErrorAction Stop
$manager = [QaShell.IApplicationActivationManager](New-Object QaShell.ApplicationActivationManager)
$pidOut = [uint32]0
$argsText = if ($PreferenceMode) { '--preferences-ci ' + $PreferenceMode + ' "' + $marker + '"' } else { '--smoke-test --smoke-output "' + $marker + '"' }
# NoErrorUI is a testing option, not a bypass of app trust or security.
$hr = $manager.ActivateApplication($aumid, $argsText, [uint32]2, [ref]$pidOut)
if ($hr -ne 0 -or $pidOut -eq 0) {
    throw ("Packaged Start-menu activation failed: hresult={0}; PID={1}" -f $hr, $pidOut)
}
$deadline = [DateTime]::UtcNow.AddSeconds(35)
while (-not (Test-Path -LiteralPath $marker) -and [DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 200
}
if (-not (Test-Path -LiteralPath $marker)) {
    throw "Packaged GUI process did not write smoke marker in LocalState"
}
$proof = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
if ($PreferenceMode) {
    if ($proof.status -ne "GUI_REAL_PREFERENCES_OK" -or $proof.mode -ne $PreferenceMode -or
        $proof.schema_version -ne 1 -or -not $proof.preferences_sha256) {
        throw "Packaged app did not validate real user preferences"
    }
} elseif ($proof.status -ne "GUI_PROCESS_SMOKE_OK" -or -not $proof.title) {
    throw "Packaged GUI marker did not confirm widget initialization"
}
$verify = @(Get-AppxPackage -Name $pkg.Name -ErrorAction Stop)
if ($verify.Count -ne 1 -or $verify[0].PackageFamilyName -ne $PackageFamilyName) {
    throw "Package registration changed during activation"
}
Write-Host ("QA_MSIX_PACKAGED_GUI_LAUNCH_OK family={0} pid={1} marker={2}" -f $PackageFamilyName,$pidOut,$marker)
) {
    throw "Marker path must be a QA-only file inside the installed app LocalState"
}
if (Test-Path -LiteralPath $marker) { throw "Marker already exists; refusing overwrite" }
if (-not (Test-Path -LiteralPath $root)) {
    New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
}
$manifest = Get-AppxPackageManifest -Package $pkg.PackageFullName
$appIds = @($manifest.Package.Applications.Application | ForEach-Object { [string]$_.Id })
if ($appIds.Count -ne 1 -or $appIds[0] -ne "App") { throw "Unexpected package AppUserModelID suffix" }
$aumid = "$PackageFamilyName!App"

# COM contract: https://learn.microsoft.com/windows/win32/api/shobjidl_core/nf-shobjidl_core-iapplicationactivationmanager-activateapplication
$interop = @'
using System;
using System.Runtime.InteropServices;
namespace QaShell {
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager {
        [PreserveSig]
        int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    public class ApplicationActivationManager : IApplicationActivationManager {
        [System.Runtime.CompilerServices.MethodImpl(
          System.Runtime.CompilerServices.MethodImplOptions.InternalCall,
          MethodCodeType = System.Runtime.CompilerServices.MethodCodeType.Runtime),
          PreserveSig]
        public extern int ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            uint options,
            out uint processId);
    }
}
'@
Add-Type -TypeDefinition $interop -ErrorAction Stop
$manager = [QaShell.IApplicationActivationManager](New-Object QaShell.ApplicationActivationManager)
$pidOut = [uint32]0
$argsText = '--smoke-test --smoke-output "' + $marker + '"'
# NoErrorUI is a testing option, not a bypass of app trust or security.
$hr = $manager.ActivateApplication($aumid, $argsText, [uint32]2, [ref]$pidOut)
if ($hr -ne 0 -or $pidOut -eq 0) {
    throw ("Packaged Start-menu activation failed: hresult={0}; PID={1}" -f $hr, $pidOut)
}
$deadline = [DateTime]::UtcNow.AddSeconds(35)
while (-not (Test-Path -LiteralPath $marker) -and [DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 200
}
if (-not (Test-Path -LiteralPath $marker)) {
    throw "Packaged GUI process did not write smoke marker in LocalState"
}
$proof = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
if ($proof.status -ne "GUI_PROCESS_SMOKE_OK" -or -not $proof.title) {
    throw "Packaged GUI marker did not confirm widget initialization"
}
$verify = @(Get-AppxPackage -Name $pkg.Name -ErrorAction Stop)
if ($verify.Count -ne 1 -or $verify[0].PackageFamilyName -ne $PackageFamilyName) {
    throw "Package registration changed during activation"
}
Write-Host ("QA_MSIX_PACKAGED_GUI_LAUNCH_OK family={0} pid={1} marker={2}" -f $PackageFamilyName,$pidOut,$marker)

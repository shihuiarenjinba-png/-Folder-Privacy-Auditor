function Resolve-BuildPython {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if (-not [string]::IsNullOrWhiteSpace($env:PRODUCT_BUILD_PYTHON)) { $candidates.Add($env:PRODUCT_BUILD_PYTHON) }
    foreach ($folder in @("Python312", "Python313", "Python311", "Python310")) { $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\$folder\python.exe")) }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($line in @(& py -0p 2>$null)) {
            if ($line -match '([A-Za-z]:\\.*python\.exe)\s*$') { $candidates.Add($Matches[1]) }
        }
    }
    foreach ($command in @(Get-Command python -All -ErrorAction SilentlyContinue)) { $candidates.Add($command.Source) }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        & $candidate -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    throw "A working Python 3.10-3.13 interpreter is required. Set PRODUCT_BUILD_PYTHON to its full path."
}

<# Start RADAR BOURSE backend on Windows for alpha validation. #>
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$TrustProxy
)

$ErrorActionPreference = "Stop"
$backend = Join-Path $ProjectRoot "backend"
$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "Virtualenv python not found. Run scripts/windows/install.ps1 first." }
if (-not (Test-Path $backend)) { throw "Backend path not found: $backend" }

$env:PYTHONPATH = $backend
$env:HOST = $HostAddress
$env:PORT = [string]$Port
if ($TrustProxy) { $proxyArgs = @("--proxy-headers") } else { $proxyArgs = @("--no-proxy-headers") }

Set-Location $backend
Write-Host "Starting RADAR BOURSE backend on http://$HostAddress`:$Port"
& $venvPython -m uvicorn app.main:app --host $HostAddress --port $Port @proxyArgs

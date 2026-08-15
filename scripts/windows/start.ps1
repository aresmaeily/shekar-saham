<# Start RADAR BOURSE backend on Windows for alpha validation. #>
[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$TrustProxy
)

$ErrorActionPreference = "Stop"

function Resolve-RadarBourseProjectRoot {
    param([string]$ExplicitRoot)
    if (-not [string]::IsNullOrWhiteSpace($ExplicitRoot)) {
        if (-not (Test-Path -LiteralPath $ExplicitRoot)) {
            throw "Project root not found: $ExplicitRoot"
        }
        return (Resolve-Path -LiteralPath $ExplicitRoot).Path
    }
    $scriptDir = $null
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $scriptDir = $PSScriptRoot
    } elseif (-not [string]::IsNullOrWhiteSpace($PSCommandPath)) {
        $scriptDir = Split-Path -Parent $PSCommandPath
    } elseif ($MyInvocation.MyCommand.Path) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        throw "Cannot determine script directory. Pass -ProjectRoot explicitly."
    }
    $candidate = Join-Path $scriptDir "..\.."
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw "Project root not found relative to script: $candidate"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

$ProjectRoot = Resolve-RadarBourseProjectRoot -ExplicitRoot $ProjectRoot
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

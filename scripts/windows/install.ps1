<#
RADAR BOURSE Alpha native installer for Windows.
Creates/uses a local Python venv and installs backend requirements.
Does NOT create secrets. Does NOT start production deployment.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$SkipDependencyInstall,
    [switch]$NoEnvCopy
)

$ErrorActionPreference = "Stop"
$backend = Join-Path $ProjectRoot "backend"
$venv = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$envExample = Join-Path $ProjectRoot ".env.example"
$envFile = Join-Path $ProjectRoot ".env"
$dataDir = Join-Path $ProjectRoot "data"

function Find-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    return $null
}

function Test-PythonVersion($PythonCommand) {
    $script = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
    & $PythonCommand -c $script
    return ($LASTEXITCODE -eq 0)
}

Write-Host "RADAR BOURSE Alpha installation preparation"
Write-Host "Project Root: $ProjectRoot"

if (-not (Test-Path $backend)) { throw "Backend path not found: $backend" }
$pythonCmd = Find-PythonCommand
if (-not $pythonCmd) { throw "Python 3.10+ is required and was not found in PATH." }
if (-not (Test-PythonVersion $pythonCmd)) { throw "Python 3.10+ is required. Detected Python is too old." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git is required and was not found in PATH." }

if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }

if (-not $NoEnvCopy -and -not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host ".env created from .env.example. EDIT SECRETS BEFORE STARTING BACKEND."
}

if (-not (Test-Path $venvPython)) {
    & $pythonCmd -m venv $venv
}

if (-not $SkipDependencyInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
}

Write-Host "Installation preparation complete."
Write-Host "Next: edit .env securely, then run scripts/windows/start.ps1"

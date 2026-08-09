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

Write-Host "RADAR BOURSE Alpha installation preparation"
Write-Host "Project Root: $ProjectRoot"

if (-not (Test-Path $backend)) { throw "Backend path not found: $backend" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python is required and was not found in PATH." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git is required and was not found in PATH." }

if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }

if (-not $NoEnvCopy -and -not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host ".env created from .env.example. EDIT SECRETS BEFORE STARTING BACKEND."
}

if (-not (Test-Path $venvPython)) {
    python -m venv $venv
}

if (-not $SkipDependencyInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
}

Write-Host "Installation preparation complete."
Write-Host "Next: edit .env securely, then run scripts/windows/start.ps1"

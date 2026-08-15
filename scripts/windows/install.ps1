<#
RADAR BOURSE Alpha native installer for Windows.
Creates/uses a local Python venv and installs backend requirements.
Does NOT create secrets. Does NOT start production deployment.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [switch]$SkipDependencyInstall,
    [switch]$NoEnvCopy
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

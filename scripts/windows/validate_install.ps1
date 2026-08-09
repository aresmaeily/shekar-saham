<#
RADAR BOURSE Alpha installation prerequisite validator for Windows.
Read-only by default: it checks tools, paths, ports, disk, memory, and env status.
It never prints secret values.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$Port = 8000,
    [switch]$Json
)

$ErrorActionPreference = "Continue"

function Test-CommandExists($Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return $null }
    return $cmd.Source
}

function Get-VersionOutput($Command, $Args) {
    try {
        $out = & $Command @Args 2>$null | Select-Object -First 1
        if ($LASTEXITCODE -ne 0 -and [string]::IsNullOrWhiteSpace($out)) { return $null }
        return [string]$out
    } catch { return $null }
}

function Get-EnvStatus($Name, [bool]$Secret = $false) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    [ordered]@{
        name = $Name
        secret = $Secret
        status = if ([string]::IsNullOrWhiteSpace($value)) { "MISSING" } else { "SET" }
    }
}

$pythonCmd = Test-CommandExists "python"
if (-not $pythonCmd) { $pythonCmd = Test-CommandExists "py" }
$gitCmd = Test-CommandExists "git"
$nodeCmd = Test-CommandExists "node"
$npmCmd = Test-CommandExists "npm"
$dockerCmd = Test-CommandExists "docker"

$projectExists = Test-Path $ProjectRoot
$backend = Join-Path $ProjectRoot "backend"
$frontend = Join-Path $ProjectRoot "frontend"
$electron = Join-Path $ProjectRoot "electron"
$envExample = Join-Path $ProjectRoot ".env.example"
$envFile = Join-Path $ProjectRoot ".env"
$requirements = Join-Path $backend "requirements.txt"

$portOpen = $false
try {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $portOpen = $null -ne $listener
} catch { $portOpen = $false }

$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($ProjectRoot).Substring(0,1)) -ErrorAction SilentlyContinue
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$memoryGB = if ($os) { [math]::Round($os.TotalVisibleMemorySize / 1MB, 2) } else { $null }

$result = [ordered]@{
    ok = $true
    project_root = $ProjectRoot
    os = [ordered]@{
        caption = if ($os) { $os.Caption } else { "NOT_VERIFIED" }
        version = if ($os) { $os.Version } else { "NOT_VERIFIED" }
        architecture = $env:PROCESSOR_ARCHITECTURE
    }
    tools = [ordered]@{
        powershell = $PSVersionTable.PSVersion.ToString()
        python = if ($pythonCmd) { Get-VersionOutput $pythonCmd @("--version") } else { "MISSING" }
        pip = if ($pythonCmd) { Get-VersionOutput $pythonCmd @("-m", "pip", "--version") } else { "MISSING" }
        git = if ($gitCmd) { Get-VersionOutput "git" @("--version") } else { "MISSING" }
        node = if ($nodeCmd) { Get-VersionOutput "node" @("--version") } else { "MISSING" }
        npm = if ($npmCmd) { Get-VersionOutput "npm" @("--version") } else { "MISSING" }
        docker = if ($dockerCmd) { Get-VersionOutput "docker" @("--version") } else { "MISSING_OPTIONAL" }
    }
    paths = [ordered]@{
        project_root = $projectExists
        backend = Test-Path $backend
        frontend = Test-Path $frontend
        electron = Test-Path $electron
        env_example = Test-Path $envExample
        env = Test-Path $envFile
        requirements = Test-Path $requirements
    }
    resources = [ordered]@{
        disk_free_gb = if ($drive) { [math]::Round($drive.Free / 1GB, 2) } else { "NOT_VERIFIED" }
        memory_gb = if ($memoryGB) { $memoryGB } else { "NOT_VERIFIED" }
        port_8000_in_use = $portOpen
    }
    environment = @(
        Get-EnvStatus "DATA_SOURCE" $false
        Get-EnvStatus "PRIVATE_MODE" $false
        Get-EnvStatus "PRIVATE_PASSWORD" $true
        Get-EnvStatus "API_KEY" $true
        Get-EnvStatus "FERNET_KEY" $true
        Get-EnvStatus "BRSAPI_KEY" $true
        Get-EnvStatus "COOKIE_SECURE" $false
        Get-EnvStatus "TRUST_PROXY" $false
        Get-EnvStatus "CORS_ORIGINS" $false
        Get-EnvStatus "RADAR_BOURSE_URL" $false
    )
    notes = @(
        "Secret values are never printed.",
        "Docker is optional for native alpha installation.",
        "Port 8000 should be free before backend start unless PORT is changed.",
        "Live data is not validated by this script."
    )
}

foreach ($k in @('project_root','backend','frontend','env_example','requirements')) {
    if (-not $result.paths[$k]) { $result.ok = $false }
}
if (-not $pythonCmd -or -not $gitCmd) { $result.ok = $false }

if ($Json) {
    $result | ConvertTo-Json -Depth 6
} else {
    Write-Host "RADAR BOURSE Alpha prerequisite validation"
    Write-Host "Project Root: $ProjectRoot"
    Write-Host "OK: $($result.ok)"
    Write-Host "Tools:"
    $result.tools.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value)" }
    Write-Host "Paths:"
    $result.paths.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value)" }
    Write-Host "Environment status only:"
    $result.environment | ForEach-Object { Write-Host "  $($_.name): $($_.status)" }
}

if ($result.ok) { exit 0 } else { exit 1 }

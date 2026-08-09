<# Runtime alpha validation for a running RADAR BOURSE backend. #>
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "",
    [switch]$Json
)

$ErrorActionPreference = "Continue"
$checks = @(
    @{ name = "health"; url = "$BaseUrl/api/health"; required = $true },
    @{ name = "status"; url = "$BaseUrl/api/status"; required = $true },
    @{ name = "live_status"; url = "$BaseUrl/api/live/status"; required = $true },
    @{ name = "frontend"; url = "$BaseUrl/"; required = $true },
    @{ name = "symbol_page"; url = "$BaseUrl/symbol/فملی"; required = $false }
)

$headers = @{}
if (-not [string]::IsNullOrWhiteSpace($ApiKey)) { $headers["X-API-Key"] = $ApiKey }
$results = @()
$ok = $true
foreach ($c in $checks) {
    try {
        $response = Invoke-WebRequest -Uri $c.url -Headers $headers -UseBasicParsing -TimeoutSec 15
        $item = [ordered]@{ name=$c.name; url=$c.url; status=[int]$response.StatusCode; ok=($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) }
    } catch {
        $item = [ordered]@{ name=$c.name; url=$c.url; status="ERROR"; ok=$false; error=$_.Exception.Message }
    }
    if ($c.required -and -not $item.ok) { $ok = $false }
    $results += $item
}
$out = [ordered]@{
    ok = $ok
    base_url = $BaseUrl
    live_data_verified = $false
    note = "This script validates app availability only. Data trust must be inspected from API responses; mock/fallback is not live."
    checks = $results
}
if ($Json) { $out | ConvertTo-Json -Depth 6 } else { $out | ConvertTo-Json -Depth 6 }
if ($ok) { exit 0 } else { exit 1 }

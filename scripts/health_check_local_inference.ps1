# Health check: Dell LiteLLM proxy + vLLM backend + optional chat smoke.
param(
    [switch]$SmokeChat,
    [string]$ProxyBase = "http://100.103.33.54:4000/v1",
    [string]$BackendBase = "http://100.103.33.54:8000/v1",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Continue"
$script:fail = 0

if (-not $EnvFile) {
    $EnvFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env.local"
}

function Test-HttpOk {
    param(
        [string]$Label,
        [string]$Url,
        [hashtable]$Headers = @{},
        [switch]$WarnOnly
    )
    try {
        $r = Invoke-WebRequest -Uri $Url -Headers $Headers -TimeoutSec 15 -UseBasicParsing
        Write-Host "[OK] $Label ($($r.StatusCode))"
        return $true
    } catch {
        if ($WarnOnly) {
            Write-Host "[WARN] $Label - $($_.Exception.Message)"
        } else {
            Write-Host "[FAIL] $Label - $($_.Exception.Message)"
            $script:fail = 1
        }
        return $false
    }
}

$key = $null
if (Test-Path $EnvFile) {
    $line = Get-Content $EnvFile | Where-Object { $_ -match '^\s*LOCAL_LITELLM_MASTER_KEY=' } | Select-Object -First 1
    if ($line) { $key = ($line -split '=', 2)[1].Trim() }
}

Write-Host "=== Dell local inference health ==="
Test-HttpOk "vLLM backend /models (local-primary only)" "$BackendBase/models" -WarnOnly | Out-Null

if ($key) {
    Test-HttpOk "LiteLLM proxy /models" "$ProxyBase/models" @{ Authorization = "Bearer $key" } | Out-Null
} else {
    Write-Host "[WARN] No LOCAL_LITELLM_MASTER_KEY - skipping proxy auth check"
    $script:fail = 1
}

if ($SmokeChat -and $key) {
    Write-Host ""
    Write-Host "=== Chat smoke ==="
    foreach ($model in @("local-driver", "local-coder")) {
        try {
            $out = & (Join-Path $PSScriptRoot "ask_local_worker.ps1") -Model $model -Prompt "Reply exactly: $model ok" -MaxTokens 16 -TimeoutSec 120
            Write-Host "[OK] $model - $out"
        } catch {
            Write-Host "[FAIL] $model - $($_.Exception.Message)"
            $script:fail = 1
        }
    }
}

Write-Host ""
if ($script:fail -eq 0) {
    Write-Host "All checks passed."
    exit 0
}
Write-Host "One or more checks failed. See docs/runbooks/dell-qwen-worker-lane.md"
exit 1

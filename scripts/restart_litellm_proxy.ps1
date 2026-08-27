# Restart LiteLLM proxy on Dell (picks up litellm/config.yaml changes e.g. local-coder).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/restart_litellm_proxy.ps1

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $repo)) {
    throw "Missing repo root: $repo"
}

function Import-LiteLlmDotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line -notmatch "=") { return }
        $name, $value = $line -split "=", 2
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($name) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

# Langfuse keys stay in gitignored .env.langfuse / .env.local. Do not Write-Host them.
Import-LiteLlmDotEnv (Join-Path $repo ".env.langfuse")
$envFile = Join-Path $repo ".env.local"
if (-not (Test-Path $envFile)) {
    throw "Missing $envFile"
}
Import-LiteLlmDotEnv $envFile

if (-not $env:LOCAL_LITELLM_MASTER_KEY) { throw "LOCAL_LITELLM_MASTER_KEY not in .env.local" }
$key = $env:LOCAL_LITELLM_MASTER_KEY
if (-not $env:LANGFUSE_OTEL_HOST) { $env:LANGFUSE_OTEL_HOST = "http://127.0.0.1:3100" }

Write-Host "Stopping existing LiteLLM on port 4000..."
Get-NetTCPConnection -LocalPort 4000 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object {
        if ($_ -and $_ -ne 0) {
            Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
            Write-Host "  stopped PID $_"
        }
    }
Start-Sleep -Seconds 2

$litellm = Join-Path $repo ".venv\Scripts\litellm.exe"
$config = Join-Path $repo "litellm\config.yaml"
if (-not (Test-Path $litellm)) {
    throw "Missing $litellm - run local-inference setup first"
}

$env:LITELLM_MASTER_KEY = $key
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:NO_COLOR = "1"

Write-Host "Starting LiteLLM from $repo ..."
Start-Process -FilePath $litellm `
    -ArgumentList @("--config", $config, "--host", "0.0.0.0", "--port", "4000") `
    -WorkingDirectory $repo `
    -WindowStyle Minimized

Start-Sleep -Seconds 5

try {
    $models = Invoke-RestMethod -Uri "http://127.0.0.1:4000/v1/models" `
        -Headers @{ Authorization = "Bearer $key" } -TimeoutSec 30
    $ids = ($models.data | ForEach-Object { $_.id }) -join ", "
    Write-Host "Proxy up. Models: $ids"
    if ($ids -notmatch "local-coder") {
        Write-Host "WARN: local-coder missing - check litellm/config.yaml"
    }
} catch {
    Write-Host "Proxy starting (not ready yet). Retry: health_check_local_inference.ps1 -SmokeChat"
}

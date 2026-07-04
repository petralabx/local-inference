# Start durable Qwen3-32B-AWQ vLLM on Dell (port 8000). Idempotent.
# Requires Docker Desktop with GPU on the Dell (VTA).
# Usage: powershell -ExecutionPolicy Bypass -File start_dell_qwen_stack.ps1

$ErrorActionPreference = "Stop"

$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
if (-not (Test-Path $docker)) {
    throw "Docker not found at $docker — install Docker Desktop + WSL2 + GPU support."
}

$hfCache = Join-Path $env:USERPROFILE ".cache\huggingface"
New-Item -ItemType Directory -Force -Path $hfCache | Out-Null

$name = "vllm-local-primary"
Write-Host "Removing prior container '$name' if present..."
& $docker rm -f $name 2>$null | Out-Null

Write-Host "Starting $name (Qwen3-32B-AWQ, durable, tool calling enabled)..."
& $docker run -d `
    --name $name `
    --restart=unless-stopped `
    --gpus all `
    -p 8000:8000 `
    -v "${hfCache}:/root/.cache/huggingface" `
    vllm/vllm-openai:v0.10.2 `
    --model Qwen/Qwen3-32B-AWQ `
    --quantization awq `
    --gpu-memory-utilization 0.85 `
    --max-model-len 32768 `
    --enable-auto-tool-choice `
    --tool-call-parser hermes `
    --port 8000 `
    --host 0.0.0.0

Write-Host "Waiting for vLLM to load (may take several minutes on first pull)..."
$deadline = (Get-Date).AddMinutes(20)
do {
    Start-Sleep -Seconds 10
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/models" -TimeoutSec 10
        if ($r.data) {
            Write-Host "vLLM ready: $($r.data[0].id)"
            Write-Host ""
            Write-Host "Next: ensure LiteLLM proxy is running (local-inference/scripts/start_proxy.sh or your service)."
            Write-Host "Verify: powershell -ExecutionPolicy Bypass -File $(Join-Path $PSScriptRoot 'health_check_local_inference.ps1') -SmokeChat"
            exit 0
        }
    } catch { Write-Host "." -NoNewline }
} while ((Get-Date) -lt $deadline)

throw "vLLM did not become ready within 20 minutes. Check: docker logs vllm-local-primary"

# Swap Dell vLLM from Qwen3-32B-AWQ to Qwen3-Coder-30B-FP8 (same port 8000).
# Only one fits on the GPU at a time. LiteLLM alias: local-coder
# Usage: powershell -ExecutionPolicy Bypass -File swap_dell_qwen_coder.ps1

$ErrorActionPreference = "Stop"

$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
if (-not (Test-Path $docker)) {
    throw "Docker not found at $docker"
}

$hfCache = Join-Path $env:USERPROFILE ".cache\huggingface"
New-Item -ItemType Directory -Force -Path $hfCache | Out-Null

$name = "vllm-local-primary"
Write-Host "Stopping $name..."
& $docker rm -f $name 2>$null | Out-Null

Write-Host "Starting Qwen3-Coder-30B-A3B-Instruct-FP8 on :8000..."
& $docker run -d `
    --name $name `
    --restart=unless-stopped `
    --gpus all `
    -p 8000:8000 `
    -v "${hfCache}:/root/.cache/huggingface" `
    vllm/vllm-openai:v0.10.2 `
    --model Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 `
    --gpu-memory-utilization 0.85 `
    --max-model-len 32768 `
    --enable-auto-tool-choice `
    --tool-call-parser hermes `
    --port 8000 `
    --host 0.0.0.0

Write-Host "Use LiteLLM model alias: local-coder"
Write-Host "Swap back: powershell -ExecutionPolicy Bypass -File $(Join-Path $PSScriptRoot 'start_dell_qwen_stack.ps1')"

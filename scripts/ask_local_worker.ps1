# One-shot chat via Dell LiteLLM proxy.
# Models: local-glm52 (prose), local-primary (Qwen3-32B tools/JSON), local-coder (Qwen3-Coder — swap container first)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File ask_local_worker.ps1 -Prompt "Hello"
#   powershell -ExecutionPolicy Bypass -File ask_local_worker.ps1 -Model local-primary -Prompt "Return JSON: ..."
#   powershell -ExecutionPolicy Bypass -File ask_local_worker.ps1 -Model local-coder -System "Staff engineer" -Prompt "Fix this stack trace: ..."

param(
    [Parameter(Mandatory = $true)]
    [string]$Prompt,
    [string]$System = "",
    [ValidateSet("local-glm52", "local-primary", "local-coder", "local-fast")]
    [string]$Model = "local-glm52",
    [string]$BaseUrl = "http://100.103.33.54:4000/v1",
    [string]$EnvFile = "",
    [int]$MaxTokens = 2048,
    [double]$Temperature = 0.3,
    [int]$TimeoutSec = 300
)

$ErrorActionPreference = "Stop"

if (-not $EnvFile) {
    $EnvFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env.local"
}

if (-not (Test-Path $EnvFile)) {
    throw "Missing env file: $EnvFile"
}

$keyLine = Get-Content $EnvFile | Where-Object { $_ -match '^\s*LOCAL_LITELLM_MASTER_KEY=' } | Select-Object -First 1
if (-not $keyLine) {
    throw "LOCAL_LITELLM_MASTER_KEY not found in $EnvFile"
}
$key = ($keyLine -split '=', 2)[1].Trim()
if (-not $key -or $key -match 'CHANGE-ME') {
    throw "LOCAL_LITELLM_MASTER_KEY is unset in $EnvFile"
}

$userPrompt = $Prompt
if ($Model -match '^local-(primary|coder|fast)$' -and $userPrompt -notmatch '/no_think') {
    $userPrompt = "$userPrompt /no_think"
}

$messages = @()
if ($System) {
    $messages += @{ role = "system"; content = $System }
}
$messages += @{ role = "user"; content = $userPrompt }

$body = @{
    model       = $Model
    messages    = $messages
    max_tokens  = $MaxTokens
    temperature = $Temperature
} | ConvertTo-Json -Depth 6

$uri = ($BaseUrl.TrimEnd("/")) + "/chat/completions"
$response = Invoke-RestMethod -Uri $uri -Method Post `
    -Headers @{ Authorization = "Bearer $key" } `
    -ContentType "application/json" `
    -Body $body `
    -TimeoutSec $TimeoutSec

$content = $response.choices[0].message.content
if (-not $content) {
    throw "Empty response from $Model"
}

# Strip Qwen3 thinking blocks if model ignored /no_think
$thinkOpen = [char]60 + 'redacted_thinking' + [char]62
$thinkClose = [char]60 + '/' + 'redacted_thinking' + [char]62
$content = [regex]::Replace($content, "(?s)$([regex]::Escape($thinkOpen)).*?$([regex]::Escape($thinkClose))\s*", '').Trim()
$thinkOpen2 = [char]60 + 'think' + [char]62
$thinkClose2 = [char]60 + '/' + 'think' + [char]62
$content = [regex]::Replace($content, "(?s)$([regex]::Escape($thinkOpen2)).*?$([regex]::Escape($thinkClose2))\s*", '').Trim()
if (-not $content) {
    throw "Empty content after stripping thinking blocks from $Model"
}

Write-Output $content

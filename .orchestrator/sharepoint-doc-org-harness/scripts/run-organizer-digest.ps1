#Requires -Version 5.1
<#
  Daily Organizer digest on VTA (ADR 0006 / 0023).
  Loads LOCAL_LITELLM_MASTER_KEY from the live LiteLLM checkout. Never prints the key.
#>
[CmdletBinding()]
param(
    [string]$HarnessRoot = "",
    [string]$EnvFile = "C:\Users\vince\local-inference\.env.local",
    [string]$PythonExe = "",
    [string]$ConfigRel = "config/local.yaml",
    [string]$ReportPath = ""
)

$ErrorActionPreference = "Stop"

if (-not $HarnessRoot) {
    $HarnessRoot = Split-Path -Parent $PSScriptRoot
}
if (-not (Test-Path -LiteralPath $HarnessRoot)) {
    throw "Missing harness root: $HarnessRoot"
}

function Resolve-OrganizerPython {
    param([string]$Preferred)
    $candidates = @(
        $Preferred,
        $env:HARNESS_PYTHON,
        "C:\Users\vince\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Users\vince\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
    ) | Where-Object { $_ }
    foreach ($cand in $candidates) {
        if (-not (Test-Path -LiteralPath $cand)) { continue }
        & $cand -c "import yaml, pydantic, httpx" 2>$null
        if ($LASTEXITCODE -eq 0) { return $cand }
    }
    throw "No Python with harness deps (yaml/pydantic/httpx)"
}

$PythonExe = Resolve-OrganizerPython -Preferred $PythonExe
if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing LiteLLM env file: $EnvFile"
}

$keyLine = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match '^\s*LOCAL_LITELLM_MASTER_KEY=' } | Select-Object -First 1
if (-not $keyLine) {
    throw "LOCAL_LITELLM_MASTER_KEY not in env file"
}
$key = ($keyLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
if (-not $key) {
    throw "LOCAL_LITELLM_MASTER_KEY is empty"
}

$reportsDir = Join-Path $HarnessRoot "data\reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null
if (-not $ReportPath) {
    $stamp = Get-Date -Format "yyyy-MM-dd"
    $ReportPath = Join-Path $reportsDir ("digest-{0}.json" -f $stamp)
}

$env:LOCAL_LITELLM_MASTER_KEY = $key
$env:HARNESS_CONFIG = $ConfigRel
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Write-Output "harness_root=$HarnessRoot"
Write-Output "config=$ConfigRel"
Write-Output "report=$ReportPath"
Write-Output "action=python -m harness.cli.main digest"

Push-Location $HarnessRoot
try {
    & $PythonExe -m harness.cli.main digest --report $ReportPath
    if ($LASTEXITCODE -ne 0) {
        throw "digest exited $LASTEXITCODE"
    }
} finally {
    Pop-Location
}
Write-Output "digest_ok=1"

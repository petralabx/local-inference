#Requires -Version 5.1
<#
  Relabel already-filed VincePersonal homes (ADR 0011 / 0024).
  Single writer: VTA only. Loads LOCAL_LITELLM_MASTER_KEY from the live LiteLLM
  checkout. Never prints the key.
#>
[CmdletBinding()]
param(
    [string]$HarnessRoot = "",
    [string]$EnvFile = "C:\Users\vince\local-inference\.env.local",
    [string]$PythonExe = "",
    [string]$ConfigRel = "config/local.yaml",
    [string]$ReportPath = "",
    [int]$Limit = 0
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
    $stamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
    $suffix = if ($Limit -gt 0) { "proof-$Limit" } else { "full" }
    $ReportPath = Join-Path $reportsDir ("relabel-{0}-{1}.json" -f $stamp, $suffix)
}

function Read-EnvValue {
    param([string]$Name)
    $line = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match ("^\s*" + [regex]::Escape($Name) + "=") } | Select-Object -First 1
    if (-not $line) { return "" }
    return ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
}

$env:LOCAL_LITELLM_MASTER_KEY = $key
$vmcKey = Read-EnvValue -Name "VMC_API_KEY"
if ($vmcKey) { $env:VMC_API_KEY = $vmcKey }
$vmcBase = Read-EnvValue -Name "VMC_BASE_URL"
if ($vmcBase) { $env:VMC_BASE_URL = $vmcBase }
$env:HARNESS_CONFIG = $ConfigRel
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

Write-Output "harness_root=$HarnessRoot"
Write-Output "config=$ConfigRel"
Write-Output "report=$ReportPath"
Write-Output "python=$PythonExe"
if ($Limit -gt 0) { Write-Output "limit=$Limit" }
Write-Output "action=python -m harness.cli.main relabel"

$cliArgs = @("-m", "harness.cli.main", "relabel", "--report", $ReportPath)
if ($Limit -gt 0) {
    $cliArgs += @("--limit", "$Limit")
}
$errLog = Join-Path $reportsDir ("relabel-python-{0}.err" -f (Get-Date -Format "yyyy-MM-dd-HHmmss"))

Push-Location $HarnessRoot
try {
    # pypdf writes warnings to stderr. With ErrorAction Stop, Windows
    # PowerShell 5 treats that as a terminating error and kills the pass.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonExe @cliArgs 2> $errLog
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
    }
    Write-Output "python_exit=$code"
    if ($code -ne 0) {
        Write-Output "python_err=$errLog"
        throw "relabel exited $code"
    }
} finally {
    Pop-Location
}
Write-Output "relabel_ok=1"

<#
.SYNOPSIS
  Registers (or previews) the Windows scheduled task for the MCP health probe.

.DESCRIPTION
  Operator step. Without -Install this only prints what would be registered.
  Credentials (MC_MCP_API_KEY, optional MCP_HEALTH_WEBHOOK_URL) must be set as
  user environment variables for the account the task runs as; they are never
  written by this script. See docs/runbooks/mcp-health-probe.md.
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [string]$TaskName = "LocalInference-McpHealthProbe",
    [int]$IntervalMinutes = 15,
    [string]$RepoRoot = $(if ($env:LOCAL_INFERENCE_ROOT) { $env:LOCAL_INFERENCE_ROOT } else { Split-Path -Parent $PSScriptRoot }),
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$marker = Join-Path $RepoRoot "config\execution-primitives.local.yaml"
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".mcp.json") -PathType Leaf) -or
    -not (Test-Path -LiteralPath $marker -PathType Leaf) -or
    -not ((Get-Content -LiteralPath $marker) -contains "repo: petralabx/local-inference")) {
    throw "Invalid local-inference checkout '$RepoRoot'; set -RepoRoot or LOCAL_INFERENCE_ROOT to a checkout containing .mcp.json and the repository marker."
}
if (-not $Python) { $Python = Join-Path $RepoRoot ".venv\Scripts\python.exe" }
$script = Join-Path $RepoRoot "scripts\mcp_health_probe.py"
$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`" --root `"$RepoRoot`"" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

if (-not $Install) {
    Write-Host "Preview only (pass -Install to register):"
    Write-Host "  task:     $TaskName"
    Write-Host "  command:  $Python `"$script`" --root `"$RepoRoot`""
    Write-Host "  interval: every $IntervalMinutes minutes"
    exit 0
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Probe enabled MCP targets; state under %LOCALAPPDATA%\local-inference" -Force | Out-Null
Write-Host "Registered $TaskName"

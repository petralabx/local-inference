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
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Python = (Join-Path (Split-Path -Parent $PSScriptRoot) ".venv\Scripts\python.exe")
)

$ErrorActionPreference = "Stop"
$script = Join-Path $RepoRoot "scripts\mcp_health_probe.py"
$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

if (-not $Install) {
    Write-Host "Preview only (pass -Install to register):"
    Write-Host "  task:     $TaskName"
    Write-Host "  command:  $Python `"$script`""
    Write-Host "  interval: every $IntervalMinutes minutes"
    exit 0
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Probe enabled MCP targets; state under %LOCALAPPDATA%\local-inference" -Force | Out-Null
Write-Host "Registered $TaskName"

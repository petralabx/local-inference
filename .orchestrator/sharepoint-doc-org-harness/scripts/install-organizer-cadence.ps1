#Requires -Version 5.1
<#
  Organizer cadence (ADR 0023).
  Default is dry-run. -Install registers the job. Until proven: once daily.
  After proof: 06:00 / 10:00 / 14:00 / 18:00 America/Toronto.
#>
[CmdletBinding()]
param(
    [ValidateSet("daily", "every-4h")]
    [string]$Mode = "daily",
    [switch]$Install,
    [switch]$DryRun,
    [string]$TaskName = "VincePersonal-Organizer-Digest",
    [string]$HarnessRoot = ""
)

$ErrorActionPreference = "Stop"
$tz = "America/Toronto"
$fourHourStamps = @("06:00", "10:00", "14:00", "18:00")

$effectiveDryRun = -not $Install
if ($DryRun) { $effectiveDryRun = $true }

if (-not $HarnessRoot) {
    $HarnessRoot = Split-Path -Parent $PSScriptRoot
}

Write-Output "mode=$Mode"
Write-Output "timezone=$tz"
Write-Output "task_name=$TaskName"
Write-Output "harness_root=$HarnessRoot"
if ($Mode -eq "every-4h") {
    Write-Output ("triggers=" + ($fourHourStamps -join ","))
} else {
    Write-Output "triggers=once-daily"
}
Write-Output "action=python -m harness.cli.main digest"

if ($effectiveDryRun) {
    Write-Output "dry-run: Task Scheduler not changed"
    exit 0
}

Write-Output "install: register $TaskName ($Mode) - operator step"
exit 0

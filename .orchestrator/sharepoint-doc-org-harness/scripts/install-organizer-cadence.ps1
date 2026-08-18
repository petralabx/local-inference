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

$runner = Join-Path $HarnessRoot "scripts\run-organizer-digest.ps1"

Write-Output "mode=$Mode"
Write-Output "timezone=$tz"
Write-Output "task_name=$TaskName"
Write-Output "harness_root=$HarnessRoot"
Write-Output "runner=$runner"
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

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Missing digest runner: $runner"
}

$stamps = if ($Mode -eq "every-4h") { $fourHourStamps } else { @("06:00") }
$triggers = foreach ($stamp in $stamps) {
    New-ScheduledTaskTrigger -Daily -At $stamp
}

$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$actionArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$action = New-ScheduledTaskAction -Execute $ps -Argument $actionArguments -WorkingDirectory $HarnessRoot
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 8)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$description = "VincePersonal Organizer digest ($Mode, $tz). Single writer on VTA."

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description $description | Out-Null
Write-Output "install: registered $TaskName ($Mode)"
$info = Get-ScheduledTask -TaskName $TaskName
Write-Output ("state=" + $info.State)
$next = (Get-ScheduledTaskInfo -TaskName $TaskName).NextRunTime
Write-Output ("next_run=" + $next)

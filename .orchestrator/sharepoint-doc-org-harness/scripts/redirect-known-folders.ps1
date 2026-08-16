#Requires -Version 5.1
<#
  One redirect method (ADR 0010 / 0022).
  Default is dry-run. Pass -Apply only on VTA while Vince is present.
  Do not apply on taylorvalton until Vince is at that machine.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Undo,
    [switch]$DryRun,
    [string]$SyncRoot = "C:\Users\vince\OneDrive - Petra Hygienic Systems Int Ltd\Vince Personal - Documents",
    [string]$StatePath = ""
)

$ErrorActionPreference = "Stop"

$Capture = @{
    Desktop   = "00_Inbox\_from_desktop"
    Documents = "00_Inbox\_from_documents"
    Downloads = "00_Inbox\_from_downloads"
}

$FolderIds = @{
    Desktop   = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
    Documents = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"
    Downloads = "{374DE290-123F-4565-9164-39C4925E467B}"
}

if (-not $StatePath) {
    $StatePath = Join-Path $SyncRoot "00_Inbox\_redirect_state.json"
}

$effectiveDryRun = $true
if ($Apply -or $Undo) {
    $effectiveDryRun = $false
}
if ($DryRun) {
    $effectiveDryRun = $true
}

if (-not ([System.Management.Automation.PSTypeName]"KnownFolderNative").Type) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class KnownFolderNative {
  [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
  public static extern int SHSetKnownFolderPath(ref Guid rfid, uint dwFlags, IntPtr hToken, string pszPath);
}
"@
}

function Get-KnownFolderPath {
    param([string]$Name)
    switch ($Name) {
        "Desktop" { [Environment]::GetFolderPath("Desktop") }
        "Documents" { [Environment]::GetFolderPath("MyDocuments") }
        "Downloads" {
            $shell = New-Object -ComObject Shell.Application
            $shell.NameSpace("shell:Downloads").Self.Path
        }
        default { throw "Unknown folder $Name" }
    }
}

function Set-KnownFolderPath {
    param([string]$FolderId, [string]$Path)
    $guid = [Guid]$FolderId
    $code = [KnownFolderNative]::SHSetKnownFolderPath([ref]$guid, 0, [IntPtr]::Zero, $Path)
    if ($code -ne 0) {
        throw ("SHSetKnownFolderPath failed for {0} -> {1} hr=0x{2:X8}" -f $FolderId, $Path, $code)
    }
}

$plan = @()
foreach ($name in @("Desktop", "Documents", "Downloads")) {
    $target = Join-Path $SyncRoot $Capture[$name]
    $current = Get-KnownFolderPath -Name $name
    $plan += [pscustomobject]@{
        Name     = $name
        FolderId = $FolderIds[$name]
        Current  = $current
        Target   = $target
        Capture  = $Capture[$name]
    }
}

Write-Output "mode=$(if ($Undo) { 'undo' } elseif ($effectiveDryRun) { 'dry-run' } else { 'apply' })"
Write-Output "sync_root=$SyncRoot"
Write-Output "taylorvalton=blocked-until-vince-present"
foreach ($row in $plan) {
    Write-Output ("{0} current={1} target={2}" -f $row.Name, $row.Current, $row.Target)
}

if ($effectiveDryRun) {
    Write-Output "dry-run: no known-folder change"
    exit 0
}

if ($Undo) {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        throw "No redirect state at $StatePath"
    }
    $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    foreach ($row in $state.folders) {
        if (-not $row.Previous) { throw "State missing Previous for $($row.Name)" }
        Set-KnownFolderPath -FolderId $row.FolderId -Path $row.Previous
        Write-Output ("restored {0} -> {1}" -f $row.Name, $row.Previous)
    }
    Write-Output "undo: restored previous known-folder targets from $StatePath"
    exit 0
}

$stateObj = [ordered]@{
    savedAt = (Get-Date).ToString("o")
    host    = $env:COMPUTERNAME
    folders = @()
}
foreach ($row in $plan) {
    New-Item -ItemType Directory -Force -Path $row.Target | Out-Null
    $stateObj.folders += [ordered]@{
        Name     = $row.Name
        FolderId = $row.FolderId
        Previous = $row.Current
        Target   = $row.Target
    }
}
$stateDir = Split-Path -Parent $StatePath
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
($stateObj | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $StatePath -Encoding utf8

foreach ($row in $plan) {
    Set-KnownFolderPath -FolderId $row.FolderId -Path $row.Target
    Write-Output ("applied {0} -> {1}" -f $row.Name, $row.Target)
}
Write-Output "apply: Desktop/Documents/Downloads now point at 00_Inbox/_from_*"
exit 0

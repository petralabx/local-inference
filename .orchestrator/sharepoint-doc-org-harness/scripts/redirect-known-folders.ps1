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

# FOLDERID_* (Known Folder GUIDs)
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

$plan = @()
foreach ($name in @("Desktop", "Documents", "Downloads")) {
    $target = Join-Path $SyncRoot $Capture[$name]
    $current = Get-KnownFolderPath -Name $name
    $plan += [pscustomobject]@{
        Name    = $name
        FolderId = $FolderIds[$name]
        Current = $current
        Target  = $target
        Capture = $Capture[$name]
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
    Write-Output "undo: restore previous known-folder targets from $StatePath"
    exit 0
}

Write-Output "apply: would set Desktop/Documents/Downloads into 00_Inbox/_from_* (Vince present only)"
exit 0

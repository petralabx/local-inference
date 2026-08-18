#Requires -Version 5.1
<#
  Hide drained Petra OneDrive source folders (ADR 0020).
  Default is dry-run. Does not hide Vince Personal - Documents.
  Do not apply until unique files are gone. Hash copies, secrets, and code may remain.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$DryRun,
    [string]$PetraRoot = "C:\Users\vince\OneDrive - Petra Hygienic Systems Int Ltd",
    [string[]]$Names = @()
)

$ErrorActionPreference = "Stop"

$effectiveDryRun = -not $Apply
if ($DryRun) { $effectiveDryRun = $true }

$neverHide = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@("Vince Personal - Documents", "Vince Personal") | ForEach-Object { [void]$neverHide.Add($_) }

if (-not $Names -or $Names.Count -lt 1) {
    $Names = @(
        "00_INBOX", "01_Projects", "02_Customers", "03_Finance", "04_Operations",
        "05_HR", "06_Marketing", "07_Admin", "08_Personal", "09_Archive",
        "CursorInbox", "Desktop", "Microsoft Copilot Chat Files",
        "Microsoft Teams Chat Files", "Notebooks", "OLD LAPTOP FILES", "Vince Backup"
    )
}

Write-Output "petra_root=$PetraRoot"
Write-Output ("targets=" + ($Names -join ","))
if ($effectiveDryRun) {
    Write-Output "dry-run: attributes not changed"
}

foreach ($name in $Names) {
    if ($neverHide.Contains($name)) {
        Write-Output "skip_never_hide=$name"
        continue
    }
    $path = Join-Path $PetraRoot $name
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Output "missing=$name"
        continue
    }
    if ($effectiveDryRun) {
        Write-Output "would_hide=$name"
        continue
    }
    $item = Get-Item -LiteralPath $path -Force
    $item.Attributes = $item.Attributes -bor [IO.FileAttributes]::Hidden
    Write-Output "hidden=$name"
}

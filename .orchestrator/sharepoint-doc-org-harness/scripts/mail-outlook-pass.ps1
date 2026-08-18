#Requires -Version 5.1
<#
  Outlook attachment pass into VincePersonal 00_Inbox/_from_mail.
  Does not move mail or invent Outlook folders (ADR 0012 / 0021).
  first-pass: ReceivedTime >= now-90d. remainder: ReceivedTime < now-90d.
#>
[CmdletBinding()]
param(
    [ValidateSet("first-pass", "remainder")]
    [string]$Mode = "remainder",
    [int]$LookbackDays = 90,
    [switch]$DryRun,
    [string]$DestRoot = "C:\Users\vince\OneDrive - Petra Hygienic Systems Int Ltd\Vince Personal - Documents\00_Inbox\_from_mail",
    [string]$ManifestPath = "",
    [string]$ReportPath = "",
    [string]$Mailbox = "vince@petrasoap.com"
)

$ErrorActionPreference = "Stop"

if (-not $ManifestPath) {
    $ManifestPath = Join-Path (Split-Path -Parent $PSScriptRoot) "data\processed_manifest.json"
}
if (-not $ReportPath) {
    $stamp = Get-Date -Format "yyyy-MM-dd"
    $ReportPath = Join-Path (Split-Path -Parent $PSScriptRoot) ("data\reports\mail-{0}-{1}.json" -f $Mode, $stamp)
}

$Since = (Get-Date).ToUniversalTime().AddDays(-$LookbackDays)
$SkipFolders = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@("Deleted Items", "Junk Email", "Outbox", "Sync Issues", "Conversation History", "RSS Feeds", "Calendar", "Contacts", "Tasks", "Notes", "Journal") | ForEach-Object { [void]$SkipFolders.Add($_) }
$SecretNames = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@("credentials.json", "credentials", ".env", "id_rsa", "id_ed25519", "id_dsa") | ForEach-Object { [void]$SecretNames.Add($_) }
$SecretSuffixes = @(".pem", ".pfx", ".p12", ".key")
$InlineName = [regex]"^(image|img|untitled)\d*\.(png|gif|jpe?g|bmp|wmz)$"

function Test-SecretName([string]$name) {
    if ([string]::IsNullOrWhiteSpace($name)) { return $true }
    $n = $name.Trim()
    if ($SecretNames.Contains($n)) { return $true }
    if ($n.StartsWith(".env.")) { return $true }
    $ext = [IO.Path]::GetExtension($n)
    return $SecretSuffixes -contains $ext.ToLowerInvariant()
}

function Get-FreePath([string]$dir, [string]$name) {
    $safe = ($name -replace '[<>:"/\\|?*]', "_").Trim()
    if (-not $safe) { $safe = "attachment.bin" }
    $dest = Join-Path $dir $safe
    if (-not (Test-Path -LiteralPath $dest)) { return $dest }
    $stem = [IO.Path]::GetFileNameWithoutExtension($safe)
    $ext = [IO.Path]::GetExtension($safe)
    $i = 2
    while ($true) {
        $cand = Join-Path $dir ("{0}-{1}{2}" -f $stem, $i, $ext)
        if (-not (Test-Path -LiteralPath $cand)) { return $cand }
        $i++
    }
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $ReportPath) | Out-Null

$seen = New-Object "System.Collections.Generic.HashSet[string]"
if (Test-Path -LiteralPath $ManifestPath) {
    $man = Get-Content -LiteralPath $ManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($h in @($man.sha256)) {
        if ($h) { [void]$seen.Add(([string]$h).ToLowerInvariant()) }
    }
}
Get-ChildItem -LiteralPath $DestRoot -File -ErrorAction SilentlyContinue | ForEach-Object {
    [void]$seen.Add((Get-Sha256 $_.FullName))
}

$outlook = New-Object -ComObject Outlook.Application
$ns = $outlook.GetNamespace("MAPI")
$root = $ns.GetDefaultFolder(6).Store.GetRootFolder()
$sinceLocal = $Since.ToLocalTime().ToString("g")
if ($Mode -eq "remainder") {
    $filter = "[ReceivedTime] < '{0}'" -f $sinceLocal
} else {
    $filter = "[ReceivedTime] >= '{0}'" -f $sinceLocal
}

$folders = New-Object System.Collections.Generic.List[object]
$stack = New-Object System.Collections.Stack
$stack.Push($root)
while ($stack.Count -gt 0) {
    $folder = $stack.Pop()
    $name = $folder.Name
    if ($SkipFolders.Contains($name)) { continue }
    if ($folder.DefaultItemType -eq 0) { $folders.Add($folder) }
    foreach ($child in $folder.Folders) { $stack.Push($child) }
}

$report = [ordered]@{
    started_at                 = (Get-Date).ToUniversalTime().ToString("o")
    mailbox                    = $Mailbox
    mode                       = $Mode
    lookback_days              = $LookbackDays
    since                      = $Since.ToString("o")
    dest                       = $DestRoot
    dry_run                    = [bool]$DryRun
    seeded_hashes              = $seen.Count
    folders_scanned            = 0
    messages_in_window         = 0
    messages_with_attachments  = 0
    saved                      = 0
    skipped_duplicate          = 0
    skipped_inline             = 0
    skipped_secret             = 0
    errors                     = 0
    notes                      = New-Object System.Collections.Generic.List[string]
}

function Write-MailReport {
    $report.unique_hashes = $seen.Count
    $report.updated_at = (Get-Date).ToUniversalTime().ToString("o")
    ($report | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $ReportPath -Encoding utf8
}

Write-Output ("mode={0} since={1} dest={2} seeded_hashes={3} folders={4} dry_run={5}" -f $Mode, $Since.ToString("o"), $DestRoot, $seen.Count, $folders.Count, [bool]$DryRun)

foreach ($folder in $folders) {
    $report.folders_scanned++
    try {
        $items = $folder.Items.Restrict($filter)
    } catch {
        $report.notes.Add(("restrict_fail {0}: {1}" -f $folder.FolderPath, $_.Exception.Message))
        continue
    }
    $count = 0
    try { $count = $items.Count } catch { $count = 0 }
    $report.messages_in_window += $count
    Write-Output ("folder={0} messages={1}" -f $folder.FolderPath, $count)
    foreach ($it in $items) {
        try {
            if ($it.Class -ne 43) { continue }
            $attCount = $it.Attachments.Count
            if ($attCount -lt 1) { continue }
            $report.messages_with_attachments++
            for ($i = 1; $i -le $attCount; $i++) {
                $att = $it.Attachments.Item($i)
                $fileName = [string]$att.FileName
                if ($att.Type -ne 1) {
                    $report.skipped_inline++
                    continue
                }
                if ($InlineName.IsMatch($fileName)) {
                    $report.skipped_inline++
                    continue
                }
                if (Test-SecretName $fileName) {
                    $report.skipped_secret++
                    continue
                }
                if ($DryRun) { continue }
                $dest = Get-FreePath $DestRoot $fileName
                try {
                    $att.SaveAsFile($dest)
                } catch {
                    $report.errors++
                    if ($report.notes.Count -lt 40) {
                        $report.notes.Add(("save_fail {0}: {1}" -f $fileName, $_.Exception.Message))
                    }
                    continue
                }
                if (-not (Test-Path -LiteralPath $dest)) { continue }
                $info = Get-Item -LiteralPath $dest
                if ($info.Length -le 0) {
                    Remove-Item -LiteralPath $dest -Force
                    continue
                }
                $digest = Get-Sha256 $dest
                if ($seen.Contains($digest)) {
                    Remove-Item -LiteralPath $dest -Force
                    $report.skipped_duplicate++
                    continue
                }
                [void]$seen.Add($digest)
                $report.saved++
                if (($report.saved % 50) -eq 0) {
                    Write-MailReport
                    Write-Output ("saved={0} skipped_duplicate={1} errors={2}" -f $report.saved, $report.skipped_duplicate, $report.errors)
                }
            }
        } catch {
            $report.errors++
            if ($report.notes.Count -lt 40) {
                $report.notes.Add($_.Exception.Message)
            }
        }
    }
}

$report.finished_at = (Get-Date).ToUniversalTime().ToString("o")
Write-MailReport
Write-Output ("saved={0} skipped_duplicate={1} skipped_inline={2} skipped_secret={3} errors={4} messages_in_window={5} with_att={6} folders={7}" -f `
    $report.saved, $report.skipped_duplicate, $report.skipped_inline, $report.skipped_secret, $report.errors, $report.messages_in_window, $report.messages_with_attachments, $report.folders_scanned)
Write-Output ("report=$ReportPath")

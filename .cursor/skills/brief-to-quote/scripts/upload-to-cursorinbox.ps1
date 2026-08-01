<#
.SYNOPSIS
  Upload finished report files to the operator's cloud OneDrive CursorInbox via
  Microsoft Graph (app-only), so they're available online immediately without
  waiting for the OneDrive client to sync.

.EXAMPLE
  ./upload-to-cursorinbox.ps1 -Files report.pdf,report.html -Folder Acme-Pricing-2026-06-30
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string[]]$Files,
  [string]$Folder = "",
  [string]$User = "vince@petrasoap.com"
)
$ErrorActionPreference = 'Stop'

. $HOME/.secrets-env.staging.ps1 2>$null
$tenant = $env:MICROSOFT_GRAPH_TENANT_ID
$cid = $env:MICROSOFT_GRAPH_CLIENT_ID
$secret = $env:MICROSOFT_GRAPH_CLIENT_SECRET
if (-not ($tenant -and $cid -and $secret)) {
  Write-Error "Microsoft Graph creds missing. Run: . `$HOME/.secrets-env.staging.ps1"
  exit 1
}

$body = @{ client_id = $cid; client_secret = $secret; scope = "https://graph.microsoft.com/.default"; grant_type = "client_credentials" }
try {
  $tok = Invoke-RestMethod -Method Post -Uri "https://login.microsoftonline.com/$tenant/oauth2/v2.0/token" -Body $body
} catch { Write-Error ("Token request failed: " + $_.Exception.Message); exit 1 }
$hdr = @{ Authorization = "Bearer $($tok.access_token)" }

$prefix = if ($Folder) { "CursorInbox/$Folder" } else { "CursorInbox" }
$ok = 0
foreach ($f in $Files) {
  if (-not (Test-Path $f)) { Write-Warning "skip (missing): $f"; continue }
  $name = Split-Path $f -Leaf
  $uri = "https://graph.microsoft.com/v1.0/users/$User/drive/root:/$prefix/$name`:/content"
  try {
    $r = Invoke-RestMethod -Method Put -Uri $uri -Headers $hdr -InFile $f -ContentType "application/octet-stream"
    Write-Output ("UP OK: " + $r.name + "  " + $r.webUrl)
    $ok++
  } catch { Write-Output ("UP FAIL: " + $name + " :: " + $_.Exception.Message) }
}
if ($ok -eq 0) { Write-Error "No files uploaded."; exit 1 }

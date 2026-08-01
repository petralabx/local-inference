#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Verify a Graph app-only credential end to end: token, consented roles,
  drive read, scoped send, and the negative send that proves mail is restricted.

.DESCRIPTION
  Reads MICROSOFT_GRAPH_TENANT_ID / _CLIENT_ID / _CLIENT_SECRET from the
  environment. Run it on the workstation after sourcing the secrets loader, and
  again from a cloud agent run so both surfaces are proven with the same checks.

  The negative tests are the ones that matter: if the app can send as, or read,
  a mailbox other than the allowed sender, the Exchange application access policy
  is not in effect and the credential can act on any mailbox in the tenant. The
  send probe targets the probe mailbox itself, so a policy failure lands a canary
  in that inbox rather than reaching anyone else.

  A negative test only counts when the allowed send PASSES. A credential denied on
  every mailbox produces the same 403 as a correctly scoped one, so a 403 read in
  isolation is not evidence of anything. On 2026-07-27 that false pass hid a
  credential that could read every mailbox and send as any user for several hours.
  Both negative checks now report INCONCLUSIVE rather than PASS in that state.

  Reads are checked separately from sends because the two are independently
  scoped: an app can be blocked from sending as a mailbox while still reading its
  message bodies.

  Never prints the client secret. Exits non-zero if any check fails.

.EXAMPLE
  . $HOME/.secrets-env.staging.ps1
  ./verify-graph-app.ps1
#>
[CmdletBinding()]
param(
  [string]$DriveUser      = 'vince@petrasoap.com',
  [string]$SendAs         = 'cos@petrasoap.com',
  [string]$MustNotSendAs  = 'vince@petrasoap.com',
  [string]$To             = 'vince@petrasoap.com',
  # The token is the only reliable evidence of effective permission. Removing a
  # permission in App registrations does not always revoke the existing consent
  # grant on the enterprise application, so the role can survive the removal.
  # Mail.Read is deliberate, not drift: retained by operator decision 2026-07-27.
  # It is not needed to send, and the RestrictAccess policy bounds which mailboxes
  # it can reach, so the read-denied probe below still has to pass.
  [string[]]$ExpectedRoles = @(
    'Files.ReadWrite.All', 'Sites.ReadWrite.All', 'Sites.Manage.All',
    'Mail.Send', 'Mail.ReadWrite', 'Mail.Read'
  ),
  [switch]$SkipSend
)

$ErrorActionPreference = 'Stop'
$graph = 'https://graph.microsoft.com/v1.0'

function Get-GraphError($err) {
  $status = $null; $code = $null
  try { $status = [int]$err.Exception.Response.StatusCode } catch { }
  try { $code = ($err.ErrorDetails.Message | ConvertFrom-Json).error.code } catch { }
  if ($code) { "$status $code" } else { "$status $($err.Exception.Message)" }
}

$tenant = $env:MICROSOFT_GRAPH_TENANT_ID
$cid    = $env:MICROSOFT_GRAPH_CLIENT_ID
$secret = $env:MICROSOFT_GRAPH_CLIENT_SECRET
if (-not ($tenant -and $cid -and $secret)) {
  Write-Error "Missing MICROSOFT_GRAPH_* env vars. Workstation: . `$HOME/.secrets-env.staging.ps1"
  exit 1
}
Write-Host "tenant=$tenant  client=$cid" -ForegroundColor DarkGray

$results = [ordered]@{}
$failed  = $false

# 1 - client credentials token
try {
  $tok = Invoke-RestMethod -Method Post -ErrorAction Stop `
    -Uri "https://login.microsoftonline.com/$tenant/oauth2/v2.0/token" `
    -ContentType 'application/x-www-form-urlencoded' `
    -Body @{
      client_id     = $cid
      client_secret = $secret
      scope         = 'https://graph.microsoft.com/.default'
      grant_type    = 'client_credentials'
    }
  $results['token'] = 'PASS'
} catch {
  Write-Host "token  FAIL - $(Get-GraphError $_)" -ForegroundColor Red
  Write-Host "A failure here is credentials or admin consent, not permissions scope." -ForegroundColor Yellow
  exit 1
}
$hdr = @{ Authorization = "Bearer $($tok.access_token)" }

# Consented application roles, decoded from the token itself
try {
  $p = $tok.access_token.Split('.')[1].Replace('-', '+').Replace('_', '/')
  switch ($p.Length % 4) { 2 { $p += '==' } 3 { $p += '=' } }
  $roles = ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | ConvertFrom-Json).roles
  Write-Host "roles ($($roles.Count)): $(($roles | Sort-Object) -join ', ')" -ForegroundColor DarkGray

  $excess  = $roles | Where-Object { $_ -notin $ExpectedRoles } | Sort-Object
  $missing = $ExpectedRoles | Where-Object { $_ -notin $roles } | Sort-Object
  if ($missing) { $results['roles-expected'] = "FAIL - not granted: $($missing -join ', ')"; $failed = $true }
  if ($excess) {
    $results['roles-excess'] = "FAIL - $($excess.Count) beyond brief: $($excess -join ', ')"
    $failed = $true
  } else {
    $results['roles-excess'] = 'PASS (no roles beyond brief)'
  }
} catch {
  Write-Host "roles: (could not decode token)" -ForegroundColor DarkGray
  $results['roles-excess'] = 'INCONCLUSIVE - could not decode token'
  $failed = $true
}

# 2 - drive read
try {
  $r = Invoke-RestMethod -Headers $hdr -Method Get -ErrorAction Stop `
    -Uri "$graph/users/$DriveUser/drive/root/children?`$select=name&`$top=5"
  $results['drive-read'] = "PASS ($($r.value.Count) items)"
} catch {
  $results['drive-read'] = "FAIL - $(Get-GraphError $_)"
  $failed = $true
}

function New-MailBody($subject) {
  @{
    message = @{
      subject      = $subject
      body         = @{ contentType = 'Text'; content = "Automated verification from app $cid at $(Get-Date -Format o)." }
      toRecipients = @(@{ emailAddress = @{ address = $To } })
    }
    saveToSentItems = $false
  } | ConvertTo-Json -Depth 8
}

if ($SkipSend) {
  $results['send-as-allowed'] = 'SKIPPED'
  $results['send-as-denied']  = 'SKIPPED'
  $results['read-denied']     = 'SKIPPED'
} else {
  # 3 - send as the allowed mailbox (expect 202)
  try {
    Invoke-RestMethod -Headers $hdr -Method Post -ErrorAction Stop `
      -Uri "$graph/users/$SendAs/sendMail" -ContentType 'application/json' `
      -Body (New-MailBody "Graph verify - allowed send as $SendAs") | Out-Null
    $results['send-as-allowed'] = "PASS (sent as $SendAs)"
  } catch {
    $results['send-as-allowed'] = "FAIL - $(Get-GraphError $_)"
    $failed = $true
  }

  # 4 - negative: sending as any other mailbox must be refused
  if ($MustNotSendAs -and $MustNotSendAs -ne $SendAs) {
    try {
      Invoke-RestMethod -Headers $hdr -Method Post -ErrorAction Stop `
        -Uri "$graph/users/$MustNotSendAs/sendMail" -ContentType 'application/json' `
        -Body (New-MailBody "CANARY - unrestricted send as $MustNotSendAs") | Out-Null
      $results['send-as-denied'] = "FAIL - send as $MustNotSendAs SUCCEEDED (tenant-wide send)"
      $failed = $true
    } catch {
      $e = Get-GraphError $_
      if ($e -notmatch '403') {
        $results['send-as-denied'] = "INCONCLUSIVE - expected 403, got $e"
        $failed = $true
      } elseif ($results['send-as-allowed'] -notlike 'PASS*') {
        # A 403 here proves nothing while the allowed send is also failing: a
        # credential denied on every mailbox looks identical to a working scope.
        # This exact false pass masked a tenant-wide exposure on 2026-07-27.
        $results['send-as-denied'] = "INCONCLUSIVE - denied, but allowed send also failed"
        $failed = $true
      } else {
        $results['send-as-denied'] = "PASS (refused: $e)"
      }
    }
  }

  # 5 - the send scope says nothing about reads. An app can be unable to send as
  # a mailbox while still reading its message bodies.
  if ($MustNotSendAs -and $MustNotSendAs -ne $SendAs) {
    try {
      Invoke-RestMethod -Headers $hdr -Method Get -ErrorAction Stop `
        -Uri "$graph/users/$MustNotSendAs/messages?`$top=1&`$select=subject" | Out-Null
      $results['read-denied'] = "FAIL - can read $MustNotSendAs message bodies"
      $failed = $true
    } catch {
      $e = Get-GraphError $_
      if ($e -notmatch '403') {
        $results['read-denied'] = "INCONCLUSIVE - expected 403, got $e"
        $failed = $true
      } elseif ($results['send-as-allowed'] -notlike 'PASS*') {
        $results['read-denied'] = "INCONCLUSIVE - denied, but allowed send also failed"
        $failed = $true
      } else {
        $results['read-denied'] = "PASS (refused: $e)"
      }
    }
  }
}

Write-Host "`n--- Results ---" -ForegroundColor Cyan
foreach ($k in $results.Keys) {
  $v = $results[$k]
  $c = if ($v -like 'PASS*') { 'Green' } elseif ($v -like 'SKIPPED*') { 'DarkGray' } else { 'Red' }
  Write-Host ("{0,-18} {1}" -f $k, $v) -ForegroundColor $c
}

if ($failed) {
  Write-Host "`n401 anywhere = credentials or admin consent, not scope." -ForegroundColor Yellow
  if ($results['send-as-allowed'] -like 'FAIL*') {
    Write-Host "The allowed send failed, so no scope conclusion can be drawn from this run." -ForegroundColor Yellow
    Write-Host "A blanket 403 mimics a working restriction. Re-run once the allowed send passes." -ForegroundColor Yellow
    Write-Host "Policy changes can take ~30 min; that is the usual cause immediately after a change." -ForegroundColor Yellow
  }
  if ($results['send-as-denied'] -like 'FAIL*' -or $results['read-denied'] -like 'FAIL*') {
    Write-Host "TENANT-WIDE MAILBOX ACCESS DETECTED - this credential is not restricted." -ForegroundColor Red
    Write-Host "Fix with scope-mail-to-mailbox.ps1. Note that RBAC role assignments are" -ForegroundColor Red
    Write-Host "additive grants and will NOT restrict; the RestrictAccess policy is required." -ForegroundColor Red
  }
  if ($results['roles-excess'] -like 'FAIL*') {
    Write-Host "Roles beyond the brief are granted. Removing a permission in App registrations" -ForegroundColor Red
    Write-Host "does not always revoke consent - check Enterprise applications > Permissions." -ForegroundColor Red
  }
  exit 1
}

Write-Host "`nAll checks passed." -ForegroundColor Green

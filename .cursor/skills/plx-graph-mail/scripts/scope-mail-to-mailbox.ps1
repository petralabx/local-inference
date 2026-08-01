#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Restrict an app-only Graph credential so Mail.Send can only act on one mailbox.

.DESCRIPTION
  Application Mail.Send is tenant-wide by default: the app can send as ANY
  mailbox. This creates a mail-enabled security group containing only the
  allowed sender and binds an Exchange application access policy to it, then
  verifies both the allow and the deny direction.

  Policy changes can take up to an hour to propagate. A Denied result for the
  allowed mailbox immediately after creation is usually propagation, not failure.

  Requires Exchange administrator rights and the ExchangeOnlineManagement module.

.EXAMPLE
  ./scope-mail-to-mailbox.ps1 -AppId <client-id> -AllowedMailbox cos@petrasoap.com `
    -DeniedProbe vince@petrasoap.com
#>
[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory)][string]$AppId,
  [Parameter(Mandatory)][string]$AllowedMailbox,
  [string]$DeniedProbe,
  [string]$ScopeGroupAddress = 'graph-cursor-mailscope@petrasoap.com',
  [string]$ScopeGroupName    = 'GraphCursorMailScope',
  [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name ExchangeOnlineManagement)) {
  throw "ExchangeOnlineManagement module not found. Install-Module ExchangeOnlineManagement -Scope CurrentUser"
}
Import-Module ExchangeOnlineManagement -ErrorAction Stop

if (-not (Get-ConnectionInformation -ErrorAction SilentlyContinue)) {
  Write-Host "Connecting to Exchange Online..." -ForegroundColor Cyan
  Connect-ExchangeOnline -ShowBanner:$false
}

if (-not $VerifyOnly) {
  $group = Get-DistributionGroup -Identity $ScopeGroupAddress -ErrorAction SilentlyContinue
  if (-not $group) {
    if ($PSCmdlet.ShouldProcess($ScopeGroupAddress, 'Create mail-enabled security group')) {
      New-DistributionGroup -Name $ScopeGroupName -Type Security `
        -PrimarySmtpAddress $ScopeGroupAddress -Members $AllowedMailbox | Out-Null
      Write-Host "Created scope group $ScopeGroupAddress" -ForegroundColor Green
    }
  } else {
    Write-Host "Scope group $ScopeGroupAddress already exists" -ForegroundColor DarkGray
    $members = Get-DistributionGroupMember -Identity $ScopeGroupAddress |
      Select-Object -ExpandProperty PrimarySmtpAddress
    if ($members -notcontains $AllowedMailbox) {
      Add-DistributionGroupMember -Identity $ScopeGroupAddress -Member $AllowedMailbox
      Write-Host "Added $AllowedMailbox to scope group" -ForegroundColor Green
    }
    # Anything else in this group can also be impersonated by the app.
    $extra = $members | Where-Object { $_ -ne $AllowedMailbox }
    if ($extra) {
      Write-Warning "Scope group also contains: $($extra -join ', ')"
    }
  }

  $existing = Get-ApplicationAccessPolicy -ErrorAction SilentlyContinue |
    Where-Object { $_.AppId -eq $AppId }
  if ($existing) {
    Write-Host "Policy already present for AppId $AppId" -ForegroundColor DarkGray
  } elseif ($PSCmdlet.ShouldProcess($AppId, 'Create RestrictAccess application access policy')) {
    New-ApplicationAccessPolicy -AppId $AppId `
      -PolicyScopeGroupId $ScopeGroupAddress `
      -AccessRight RestrictAccess `
      -Description "Cursor Graph app restricted to $AllowedMailbox" | Out-Null
    Write-Host "Created RestrictAccess policy for $AppId" -ForegroundColor Green
  }
}

Write-Host "`n--- Verification ---" -ForegroundColor Cyan
$allow = Test-ApplicationAccessPolicy -Identity $AllowedMailbox -AppId $AppId
Write-Host ("{0,-32} {1}" -f $AllowedMailbox, $allow.AccessCheckResult)

$failed = $allow.AccessCheckResult -ne 'Granted'

if ($DeniedProbe) {
  $deny = Test-ApplicationAccessPolicy -Identity $DeniedProbe -AppId $AppId
  Write-Host ("{0,-32} {1}" -f $DeniedProbe, $deny.AccessCheckResult)
  if ($deny.AccessCheckResult -ne 'Denied') {
    Write-Warning "$DeniedProbe is NOT denied - the app can still send as this mailbox."
    $failed = $true
  }
}

if ($failed) {
  Write-Warning "Verification incomplete. Policy propagation can take up to 1 hour; re-run with -VerifyOnly."
  exit 1
}

Write-Host "`nMail send scope confirmed: $AllowedMailbox only." -ForegroundColor Green

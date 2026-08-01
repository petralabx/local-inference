#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Diagnose why an app-only Graph credential is denied on all mailbox operations.

.DESCRIPTION
  Run when Mail.Send returns 403 ErrorAccessDenied even for the mailbox an
  application access policy is supposed to allow. Distinguishes three causes:

    1. The allowed address is not a normal mailbox.
    2. The access policy bound to a scope Exchange could not resolve.
    3. The tenant has moved to RBAC for Applications, where an app with no
       Exchange service principal and no role assignment is denied everywhere
       even though the legacy policy still reports Granted.

  Connects to Exchange Online if no session is active. Read-only; changes nothing.

.EXAMPLE
  ./diagnose-mail-scope.ps1 -AppId 34cd4ff8-3797-4c98-a365-f2c0e2db8565 -AllowedMailbox cos@petrasoap.com
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$AppId,
  [Parameter(Mandatory)][string]$AllowedMailbox,
  [string]$ScopeGroupAddress = 'graph-cursor-mailscope@petrasoap.com'
)

$ErrorActionPreference = 'Continue'

Import-Module ExchangeOnlineManagement -ErrorAction Stop
if (-not (Get-ConnectionInformation -ErrorAction SilentlyContinue)) {
  Write-Host "Connecting to Exchange Online (browser sign-in)..." -ForegroundColor Cyan
  Connect-ExchangeOnline -ShowBanner:$false
} else {
  Write-Host "Reusing existing Exchange Online session." -ForegroundColor DarkGray
}

function Section($n) { Write-Host "`n=== $n ===" -ForegroundColor Cyan }

Section "1. Mailbox type for $AllowedMailbox"
try {
  Get-Mailbox $AllowedMailbox -ErrorAction Stop |
    Format-List DisplayName, PrimarySmtpAddress, RecipientTypeDetails, ExternalDirectoryObjectId
} catch {
  Write-Warning "Get-Mailbox failed: $($_.Exception.Message)"
}

Section "2. Application access policy binding"
$pol = Get-ApplicationAccessPolicy -ErrorAction SilentlyContinue | Where-Object { $_.AppId -eq $AppId }
if ($pol) {
  $pol | Format-List AppId, AccessRight, ScopeName, ScopeIdentity, Description
  if (-not $pol.ScopeName) { Write-Warning "ScopeName is empty - the policy scope did not resolve." }
} else {
  Write-Warning "No application access policy found for $AppId."
}

Section "3. Scope group membership"
try {
  Get-DistributionGroupMember $ScopeGroupAddress -ErrorAction Stop |
    Format-Table DisplayName, PrimarySmtpAddress, RecipientType -AutoSize
} catch {
  Write-Warning "Get-DistributionGroupMember failed: $($_.Exception.Message)"
}

Section "4. RBAC for Applications (is the tenant on the new model?)"
$sp = Get-ServicePrincipal -Identity $AppId -ErrorAction SilentlyContinue
if ($sp) {
  $sp | Format-List DisplayName, AppId, ServicePrincipalName, ObjectId
} else {
  Write-Host "No Exchange service principal registered for $AppId." -ForegroundColor Yellow
}

$ra = Get-ManagementRoleAssignment -RoleAssignee $AppId -ErrorAction SilentlyContinue
if ($ra) {
  $ra | Format-Table Name, Role, RoleAssigneeName, CustomResourceScope -AutoSize
} else {
  Write-Host "No management role assignments for $AppId." -ForegroundColor Yellow
}

Section "Interpretation"
if (-not $sp -and $pol -and $pol.ScopeName) {
  Write-Host "Legacy policy is bound correctly but the app has no Exchange service" -ForegroundColor Yellow
  Write-Host "principal. If this tenant enforces RBAC for Applications, that is the" -ForegroundColor Yellow
  Write-Host "cause of the blanket 403 - the legacy policy is being ignored." -ForegroundColor Yellow
} elseif ($pol -and -not $pol.ScopeName) {
  Write-Host "Policy scope did not resolve - recreate it once the group has replicated." -ForegroundColor Yellow
} elseif (-not $pol) {
  Write-Host "No policy present - mail access is unrestricted or blocked elsewhere." -ForegroundColor Yellow
} else {
  Write-Host "Policy and service principal both present; likely still propagating." -ForegroundColor Yellow
}

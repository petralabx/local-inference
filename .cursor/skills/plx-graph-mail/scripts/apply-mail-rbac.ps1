#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Grant an app-only Graph credential scoped Mail.Send via Exchange RBAC for Applications.

.DESCRIPTION
  Registers the app as an Exchange service principal, creates a management scope
  limited to one mailbox, and assigns mail roles against that scope.

  Runs read-only by default and reports whether the tenant supports RBAC for
  Applications. Pass -Apply to make changes.

  READ THIS FIRST - these role assignments are ADDITIVE GRANTS, NOT RESTRICTIONS.

  Verified empirically in the petrasoap.com tenant on 2026-07-27: with
  'Application Mail.Send' and 'Application Mail.ReadWrite' assigned against a
  single-mailbox scope, and Test-ServicePrincipalAuthorization reporting
  InScope=True, the app could still read every mailbox in the tenant AND send as
  any user. Scoped assignments add access; they do not remove the tenant-wide
  access that Entra admin consent already grants.

  The mechanism that actually restricts which mailboxes an app-only credential can
  touch is the legacy RestrictAccess application access policy - see
  scope-mail-to-mailbox.ps1. Do not treat this script as a substitute for it.

  Corollary: RBAC cannot limit WHAT operations the app performs either. A consented
  permission with no scoped assignment stays tenant-wide, so Mail.Read,
  MailboxFolder.*, MailboxItem.*, MailboxSettings.* and MailTips.* remain global
  unless removed from the app registration. Grant only what the app needs.

.EXAMPLE
  # Preflight, changes nothing
  ./apply-mail-rbac.ps1 -AppId <appId> -SpObjectId <sp-object-id> -AllowedMailbox cos@petrasoap.com

.EXAMPLE
  # Apply
  ./apply-mail-rbac.ps1 -AppId <appId> -SpObjectId <sp-object-id> -AllowedMailbox cos@petrasoap.com -Apply
#>
[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory)][string]$AppId,
  [Parameter(Mandatory)][string]$SpObjectId,
  [Parameter(Mandatory)][string]$AllowedMailbox,
  [string]$DisplayName = 'PLX_Cursor_Graph',
  [string]$ScopeName   = 'CursorGraphMailScope',
  # Each Graph mail permission needs its own Exchange role assignment. Consenting
  # Mail.ReadWrite in Entra does nothing until 'Application Mail.ReadWrite' is
  # assigned here as well.
  [string[]]$Roles     = @('Application Mail.Send'),
  [switch]$Apply,
  # Removing the legacy policy removes the only mechanism that restricts which
  # mailboxes the app can reach. Requires -IUnderstandThisRemovesAllRestriction.
  [switch]$RemoveLegacyPolicy,
  [switch]$IUnderstandThisRemovesAllRestriction
)

$ErrorActionPreference = 'Stop'

Import-Module ExchangeOnlineManagement -ErrorAction Stop
if (-not (Get-ConnectionInformation -ErrorAction SilentlyContinue)) {
  Write-Host "Connecting to Exchange Online (browser sign-in)..." -ForegroundColor Cyan
  Connect-ExchangeOnline -ShowBanner:$false
}

Write-Host "`n=== Preflight ===" -ForegroundColor Cyan

$hasCmdlet = [bool](Get-Command New-ServicePrincipal -ErrorAction SilentlyContinue)
Write-Host ("{0,-38} {1}" -f 'New-ServicePrincipal available', $hasCmdlet)

$rolesPresent = $true
foreach ($r in $Roles) {
  $found = [bool](Get-ManagementRole -Identity $r -ErrorAction SilentlyContinue)
  Write-Host ("{0,-38} {1}" -f "Role '$r' present", $found)
  if (-not $found) { $rolesPresent = $false }
}

$sp = Get-ServicePrincipal -Identity $AppId -ErrorAction SilentlyContinue
Write-Host ("{0,-38} {1}" -f 'App registered in Exchange', [bool]$sp)

$scope = Get-ManagementScope -Identity $ScopeName -ErrorAction SilentlyContinue
Write-Host ("{0,-38} {1}" -f "Scope '$ScopeName' exists", [bool]$scope)

$legacy = Get-ApplicationAccessPolicy -ErrorAction SilentlyContinue | Where-Object { $_.AppId -eq $AppId }
Write-Host ("{0,-38} {1}" -f 'Legacy access policy present', [bool]$legacy)

$assigned = Get-ManagementRoleAssignment -RoleAssignee $AppId -ErrorAction SilentlyContinue
foreach ($r in $Roles) {
  $have = [bool]($assigned | Where-Object { $_.Role -eq $r })
  Write-Host ("{0,-38} {1}" -f "  assigned: $r", $have)
}

if (-not $hasCmdlet -or -not $rolesPresent) {
  Write-Host "`nThis tenant does not expose RBAC for Applications." -ForegroundColor Yellow
  Write-Host "The legacy application access policy is the only mechanism; give it more time." -ForegroundColor Yellow
  return
}

if (-not $Apply) {
  Write-Host "`nPreflight only. Re-run with -Apply to make changes." -ForegroundColor DarkGray
  return
}

Write-Host "`n=== Applying ===" -ForegroundColor Cyan

if (-not $sp) {
  if ($PSCmdlet.ShouldProcess($AppId, 'Register Exchange service principal')) {
    New-ServicePrincipal -AppId $AppId -ObjectId $SpObjectId -DisplayName $DisplayName | Out-Null
    Write-Host "Registered service principal for $AppId" -ForegroundColor Green
  }
} else {
  Write-Host "Service principal already registered" -ForegroundColor DarkGray
}

if (-not $scope) {
  if ($PSCmdlet.ShouldProcess($ScopeName, "Create management scope for $AllowedMailbox")) {
    New-ManagementScope -Name $ScopeName `
      -RecipientRestrictionFilter "PrimarySmtpAddress -eq '$AllowedMailbox'" | Out-Null
    Write-Host "Created scope $ScopeName limited to $AllowedMailbox" -ForegroundColor Green
  }
} else {
  Write-Host "Scope $ScopeName already exists" -ForegroundColor DarkGray
}

foreach ($r in $Roles) {
  $existing = Get-ManagementRoleAssignment -RoleAssignee $AppId -ErrorAction SilentlyContinue |
    Where-Object { $_.Role -eq $r }
  if ($existing) {
    Write-Host "Role assignment already present: $r" -ForegroundColor DarkGray
    continue
  }
  # Assignment names must be unique per role.
  $name = 'CursorGraph' + (($r -replace '^Application\s+', '') -replace '[^A-Za-z0-9]', '')
  if ($PSCmdlet.ShouldProcess($AppId, "Assign '$r' scoped to $ScopeName")) {
    New-ManagementRoleAssignment -Name $name -App $AppId `
      -Role $r -CustomResourceScope $ScopeName | Out-Null
    Write-Host "Assigned '$r' scoped to $ScopeName (as $name)" -ForegroundColor Green
  }
}

if ($RemoveLegacyPolicy -and $legacy) {
  if (-not $IUnderstandThisRemovesAllRestriction) {
    Write-Warning "REFUSING to remove the legacy application access policy."
    Write-Warning "It is the only mechanism restricting which mailboxes this app can reach."
    Write-Warning "The role assignments above are additive grants and will NOT replace it."
    Write-Warning "Re-run with -IUnderstandThisRemovesAllRestriction only if that is genuinely intended."
  } elseif ($PSCmdlet.ShouldProcess($AppId, 'Remove legacy application access policy')) {
    Remove-ApplicationAccessPolicy -Identity $legacy.Identity -Confirm:$false
    Write-Warning "Removed legacy application access policy - this app now has TENANT-WIDE mailbox access."
    Write-Warning "Verify with verify-graph-app.ps1 and re-scope via scope-mail-to-mailbox.ps1."
  }
}

Write-Host "`n=== Result ===" -ForegroundColor Cyan
Get-ManagementRoleAssignment -RoleAssignee $AppId -ErrorAction SilentlyContinue |
  Format-Table Name, Role, CustomResourceScope -AutoSize

Write-Host "RBAC changes can take time to take effect. Verify with:" -ForegroundColor Yellow
Write-Host "  verify-graph-app.ps1" -ForegroundColor Yellow

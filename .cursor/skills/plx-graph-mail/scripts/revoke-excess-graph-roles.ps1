#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Revoke Graph application permissions that were consented but are not needed.

.DESCRIPTION
  Deleting a permission under App registrations > API permissions only changes what the
  app REQUESTS. The grant itself is an appRoleAssignment on the service principal and
  survives that deletion, so the app keeps minting tokens carrying the old roles. This
  removes the assignments themselves.

  Read-only by default: it prints what is granted, what would be kept, and what would be
  revoked. Pass -Apply to make the change.

  Verify afterwards with verify-graph-app.ps1, which decodes the token's roles claim. The
  token is the only reliable evidence - the portal can show a permission as removed while
  the grant is still live.

  Requires the Microsoft.Graph module and an admin able to consent
  AppRoleAssignment.ReadWrite.All.

.EXAMPLE
  # Preflight
  ./revoke-excess-graph-roles.ps1 -AppId 34cd4ff8-3797-4c98-a365-f2c0e2db8565

.EXAMPLE
  # Apply
  ./revoke-excess-graph-roles.ps1 -AppId 34cd4ff8-3797-4c98-a365-f2c0e2db8565 -Apply
#>
[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory)][string]$AppId,
  [string[]]$Keep = @(
    'Files.ReadWrite.All', 'Sites.ReadWrite.All', 'Sites.Manage.All',
    'Mail.Send', 'Mail.ReadWrite'
  ),
  [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$GraphAppId = '00000003-0000-0000-c000-000000000000'

if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Applications)) {
  throw "Microsoft.Graph module not found. Install-Module Microsoft.Graph -Scope CurrentUser"
}
Import-Module Microsoft.Graph.Applications -ErrorAction Stop

if (-not (Get-MgContext)) {
  Write-Host "Signing in to Microsoft Graph..." -ForegroundColor Cyan
  Connect-MgGraph -Scopes 'Application.Read.All', 'AppRoleAssignment.ReadWrite.All' -NoWelcome
}

$sp = Get-MgServicePrincipal -Filter "appId eq '$AppId'" -ErrorAction Stop
if (-not $sp) { throw "No service principal found for appId $AppId" }
Write-Host "app: $($sp.DisplayName)  sp: $($sp.Id)" -ForegroundColor DarkGray

$graphSp = Get-MgServicePrincipal -Filter "appId eq '$GraphAppId'" -ErrorAction Stop
# appRoleId -> permission name, e.g. Mail.Send
$roleMap = @{}
foreach ($r in $graphSp.AppRoles) { $roleMap[$r.Id] = $r.Value }

$assignments = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id -All |
  Where-Object { $_.ResourceId -eq $graphSp.Id }

if (-not $assignments) {
  Write-Host "No Microsoft Graph application permissions are granted." -ForegroundColor Green
  return
}

$rows = foreach ($a in $assignments) {
  $name = $roleMap[$a.AppRoleId]
  if (-not $name) { $name = "(unknown $($a.AppRoleId))" }
  [pscustomobject]@{
    Name     = $name
    Action   = if ($name -in $Keep) { 'keep' } else { 'REVOKE' }
    Id       = $a.Id
  }
}

Write-Host "`n=== Granted Microsoft Graph application permissions ($($rows.Count)) ===" -ForegroundColor Cyan
foreach ($r in ($rows | Sort-Object Action, Name)) {
  $c = if ($r.Action -eq 'keep') { 'Green' } else { 'Yellow' }
  Write-Host ("  {0,-8} {1}" -f $r.Action, $r.Name) -ForegroundColor $c
}

$missing = $Keep | Where-Object { $_ -notin $rows.Name }
if ($missing) { Write-Warning "Expected but NOT granted: $($missing -join ', ')" }

$toRevoke = $rows | Where-Object Action -eq 'REVOKE'
if (-not $toRevoke) {
  Write-Host "`nNothing to revoke - granted set already matches the brief." -ForegroundColor Green
  return
}

if (-not $Apply) {
  Write-Host "`nPreflight only. $($toRevoke.Count) would be revoked. Re-run with -Apply." -ForegroundColor DarkGray
  return
}

Write-Host "`n=== Revoking ===" -ForegroundColor Cyan
$failed = 0
foreach ($r in $toRevoke) {
  if (-not $PSCmdlet.ShouldProcess($r.Name, 'Revoke app role assignment')) { continue }
  try {
    Remove-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id `
      -AppRoleAssignmentId $r.Id -ErrorAction Stop
    Write-Host "  revoked $($r.Name)" -ForegroundColor Green
  } catch {
    Write-Host "  FAILED  $($r.Name) - $($_.Exception.Message)" -ForegroundColor Red
    $failed++
  }
}

Write-Host "`nRevocation is not always immediate in freshly minted tokens." -ForegroundColor Yellow
Write-Host "Confirm with:  verify-graph-app.ps1" -ForegroundColor Yellow
if ($failed) { exit 1 }

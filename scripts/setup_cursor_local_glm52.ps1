# DEPRECATED: use setup_cursor_profiles_local_glm.ps1 instead (safe Default + Local GLM profiles).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/setup_cursor_local_glm52.ps1

$ErrorActionPreference = "Stop"
$profilesScript = Join-Path $PSScriptRoot "setup_cursor_profiles_local_glm.ps1"
Write-Host "Note: redirecting to setup_cursor_profiles_local_glm.ps1 (safer profile split)."
& $profilesScript
exit $LASTEXITCODE

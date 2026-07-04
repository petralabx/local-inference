# One-command Cursor profile setup: clean Default + configure Local GLM.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/setup_cursor_profiles_local_glm.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pyScript = Join-Path $repoRoot "scripts/setup_cursor_profiles_local_glm.py"

Write-Host "Configuring Cursor Default + Local GLM profiles..."
Write-Host "(Cursor can stay open, but fully quit and reopen afterward.)"
Write-Host ""

python $pyScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Next: quit ALL Cursor windows, reopen."
Write-Host "  Default profile -> Composer / Claude (normal work)"
Write-Host "  Local GLM profile -> local-glm52 only (drafts / local sessions)"

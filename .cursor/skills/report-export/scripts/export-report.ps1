<#
.SYNOPSIS
  Convert a Markdown or HTML report to PDF (Edge/Chrome headless) and Word (.docx via pandoc),
  optionally copying outputs to the operator's OneDrive CursorInbox for sharing.

.EXAMPLE
  ./export-report.ps1 -InputPath report.md -Share
  ./export-report.ps1 -InputPath report.html -OutDir out -Name Q3-Pricing
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$InputPath,
  [string]$OutDir,
  [string]$Name,
  [string]$Css,
  [switch]$Pdf = $true,
  [switch]$Docx = $true,
  [switch]$Share
)
$ErrorActionPreference = 'Stop'

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
}
function Find-Browser {
  $cands = @(
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
  )
  foreach ($c in $cands) { if (Test-Path $c) { return $c } }
  return $null
}
function Ensure-Pandoc {
  Refresh-Path
  if (Get-Command pandoc -ErrorAction SilentlyContinue) { return $true }
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Installing pandoc (winget, user scope)..."
    winget install --id JohnMacFarlane.Pandoc -e --source winget --scope user `
      --accept-package-agreements --accept-source-agreements --disable-interactivity | Out-Null
    Refresh-Path
  }
  return [bool](Get-Command pandoc -ErrorAction SilentlyContinue)
}

$in = (Resolve-Path $InputPath).Path
$ext = [IO.Path]::GetExtension($in).ToLower()
if (-not $OutDir) { $OutDir = Split-Path $in -Parent }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (-not $Name) { $Name = [IO.Path]::GetFileNameWithoutExtension($in) }
if (-not $Css) { $Css = Join-Path (Split-Path $PSScriptRoot -Parent) "assets/report.css" }

# Resolve an HTML file to feed the PDF engine.
$htmlForPdf = $null
if ($ext -in ".html", ".htm") {
  $htmlForPdf = $in
}
elseif ($ext -in ".md", ".markdown") {
  if (-not (Ensure-Pandoc)) { throw "pandoc is required to convert Markdown but could not be installed." }
  $htmlForPdf = Join-Path $OutDir "$Name.html"
  $cssArgs = @(); if (Test-Path $Css) { $cssArgs = @("--css", $Css) }
  pandoc $in -o $htmlForPdf --standalone --embed-resources @cssArgs --metadata title="$Name"
}
else { throw "Unsupported input '$ext'. Provide a .md or .html file." }

$results = @()

if ($Pdf) {
  $browser = Find-Browser
  $pdfOut = Join-Path $OutDir "$Name.pdf"
  if ($browser) {
    $uri = ([uri]((Resolve-Path $htmlForPdf).Path)).AbsoluteUri
    & $browser --headless=new --disable-gpu --no-pdf-header-footer `
      --user-data-dir="$env:TEMP\report-export-profile" --virtual-time-budget=6000 `
      "--print-to-pdf=$pdfOut" $uri 2>$null
    Start-Sleep -Milliseconds 1500
    if (Test-Path $pdfOut) { $results += $pdfOut } else { Write-Warning "PDF was not produced." }
  }
  else { Write-Warning "No Edge/Chrome found; skipping PDF." }
}

if ($Docx) {
  if (Ensure-Pandoc) {
    $docxOut = Join-Path $OutDir "$Name.docx"
    pandoc $in -o $docxOut
    if (Test-Path $docxOut) { $results += $docxOut }
  }
  else { Write-Warning "pandoc unavailable; skipping DOCX." }
}

if ($Share) {
  $inbox = Get-ChildItem $HOME -Directory -Filter "OneDrive*" -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName "CursorInbox" } |
    Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($inbox) {
    $dest = Join-Path $inbox $Name
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    foreach ($r in $results) { Copy-Item $r -Destination $dest -Force }
    if (Test-Path $htmlForPdf) { Copy-Item $htmlForPdf -Destination $dest -Force -ErrorAction SilentlyContinue }
    Write-Output "SHARED -> $dest"
  }
  else { Write-Warning "No OneDrive CursorInbox found; skipped sharing." }
}

Write-Output "OUTPUTS:"
$results | ForEach-Object { Write-Output "  $_" }
if (-not $results) { throw "No outputs were produced." }

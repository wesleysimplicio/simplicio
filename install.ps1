#!/usr/bin/env pwsh
# install.ps1 — Install the simplicio binary on Windows
#
# Usage:
#   powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex"
#
# Environment variables:
#   SIMPLICIO_VERSION  - pin a specific version (default: latest)
#   SIMPLICIO_BIN_DIR  - custom install directory

param(
  [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$Repo = "wesleysimplicio/simplicio"
$BinName = "simplicio.exe"

# Detect architecture. Published Windows asset is simplicio-windows-x64.
$Arch = "x64"

Write-Host "==> simplicio installer for Windows ($Arch)"

# Determine install dir
if ($env:SIMPLICIO_BIN_DIR) {
  $InstallDir = $env:SIMPLICIO_BIN_DIR
} else {
  $InstallDir = "$env:USERPROFILE\.local\bin"
}
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Determine version
if (-not $Version -and $env:SIMPLICIO_VERSION) {
  $Version = $env:SIMPLICIO_VERSION
}
if (-not $Version) {
  Write-Host "==> fetching latest version..."
  try {
    $latest = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -ErrorAction Stop
    $Version = $latest.tag_name
    Write-Host "  ✓ latest version: $Version"
  } catch {
    $Version = "latest"
    Write-Host "  ⚠ could not determine latest, using '$Version'"
  }
}

# Download. Release assets are raw binaries named simplicio-windows-x64
# (no tarball). Try the pinned tag then the 'latest' redirect.
$Asset = "simplicio-windows-$Arch"
$DestPath = Join-Path $InstallDir $BinName
$urls = @(
  "https://github.com/$Repo/releases/download/$Version/$Asset",
  "https://github.com/$Repo/releases/latest/download/$Asset"
)
$dlOk = $false
foreach ($u in $urls) {
  Write-Host "==> downloading $u"
  try {
    Invoke-WebRequest -Uri $u -OutFile $DestPath -UseBasicParsing -ErrorAction Stop
    if ((Test-Path $DestPath) -and ((Get-Item $DestPath).Length -gt 0)) { $dlOk = $true; break }
  } catch { Write-Host "  ⚠ failed: $($_.Exception.Message)" }
}
if (-not $dlOk) {
  Write-Error "Download failed for $Asset. Get it at https://github.com/wesleysimplicio/simplicio/releases/latest"
  exit 1
}
Write-Host "  ✓ installed: $DestPath"

# Verify
try {
  $output = & $DestPath version 2>&1 | Out-String
  Write-Host "  ✓ simplicio is ready!"
} catch {
  Write-Host "  ⚠ binary installed but verification failed"
}

# PATH hint
if ($env:Path -notlike "*$InstallDir*") {
  Write-Host ""
  Write-Host "  ⚠ $InstallDir is not in PATH"
  Write-Host "    Add it to your PowerShell profile:"
  Write-Host "    `$env:Path += `";$InstallDir`""
  Write-Host ""
}

Write-Host ""
Write-Host "  ✓ simplicio $Version (windows-$Arch) installed successfully"
Write-Host ""
Write-Host "  Run:  simplicio chat 'hello' --repo ."
Write-Host "  REPL: simplicio chat --repl --repo ."
Write-Host ""

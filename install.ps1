#!/usr/bin/env pwsh
# install.ps1 — Install the simplicio binary on Windows
#
# Usage:
#   powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"
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

# Detect architecture
$Arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "x86" }

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

# Download
$Tarball = "simplicio-$Version-windows-$Arch.tar.gz"
$DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$Tarball"
$TempDir = [System.IO.Path]::GetTempPath()
$TarballPath = Join-Path $TempDir $Tarball

Write-Host "==> downloading $DownloadUrl"
try {
  Invoke-WebRequest -Uri $DownloadUrl -OutFile $TarballPath -ErrorAction Stop
} catch {
  # Fallback: try alternate URL without version in filename
  $FallbackUrl = "https://github.com/$Repo/releases/download/$Version/simplicio-windows-$Arch.tar.gz"
  Write-Host "  ⚠ trying fallback: $FallbackUrl"
  Invoke-WebRequest -Uri $FallbackUrl -OutFile $TarballPath -ErrorAction Stop
}

# Extract
Write-Host "==> extracting..."
$ExtractDir = Join-Path $TempDir "simplicio-install"
if (Test-Path $ExtractDir) { Remove-Item -Recurse -Force $ExtractDir }
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
tar -xzf $TarballPath -C $ExtractDir

# Find binary
$BinarySrc = Get-ChildItem -Path $ExtractDir -Recurse -Filter $BinName | Select-Object -First 1
if (-not $BinarySrc) {
  Write-Error "Binary not found in downloaded archive"
  exit 1
}

# Install
$DestPath = Join-Path $InstallDir $BinName
Copy-Item -Path $BinarySrc.FullName -Destination $DestPath -Force
Write-Host "  ✓ installed: $DestPath"

# Cleanup
Remove-Item -Recurse -Force $ExtractDir
Remove-Item -Force $TarballPath

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

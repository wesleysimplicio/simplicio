#!/usr/bin/env pwsh
# install.ps1 — Install/update/uninstall/doctor the Simplicio Runtime on Windows
# The installer accepts only a Runtime release whose own readiness contract
# confirms embedded sources, active Google login support, and signed updates.
# It never downloads sibling simplicio-* repositories.
#
# Usage:
#   powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex"
#   pwsh install.ps1 -Doctor
#   pwsh install.ps1 -Uninstall
#
# Environment variables:
#   SIMPLICIO_VERSION           - pin a specific version (default: latest)
#   SIMPLICIO_BIN_DIR           - custom install directory
#   SIMPLICIO_ALLOW_UNVERIFIED  - "1" to proceed even if no checksum is
#                                 published for this target (default: refuse)
#   SIMPLICIO_BUNDLE_DIR       - Runtime report directory (default: ~/.simplicio)
#
# Asset naming follows distribution/targets.json (the canonical target
# triplet table for the whole ecosystem) — target "windows-x64", asset
# "simplicio-windows-x64.exe". Any drift between this script, the release
# workflow and simplicio-update-manifest.json is caught by
# scripts/verify_distribution_consistency.py in CI.

param(
  [string]$Version = "",
  [switch]$Doctor,
  [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$Repo = "wesleysimplicio/simplicio"
$BinName = "simplicio.exe"
$Target = "windows-x64"
$Asset = "simplicio-windows-x64.exe"

if ($env:SIMPLICIO_BIN_DIR) {
  $InstallDir = $env:SIMPLICIO_BIN_DIR
} else {
  $InstallDir = "$env:USERPROFILE\.local\bin"
}
$DestPath = Join-Path $InstallDir $BinName

function Test-InPath([string]$dir) {
  return ($env:Path -split ";") -contains $dir
}

function Get-RuntimeVersionJson([string]$BinaryPath) {
  try {
    $raw = & $BinaryPath version --json 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($raw | ConvertFrom-Json)
  } catch {
    return $null
  }
}

function Test-RuntimeReleaseContract([string]$BinaryPath) {
  if (-not (Test-Path $BinaryPath)) { return $false }
  $meta = Get-RuntimeVersionJson $BinaryPath
  if ($null -eq $meta) { return $false }
  $distribution = $meta.auto_update.distribution
  $identity = $meta.identity
  $security = if ($null -ne $meta.security) { $meta.security } else { $meta.auto_update.security }
  if ($null -eq $distribution -or $null -eq $identity -or $null -eq $security) { return $false }
  return [bool](
    $distribution.source_code_distributed -eq $true -and
    $identity.enabled -eq $true -and
    $identity.login_enabled -eq $true -and
    $security.signature_required -eq $true -and
    $security.public_key_configured -eq $true
  )
}

function Test-ActiveLogin {
  if (-not (Test-Path $DestPath)) { return $false }
  try {
    $raw = & $DestPath auth status --json 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) { return $false }
    $status = $raw | ConvertFrom-Json
    $identity = $status.identity
    if ($null -eq $identity) { return $false }
    $identityEmail = [string]$identity.email
    if ([string]::IsNullOrWhiteSpace($identityEmail)) {
      $identityEmail = [string]$status.user.email
    }
    $active = (
      $identity.enabled -eq $true -and
      $identity.login_enabled -eq $true -and
      $identity.status -notin @("disabled", "logged_out", "revoked") -and
      -not [string]::IsNullOrWhiteSpace($identityEmail)
    )
    if ($null -ne $status.entitlement -and $null -ne $status.entitlement.updates_allowed) {
      $active = $active -and ($status.entitlement.updates_allowed -eq $true)
    }
    return [bool]$active
  } catch {
    return $false
  }
}

function Require-ActiveLogin {
  if (Test-ActiveLogin) { return }
  Write-Host "==> Google login is required to activate Simplicio Runtime"
  & $DestPath login google
  if ($LASTEXITCODE -ne 0 -or -not (Test-ActiveLogin)) {
    throw "Login ausente, expirado, revogado ou sem entitlement ativo; instalação bloqueada"
  }
}

# ─── -Doctor: idempotent, read-only health check ───────────────────────────
if ($Doctor) {
  Write-Host "==> simplicio doctor"
  $ok = $true

  if (Test-Path $DestPath) {
    Write-Host "  [OK] binary present: $DestPath"
  } else {
    Write-Host "  [FAIL] binary missing at $DestPath"
    $ok = $false
  }

  if (Test-InPath $InstallDir) {
    Write-Host "  [OK] $InstallDir is on PATH"
  } else {
    Write-Host "  [WARN] $InstallDir is not on PATH (current session)"
  }

  if (Test-Path $DestPath) {
    try {
      $verOut = & $DestPath version 2>&1 | Out-String
      if ($LASTEXITCODE -ne 0) { throw "version command returned $LASTEXITCODE" }
      Write-Host "  [OK] binary runs: $($verOut.Trim())"
    } catch {
      Write-Host "  [FAIL] binary present but failed to execute: $($_.Exception.Message)"
      $ok = $false
    }

    if (Test-RuntimeReleaseContract $DestPath) {
      Write-Host "  [OK] Runtime release contract is ready"
    } else {
      Write-Host "  [FAIL] release is missing embedded sources, login activation, or update key"
      $ok = $false
    }

    if (Test-ActiveLogin) {
      Write-Host "  [OK] active Google session and entitlement"
    } else {
      Write-Host "  [FAIL] missing, expired, revoked, or inactive Google session"
      $ok = $false
    }
  }

  if ($ok) {
    Write-Host ""
    Write-Host "  ✓ simplicio looks healthy"
    exit 0
  } else {
    Write-Host ""
    Write-Host "  ✗ simplicio has problems — re-run the installer"
    exit 1
  }
}

# ─── -Uninstall: idempotent removal, safe to run repeatedly ────────────────
if ($Uninstall) {
  Write-Host "==> simplicio uninstall"
  if (Test-Path $DestPath) {
    Remove-Item -Force $DestPath
    Write-Host "  ✓ removed $DestPath"
  } else {
    Write-Host "  ✓ already removed (nothing at $DestPath)"
  }
  # Data/config is intentionally preserved (idempotent, non-destructive
  # uninstall) — user data under ~/.simplicio is never touched here.
  Write-Host "  ✓ user data under `$env:USERPROFILE\.simplicio was preserved"
  Write-Host ""
  Write-Host "  Note: if you added $InstallDir to your PowerShell profile's"
  Write-Host "  `$env:Path, remove that line manually — this script never"
  Write-Host "  edits your profile."
  exit 0
}

# ─── Install / update ───────────────────────────────────────────────────────
Write-Host "==> simplicio installer for Windows ($Target)"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

if (-not $Version -and $env:SIMPLICIO_VERSION) {
  $Version = $env:SIMPLICIO_VERSION
}
if (-not $Version) {
  Write-Host "==> fetching latest version..."
  try {
    $latest = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -ErrorAction Stop
    $Version = $latest.tag_name
    Write-Host "  - latest version: $Version"
  } catch {
    $Version = "latest"
    Write-Host "  ! could not determine latest, using '$Version'"
  }
}

# Resolve the release base (pinned tag, or the 'latest' redirect) once so the
# binary and the manifest we verify it against come from the same place.
if ($Version -eq "latest") {
  $ReleaseBase = "https://github.com/$Repo/releases/latest/download"
} else {
  $ReleaseBase = "https://github.com/$Repo/releases/download/$Version"
}

# ─── Fetch update manifest for checksum verification ───────────────────────
$ManifestUrl = "$ReleaseBase/simplicio-update-manifest.json"
$Manifest = $null
try {
  Write-Host "==> fetching update manifest for verification..."
  $Manifest = Invoke-RestMethod -Uri $ManifestUrl -ErrorAction Stop
} catch {
  Write-Host "  ! could not fetch update manifest: $($_.Exception.Message)"
}

$ExpectedSha256 = $null
$ExpectedSigned = $false
$ExpectedSignature = $null
$SignatureRequired = $false
if ($Manifest) {
  $artifact = $Manifest.artifacts | Where-Object { $_.target -eq $Target } | Select-Object -First 1
  if ($artifact) {
    $ExpectedSha256 = $artifact.sha256
    $ExpectedSigned = [bool]$artifact.signed -or ([string]$artifact.signature).StartsWith("ed25519:")
    $ExpectedSignature = $artifact.signature
  }
  $SignatureRequired = [bool]$Manifest.security.signature_required
}

if ($SignatureRequired -and (-not $ExpectedSigned -or [string]::IsNullOrWhiteSpace([string]$ExpectedSignature))) {
  Write-Error "Refusing to install: the manifest requires an Ed25519 signature, but target '$Target' has no published signature."
  exit 1
} elseif (-not $ExpectedSha256) {
  if ($env:SIMPLICIO_ALLOW_UNVERIFIED -eq "1") {
    Write-Host "  ! no published checksum for target '$Target' — proceeding UNVERIFIED (SIMPLICIO_ALLOW_UNVERIFIED=1)"
  } else {
    Write-Error "Refusing to install: no published SHA256 checksum for target '$Target' in the update manifest. Set SIMPLICIO_ALLOW_UNVERIFIED=1 to override at your own risk."
    exit 1
  }
} elseif (-not $ExpectedSigned) {
  Write-Host "  ! checksum will be verified, but this release channel does not yet require an Ed25519 signature for $Target"
}

# ─── Download to a staging file, verify, then atomically swap in ──────────
$DownloadUrl = "$ReleaseBase/$Asset"
$StagingPath = "$DestPath.download-$([guid]::NewGuid().ToString('N')).exe"

Write-Host "==> downloading $DownloadUrl"
try {
  Invoke-WebRequest -Uri $DownloadUrl -OutFile $StagingPath -UseBasicParsing -ErrorAction Stop
} catch {
  Write-Error "Download failed for $Asset from $DownloadUrl : $($_.Exception.Message)"
  if (Test-Path $StagingPath) { Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue }
  exit 1
}

if (-not (Test-Path $StagingPath) -or (Get-Item $StagingPath).Length -eq 0) {
  Write-Error "Downloaded file is missing or empty: $StagingPath"
  if (Test-Path $StagingPath) { Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue }
  exit 1
}

if ($ExpectedSha256) {
  $actualSha256 = (Get-FileHash -Path $StagingPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualSha256 -ne $ExpectedSha256.ToLowerInvariant()) {
    Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
    Write-Error "Checksum mismatch for $Asset. Expected $ExpectedSha256, got $actualSha256. Refusing to install a tampered or corrupt binary."
    exit 1
  }
  Write-Host "  ✓ SHA256 verified: $actualSha256"
}

# Validate the staged executable before the atomic swap. A release that lacks
# embedded sources, Google login activation, or the signed-update key must not
# replace a working installation and then fail its post-install checks.
if (-not (Test-RuntimeReleaseContract $StagingPath)) {
  Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
  Write-Error "Runtime release does not meet the distribution contract (embedded sources, Google login, and signed-update key); installation aborted."
  exit 1
}

# Atomic swap: rename into place on the same volume so there is never a
# window where $DestPath is a half-written file, and re-running this script
# (idempotent update) never leaves stale .tmp files behind on success.
try {
  Move-Item -Force -Path $StagingPath -Destination $DestPath
} catch {
  Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
  Write-Error "Could not move verified binary into place: $($_.Exception.Message)"
  exit 1
}
Write-Host "  ✓ installed: $DestPath"

# ─── Verify the downloaded Runtime ──────────────────────────────────────────
try {
  $output = & $DestPath version 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) { throw "version command returned $LASTEXITCODE" }
} catch {
  Write-Error "Binary installed but version verification failed: $($_.Exception.Message)"
  exit 1
}

if (-not (Test-RuntimeReleaseContract $DestPath)) {
  Write-Error "This Runtime does not meet the distribution contract; refusing to finish installation. Install a compatible Runtime release."
  exit 1
}
Write-Host "  ✓ Runtime release contract verified"

# ─── Active login is mandatory; beta does not bypass this gate ──────────────
try {
  Require-ActiveLogin
} catch {
  Write-Error $_.Exception.Message
  exit 1
}
Write-Host "  ✓ active Google session and entitlement verified"

# Codex only renders its Authenticate action for an OAuth-capable HTTP server.
# Other hosts retain their stdio fallback inside `simplicio mcp register`.
try {
  & $DestPath mcp register | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "mcp register returned $LASTEXITCODE" }
  Write-Host "  ✓ local HTTP/OAuth MCP registered for Codex"
} catch {
  Write-Warning "could not register MCP automatically; run: simplicio mcp register"
}

$BundleDir = if ($env:SIMPLICIO_BUNDLE_DIR) { $env:SIMPLICIO_BUNDLE_DIR } else { Join-Path $env:USERPROFILE ".simplicio" }
New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
$RuntimeReport = Join-Path $BundleDir "runtime-release.json"
try {
  $runtimeJson = & $DestPath version --json 2>&1
  if ($LASTEXITCODE -ne 0) { throw "version --json returned $LASTEXITCODE" }
  $runtimeJson | Set-Content -Encoding UTF8 $RuntimeReport
  Write-Host "  ✓ Runtime release report: $RuntimeReport"
} catch {
  if (Test-Path $RuntimeReport) { Remove-Item -Force $RuntimeReport -ErrorAction SilentlyContinue }
  Write-Error "Could not persist the Runtime release report: $($_.Exception.Message)"
  exit 1
}

# PATH hint
if (-not (Test-InPath $InstallDir)) {
  Write-Host ""
  Write-Host "  ! $InstallDir is not in PATH"
  Write-Host "    Add it to your PowerShell profile:"
  Write-Host "    `$env:Path += `";$InstallDir`""
  Write-Host ""
}

Write-Host ""
Write-Host "  ✓ simplicio Runtime $Version (windows-x64) installed successfully"
Write-Host "  ✓ Runtime release contract is active"
Write-Host "  ✓ no pip packages or sibling checkouts were installed"
Write-Host "  ✓ active Google login is required for product commands"
Write-Host ""
Write-Host "  Run:     simplicio chat 'hello' --repo ."
Write-Host "  REPL:    simplicio chat --repl --repo ."
Write-Host "  Doctor:  pwsh install.ps1 -Doctor"
Write-Host "  Remove:  pwsh install.ps1 -Uninstall"
Write-Host ""

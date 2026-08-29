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
#   SIMPLICIO_BIN_DIR           - custom MCP binary directory (default: ~/.simplicio/bin)
#   SIMPLICIO_MCP_URL           - local HTTP MCP URL exposed to stdio servers
#   SIMPLICIO_ALLOW_UNVERIFIED  - "1" to proceed even if no checksum is
#                                 published for this target (default: refuse)
#   SIMPLICIO_BUNDLE_DIR       - Runtime report directory (default: ~/.simplicio)
#   SIMPLICIO_INSTALL_HOST_PLUGINS - "0" skips detected native host plugins
#                                    (default: install Codex/Claude/Gemini packages)
#
# Asset naming follows distribution/targets.json (the canonical target
# triplet table for the whole ecosystem) — target "windows-x64", asset
# "simplicio-windows-x64.exe". Any drift between this script, the release
# workflow and simplicio-update-manifest.json is caught by
# scripts/verify_distribution_consistency.py in CI.

param(
  [string]$Version = "",
  [switch]$Doctor,
  [switch]$Uninstall,
  [switch]$KeepData,
  [switch]$Purge
)

$ErrorActionPreference = "Stop"

$Repo = "wesleysimplicio/simplicio"
$BinName = "simplicio.exe"
$Target = "windows-x64"
$Asset = "simplicio-windows-x64.exe"
$Ed25519PublicKey = "2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok="
$Ed25519HelperUrl = "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/scripts/verify_ed25519.py"
$Ed25519HelperSha256 = "f03a0719dd557ddea27dc4cf1456d6f06a47b9056505e4d4b8453090697600d0"
$PinnedPublicKey = ([string]$Ed25519PublicKey).Trim()
$script:Ed25519VerifyError = ""
$SimplicioMcpUrl = if ($env:SIMPLICIO_MCP_URL) { $env:SIMPLICIO_MCP_URL } else { "http://127.0.0.1:8787/mcp" }

if ($env:SIMPLICIO_BIN_DIR) {
  $InstallDir = $env:SIMPLICIO_BIN_DIR
} else {
  $InstallDir = Join-Path $env:USERPROFILE ".simplicio\bin"
}
$DestPath = Join-Path $InstallDir $BinName
$InstallTransactionActive = $false
$PreviousPath = ""
$PurgeDir = if ($env:SIMPLICIO_BUNDLE_DIR) { $env:SIMPLICIO_BUNDLE_DIR } else { Join-Path $env:USERPROFILE ".simplicio" }
$AuthFile = Join-Path $PurgeDir "login.json"
$AuthFileWasPresent = Test-Path $AuthFile

function Invoke-Rollback {
  if ($InstallTransactionActive) {
    if ($PreviousPath -and (Test-Path $PreviousPath)) {
      Move-Item -Force -Path $PreviousPath -Destination $DestPath
    } elseif (Test-Path $DestPath) {
      Remove-Item -Force $DestPath
    }
    $script:InstallTransactionActive = $false
  }
}

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


function Test-Ed25519Signature([string]$BinaryPath, [string]$Signature, [string]$PublicKey, [string]$Digest) {
  $helperPath = Join-Path ([IO.Path]::GetTempPath()) ("simplicio-verify-$([guid]::NewGuid().ToString('N')).py")
  try {
    $python = $null
    $pythonArgs = @()
    foreach ($candidate in @(
      @{ Name = "py"; Args = @('-3') },
      @{ Name = "python3"; Args = @() },
      @{ Name = "python"; Args = @() }
    )) {
      if (-not (Get-Command $candidate.Name -ErrorAction SilentlyContinue)) { continue }
      & $candidate.Name @($candidate.Args) -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" 2>$null
      if ($LASTEXITCODE -eq 0) {
        $python = $candidate.Name
        $pythonArgs = @($candidate.Args)
        break
      }
    }
    if (-not $python) {
      $script:Ed25519VerifyError = "Python 3 is required for Ed25519 verification; install Python 3 or ensure py, python3, or python points to Python 3."
      return $false
    }
    try {
      Invoke-WebRequest -Uri $Ed25519HelperUrl -OutFile $helperPath -UseBasicParsing -ErrorAction Stop
    } catch {
      $script:Ed25519VerifyError = "could not download Ed25519 verification helper: $($_.Exception.Message)"
      return $false
    }
    $helperHash = (Get-FileHash -Path $helperPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($helperHash -ne $Ed25519HelperSha256.ToLowerInvariant()) {
      $script:Ed25519VerifyError = "Ed25519 verification helper SHA256 mismatch: expected $Ed25519HelperSha256, got $helperHash"
      return $false
    }
    $normalizedSignature = ([string]$Signature).Trim()
    $normalizedPublicKey = ([string]$PublicKey).Trim()
    $normalizedDigest = ([string]$Digest).Trim().ToLowerInvariant()
    $verifyOutput = & $python @pythonArgs $helperPath --public-key $normalizedPublicKey --signature $normalizedSignature --sha256 $normalizedDigest 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
      $detail = $verifyOutput.Trim()
      if ([string]::IsNullOrWhiteSpace($detail)) {
        $detail = "verification helper exited with code $LASTEXITCODE"
      } else {
        $detail = "verification helper exited with code ${LASTEXITCODE}: $detail"
      }
      $script:Ed25519VerifyError = $detail
      return $false
    }
    return $true
  } catch {
    return $false
  } finally {
    if (Test-Path $helperPath) { Remove-Item -Force $helperPath -ErrorAction SilentlyContinue }
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
    $identityEmail = if ($null -ne $identity.email) { $identity.email } else { $status.user.email }
    $active = (
      $identity.enabled -eq $true -and
      $identity.login_enabled -eq $true -and
      $identity.status -notin @("disabled", "logged_out", "revoked") -and
      -not [string]::IsNullOrWhiteSpace([string]$identityEmail)
    )
    if ($null -ne $status.entitlement -and $null -ne $status.entitlement.updates_allowed) {
      $active = $active -and ($status.entitlement.updates_allowed -eq $true)
    }
    return [bool]$active
  } catch {
    return $false
  }
}

function Report-LoginState {
  if (Test-ActiveLogin) {
    Write-Host "  ✓ active Google session and entitlement verified"
    return
  }
  Write-Warning "Google login missing or entitlement inactive; run: `"$DestPath`" auth login"
}

function Test-McpToolSurface([string]$BinaryPath) {
  if (-not (Test-Path $BinaryPath)) { return $false }
  try {
    $env:SIMPLICIO_MCP_URL = $SimplicioMcpUrl
    & $BinaryPath mcp register --binary $BinaryPath --json | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Invoke-NativeHostCommand([string]$Command, [string[]]$Arguments) {
  try {
    & $Command @Arguments *> $null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Install-GeminiExtension {
  $installedManifest = Join-Path $env:USERPROFILE ".gemini\extensions\simplicio\gemini-extension.json"
  if (Test-Path $installedManifest) {
    Write-Host "  ✓ Gemini CLI native extension already installed"
    return $true
  }

  $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("simplicio-plugin-" + [guid]::NewGuid().ToString("N"))
  $archive = Join-Path $tempRoot "simplicio-master.zip"
  $unpacked = Join-Path $tempRoot "unpacked"
  try {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
    Invoke-WebRequest -Uri "https://github.com/$Repo/archive/refs/heads/master.zip" -OutFile $archive -UseBasicParsing
    Expand-Archive -Path $archive -DestinationPath $unpacked -Force
    $manifest = Get-ChildItem -Path $unpacked -Recurse -File -Filter "gemini-extension.json" |
      Where-Object { $_.FullName -match "[\\/]plugins[\\/]simplicio[\\/]gemini-extension\.json$" } |
      Select-Object -First 1
    if ($null -eq $manifest) { return $false }
    if (Invoke-NativeHostCommand "gemini" @("extensions", "install", $manifest.DirectoryName, "--consent")) {
      Write-Host "  ✓ Gemini CLI native extension installed"
      return $true
    }
    return $false
  } catch {
    return $false
  } finally {
    if (Test-Path $tempRoot) {
      Remove-Item -Recurse -Force $tempRoot -ErrorAction SilentlyContinue
    }
  }
}

function Install-DetectedHostPlugins {
  if ($env:SIMPLICIO_INSTALL_HOST_PLUGINS -eq "0") {
    Write-Host "  - native host plugin installation skipped by SIMPLICIO_INSTALL_HOST_PLUGINS=0"
    return $true
  }

  $detected = 0
  $failures = 0
  if (Get-Command codex -CommandType Application -ErrorAction SilentlyContinue) {
    $detected += 1
    [void](Invoke-NativeHostCommand "codex" @("plugin", "marketplace", "add", $Repo, "--ref", "master"))
    if (Invoke-NativeHostCommand "codex" @("plugin", "add", "simplicio@simplicio-codex")) {
      Write-Host "  ✓ Codex native plugin installed"
    } else {
      Write-Warning "Codex detected, but simplicio@simplicio-codex could not be installed"
      $failures += 1
    }
  }

  if (Get-Command claude -CommandType Application -ErrorAction SilentlyContinue) {
    $detected += 1
    [void](Invoke-NativeHostCommand "claude" @("plugin", "marketplace", "add", $Repo))
    if (Invoke-NativeHostCommand "claude" @("plugin", "install", "simplicio@simplicio", "--scope", "user")) {
      Write-Host "  ✓ Claude Code native plugin installed"
    } else {
      Write-Warning "Claude Code detected, but simplicio@simplicio could not be installed"
      $failures += 1
    }
  }

  if (Get-Command gemini -CommandType Application -ErrorAction SilentlyContinue) {
    $detected += 1
    if (-not (Install-GeminiExtension)) {
      Write-Warning "Gemini CLI detected, but the Simplicio native extension could not be installed"
      $failures += 1
    }
  }

  if ($detected -eq 0) {
    Write-Host "  - no native-package host detected; Runtime MCP registration covers the other clients"
  }
  return ($failures -eq 0)
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
  if ($Purge -and $KeepData) {
    Write-Error "-Purge and -KeepData are mutually exclusive"
    exit 1
  }
  if (-not $Purge -and -not $KeepData) { $KeepData = $true }
  if ($Purge -and $env:SIMPLICIO_CONFIRM_PURGE -ne "1") {
    Write-Error "-Purge requires SIMPLICIO_CONFIRM_PURGE=1; no data was removed"
    exit 1
  }
  if (Test-Path $DestPath) {
    Remove-Item -Force $DestPath
    Write-Host "  ✓ removed $DestPath"
  } else {
    Write-Host "  ✓ already removed (nothing at $DestPath)"
  }
  if ($Purge) {
    if (Test-Path $PurgeDir) {
      Get-ChildItem -Force -Path $PurgeDir | Where-Object { $_.Name -ne ".env" } | Remove-Item -Recurse -Force
    }
    if ($AuthFileWasPresent) {
      Write-Warning "Login state disappeared during the upgrade/purge"
    }
    Write-Host "  ✓ .env and login state removed by explicit purge"
  } else {
    Write-Host "  ✓ user data under `$env:USERPROFILE\.simplicio was preserved (-KeepData)"
  }
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
  $ReleaseTag = if ($Version.StartsWith("v")) { $Version } else { "v$Version" }
  $ReleaseBase = "https://github.com/$Repo/releases/download/$ReleaseTag"
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
$ExpectedPublicKey = ""
$SignatureRequired = $false
if ($Manifest) {
  $artifact = $Manifest.artifacts | Where-Object { $_.target -eq $Target } | Select-Object -First 1
  if ($artifact) {
    $ExpectedSha256 = [string]$artifact.sha256
    $ExpectedSigned = [bool]$artifact.signed -or ([string]$artifact.signature).StartsWith("ed25519:")
    $ExpectedSignature = [string]$artifact.signature
  }
  $ExpectedPublicKey = ([string]$Manifest.signing_pubkey).Trim()
  $SignatureRequired = [bool]$Manifest.security.signature_required
}

if ($SignatureRequired -or $ExpectedSigned) {
  if ([string]::IsNullOrWhiteSpace($ExpectedPublicKey)) {
    Write-Error "Refusing to install: manifest requires Ed25519 signatures but signing_pubkey is missing."
    exit 1
  }
  if ($SignatureRequired -and $ExpectedPublicKey -cne $PinnedPublicKey) {
    Write-Error "Refusing to install: manifest Ed25519 public key does not match the pinned installer key."
    exit 1
  }
}
if ($SignatureRequired -and (-not $ExpectedSigned -or [string]::IsNullOrWhiteSpace($ExpectedSignature))) {
  Write-Error "Refusing to install: the manifest requires an Ed25519 signature, but target '$Target' has no published signature."
  exit 1
} elseif (-not $ExpectedSha256) {
  if ($ExpectedSigned) {
    Write-Error "Refusing to install: published Ed25519 signature has no verifiable SHA256 digest."
    exit 1
  } elseif ($env:SIMPLICIO_ALLOW_UNVERIFIED -eq "1" -and $env:SIMPLICIO_CHANNEL -eq "unofficial") {
    Write-Host "  ! no published checksum for target '$Target' — proceeding UNVERIFIED (SIMPLICIO_ALLOW_UNVERIFIED=1, unofficial channel)"
  } else {
    Write-Error "Refusing to install: no published SHA256 checksum for target '$Target' in the update manifest."
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

if ($ExpectedSigned) {
  if (-not (Test-Ed25519Signature $StagingPath $ExpectedSignature $PinnedPublicKey $ExpectedSha256)) {
    Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($script:Ed25519VerifyError)) {
      Write-Error "Ed25519 signature verification failed; refusing to install."
    } else {
      Write-Error "Ed25519 signature verification failed: $script:Ed25519VerifyError; refusing to install."
    }
    exit 1
  }
  Write-Host "  ✓ Ed25519 signature verified over SHA256 digest"
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
$PreviousPath = "$DestPath.previous-$([guid]::NewGuid().ToString('N'))"
if (Test-Path $DestPath) {
  Copy-Item -Force -Path $DestPath -Destination $PreviousPath
}
$InstallTransactionActive = $true
try {
  Move-Item -Force -Path $StagingPath -Destination $DestPath
  $InstallTransactionActive = $false
  if (Test-Path $PreviousPath) { Remove-Item -Force $PreviousPath -ErrorAction SilentlyContinue }
} catch {
  Invoke-Rollback
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

# ─── Register MCP and native hooks for every detected client ──────────────
if (Test-McpToolSurface $DestPath) {
  Write-Host "  ✓ MCP and hooks registered automatically for detected clients"
} else {
  Write-Error "Runtime installed, but automatic MCP/hooks registration failed: $DestPath mcp register --binary $DestPath --json"
  exit 1
}

# Native packages add skills, commands and host-specific lifecycle behavior on
# top of Runtime MCP registration. Unsupported/undocumented host installers are
# never guessed; those clients remain on the verified MCP/hooks path.
if (Install-DetectedHostPlugins) {
  Write-Host "  ✓ native plugins reconciled for detected hosts"
} else {
  Write-Warning "Runtime/MCP are ready, but one or more native plugins need manual action; see PLUGIN.md"
}
Report-LoginState
Write-Host "  ✓ Direct MCP: $DestPath serve --mcp --stdio; SIMPLICIO_MCP_URL=$SimplicioMcpUrl"

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

# PATH is optional for MCP because host configs point at $DestPath directly.
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
Write-Host "  ✓ active Google login is verified after auth login"
Write-Host "  ✓ MCP command points at $DestPath"
Write-Host "  ✓ SIMPLICIO_MCP_URL=$SimplicioMcpUrl"
Write-Host ""
Write-Host "  Run:     simplicio chat 'hello' --repo ."
Write-Host "  REPL:    simplicio chat --repl --repo ."
Write-Host "  Doctor:  pwsh install.ps1 -Doctor"
Write-Host "  Remove:  pwsh install.ps1 -Uninstall"
Write-Host ""

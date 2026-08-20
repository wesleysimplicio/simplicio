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
$Ed25519PublicKey = "2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok="
$Ed25519HelperUrl = "https://raw.githubusercontent.com/$Repo/master/scripts/verify_ed25519.py"
$Ed25519HelperSha256 = "6d25fed7ea3d45db4a184d0c499511d235931b2693e5d8369851d27b349d932b"
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

function Test-Ed25519Signature([string]$BinaryPath, [string]$Signature, [string]$PublicKey, [string]$Digest) {
  $helperPath = Join-Path ([IO.Path]::GetTempPath()) ("simplicio-verify-$([guid]::NewGuid().ToString('N')).py")
  try {
    $python = $null
    $pythonArgs = @()
    if (Get-Command python3 -ErrorAction SilentlyContinue) { $python = "python3" }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { $python = "py"; $pythonArgs = @('-3') }
    if (-not $python) { return $false }
    Invoke-WebRequest -Uri $Ed25519HelperUrl -OutFile $helperPath -UseBasicParsing -ErrorAction Stop
    $helperHash = (Get-FileHash -Path $helperPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($helperHash -ne $Ed25519HelperSha256.ToLowerInvariant()) { return $false }
    & $python @pythonArgs $helperPath --public-key $PublicKey --signature $Signature --sha256 $Digest
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  } finally {
    Remove-Item -Force $helperPath -ErrorAction SilentlyContinue
  }
}
function Test-McpToolSurface([string]$BinaryPath) {
  if (-not (Test-Path $BinaryPath)) { return $false }
  $required = @(
    "simplicio_map", "simplicio_memory", "simplicio_edit", "simplicio_gate",
    "simplicio_validate", "simplicio_run", "simplicio_symbol", "simplicio_search",
    "simplicio_read", "simplicio_exec"
  )
  $payload = @(
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
  ) -join [Environment]::NewLine
  try {
    $raw = $payload | & $BinaryPath serve --mcp --stdio --json 2>$null | Out-String
    if ($LASTEXITCODE -ne 0) { return $false }
    $response = $null
    foreach ($line in ($raw -split "\r?\n")) {
      if ([string]::IsNullOrWhiteSpace($line)) { continue }
      try {
        $candidate = $line | ConvertFrom-Json
        if ($candidate.id -eq 2) { $response = $candidate }
      } catch { continue }
    }
    if ($null -eq $response -or $null -eq $response.result) { return $false }
    $names = @($response.result.tools | ForEach-Object { [string]$_.name })
    $missing = @($required | Where-Object { $_ -notin $names })
    if ($missing.Count -gt 0) {
      Write-Host "  [FAIL] MCP tool surface incomplete; missing: $($missing -join ', ')"
      return $false
    }
    return $true
  } catch {
    return $false
  }
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

function Backup-Once([string]$Path) {
  if ((Test-Path -LiteralPath $Path) -and -not (Test-Path -LiteralPath "$Path.simplicio.bak")) {
    Copy-Item -LiteralPath $Path -Destination "$Path.simplicio.bak" -Force
  }
}

function Write-AtomicText([string]$Path, [string]$Content) {
  $parent = Split-Path -Parent $Path
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  $temp = "$Path.simplicio.tmp"
  Set-Content -LiteralPath $temp -Value $Content -Encoding UTF8
  Move-Item -Force -LiteralPath $temp -Destination $Path
}

function Remove-Legacy-CodexHooks([object]$Root) {
  if ($null -eq $Root -or -not $Root.PSObject.Properties["hooks"]) { return }
  $hooks = $Root.hooks
  if ($null -eq $hooks -or -not $hooks.PSObject) { return }
  $eventNames = @($hooks.PSObject.Properties | ForEach-Object { $_.Name })
  foreach ($eventName in $eventNames) {
    $eventProperty = $hooks.PSObject.Properties[$eventName]
    if ($null -eq $eventProperty) { continue }
    $items = @($eventProperty.Value)
    $keptItems = @()
    foreach ($item in $items) {
      if ($null -eq $item -or -not $item.PSObject.Properties["hooks"]) {
        $keptItems += $item
        continue
      }
      $keptHooks = @()
      foreach ($legacyHook in @($item.hooks)) {
        $command = [string]$legacyHook.command
        $isLegacySimplicio = (
          $command -match '(?i)mcp-route\.sh|simplicio-mcp-route' -or
          (($command -match '(?i)/bin/bash') -and ($command -match '(?i)simplicio'))
        )
        if (-not $isLegacySimplicio) { $keptHooks += $legacyHook }
      }
      if ($keptHooks.Count -gt 0) {
        $item.hooks = $keptHooks
        $keptItems += $item
      }
    }
    if ($keptItems.Count -gt 0) {
      $hooks | Add-Member -MemberType NoteProperty -Name $eventName -Value $keptItems -Force
    } else {
      $hooks.PSObject.Properties.Remove($eventName)
    }
  }
}


function Install-CodexIntegration {
  $codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
  $codexConfig = Join-Path $codexDir "config.toml"
  $codexHooks = Join-Path $codexDir "hooks.json"
  $hookDir = Join-Path $env:USERPROFILE ".simplicio\hooks"
  $hookPath = Join-Path $hookDir "mcp-route.ps1"
  $hookTemp = "$hookPath.download-$([guid]::NewGuid().ToString('N')).tmp"
  New-Item -ItemType Directory -Force -Path $codexDir, $hookDir | Out-Null

  Write-Host "==> configuring Codex STDIO MCP and hooks"
  $installedVersion = (& $DestPath --version 2>$null | Select-Object -First 1).Split(' ')[1].TrimStart('v')
  $hookRef = if ($env:SIMPLICIO_CODEX_HOOK_REF) { $env:SIMPLICIO_CODEX_HOOK_REF } else { "v$installedVersion" }
  if ([string]::IsNullOrWhiteSpace($installedVersion)) { throw "could not derive a versioned Codex hook ref" }
  $hookUrl = "https://raw.githubusercontent.com/$Repo/$hookRef/codex/mcp-route.ps1"
  try {
    Invoke-WebRequest -Uri $hookUrl -OutFile $hookTemp -UseBasicParsing -ErrorAction Stop
    Move-Item -Force -LiteralPath $hookTemp -Destination $hookPath
  } catch {
    if (Test-Path -LiteralPath $hookTemp) { Remove-Item -Force -LiteralPath $hookTemp -ErrorAction SilentlyContinue }
    throw "could not download the Codex hook: $($_.Exception.Message)"
  }

  Backup-Once $codexConfig
  $config = if (Test-Path -LiteralPath $codexConfig) { Get-Content -Raw -LiteralPath $codexConfig } else { "" }
  $escapedBinary = $DestPath.Replace('\', '\\').Replace('"', '\"')
  $stdioBlock = '[mcp_servers.simplicio]' + [Environment]::NewLine +
    'command = "' + $escapedBinary + '"' + [Environment]::NewLine +
    'args = ["serve", "--mcp", "--stdio"]' + [Environment]::NewLine
  $sectionRegex = '(?ms)^\[mcp_servers\.simplicio\]\r?\n.*?(?=^\[|\z)'
  if ([regex]::IsMatch($config, $sectionRegex)) {
    $config = [regex]::Replace($config, $sectionRegex, [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $stdioBlock }, 1)
  } else {
    $separator = if ([string]::IsNullOrWhiteSpace($config)) { "" } else { [Environment]::NewLine + [Environment]::NewLine }
    $config = $config.TrimEnd() + $separator + $stdioBlock
  }
  Write-AtomicText $codexConfig $config

  Backup-Once $codexHooks
  try {
    $root = if (Test-Path -LiteralPath $codexHooks) {
      (Get-Content -Raw -LiteralPath $codexHooks | ConvertFrom-Json)
    } else {
      [pscustomobject]@{}
    }
  } catch {
    throw "hooks.json is invalid and was preserved: $($_.Exception.Message)"
  }
  if ($null -eq $root) { $root = [pscustomobject]@{} }
  Remove-Legacy-CodexHooks $root
  if (-not $root.PSObject.Properties["hooks"]) {
    $root | Add-Member -MemberType NoteProperty -Name hooks -Value ([pscustomobject]@{})
  }
  $hooks = $root.hooks
  if ($null -eq $hooks -or -not $hooks.PSObject) { throw "hooks.json has an invalid hooks object" }
  $hookCommand = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + $hookPath + '"'

  function Upsert-CodexHook([string]$Event, [string]$Matcher) {
    $property = $hooks.PSObject.Properties[$Event]
    $items = if ($property) { @($property.Value) } else { @() }
    foreach ($item in $items) {
      if ($null -eq $item -or -not $item.PSObject.Properties["hooks"]) { continue }
      foreach ($existing in @($item.hooks)) {
        if ($existing -and ([string]$existing.command).Contains("mcp-route.ps1")) {
          $existing.command = $hookCommand
          $existing.timeout = 8
          $existing.type = "command"
          $existing.statusMessage = "Routing through Simplicio MCP"
          if ($Matcher) { $item.matcher = $Matcher }
          $hooks | Add-Member -MemberType NoteProperty -Name $Event -Value $items -Force
          return
        }
      }
    }
    $hook = [pscustomobject]@{
      type = "command"
      command = $hookCommand
      timeout = 8
      statusMessage = "Routing through Simplicio MCP"
    }
    $entry = [pscustomobject]@{ hooks = @($hook) }
    if ($Matcher) { $entry | Add-Member -MemberType NoteProperty -Name matcher -Value $Matcher }
    $items += $entry
    $hooks | Add-Member -MemberType NoteProperty -Name $Event -Value $items -Force
  }

  Upsert-CodexHook "PreToolUse" "Bash|apply_patch|Edit|Write"
  Upsert-CodexHook "SessionStart" "startup|resume|clear|compact"
  Upsert-CodexHook "SubagentStart" ""
  Upsert-CodexHook "UserPromptSubmit" ""
  Write-AtomicText $codexHooks ($root | ConvertTo-Json -Depth 20)
  Write-Host "  ✓ Codex configured for simplicio serve --mcp --stdio"
  Write-Host "  ✓ Codex hooks installed at $hookPath"
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

    if (Test-McpToolSurface $DestPath) {
      Write-Host "  [OK] MCP exposes the 10 documented tools after authentication"
    } else {
      Write-Host "  [FAIL] MCP does not expose the complete documented tool surface after login"
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
$ExpectedPublicKey = $null
$SignatureRequired = $false
if ($Manifest) {
  $artifact = $Manifest.artifacts | Where-Object { $_.target -eq $Target } | Select-Object -First 1
  if ($artifact) {
    $ExpectedSha256 = $artifact.sha256
    $ExpectedSigned = [bool]$artifact.signed -or ([string]$artifact.signature).StartsWith("ed25519:")
    $ExpectedSignature = $artifact.signature
  }
  $ExpectedPublicKey = [string]$Manifest.signing_pubkey
  $SignatureRequired = [bool]$Manifest.security.signature_required
}

if ($SignatureRequired -and (-not $ExpectedSigned -or [string]::IsNullOrWhiteSpace([string]$ExpectedSignature))) {
  Write-Error "Refusing to install: the manifest requires an Ed25519 signature, but target '$Target' has no published signature."
  exit 1
} elseif ($SignatureRequired -and $ExpectedPublicKey -ne $Ed25519PublicKey) {
  Write-Error "Refusing to install: manifest Ed25519 public key does not match the pinned installer key."
  exit 1
} elseif (-not $ExpectedSha256) {
  if ($ExpectedSigned) {
    Write-Error "Refusing to install: published Ed25519 signature has no verifiable SHA256 digest."
    exit 1
  } elseif ($env:SIMPLICIO_ALLOW_UNVERIFIED -eq "1") {
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

if ($ExpectedSigned) {
  if ($ExpectedPublicKey -ne $Ed25519PublicKey -or -not (Test-Ed25519Signature $StagingPath ([string]$ExpectedSignature) $Ed25519PublicKey ([string]$ExpectedSha256))) {
    Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
    Write-Error "Ed25519 signature verification failed; refusing to install."
    exit 1
  }
  Write-Host "  ✓ Ed25519 signature verified over SHA256 digest"
}
# A clean HOME has no authenticated session yet. Validate only the offline
# Runtime release contract before the swap; MCP initialize/tools/list runs
# after Require-ActiveLogin below.
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
# MCP initialize/tools/list is authenticated and is intentionally deferred until
# after Require-ActiveLogin below for clean-HOME bootstrap.

# ─── Active login precedes the authenticated MCP handshake ──────────────────
try {
  Require-ActiveLogin
} catch {
  Write-Error $_.Exception.Message
  exit 1
}
Write-Host "  ✓ active Google session and entitlement verified"

if (-not (Test-McpToolSurface $DestPath)) {
  Write-Error "This Runtime does not expose the complete MCP tool surface after login; refusing to finish installation."
  exit 1
}
# Codex integration is opt-in. MCP registration and routing hooks remain
# separate, and the hook reference is versioned/pinned inside the function.
if ($env:SIMPLICIO_INSTALL_CODEX -eq "1") {
  Install-CodexIntegration
} else {
  Write-Host "==> Codex integration not installed automatically; set SIMPLICIO_INSTALL_CODEX=1 to enable"
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

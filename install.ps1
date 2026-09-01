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
#
# Host plugins are deliberately outside this installer transaction. The
# Runtime/MCP/hook install completes first; a separate explicit consent flow
# owned by `simplicio host-plugins` may be started afterwards.
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
$PublicRouteRef = "68b4c7f7ac27d07624ffa4ddf0673a43e180c3e5"
$PublicRouteUrl = "https://raw.githubusercontent.com/$Repo/$PublicRouteRef/codex/mcp-route.ps1"
$PublicRouteSha256 = "022de213e2b69eda16c89ff3298bc8dd2e0c82ffdfb351665eada46fb83af03c"
$PinnedPublicKey = ([string]$Ed25519PublicKey).Trim()
$script:Ed25519VerifyError = ""
$script:McpFailureCode = ""
$script:McpFailureReason = ""
$script:HostPluginsState = "unavailable"
$script:HostPluginsCommand = $null
$script:HostPluginsReason = "Runtime host-plugins capability was not checked"
$script:HookFailureCode = ""
$script:HookFailureReason = ""
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
$InstallReceipt = Join-Path $PurgeDir "install-receipt.json"
$script:InstallStage = "preflight"
$script:InstallEffectStarted = $false
$script:RuntimeInstalled = $false
$script:McpRegistered = $false
$script:HookInstalled = $false
$AuthFileWasPresent = Test-Path $AuthFile

function New-InstallReceipt(
  [string]$Status,
  [int]$ExitCode,
  [string]$FailureCode,
  [string]$FailureReason
) {
  $failure = $null
  if (-not [string]::IsNullOrWhiteSpace($FailureCode)) {
    $failure = [ordered]@{
      code = $FailureCode
      reason = $FailureReason
    }
  }
  return [ordered]@{
    schema = "simplicio-install-receipt/v1"
    status = $Status
    exit_code = $ExitCode
    stage = $script:InstallStage
    failure = $failure
    runtime = [ordered]@{ installed = [bool]$script:RuntimeInstalled }
    mcp = [ordered]@{ registered = [bool]$script:McpRegistered }
    hook = [ordered]@{ installed = [bool]$script:HookInstalled }
    host_plugins = [ordered]@{
      state = $script:HostPluginsState
      owner = "simplicio-runtime"
      command = $script:HostPluginsCommand
      mutated = $false
      reason = $script:HostPluginsReason
    }
  }
}

function Protect-InstallReceipt([string]$Path) {
  if ($env:OS -eq "Windows_NT") {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $acl = Get-Acl -Path $Path
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) {
      [void]$acl.RemoveAccessRuleSpecific($rule)
    }
    $ownerRule = New-Object Security.AccessControl.FileSystemAccessRule(
      $identity.User,
      [Security.AccessControl.FileSystemRights]::FullControl,
      [Security.AccessControl.AccessControlType]::Allow
    )
    $acl.SetAccessRule($ownerRule)
    Set-Acl -Path $Path -AclObject $acl
    return
  }
  & chmod 600 $Path
  if ($LASTEXITCODE -ne 0) { throw "Could not set private mode 0600 on $Path" }
}

function Save-InstallReceipt(
  [string]$Status,
  [int]$ExitCode,
  [string]$FailureCode,
  [string]$FailureReason
) {
    New-Item -ItemType Directory -Force -Path $PurgeDir | Out-Null
    $receiptTemp = "$InstallReceipt.tmp.$PID"
    $receiptBackup = $null
    $receiptActivated = $false
    try {
    $json = New-InstallReceipt $Status $ExitCode $FailureCode $FailureReason |
      ConvertTo-Json -Depth 6 -Compress
      [IO.File]::WriteAllText(
      $receiptTemp,
      $json + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
      )
      # The candidate must already be private before it can become the active
      # receipt. Keep any previous receipt as a rollback source until the
      # active path has also passed the ACL check.
      Protect-InstallReceipt $receiptTemp
      if (Test-Path $InstallReceipt) {
        $receiptBackup = "$InstallReceipt.backup.$PID"
        Remove-Item -Force $receiptBackup -ErrorAction SilentlyContinue
        [IO.File]::Replace($receiptTemp, $InstallReceipt, $receiptBackup, $true)
      } else {
        [IO.File]::Move($receiptTemp, $InstallReceipt)
      }
      $receiptActivated = $true
      Protect-InstallReceipt $InstallReceipt
      if ($receiptBackup -and (Test-Path $receiptBackup)) {
        Remove-Item -Force $receiptBackup -ErrorAction Stop
      }
      return $json
    } catch {
      $receiptFailure = $_.Exception
      if (Test-Path $receiptTemp) {
        Remove-Item -Force $receiptTemp -ErrorAction SilentlyContinue
      }
      if ($receiptBackup -and (Test-Path $receiptBackup)) {
        try {
          if (Test-Path $InstallReceipt) {
            Remove-Item -Force $InstallReceipt -ErrorAction Stop
          }
          [IO.File]::Move($receiptBackup, $InstallReceipt)
        } catch {
          throw "Receipt protection failed ($($receiptFailure.Message)); prior receipt restoration also failed ($($_.Exception.Message)); backup retained at $receiptBackup"
        }
      } elseif ($receiptActivated -and (Test-Path $InstallReceipt)) {
        Remove-Item -Force $InstallReceipt -ErrorAction SilentlyContinue
      }
      throw $receiptFailure
    }
}

function Fail-Install(
  [string]$FailureReason,
  [string]$FailureCode = ""
) {
  $resolvedFailureCode = if ([string]::IsNullOrWhiteSpace($FailureCode)) {
    "$($script:InstallStage)_failed"
  } else {
    $FailureCode
  }
  $status = if ($script:InstallEffectStarted) { "partial" } else { "failed" }
  try {
    [void](Save-InstallReceipt $status 1 $resolvedFailureCode $FailureReason)
  } catch {
    $fallback = New-InstallReceipt $status 1 $resolvedFailureCode $FailureReason |
      ConvertTo-Json -Depth 6 -Compress
    [Console]::Error.WriteLine($fallback)
  }
  [Console]::Error.WriteLine("  [FAIL] $FailureReason")
  exit 1
}

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
    $result = Invoke-BoundedNativeCommand $DestPath @("auth", "status", "--json")
    if ($result.ExitCode -ne 0) { return $false }
    $status = $result.Stdout | ConvertFrom-Json
    $identity = $status.identity
    $entitlement = $status.entitlement
    $sessionVerification = $status.session_verification
    if ($null -eq $identity -or $null -eq $entitlement -or $null -eq $sessionVerification) {
      return $false
    }
    $identityEmail = if ($null -ne $identity.email) { $identity.email } else { $status.user.email }
    $active = (
      $identity.enabled -eq $true -and
      $identity.login_enabled -eq $true -and
      $identity.status -eq "active" -and
      -not [string]::IsNullOrWhiteSpace([string]$identityEmail) -and
      $entitlement.updates_allowed -eq $true -and
      $sessionVerification.verified -eq $true -and
      $sessionVerification.cached -eq $false
    )
    return [bool]$active
  } catch {
    return $false
  }
}

function Report-LoginState {
  if (Test-ActiveLogin) {
    Write-Host "  ✓ fresh Google session and entitlement verified"
    return
  }
  Write-Warning "Google session is not freshly verified (missing, cached, or inactive entitlement); run: `"$DestPath`" auth login"
}

function Get-ObjectPropertyValue([object]$Object, [string]$Name) {
  if ($null -eq $Object) { return $null }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) { return $null }
  return $property.Value
}

function Convert-ToFailureText([object]$Value) {
  if ($null -eq $Value) { return "" }
  if ($Value -is [string]) { return $Value }
  if ($Value -is [System.Collections.IDictionary] -or $Value -is [System.Collections.IList]) {
    return ""
  }
  return [string]$Value
}

function Limit-FailureText([string]$Text, [int]$Limit = 8192) {
  $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
  if ($bytes.Length -le $Limit) { return $Text }
  return [Text.Encoding]::UTF8.GetString($bytes, 0, $Limit) +
    "`n...[output truncated at 8192 bytes]"
}

function Resolve-RuntimeFailure(
  [string]$Stdout,
  [string]$Stderr,
  [int]$ExitCode
) {
  $payload = $null
  $candidates = @()
  if (-not [string]::IsNullOrWhiteSpace($Stdout)) {
    $candidates += $Stdout.Trim()
    $lines = @($Stdout -split "`r?`n")
    [array]::Reverse($lines)
    $candidates += @($lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  }
  foreach ($candidate in $candidates) {
    try {
      $decoded = $candidate | ConvertFrom-Json -ErrorAction Stop
      if ($null -ne $decoded -and $null -ne $decoded.PSObject) {
        $payload = $decoded
        break
      }
    } catch {
      continue
    }
  }

  $failure = Get-ObjectPropertyValue $payload "failure"
  $errorValue = Get-ObjectPropertyValue $payload "error"
  $code = Convert-ToFailureText (Get-ObjectPropertyValue $failure "code")
  if ([string]::IsNullOrWhiteSpace($code)) {
    $code = Convert-ToFailureText (Get-ObjectPropertyValue $payload "code")
  }
  if ([string]::IsNullOrWhiteSpace($code)) {
    $code = Convert-ToFailureText (Get-ObjectPropertyValue $payload "error_code")
  }
  if ([string]::IsNullOrWhiteSpace($code)) {
    $code = Convert-ToFailureText (Get-ObjectPropertyValue $errorValue "code")
  }
  if ([string]::IsNullOrWhiteSpace($code)) { $code = "mcp_registration_failed" }

  $reason = Convert-ToFailureText (Get-ObjectPropertyValue $failure "reason")
  if ([string]::IsNullOrWhiteSpace($reason)) {
    $reason = Convert-ToFailureText (Get-ObjectPropertyValue $payload "reason")
  }
  if ([string]::IsNullOrWhiteSpace($reason)) {
    $reason = Convert-ToFailureText (Get-ObjectPropertyValue $payload "message")
  }
  if ([string]::IsNullOrWhiteSpace($reason)) {
    $reason = Convert-ToFailureText (Get-ObjectPropertyValue $errorValue "reason")
  }
  if ([string]::IsNullOrWhiteSpace($reason)) {
    $reason = Convert-ToFailureText (Get-ObjectPropertyValue $errorValue "message")
  }
  if ([string]::IsNullOrWhiteSpace($reason) -and $errorValue -is [string]) {
    $reason = $errorValue
  }
  if ([string]::IsNullOrWhiteSpace($reason)) {
    $fallback = @()
    if (-not [string]::IsNullOrWhiteSpace($Stderr)) { $fallback += $Stderr.Trim() }
    if (-not [string]::IsNullOrWhiteSpace($Stdout) -and $Stdout.Trim() -notin $fallback) {
      $fallback += $Stdout.Trim()
    }
    $reason = $fallback -join "`n"
  }
  if ([string]::IsNullOrWhiteSpace($reason)) {
    $reason = "Runtime MCP registration failed with exit code $ExitCode"
  }

  return [pscustomobject]@{
    Code = Limit-FailureText $code
    Reason = Limit-FailureText $reason
  }
}

function Convert-ToProcessArgument([string]$Argument) {
  if ($Argument.Length -eq 0) { return '""' }
  if ($Argument -notmatch '[\s"]') { return $Argument }
  $builder = New-Object Text.StringBuilder
  [void]$builder.Append('"')
  $backslashes = 0
  foreach ($character in $Argument.ToCharArray()) {
    if ($character -eq '\') {
      $backslashes += 1
      continue
    }
    if ($character -eq '"') {
      if ($backslashes -gt 0) { [void]$builder.Append(('\' * ($backslashes * 2))) }
      [void]$builder.Append('\"')
      $backslashes = 0
      continue
    }
    if ($backslashes -gt 0) { [void]$builder.Append(('\' * $backslashes)) }
    [void]$builder.Append($character)
    $backslashes = 0
  }
  if ($backslashes -gt 0) { [void]$builder.Append(('\' * ($backslashes * 2))) }
  [void]$builder.Append('"')
  return $builder.ToString()
}

function Invoke-BoundedNativeCommand(
  [string]$FilePath,
  [string[]]$Arguments,
  [hashtable]$Environment = @{},
  [int]$Limit = 8192
) {
  $startInfo = New-Object Diagnostics.ProcessStartInfo
  $startInfo.FileName = $FilePath
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  if ($startInfo.PSObject.Properties.Name -contains "ArgumentList") {
    foreach ($argument in $Arguments) { [void]$startInfo.ArgumentList.Add($argument) }
  } else {
    $startInfo.Arguments = (($Arguments | ForEach-Object { Convert-ToProcessArgument $_ }) -join " ")
  }
  foreach ($name in $Environment.Keys) {
    $startInfo.EnvironmentVariables[[string]$name] = [string]$Environment[$name]
  }

  $process = New-Object Diagnostics.Process
  $process.StartInfo = $startInfo
  $stdout = New-Object IO.MemoryStream
  $stderr = New-Object IO.MemoryStream
  $stdoutTruncated = $false
  $stderrTruncated = $false
  try {
    if (-not $process.Start()) { throw "Could not start $FilePath" }
    $stdoutBuffer = New-Object byte[] 4096
    $stderrBuffer = New-Object byte[] 4096
    $stdoutTask = $process.StandardOutput.BaseStream.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)
    $stderrTask = $process.StandardError.BaseStream.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)
    while ($null -ne $stdoutTask -or $null -ne $stderrTask) {
      $tasks = New-Object 'System.Collections.Generic.List[System.Threading.Tasks.Task]'
      if ($null -ne $stdoutTask) { [void]$tasks.Add($stdoutTask) }
      if ($null -ne $stderrTask) { [void]$tasks.Add($stderrTask) }
      $completedIndex = [Threading.Tasks.Task]::WaitAny($tasks.ToArray())
      $completed = $tasks[$completedIndex]
      if ($null -ne $stdoutTask -and [object]::ReferenceEquals($completed, $stdoutTask)) {
        $count = $stdoutTask.Result
        if ($count -eq 0) {
          $stdoutTask = $null
        } else {
          $remaining = [Math]::Max(0, $Limit - [int]$stdout.Length)
          $kept = [Math]::Min($remaining, $count)
          if ($kept -gt 0) { $stdout.Write($stdoutBuffer, 0, $kept) }
          if ($count -gt $kept) { $stdoutTruncated = $true }
          $stdoutTask = $process.StandardOutput.BaseStream.ReadAsync($stdoutBuffer, 0, $stdoutBuffer.Length)
        }
      } elseif ($null -ne $stderrTask) {
        $count = $stderrTask.Result
        if ($count -eq 0) {
          $stderrTask = $null
        } else {
          $remaining = [Math]::Max(0, $Limit - [int]$stderr.Length)
          $kept = [Math]::Min($remaining, $count)
          if ($kept -gt 0) { $stderr.Write($stderrBuffer, 0, $kept) }
          if ($count -gt $kept) { $stderrTruncated = $true }
          $stderrTask = $process.StandardError.BaseStream.ReadAsync($stderrBuffer, 0, $stderrBuffer.Length)
        }
      }
    }
    $process.WaitForExit()
    $stdoutText = [Text.Encoding]::UTF8.GetString($stdout.ToArray())
    $stderrText = [Text.Encoding]::UTF8.GetString($stderr.ToArray())
    if ($stdoutTruncated) { $stdoutText += "`n...[output truncated at 8192 bytes]" }
    if ($stderrTruncated) { $stderrText += "`n...[output truncated at 8192 bytes]" }
    return [pscustomobject]@{
      ExitCode = $process.ExitCode
      Stdout = $stdoutText
      Stderr = $stderrText
      StdoutBytesStored = $stdout.Length
      StderrBytesStored = $stderr.Length
    }
  } finally {
    $stdout.Dispose()
    $stderr.Dispose()
    $process.Dispose()
  }
}

function Test-McpToolSurface([string]$BinaryPath) {
  $script:McpFailureCode = ""
  $script:McpFailureReason = ""
  if (-not (Test-Path $BinaryPath)) {
    $script:McpFailureCode = "mcp_binary_missing"
    $script:McpFailureReason = "Runtime binary is missing: $BinaryPath"
    return $false
  }
  try {
      # Runtime argv contract: mcp register --binary $BinaryPath --json
      $result = Invoke-BoundedNativeCommand `
      $BinaryPath `
      @("mcp", "register", "--binary", $BinaryPath, "--json") `
      @{ SIMPLICIO_MCP_URL = $SimplicioMcpUrl }
    if ($result.ExitCode -eq 0) { return $true }
    $failure = Resolve-RuntimeFailure `
      $result.Stdout `
      $result.Stderr `
      $result.ExitCode
    $script:McpFailureCode = $failure.Code
    $script:McpFailureReason = $failure.Reason
    return $false
  } catch {
    $script:McpFailureCode = "mcp_registration_failed"
    $script:McpFailureReason = Limit-FailureText $_.Exception.Message
    return $false
  }
}

function Sync-PublicRouteOverlay {
  $script:HookFailureCode = ""
  $script:HookFailureReason = ""
  $hookDir = Join-Path $PurgeDir "hooks"
  $hookPath = Join-Path $hookDir "mcp-route.ps1"
  $hookTemp = Join-Path $hookDir (".mcp-route.ps1.download-$PID")
  $hookStage = "existing_checksum"
  try {
    if (Test-Path $hookPath) {
      $currentHash = (Get-FileHash -Algorithm SHA256 -Path $hookPath).Hash.ToLowerInvariant()
      if ($currentHash -eq $PublicRouteSha256) { return $true }
    }
    $hookStage = "directory_create"
    New-Item -ItemType Directory -Force -Path $hookDir | Out-Null
    $hookStage = "download"
    Invoke-WebRequest -Uri $PublicRouteUrl -OutFile $hookTemp -UseBasicParsing
    $hookStage = "download_checksum"
    $downloadHash = (Get-FileHash -Algorithm SHA256 -Path $hookTemp).Hash.ToLowerInvariant()
    if ($downloadHash -ne $PublicRouteSha256) {
      $script:HookFailureCode = "hook_checksum_mismatch"
      $script:HookFailureReason = "Downloaded hook SHA256 mismatch: expected $PublicRouteSha256, got $downloadHash"
      return $false
    }
    $hookStage = "marker_check"
    $downloadText = Get-Content -Raw -Path $hookTemp
    if ($downloadText -notmatch 'simplicio-hook-version: 3240-v12') {
      $script:HookFailureCode = "hook_marker_missing"
      $script:HookFailureReason = "Downloaded hook is missing simplicio-hook-version: 3240-v12"
      return $false
    }
    $hookStage = "activation"
    Move-Item -Force -Path $hookTemp -Destination $hookPath
    return $true
  } catch {
    $errorBody = if ($null -ne $_.ErrorDetails) { Limit-FailureText $_.ErrorDetails.Message } else { "" }
    $exceptionReason = Limit-FailureText $_.Exception.Message
    if ($hookStage -eq "download" -and -not [string]::IsNullOrWhiteSpace($errorBody)) {
      $failure = Resolve-RuntimeFailure $errorBody $exceptionReason 1
      $script:HookFailureCode = if ($failure.Code -eq "mcp_registration_failed") { "hook_download_failed" } else { $failure.Code }
      $script:HookFailureReason = $failure.Reason
    } else {
      $script:HookFailureCode = "hook_$($hookStage)_failed"
      $script:HookFailureReason = $exceptionReason
    }
    return $false
  } finally {
    if (Test-Path $hookTemp) { Remove-Item -Force $hookTemp -ErrorAction SilentlyContinue }
  }
}

  function Test-HostPluginHelpContract([string]$Stdout, [string]$Stderr) {
    $helpText = "$Stdout`n$Stderr"
    $required = @(
      "simplicio.host-plugins/cli-v1",
      "simplicio host-plugins plan",
      "simplicio host-plugins apply",
      "simplicio host-plugins pending",
      "simplicio host-plugins reconcile"
    )
    foreach ($marker in $required) {
      if (-not $helpText.Contains($marker)) { return $false }
    }
    return $true
  }

  function Test-HostPluginCapability {
  $script:HostPluginsState = "unavailable"
  $script:HostPluginsCommand = $null
  $script:HostPluginsReason = "Runtime host-plugins capability is unavailable"
  if (-not (Test-Path $DestPath)) {
    $script:HostPluginsReason = "Runtime binary is missing; host-plugins capability was not checked"
    return $false
  }
  try {
    $result = Invoke-BoundedNativeCommand $DestPath @("host-plugins", "--help")
      if ($result.ExitCode -eq 0 -and (Test-HostPluginHelpContract $result.Stdout $result.Stderr)) {
      $script:HostPluginsState = "pending_consent"
        $script:HostPluginsCommand = "simplicio host-plugins plan --all"
      $script:HostPluginsReason = "Host plugins require separate explicit user consent."
      return $true
    }
      if ($result.ExitCode -eq 0) {
        $script:HostPluginsReason = "Runtime host-plugins capability unavailable: Runtime returned exit code 0 without the required simplicio.host-plugins/cli-v1 contract marker and commands"
      } else {
        $failure = Resolve-RuntimeFailure $result.Stdout $result.Stderr $result.ExitCode
        $script:HostPluginsReason = "Runtime host-plugins capability unavailable: $($failure.Reason)"
      }
    return $false
  } catch {
    $script:HostPluginsReason = "Runtime host-plugins capability unavailable: $(Limit-FailureText $_.Exception.Message)"
    return $false
  }
}

function Report-HostPluginConsent {
  if ($script:HostPluginsState -eq "pending_consent") {
    Write-Host "  - host plugins are pending separate consent; no host plugin was changed"
      Write-Host "  - review the plan only through Runtime: `"$DestPath`" host-plugins plan --all"
  } else {
    Write-Warning "Runtime host-plugins capability is unavailable; no host plugin was changed"
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
      Write-Host "  [OK] fresh Google session and entitlement verified"
    } else {
      Write-Host "  [FAIL] Google session is missing, cached, expired, revoked, or lacks entitlement"
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
try {
$script:InstallStage = "runtime_download"
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
    Fail-Install "Refusing to install: manifest requires Ed25519 signatures but signing_pubkey is missing."
    exit 1
  }
  if ($SignatureRequired -and $ExpectedPublicKey -cne $PinnedPublicKey) {
    Fail-Install "Refusing to install: manifest Ed25519 public key does not match the pinned installer key."
    exit 1
  }
}
if ($SignatureRequired -and (-not $ExpectedSigned -or [string]::IsNullOrWhiteSpace($ExpectedSignature))) {
  Fail-Install "Refusing to install: the manifest requires an Ed25519 signature, but target '$Target' has no published signature."
  exit 1
} elseif (-not $ExpectedSha256) {
  if ($ExpectedSigned) {
    Fail-Install "Refusing to install: published Ed25519 signature has no verifiable SHA256 digest."
    exit 1
  } elseif ($env:SIMPLICIO_ALLOW_UNVERIFIED -eq "1" -and $env:SIMPLICIO_CHANNEL -eq "unofficial") {
    Write-Host "  ! no published checksum for target '$Target' — proceeding UNVERIFIED (SIMPLICIO_ALLOW_UNVERIFIED=1, unofficial channel)"
  } else {
    Fail-Install "Refusing to install: no published SHA256 checksum for target '$Target' in the update manifest."
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
  Fail-Install "Download failed for $Asset from $DownloadUrl : $($_.Exception.Message)"
  if (Test-Path $StagingPath) { Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue }
  exit 1
}

if (-not (Test-Path $StagingPath) -or (Get-Item $StagingPath).Length -eq 0) {
  Fail-Install "Downloaded file is missing or empty: $StagingPath"
  if (Test-Path $StagingPath) { Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue }
  exit 1
}

if ($ExpectedSha256) {
  $actualSha256 = (Get-FileHash -Path $StagingPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualSha256 -ne $ExpectedSha256.ToLowerInvariant()) {
    Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
    Fail-Install "Checksum mismatch for $Asset. Expected $ExpectedSha256, got $actualSha256. Refusing to install a tampered or corrupt binary."
    exit 1
  }
  Write-Host "  ✓ SHA256 verified: $actualSha256"
}

if ($ExpectedSigned) {
  if (-not (Test-Ed25519Signature $StagingPath $ExpectedSignature $PinnedPublicKey $ExpectedSha256)) {
    Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($script:Ed25519VerifyError)) {
      Fail-Install "Ed25519 signature verification failed; refusing to install."
    } else {
      Fail-Install "Ed25519 signature verification failed: $script:Ed25519VerifyError; refusing to install."
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
  Fail-Install "Runtime release does not meet the distribution contract (embedded sources, Google login, and signed-update key); installation aborted."
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
$script:InstallStage = "runtime_activation"
$script:InstallEffectStarted = $true
try {
  Move-Item -Force -Path $StagingPath -Destination $DestPath
  $script:RuntimeInstalled = $true
  $InstallTransactionActive = $false
  if (Test-Path $PreviousPath) { Remove-Item -Force $PreviousPath -ErrorAction SilentlyContinue }
} catch {
  Invoke-Rollback
  Remove-Item -Force $StagingPath -ErrorAction SilentlyContinue
  Fail-Install "Could not move verified binary into place: $($_.Exception.Message)"
  exit 1
}
Write-Host "  ✓ installed: $DestPath"

# ─── Verify the downloaded Runtime ──────────────────────────────────────────
$script:InstallStage = "runtime_contract"
try {
  $output = & $DestPath version 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) { throw "version command returned $LASTEXITCODE" }
} catch {
  Fail-Install "Binary installed but version verification failed: $($_.Exception.Message)"
  exit 1
}

if (-not (Test-RuntimeReleaseContract $DestPath)) {
  Fail-Install "This Runtime does not meet the distribution contract; refusing to finish installation. Install a compatible Runtime release."
  exit 1
}
Write-Host "  ✓ Runtime release contract verified"

# ─── Register MCP and native hooks for every detected client ──────────────
$script:InstallStage = "mcp_registration"
if (Test-McpToolSurface $DestPath) {
  $script:McpRegistered = $true
  Write-Host "  ✓ MCP and hooks registered automatically for detected clients"
} else {
  Fail-Install $script:McpFailureReason $script:McpFailureCode
  exit 1
}
$script:InstallStage = "hook_registration"
if (Sync-PublicRouteOverlay) {
  $script:HookInstalled = $true
  Write-Host "  ✓ verified public v12 hook reconciled after Runtime registration"
} else {
  Fail-Install $script:HookFailureReason $script:HookFailureCode
  exit 1
}

# Host-specific plugin changes require a second, explicit consent transaction.
# This installer never invokes host CLIs and never downloads a mutable plugin
# archive. Runtime owns planning, application, receipts and reconciliation.
[void](Test-HostPluginCapability)
Report-HostPluginConsent
Report-LoginState
Write-Host "  ✓ Direct MCP: $DestPath serve --mcp --stdio; SIMPLICIO_MCP_URL=$SimplicioMcpUrl"

$BundleDir = if ($env:SIMPLICIO_BUNDLE_DIR) { $env:SIMPLICIO_BUNDLE_DIR } else { Join-Path $env:USERPROFILE ".simplicio" }
$script:InstallStage = "runtime_report"
New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
$RuntimeReport = Join-Path $BundleDir "runtime-release.json"
try {
  $runtimeJson = & $DestPath version --json 2>&1
  if ($LASTEXITCODE -ne 0) { throw "version --json returned $LASTEXITCODE" }
  $runtimeJson | Set-Content -Encoding UTF8 $RuntimeReport
  Write-Host "  ✓ Runtime release report: $RuntimeReport"
} catch {
  if (Test-Path $RuntimeReport) { Remove-Item -Force $RuntimeReport -ErrorAction SilentlyContinue }
  Fail-Install "Could not persist the Runtime release report: $($_.Exception.Message)"
  exit 1
}

$script:InstallStage = "complete"
try {
  [void](Save-InstallReceipt "succeeded" 0 "" "")
  Write-Host "  ✓ structured install receipt: $InstallReceipt"
} catch {
  $script:InstallStage = "receipt_persistence"
  Fail-Install "Runtime/MCP/hook were installed, but the structured install receipt could not be persisted: $($_.Exception.Message)"
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
if (Test-ActiveLogin) {
  Write-Host "  ✓ fresh Google session verified"
} else {
  Write-Warning "Google login is pending; run: `"$DestPath`" auth login"
}
Write-Host "  ✓ MCP command points at $DestPath"
if ($script:HostPluginsState -eq "pending_consent") {
  Write-Host "  - host plugins are pending separate consent"
} else {
  Write-Warning "host plugins are unavailable in this Runtime"
}
Write-Host "  ✓ SIMPLICIO_MCP_URL=$SimplicioMcpUrl"
Write-Host ""
Write-Host "  Run:     simplicio chat 'hello' --repo ."
Write-Host "  REPL:    simplicio chat --repl --repo ."
Write-Host "  Doctor:  pwsh install.ps1 -Doctor"
Write-Host "  Remove:  pwsh install.ps1 -Uninstall"
Write-Host ""
} catch {
  Fail-Install $_.Exception.Message
}

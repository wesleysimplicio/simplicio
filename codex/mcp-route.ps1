# Simplicio MCP route — advisory Map cache for Windows hosts.
# simplicio-hook-version: 3240-v8
# Native shell/terminal is denied unless it directly invokes Simplicio.
param([switch]$WarmWorker)

$ErrorActionPreference = 'Stop'
$MapReceiptSchema = 'simplicio.hook-map-receipt/v1'
$InjectionReceiptSchema = 'simplicio.hook-context-injection/v1'
$UserHome = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
$overrideBin = [Environment]::GetEnvironmentVariable('SIMPLICIO_BIN')
$script:SimplicioBin = if (-not [string]::IsNullOrWhiteSpace($overrideBin)) {
  $overrideBin
} elseif ([string]::IsNullOrWhiteSpace($UserHome) -or -not [IO.Path]::IsPathRooted($UserHome)) {
  ''
} else {
  Join-Path (Join-Path $UserHome '.simplicio\bin') 'simplicio.exe'
}

function ConvertTo-ProcessArgument([string]$Value) {
  if ($null -eq $Value -or $Value.Length -eq 0) { return '""' }
  if ($Value -notmatch '[\s"]') { return $Value }
  $quoted = '"'
  $slashes = 0
  foreach ($character in $Value.ToCharArray()) {
    if ($character -eq '\') {
      $slashes += 1
      continue
    }
    if ($character -eq '"') {
      $quoted += ('\' * ($slashes * 2 + 1)) + '"'
      $slashes = 0
      continue
    }
    if ($slashes -gt 0) {
      $quoted += '\' * $slashes
      $slashes = 0
    }
    $quoted += $character
  }
  if ($slashes -gt 0) { $quoted += '\' * ($slashes * 2) }
  return $quoted + '"'
}

function Invoke-MapStep([string]$Repo, [string]$OutputPath) {
  $tmp = $OutputPath + '.tmp'
  $program = $script:SimplicioBin
  $processArguments = @('map', '--repo', $Repo, '--for-llm', 'markdown')
  if ([IO.Path]::GetExtension($program) -ieq '.ps1') {
    $processArguments = @('-NoLogo', '-NoProfile', '-NonInteractive', '-File', $program) + $processArguments
    $program = (Get-Process -Id $PID -ErrorAction Stop).Path
  }

  $start = [Diagnostics.ProcessStartInfo]::new()
  $start.FileName = $program
  $start.UseShellExecute = $false
  $start.CreateNoWindow = $true
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  if ($start.PSObject.Properties.Name -contains 'ArgumentList') {
    foreach ($argument in $processArguments) {
      [void]$start.ArgumentList.Add([string]$argument)
    }
  } else {
    $start.Arguments = (($processArguments | ForEach-Object {
      ConvertTo-ProcessArgument ([string]$_)
    }) -join ' ')
  }

  $process = [Diagnostics.Process]::new()
  try {
    $process.StartInfo = $start
    if (-not $process.Start()) { return $false }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(120000)) {
      try { $process.Kill() } catch {}
      try { $process.WaitForExit() } catch {}
      try { $stdoutTask.GetAwaiter().GetResult() | Out-Null } catch {}
      try { $stderrTask.GetAwaiter().GetResult() | Out-Null } catch {}
      Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      return $false
    }
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderrTask.GetAwaiter().GetResult() | Out-Null
    if ($process.ExitCode -ne 0 -or [string]::IsNullOrEmpty($stdout)) {
      Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      return $false
    }
    [IO.File]::WriteAllText($tmp, $stdout, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tmp -Destination $OutputPath -Force
    return $true
  } catch {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    return $false
  } finally {
    $process.Dispose()
  }
}

if ($WarmWorker) {
  $repo = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_REPO')
  $outDir = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_OUT_DIR')
  $marker = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_MARKER')
  $lock = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_LOCK')
  $generationValue = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_GENERATION')
  $success = $false
  try {
    if (
      [string]::IsNullOrWhiteSpace($repo) -or
      [string]::IsNullOrWhiteSpace($outDir) -or
      [string]::IsNullOrWhiteSpace($marker) -or
      [string]::IsNullOrWhiteSpace($lock) -or
      [string]::IsNullOrWhiteSpace($generationValue)
    ) { throw 'missing Map worker environment' }

    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    Set-Content -LiteralPath $marker -Value $PID -NoNewline
    $mapPath = Join-Path $outDir 'map.md'
    $success = Invoke-MapStep $repo $mapPath
  } catch {
    $success = $false
  } finally {
    try {
      $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
      $payload = [ordered]@{
        schema = $MapReceiptSchema
        status = if ($success) { 'ready' } else { 'failed' }
        generation = $generationValue
        completed_at_unix = $now
      }
      if ($success) {
        $mapItem = Get-Item -LiteralPath $mapPath -ErrorAction Stop
        $payload['map_sha256'] = (Get-FileHash -LiteralPath $mapPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $payload['map_bytes'] = [long]$mapItem.Length
      } else {
        $payload['retry_after_unix'] = $now + 900
      }
      $receipt = Join-Path $outDir 'warm-receipt.json'
      $tmpReceipt = $receipt + '.tmp'
      $payload | ConvertTo-Json -Compress | Set-Content -LiteralPath $tmpReceipt -NoNewline
      Move-Item -LiteralPath $tmpReceipt -Destination $receipt -Force
    } catch {}
    if (-not [string]::IsNullOrWhiteSpace($marker)) {
      Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue
    }
    if (-not [string]::IsNullOrWhiteSpace($lock)) {
      Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
    }
  }
  exit 0
}

function Allow-Unchanged {
  # No decision means allow unchanged on Codex and other supported hosts.
  exit 0
}

$raw = (@($input) -join [Environment]::NewLine)
if ([string]::IsNullOrWhiteSpace($raw)) {
  $raw = [Console]::In.ReadToEnd()
}
if ([string]::IsNullOrWhiteSpace($raw)) { Allow-Unchanged }
try { $hook = $raw | ConvertFrom-Json } catch { Allow-Unchanged }
if ($null -eq $hook) { Allow-Unchanged }

$event = [string]($hook.hookEventName)
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]($hook.hook_event_name) }
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]($hook.event) }
$event = $event.Replace('-', '_').ToLowerInvariant()
$contextEvents = @{
  'sessionstart' = 'SessionStart'; 'session_start' = 'SessionStart'
  'userpromptsubmit' = 'UserPromptSubmit'; 'user_prompt_submit' = 'UserPromptSubmit'
  'subagentstart' = 'SubagentStart'; 'subagent_start' = 'SubagentStart'
}

function Emit-Context([string]$Name, [string]$Body) {
  @{ hookSpecificOutput = @{ hookEventName = $Name; additionalContext = $Body } } |
    ConvertTo-Json -Compress
  exit 0
}

function Emit-DenyNativeShell {
  @{
    hookSpecificOutput = @{
      hookEventName = 'PreToolUse'
      permissionDecision = 'deny'
      permissionDecisionReason = (
        'Native shell/terminal is disabled; use a Simplicio MCP tool or ' +
        'invoke the command directly through simplicio.'
      )
    }
  } | ConvertTo-Json -Compress
  exit 0
}

function Get-HookToolName {
  $name = [string]($hook.toolName)
  if ([string]::IsNullOrWhiteSpace($name)) { $name = [string]($hook.tool_name) }
  if ([string]::IsNullOrWhiteSpace($name)) { $name = [string]($hook.name) }
  return $name
}

function Test-NativeShellTool([string]$Name) {
  $normalized = $Name.Trim().ToLowerInvariant().Replace('-', '_')
  if (
    [string]::IsNullOrWhiteSpace($normalized) -or
    $normalized.StartsWith('mcp__') -or
    $normalized.StartsWith('app__') -or
    $normalized.StartsWith('plugin__')
  ) { return $false }
  $parts = @($normalized -split '(?:__|::|\.)')
  $leaf = if ($parts.Count -gt 0) { $parts[-1] } else { $normalized }
  $shellNames = @(
    'bash', 'cmd', 'exec_command', 'execute_command', 'powershell', 'pwsh',
    'run_command', 'run_shell_command', 'run_terminal_command', 'shell',
    'shell_command', 'terminal', 'terminal_command', 'write_stdin'
  )
  return $shellNames -contains $leaf
}

function Get-HookCommand {
  $toolInput = $hook.toolInput
  if ($null -eq $toolInput) { $toolInput = $hook.tool_input }
  if ($null -eq $toolInput) { $toolInput = $hook.input }
  if ($null -eq $toolInput) { return '' }
  foreach ($key in @('command', 'cmd', 'script')) {
    $property = $toolInput.PSObject.Properties[$key]
    if ($null -ne $property -and $property.Value -is [string]) {
      return [string]$property.Value
    }
  }
  return ''
}

function Test-DirectSimplicioCommand([string]$Command) {
  if ([string]::IsNullOrWhiteSpace($Command)) { return $false }
  $value = $Command.Trim()
  if ($value.StartsWith('&')) { $value = $value.Substring(1).TrimStart() }
  if ([string]::IsNullOrWhiteSpace($value)) { return $false }
  foreach ($marker in @("`r", "`n", ';', '&&', '||', '|', '`', '$(', '>', '<', '&')) {
    if ($value.Contains($marker)) { return $false }
  }

  $executable = ''
  if ($value[0] -eq '"' -or $value[0] -eq "'") {
    $quote = $value[0]
    $end = $value.IndexOf($quote, 1)
    if ($end -lt 2) { return $false }
    $executable = $value.Substring(1, $end - 1)
  } else {
    $match = [regex]::Match($value, '^\S+')
    if (-not $match.Success) { return $false }
    $executable = $match.Value
  }
  $parts = @(($executable.Replace('\', '/')) -split '/')
  $leaf = if ($parts.Count -gt 0) { $parts[-1].ToLowerInvariant() } else { '' }
  return $leaf -eq 'simplicio' -or $leaf -eq 'simplicio.exe'
}

function Get-Sha256Text([string]$Text) {
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
    return -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $sha.Dispose()
  }
}

function Get-RepoGeneration([string]$Root) {
  try {
    $headOutput = @(& git -C $Root rev-parse HEAD 2>$null)
    $headExit = $LASTEXITCODE
    $statusOutput = @(& git -C $Root -c core.quotepath=false status --porcelain=v1 --untracked-files=normal 2>$null)
    $statusExit = $LASTEXITCODE
    if ($headExit -eq 0 -and $statusExit -eq 0) {
      $changed = @()
      foreach ($rowValue in $statusOutput) {
        $row = [string]$rowValue
        if ($row.Length -lt 4) { continue }
        $pathText = $row.Substring(3).Trim()
        if ($pathText.Contains(' -> ')) {
          $pathText = $pathText.Split(@(' -> '), [StringSplitOptions]::None)[-1]
        }
        $pathText = $pathText.Trim('"')
        $normalized = $pathText.Replace('\', '/')
        if ($normalized -eq '.simplicio' -or $normalized.StartsWith('.simplicio/')) { continue }
        $identity = 'missing'
        try {
          $item = Get-Item -LiteralPath (Join-Path $Root $pathText) -ErrorAction Stop
          $size = if ($item.PSIsContainer) { 0 } else { [long]$item.Length }
          $identity = '{0}:{1}' -f $item.LastWriteTimeUtc.Ticks, $size
        } catch {}
        $changed += ('{0}:{1}:{2}' -f $row.Substring(0, 2), $pathText, $identity)
      }
      $material = [ordered]@{
        head = (($headOutput -join [Environment]::NewLine).Trim())
        changed = @($changed | Sort-Object)
      } | ConvertTo-Json -Compress
      return Get-Sha256Text $material
    }
  } catch {}
  try {
    $item = Get-Item -LiteralPath $Root -ErrorAction Stop
    return Get-Sha256Text ('fallback:{0}:{1}' -f $item.FullName, $item.LastWriteTimeUtc.Ticks)
  } catch {
    return Get-Sha256Text ('fallback:{0}' -f $Root)
  }
}

function Try-AcquireLock([string]$LockPath, [int]$StaleAfterSeconds) {
  foreach ($attempt in 1..2) {
    $stream = $null
    try {
      $stream = [IO.File]::Open($LockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
      $payload = [Text.Encoding]::ASCII.GetBytes(('{0}:{1}' -f $PID, [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))
      $stream.Write($payload, 0, $payload.Length)
      return $true
    } catch [IO.IOException] {
      try {
        $age = ([DateTime]::UtcNow - (Get-Item -LiteralPath $LockPath -ErrorAction Stop).LastWriteTimeUtc).TotalSeconds
        if ($age -lt $StaleAfterSeconds) { return $false }
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction Stop
      } catch {
        return $false
      }
    } finally {
      if ($null -ne $stream) { $stream.Dispose() }
    }
  }
  return $false
}

function Get-ReadyReceipt([string]$State, [string]$Generation) {
  try {
    $receiptPath = Join-Path $State 'warm-receipt.json'
    $mapPath = Join-Path $State 'map.md'
    $receipt = Get-Content -LiteralPath $receiptPath -Raw -ErrorAction Stop | ConvertFrom-Json
    $mapItem = Get-Item -LiteralPath $mapPath -ErrorAction Stop
    if (
      $receipt.schema -eq $MapReceiptSchema -and
      $receipt.status -eq 'ready' -and
      $receipt.generation -eq $Generation -and
      ([string]$receipt.map_sha256).Length -eq 64 -and
      [long]$receipt.map_bytes -gt 0 -and
      [long]$receipt.map_bytes -eq [long]$mapItem.Length
    ) { return $receipt }
  } catch {}
  return $null
}

function Start-WarmContext([string]$Root) {
  try {
    if ([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path -LiteralPath $Root -PathType Container)) {
      return $null
    }
    $generation = Get-RepoGeneration $Root
    $result = [pscustomobject]@{ Root = $Root; Generation = $generation }
    if ([string]::IsNullOrWhiteSpace($script:SimplicioBin) -or -not (Test-Path -LiteralPath $script:SimplicioBin -PathType Leaf)) {
      return $result
    }
    $state = Join-Path $Root '.simplicio/hook-context'
    New-Item -ItemType Directory -Force -Path $state | Out-Null
    if ($null -ne (Get-ReadyReceipt $state $generation)) { return $result }

    $receiptPath = Join-Path $state 'warm-receipt.json'
    if (Test-Path -LiteralPath $receiptPath -PathType Leaf) {
      try {
        $receipt = Get-Content -LiteralPath $receiptPath -Raw -ErrorAction Stop | ConvertFrom-Json
        $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        if (
          $receipt.schema -eq $MapReceiptSchema -and
          $receipt.generation -eq $generation -and
          $receipt.status -eq 'failed' -and
          [long]$receipt.retry_after_unix -gt $now
        ) { return $result }
      } catch {}
    }

    $pidPath = Join-Path $state 'warm.pid'
    if (Test-Path $pidPath) {
      try {
        if (Get-Process -Id ([int](Get-Content $pidPath -Raw)) -ErrorAction Stop) { return $result }
      } catch {
        Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
      }
    }
    $lockPath = Join-Path $state 'warm.lock'
    if (-not (Try-AcquireLock $lockPath 300)) { return $result }

    $environment = [ordered]@{
      SIMPLICIO_BIN = $script:SimplicioBin
      SIMPLICIO_HOOK_SELF = $PSCommandPath
      SIMPLICIO_HOOK_WARM_REPO = $Root
      SIMPLICIO_HOOK_WARM_OUT_DIR = $state
      SIMPLICIO_HOOK_WARM_MARKER = $pidPath
      SIMPLICIO_HOOK_WARM_LOCK = $lockPath
      SIMPLICIO_HOOK_WARM_GENERATION = $generation
    }
    $previous = @{}
    try {
      foreach ($entry in $environment.GetEnumerator()) {
        $previous[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, 'Process')
        [Environment]::SetEnvironmentVariable($entry.Key, [string]$entry.Value, 'Process')
      }
      $shellPath = (Get-Process -Id $PID -ErrorAction Stop).Path
      $encodedWorker = [Convert]::ToBase64String(
        [Text.Encoding]::Unicode.GetBytes('& $env:SIMPLICIO_HOOK_SELF -WarmWorker')
      )
      $launch = @{
        FilePath = $shellPath
        ArgumentList = @(
          '-NoLogo', '-NoProfile', '-NonInteractive',
          '-ExecutionPolicy', 'Bypass',
          '-EncodedCommand', $encodedWorker
        )
        PassThru = $true
      }
      if ($env:OS -eq 'Windows_NT') { $launch['WindowStyle'] = 'Hidden' }
      Start-Process @launch | Out-Null
    } catch {
      Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    } finally {
      foreach ($entry in $environment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $previous[$entry.Key], 'Process')
      }
    }
    return $result
  } catch {
    # Warming is advisory and must never block the host operation.
    return $null
  }
}

function Get-CompactSummaryOnce([string]$Root, [string]$Generation) {
  $state = Join-Path $Root '.simplicio/hook-context'
  $receipt = Get-ReadyReceipt $state $Generation
  if ($null -eq $receipt) { return '' }
  try {
    $marker = Join-Path $state 'summary-receipt.json'
    $lock = Join-Path $state 'summary-receipt.lock'
    if (-not (Try-AcquireLock $lock 30)) { return '' }
    try {
      if (Test-Path -LiteralPath $marker -PathType Leaf) {
        try {
          $prior = Get-Content -LiteralPath $marker -Raw -ErrorAction Stop | ConvertFrom-Json
          if (
            $prior.schema -eq $InjectionReceiptSchema -and
            $prior.generation -eq $Generation -and
            $prior.map_sha256 -eq $receipt.map_sha256
          ) { return '' }
        } catch {}
      }
      $markerTmp = $marker + '.tmp'
      [ordered]@{
        schema = $InjectionReceiptSchema
        generation = $Generation
        map_sha256 = [string]$receipt.map_sha256
      } | ConvertTo-Json -Compress | Set-Content -LiteralPath $markerTmp -NoNewline
      Move-Item -LiteralPath $markerTmp -Destination $marker -Force
    } finally {
      Remove-Item -LiteralPath $lock -Force -ErrorAction SilentlyContinue
    }
  } catch {
    return ''
  }

  return (
    'Simplicio Map cache: generation={0} map_sha256={1} map_bytes={2}. ' +
    'The complete generated Map is available on demand via simplicio_context; ' +
    'Map content is not injected into the prompt. Native shell/terminal tools ' +
    'are disabled unless routed directly through Simplicio; third-party MCP/apps ' +
    'and non-shell native tools remain allowed. Agent fan-out is off by default; ' +
    'one optional subagent may be used economically through Simplicio MCP.'
  ) -f $Generation, $receipt.map_sha256, $receipt.map_bytes
}

function Get-RepoFromHook {
  $repo = [string]($hook.cwd)
  if ([string]::IsNullOrWhiteSpace($repo)) { $repo = [string]($hook.cwd_path) }
  if ([string]::IsNullOrWhiteSpace($repo) -and $hook.workspace) {
    $repo = [string]($hook.workspace.current_dir)
  }
  if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
  return $repo
}

$repo = Get-RepoFromHook
if ($contextEvents.ContainsKey($event)) {
  $warmed = Start-WarmContext $repo
  if ($null -ne $warmed) {
    $summary = Get-CompactSummaryOnce $warmed.Root $warmed.Generation
    if (-not [string]::IsNullOrWhiteSpace($summary)) {
      Emit-Context $contextEvents[$event] $summary
    }
  }
  Allow-Unchanged
}

# Deny native terminal execution unless the command enters through the governed
# Simplicio CLI. Third-party MCP/apps and non-shell native tools pass unchanged.
if (
  @('', 'pretooluse', 'pre_tool_use') -contains $event -and
  (Test-NativeShellTool (Get-HookToolName)) -and
  -not (Test-DirectSimplicioCommand (Get-HookCommand))
) { Emit-DenyNativeShell }

Start-WarmContext $repo | Out-Null
Allow-Unchanged

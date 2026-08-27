# Simplicio MCP route — advisory PreToolUse context for Windows hosts.
# simplicio-hook-version: 3240-v6
param([switch]$WarmWorker)

$ErrorActionPreference = 'Stop'
$UserHome = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
$overrideBin = [Environment]::GetEnvironmentVariable('SIMPLICIO_BIN')
$script:SimplicioBin = if (-not [string]::IsNullOrWhiteSpace($overrideBin)) {
  $overrideBin
} elseif ([string]::IsNullOrWhiteSpace($UserHome) -or -not [IO.Path]::IsPathRooted($UserHome)) {
  ''
} else {
  Join-Path (Join-Path $UserHome '.simplicio\bin') 'simplicio.exe'
}

if ($WarmWorker) {
  $repo = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_REPO')
  $outDir = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_OUT_DIR')
  $marker = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_MARKER')
  $lock = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_LOCK')
  $generationValue = [Environment]::GetEnvironmentVariable('SIMPLICIO_HOOK_WARM_GENERATION')

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

  function Invoke-WarmStep([string[]]$Arguments, [string]$OutputPath) {
    $tmp = $OutputPath + '.tmp'
    $program = $script:SimplicioBin
    $processArguments = @($Arguments)
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
      if (-not $process.WaitForExit(45000)) {
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
      [IO.File]::WriteAllText($tmp, $stdout)
      Move-Item -LiteralPath $tmp -Destination $OutputPath -Force
      return $process.ExitCode -eq 0
    } catch {
      Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
      return $false
    } finally {
      $process.Dispose()
    }
  }

  $success = $false
  try {
    if (
      [string]::IsNullOrWhiteSpace($repo) -or
      [string]::IsNullOrWhiteSpace($outDir) -or
      [string]::IsNullOrWhiteSpace($marker) -or
      [string]::IsNullOrWhiteSpace($lock) -or
      [string]::IsNullOrWhiteSpace($generationValue)
    ) { throw 'missing warm worker environment' }

    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    Set-Content -LiteralPath $marker -Value $PID -NoNewline
    $success = $true
    foreach ($item in @(
      @('map','--repo',$repo,'--for-llm','markdown','map.md'),
      @('fast','build','--root',$repo,'--max-bytes','32000','--json','fast-build.json'),
      @('fast','context','simplicio','--root',$repo,'--max-bytes','32000','--json','fast-context.json')
    )) {
      $name = $item[-1]
      $arguments = [string[]]$item[0..($item.Length - 2)]
      $stepOk = Invoke-WarmStep $arguments (Join-Path $outDir $name)
      if (-not $stepOk) { $success = $false }
    }
  } catch {
    $success = $false
  } finally {
    try {
      $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
      $payload = [ordered]@{
        schema = 'simplicio.hook-context-receipt/v1'
        status = if ($success) { 'ready' } else { 'failed' }
        generation = $generationValue
        completed_at_unix = $now
      }
      if (-not $success) { $payload['retry_after_unix'] = $now + 60 }
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
  # Codex 0.150.0 rejects an explicit PreToolUse allow without updatedInput.
  exit 0
}

$raw = (@($input) -join [Environment]::NewLine)
if ([string]::IsNullOrWhiteSpace($raw)) {
  $raw = [Console]::In.ReadToEnd()
}
if ([string]::IsNullOrWhiteSpace($raw)) {
  Allow-Unchanged
}

try { $hook = $raw | ConvertFrom-Json } catch {
  Allow-Unchanged
}
if ($null -eq $hook) { Allow-Unchanged }

$event = [string]($hook.hookEventName)
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]($hook.hook_event_name) }
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]($hook.event) }
$event = $event.Replace('-', '_').ToLowerInvariant()
$context = 'Simplicio pre-hook ran before the requested tool. Use simplicio_map -> simplicio_context -> simplicio_edit when that improves the task, but preserve the user explicit request and allow native and third-party tools unchanged.'
$contextEvents = @{
  'sessionstart' = 'SessionStart'; 'session_start' = 'SessionStart'
  'userpromptsubmit' = 'UserPromptSubmit'; 'user_prompt_submit' = 'UserPromptSubmit'
  'subagentstart' = 'SubagentStart'; 'subagent_start' = 'SubagentStart'
}

function Emit-Context([string]$name, [string]$body) {
  @{ hookSpecificOutput = @{ hookEventName = $name; additionalContext = $body } } | ConvertTo-Json -Compress
  exit 0
}

function Get-Sha256Text([string]$text) {
  $sha = [Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [Text.Encoding]::UTF8.GetBytes($text)
    return -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
  } finally {
    $sha.Dispose()
  }
}

function Get-RepoGeneration([string]$root) {
  try {
    $headOutput = @(& git -C $root rev-parse HEAD 2>$null)
    $headExit = $LASTEXITCODE
    $statusOutput = @(& git -C $root -c core.quotepath=false status --porcelain=v1 --untracked-files=normal 2>$null)
    $statusExit = $LASTEXITCODE
    if ($headExit -eq 0 -and $statusExit -eq 0) {
      $changed = @()
      foreach ($rowValue in $statusOutput) {
        $row = [string]$rowValue
        if ($row.Length -lt 4) { continue }
        $pathText = $row.Substring(3).Trim()
        if ($pathText.Contains(' -> ')) { $pathText = $pathText.Split(@(' -> '), [StringSplitOptions]::None)[-1] }
        $pathText = $pathText.Trim('"')
        $normalized = $pathText.Replace('\', '/')
        if ($normalized -eq '.simplicio' -or $normalized.StartsWith('.simplicio/')) { continue }
        $identity = 'missing'
        try {
          $item = Get-Item -LiteralPath (Join-Path $root $pathText) -ErrorAction Stop
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
    $item = Get-Item -LiteralPath $root -ErrorAction Stop
    return Get-Sha256Text ('fallback:{0}:{1}' -f $item.FullName, $item.LastWriteTimeUtc.Ticks)
  } catch {
    return Get-Sha256Text ('fallback:{0}' -f $root)
  }
}

function Try-AcquireWarmLock([string]$lockPath) {
  foreach ($attempt in 1..2) {
    $stream = $null
    try {
      $stream = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
      $payload = [Text.Encoding]::ASCII.GetBytes(('{0}:{1}' -f $PID, [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))
      $stream.Write($payload, 0, $payload.Length)
      return $true
    } catch [IO.IOException] {
      try {
        $age = ([DateTime]::UtcNow - (Get-Item -LiteralPath $lockPath -ErrorAction Stop).LastWriteTimeUtc).TotalSeconds
        if ($age -lt 120) { return $false }
        Remove-Item -LiteralPath $lockPath -Force -ErrorAction Stop
      } catch {
        return $false
      }
    } finally {
      if ($null -ne $stream) { $stream.Dispose() }
    }
  }
  return $false
}

function Start-WarmContext([string]$root) {
  try {
  if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root -PathType Container)) { return }
  if ([string]::IsNullOrWhiteSpace($script:SimplicioBin) -or -not (Test-Path -LiteralPath $script:SimplicioBin -PathType Leaf)) { return }
  $state = Join-Path $root '.simplicio/hook-context'
  New-Item -ItemType Directory -Force -Path $state | Out-Null
  $generation = Get-RepoGeneration $root
  $receiptPath = Join-Path $state 'warm-receipt.json'
  if (Test-Path -LiteralPath $receiptPath -PathType Leaf) {
    try {
      $receipt = Get-Content -LiteralPath $receiptPath -Raw -ErrorAction Stop | ConvertFrom-Json
      $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
      if (
        $receipt.schema -eq 'simplicio.hook-context-receipt/v1' -and
        $receipt.generation -eq $generation -and
        (
          $receipt.status -eq 'ready' -or
          ($receipt.status -eq 'failed' -and [long]$receipt.retry_after_unix -gt $now)
        )
      ) { return }
    } catch {}
  }

  $pidPath = Join-Path $state 'warm.pid'
  if (Test-Path $pidPath) {
    try { if (Get-Process -Id ([int](Get-Content $pidPath -Raw)) -ErrorAction Stop) { return } } catch { Remove-Item $pidPath -Force -ErrorAction SilentlyContinue }
  }
  $lockPath = Join-Path $state 'warm.lock'
  if (-not (Try-AcquireWarmLock $lockPath)) { return }

  $environment = [ordered]@{
    SIMPLICIO_BIN = $script:SimplicioBin
    SIMPLICIO_HOOK_SELF = $PSCommandPath
    SIMPLICIO_HOOK_WARM_REPO = $root
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
      [Environment]::SetEnvironmentVariable(
        $entry.Key,
        $previous[$entry.Key],
        'Process'
      )
    }
  }
  } catch {
    # Context warming is advisory and must never block the requested host tool.
    return
  }
}

if ($contextEvents.ContainsKey($event)) {
  $repo = [string]($hook.cwd)
  if ([string]::IsNullOrWhiteSpace($repo)) { $repo = [string]$hook.cwd_path }
  if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
  Start-WarmContext $repo
  $parts = @($context)
  $state = Join-Path $repo '.simplicio/hook-context'
  foreach ($item in @(@('map.md',24000), @('fast-context.json',8000))) {
    $file = Join-Path $state $item[0]
    if (Test-Path $file) {
      $content = Get-Content -LiteralPath $file -Raw -ErrorAction SilentlyContinue
      if ($content) { $parts += "`nSimplicio $($item[0]) (background, bounded):`n" + $content.Substring(0, [Math]::Min([int]$item[1], $content.Length)) }
    }
  }
  Emit-Context $contextEvents[$event] ($parts -join '')
}

# Advisory pre-hook: begin bounded Simplicio context work before the host tool,
# then preserve the original native, third-party, or user-requested operation.
$repo = [string]($hook.cwd)
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = [string]$hook.cwd_path }
if ([string]::IsNullOrWhiteSpace($repo) -and $hook.workspace) { $repo = [string]$hook.workspace.current_dir }
if ([string]::IsNullOrWhiteSpace($repo)) { $repo = (Get-Location).Path }
Start-WarmContext $repo
Allow-Unchanged

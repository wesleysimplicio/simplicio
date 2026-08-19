# Simplicio MCP route hook for Codex on Windows.
$ErrorActionPreference = "SilentlyContinue"

function Allow-Hook {
  Write-Output '{"decision":"allow"}'
  exit 0
}

function Deny-Hook([string]$Reason) {
  $payload = @{ decision = "deny"; reason = $Reason } | ConvertTo-Json -Compress
  Write-Output $payload
  [Console]::Error.WriteLine($Reason)
  exit 2
}

if ($env:SIMPLICIO_MCP_ROUTE -eq "0" -or $env:SIMPLICIO_MCP_ROUTE -eq "off") {
  Allow-Hook
}

$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) { Allow-Hook }
try { $hook = $raw | ConvertFrom-Json } catch { Allow-Hook }

$event = [string]($hook.hookEventName)
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]$hook.hook_event_name }
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]$hook.event }
$eventKey = $event.Replace("-", "_").ToLowerInvariant()

$context = "Use Simplicio MCP for this hop. Orient: simplicio_orient (or map --task). Create: simplicio_edit. Read one file: simplicio_file_read. Do not run simplicio --help / edit --help / runtime map / search_tool for simplicio. Do not read SKILL.md / simplicio-orient / simplicio-runtime/src. Escape: SIMPLICIO_MCP_ROUTE=0 or # simplicio:allow."
$contextEvents = @{
  "sessionstart" = "SessionStart"; "session_start" = "SessionStart"
  "userpromptsubmit" = "UserPromptSubmit"; "user_prompt_submit" = "UserPromptSubmit"
  "subagentstart" = "SubagentStart"; "subagent_start" = "SubagentStart"
}
if ($contextEvents.ContainsKey($eventKey)) {
  @{ hookSpecificOutput = @{ hookEventName = $contextEvents[$eventKey]; additionalContext = $context } } | ConvertTo-Json -Compress
  exit 0
}

$tool = [string]$hook.toolName
if ([string]::IsNullOrWhiteSpace($tool)) { $tool = [string]$hook.tool_name }
if ($tool.ToLowerInvariant().Contains("simplicio")) { Allow-Hook }
$toolInput = $hook.toolInput
if ($null -eq $toolInput) { $toolInput = $hook.tool_input }
$command = [string]$toolInput.command
$path = [string]$toolInput.target_file
if ([string]::IsNullOrWhiteSpace($path)) { $path = [string]$toolInput.file_path }
if ([string]::IsNullOrWhiteSpace($path)) { $path = [string]$toolInput.path }
if ([string]::IsNullOrWhiteSpace($path)) { $path = [string]$toolInput.file }
$blob = "$command $path"
if ($blob.Contains("simplicio:allow") -or $blob.Contains("SIMPLICIO_MCP_ROUTE=0")) { Allow-Hook }

$pathNorm = $path.Replace("\", "/")
if ($pathNorm.EndsWith("/simplicio/SKILL.md") -or $path -match "AGENTS\.md|CLAUDE\.md|USER\.md|mcp-route\.ps1|[\\/]\.grok[\\/]docs[\\/]|[\\/]\.claude[\\/]hooks[\\/]|[\\/]\.simplicio[\\/]hooks[\\/]") { Allow-Hook }

$lower = $tool.ToLowerInvariant()
$base = ($lower -split "__|/")[-1] -replace "[^a-z0-9_]", ""
if ($base -in @("list_dir", "listdir", "readdirectory")) { Allow-Hook }
if ($base -in @("read", "grep", "glob", "readdirectory", "filesearch", "read_file", "readfile") -or $lower.EndsWith("_read") -or $lower.Contains("read_file")) {
  Deny-Hook ("Use simplicio_file_read / simplicio_read / simplicio_search / simplicio_orient. " + $context)
}

if ($base -in @("write") -or $lower.EndsWith("_write")) {
  $destination = $path
  if (-not [System.IO.Path]::IsPathRooted($destination) -and $hook.cwd) { $destination = Join-Path ([string]$hook.cwd) $destination }
  if ($destination -and -not (Test-Path -LiteralPath $destination)) { Allow-Hook }
}
if ($base -in @("search_replace", "searchreplace", "strreplace") -or $lower.Contains("search_replace")) { Allow-Hook }
if ($base -in @("edit", "write", "multiedit", "strreplace", "search_replace", "searchreplace", "applypatch", "apply_patch") -or $lower.EndsWith("_write")) {
  Deny-Hook ("Use simplicio_edit for mutations. " + $context)
}

if ($base -in @("bash", "run_terminal_command", "shell", "run")) {
  if ($command -match "(^|[;&|`n])\s*\S*simplicio(\s+--help|\s+-h|\s+serve\s+--help|\s+\S+\s+--help)\b") { Deny-Hook ("Do not dump simplicio --help. " + $context) }
  if ($command -match "(^|[;&|`n])\s*(?:\S*[\\/])?simplicio(?![\w./-])\s*([;&`n]|$)") { Deny-Hook ("Do not run bare simplicio. " + $context) }
  if ($command -match "simplicio-runtime[\\/](src|schemas|crates)|edit-plan\.schema|operations\.rs") { Deny-Hook ("Do not search Simplicio source to learn edit. " + $context) }
  $lead = (($command.Trim() -split "\s+") | Where-Object { $_ -notmatch "^[A-Za-z_][A-Za-z0-9_]*=" } | Select-Object -First 1)
  if ($lead -in @("cat", "head", "tail", "less", "more", "bat", "nl", "rg", "grep", "ag", "find")) { Deny-Hook ("Use simplicio_file_read / simplicio_search instead of " + $lead + ". " + $context) }
  if ($lead -in @("sed", "awk", "perl")) { Deny-Hook ("Use simplicio_edit instead of " + $lead + ". " + $context) }
}

Allow-Hook

# Simplicio MCP route — mandatory PreToolUse policy for Windows hosts.
# simplicio-hook-version: 3240-v1
$ErrorActionPreference = 'Stop'
$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
try { $hook = $raw | ConvertFrom-Json } catch { [Console]::Error.WriteLine('Simplicio MCP hook received invalid input JSON.'); exit 2 }
if ($null -eq $hook) { [Console]::Error.WriteLine('Simplicio MCP hook received an empty input payload.'); exit 2 }
$tool = [string]$hook.toolName
if ([string]::IsNullOrWhiteSpace($tool)) { $tool = [string]$hook.tool_name }
$input = $hook.toolInput
if ($null -eq $input) { $input = $hook.tool_input }
$event = [string]$hook.hookEventName
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]$hook.hook_event_name }
if ([string]::IsNullOrWhiteSpace($event)) { $event = [string]$hook.event }
$event = $event.Replace('-','_').ToLowerInvariant()
$isPreToolUse = $event -in @('pretooluse','pre_tool_use')
$command = if ($input) { [string]$input.command } else { '' }
$path = if ($input) {
  $candidate = [string]$input.target_file
  if ([string]::IsNullOrWhiteSpace($candidate)) { $candidate = [string]$input.file_path }
  if ([string]::IsNullOrWhiteSpace($candidate)) { $candidate = [string]$input.path }
  if ([string]::IsNullOrWhiteSpace($candidate)) { $candidate = [string]$input.file }
  $candidate
} else { '' }
$context = 'Simplicio MCP is mandatory. Use simplicio_map first, then simplicio_context for the bounded Fast context packet and simplicio_memory for recall; use simplicio_file_read or simplicio_read, simplicio_search, simplicio_edit, simplicio_run/simplicio_exec, and simplicio_validate. There is no host-tool escape hatch.'
$events = @{'sessionstart'='SessionStart';'session_start'='SessionStart';'userpromptsubmit'='UserPromptSubmit';'user_prompt_submit'='UserPromptSubmit';'subagentstart'='SubagentStart';'subagent_start'='SubagentStart'}
if ($events.ContainsKey($event)) {
  @{hookSpecificOutput=@{hookEventName=$events[$event];additionalContext=$context}} | ConvertTo-Json -Compress
  exit 0
}
function Deny([string]$detail) {
  $reason = '[Simplicio MCP required] ' + $detail + ' ' + $context
  EmitDecision 'deny' $reason
  [Console]::Error.WriteLine($reason)
  exit 2
}
function EmitDecision([string]$decision, [string]$reason = '') {
  if ($isPreToolUse) {
    $specific = @{hookEventName='PreToolUse';permissionDecision=$decision}
    if ($reason) { $specific.permissionDecisionReason = $reason }
    @{hookSpecificOutput=$specific} | ConvertTo-Json -Compress
  } else {
    $result = @{decision=$decision}
    if ($reason) { $result.reason = $reason }
    $result | ConvertTo-Json -Compress
  }
}
if ($tool.ToLowerInvariant().Contains('simplicio')) { EmitDecision 'allow'; exit 0 }
$normalized = $path.Replace('\','/')
if ((Split-Path -Leaf $normalized) -in @('AGENTS.md','CLAUDE.md','GEMINI.md','USER.md') -or $normalized.Contains('/.simplicio/hooks/')) { EmitDecision 'allow'; exit 0 }
$tokens = $command.Trim() -split '\s+' | Where-Object { $_ -ne '' }
$index = 0
while ($index -lt $tokens.Count -and $tokens[$index] -match '^[A-Za-z_][A-Za-z0-9_]*=') { $index++ }
$lead = if ($index -lt $tokens.Count) { Split-Path -Leaf $tokens[$index] } else { '' }
$base = $tool.ToLowerInvariant().Split('__')[-1].Split('/')[-1] -replace '[^a-z0-9_]',''
if ($base -in @('bash','shell','run','runterminalcommand','run_terminal_command','terminal')) {
  if ($lead -in @('simplicio','simplicio.exe')) {
    if ($command -match '(^|\s)(--help|-h)(\s|$)' -or $command.Trim() -in @('simplicio','simplicio.exe')) { Deny 'Use a specific Simplicio MCP tool; do not dump CLI help or run the bare CLI.' }
    EmitDecision 'allow'; exit 0
  }
  if ($lead -in @('sed','awk','perl')) {
    if ($command -match '(^|\s)(--in-place|-i|-[A-Za-z]*i[A-Za-z]*)(\s|$)') { Deny ('Use simplicio_edit instead of ' + $lead + '.') }
    Deny ('Use simplicio_file_read / simplicio_read / simplicio_search instead of ' + $lead + '.')
  }
  Deny 'Native shell commands are disabled; use simplicio_exec, simplicio_run, or the matching Simplicio MCP tool.'
}
Deny ("Native host tool '" + $(if ($tool) { $tool } else { 'unknown' }) + "' is disabled; use the matching Simplicio MCP tool.")

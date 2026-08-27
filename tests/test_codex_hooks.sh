#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$ROOT/codex/mcp-route.sh"
WINDOWS_HOOK="$ROOT/codex/mcp-route.ps1"
PASS=0
FAIL=0

valid_output() {
  [ -z "$1" ] && return 0
  printf '%s' "$1" | python3 -c '
import json
import sys

value = json.load(sys.stdin)
specific = value.get("hookSpecificOutput") or {}
event = specific.get("hookEventName")
if event == "PreToolUse":
    decision = specific.get("permissionDecision")
    if decision == "allow" and "updatedInput" not in specific:
        raise SystemExit("unsupported permissionDecision:allow without updatedInput")
    if decision == "deny" and not specific.get("permissionDecisionReason"):
        raise SystemExit("PreToolUse deny missing permissionDecisionReason")
    if decision not in {"allow", "deny"}:
        raise SystemExit("unsupported PreToolUse decision")
elif not specific.get("additionalContext"):
    raise SystemExit("hook output has no supported context or decision")
'
}

run_case() {
  name="$1"
  payload="$2"
  want_exit="$3"
  want_token="$4"
  errfile="$(mktemp)"
  out="$(printf '%s' "$payload" | SIMPLICIO_BIN=/nonexistent bash "$HOOK" 2>"$errfile")"
  got=$?
  err="$(sed -n '1,4p' "$errfile")"
  rm -f "$errfile"

  contract_ok=0
  valid_output "$out" >/dev/null 2>&1 || contract_ok=$?
  token_ok=1
  if [ "$want_token" = "__EMPTY__" ]; then
    [ -z "$out" ] && token_ok=0
  elif printf '%s' "$out" | grep -Fq -- "$want_token"; then
    token_ok=0
  fi

  if [ "$got" = "$want_exit" ] &&
     [ "$contract_ok" -eq 0 ] &&
     [ "$token_ok" -eq 0 ]; then
    printf 'PASS %s\n' "$name"
    PASS=$((PASS + 1))
  else
    printf 'FAIL %s: exit=%s contract=%s output=%s stderr=%s\n' \
      "$name" "$got" "$contract_ok" "$out" "$err" >&2
    FAIL=$((FAIL + 1))
  fi
}

run_case "SessionStart without repository is empty" \
  '{"hook_event_name":"SessionStart","source":"startup","cwd":"/tmp"}' \
  0 '__EMPTY__'
run_case "allow Simplicio tool unchanged" \
  '{"hook_event_name":"PreToolUse","tool_name":"simplicio__simplicio_read","tool_input":{"path":"x"},"cwd":"/tmp"}' \
  0 '__EMPTY__'
run_case "allow native read unchanged" \
  '{"hook_event_name":"PreToolUse","tool_name":"read_file","tool_input":{"file_path":"src/main.rs"},"cwd":"/tmp"}' \
  0 '__EMPTY__'
run_case "allow native edit unchanged" \
  '{"hook_event_name":"PreToolUse","tool_name":"search_replace","tool_input":{"file_path":"src/main.rs"},"cwd":"/tmp"}' \
  0 '__EMPTY__'
run_case "deny native shell" \
  '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"/tmp"}' \
  0 'Native shell/terminal is disabled'
run_case "allow direct Simplicio shell unchanged" \
  '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"simplicio status --json"},"cwd":"/tmp"}' \
  0 '__EMPTY__'
run_case "deny shell wrapper around Simplicio" \
  '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"bash -lc '\''simplicio status --json'\''"},"cwd":"/tmp"}' \
  0 'Native shell/terminal is disabled'
run_case "allow third-party tool unchanged" \
  '{"hook_event_name":"PreToolUse","tool_name":"mcp__cloudflare__zones_list","tool_input":{},"cwd":"/tmp"}' \
  0 '__EMPTY__'
run_case "fail open on malformed input" 'not-json' 0 '__EMPTY__'

if ! grep -q 'Simplicio Map cache:' "$HOOK" ||
   ! grep -q 'map_sha256' "$HOOK" ||
   ! grep -q 'simplicio_context' "$HOOK"; then
  printf 'FAIL hook context is missing compact Map receipt/context routing\n' >&2
  FAIL=$((FAIL + 1))
fi
if ! grep -q 'Allow-Unchanged' "$WINDOWS_HOOK"; then
  printf 'FAIL Windows hook is missing empty allow-unchanged contract\n' >&2
  FAIL=$((FAIL + 1))
fi

if command -v pwsh >/dev/null 2>&1; then
  scratch="$(mktemp -d)"
  repo="$scratch/repo"
  fake_bin="$scratch/simplicio-fake.ps1"
  mkdir -p "$repo"
  printf '%s\n' 'exit 0' >"$fake_bin"
  chmod 0555 "$repo"
  payload="{\"hookEventName\":\"PreToolUse\",\"toolName\":\"read_file\",\"cwd\":\"$repo\"}"
  ps_out="$(printf '%s' "$payload" |
    env SIMPLICIO_BIN="$fake_bin" \
      pwsh -NoLogo -NoProfile -NonInteractive -File "$WINDOWS_HOOK" 2>/dev/null)"
  ps_exit=$?
  chmod 0755 "$repo"
  rm -rf "$scratch"
  if [ "$ps_exit" -eq 0 ] && [ -z "$ps_out" ]; then
    printf 'PASS Windows read-only repository fails open\n'
    PASS=$((PASS + 1))
  else
    printf 'FAIL Windows read-only repository exit=%s output=%s\n' \
      "$ps_exit" "$ps_out" >&2
    FAIL=$((FAIL + 1))
  fi
else
  printf 'SKIP Windows read-only repository (pwsh unavailable)\n'
fi

printf '%s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]

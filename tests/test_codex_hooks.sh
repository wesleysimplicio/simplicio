#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK="$ROOT/codex/mcp-route.sh"
PASS=0
FAIL=0

run_case() {
  name="$1"
  payload="$2"
  want_exit="$3"
  want_token="$4"
  errfile="$(mktemp)"
  out="$(printf '%s' "$payload" | bash "$HOOK" 2>"$errfile")"
  got=$?
  rm -f "$errfile"
  if [ "$got" = "$want_exit" ] && printf '%s' "$out" | grep -q "$want_token"; then
    printf 'PASS %s\n' "$name"
    PASS=$((PASS + 1))
  else
    printf 'FAIL %s: exit=%s output=%s\n' "$name" "$got" "$out" >&2
    FAIL=$((FAIL + 1))
  fi
}

run_case "context" '{"hook_event_name":"SessionStart","source":"startup"}' 0 'SessionStart'
run_case "allow simplicio tool" '{"toolName":"simplicio__simplicio_read","toolInput":{"path":"x"}}' 0 'allow'
run_case "deny host read" '{"toolName":"read_file","toolInput":{"file_path":"src/main.rs"}}' 2 'deny'
run_case "deny native edit" '{"toolName":"search_replace","toolInput":{"file_path":"src/main.rs"}}' 2 'deny'
run_case "deny native shell" '{"toolName":"Bash","toolInput":{"command":"git status"}}' 2 'deny'

check_pre_tool_use_reason() {
  name="$1"
  payload="$2"
  prefix="$3"
  out="$(printf '%s' "$payload" | bash "$HOOK" 2>/dev/null)"
  got=$?
  if [ "$got" = 2 ] && printf '%s' "$out" | PREFIX="$prefix" python3 -c '
import json, os, sys
reason = json.load(sys.stdin)["hookSpecificOutput"]["permissionDecisionReason"]
assert reason.startswith(os.environ["PREFIX"])
'; then
    printf 'PASS %s\n' "$name"
    PASS=$((PASS + 1))
  else
    printf 'FAIL %s: exit=%s output=%s\n' "$name" "$got" "$out" >&2
    FAIL=$((FAIL + 1))
  fi
}

check_pre_tool_use_reason "read-only sed points to MCP read" \
  '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"sed -n 1,5p src/main.rs"}}' \
  '[Simplicio MCP required] Use simplicio_file_read'
check_pre_tool_use_reason "mutating sed points to MCP edit" \
  '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"sed -i s/old/new/ src/main.rs"}}' \
  '[Simplicio MCP required] Use simplicio_edit'

check_pre_tool_use_schema() {
  name="$1"
  payload="$2"
  want_exit="$3"
  out="$(printf '%s' "$payload" | bash "$HOOK" 2>/dev/null)"
  got=$?
  if [ "$got" = "$want_exit" ] && printf '%s' "$out" | python3 -c '
import json, sys
value = json.load(sys.stdin)
specific = value.get("hookSpecificOutput") or {}
assert specific.get("hookEventName") == "PreToolUse"
assert specific.get("permissionDecision") in {"allow", "deny", "ask"}
'; then
    printf 'PASS %s\n' "$name"
    PASS=$((PASS + 1))
  else
    printf 'FAIL %s: exit=%s output=%s\n' "$name" "$got" "$out" >&2
    FAIL=$((FAIL + 1))
  fi
}

check_pre_tool_use_schema "PreToolUse allow schema" \
  '{"hook_event_name":"PreToolUse","tool_name":"simplicio__simplicio_read","tool_input":{"path":"src/main.rs"},"cwd":"/tmp"}' 0
check_pre_tool_use_schema "PreToolUse deny schema" \
  '{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"src/main.rs"},"cwd":"/tmp"}' 2

if ! grep -q 'simplicio_map' "$HOOK" || ! grep -q 'simplicio_context' "$HOOK"; then
  printf 'FAIL hook context is missing map/context routing\n' >&2
  FAIL=$((FAIL + 1))
fi

printf '%s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]

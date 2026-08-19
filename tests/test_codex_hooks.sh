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
run_case "allow search replace" '{"toolName":"search_replace","toolInput":{"file_path":"src/main.rs"}}' 0 'allow'

printf '%s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]

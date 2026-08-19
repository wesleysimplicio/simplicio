#!/usr/bin/env bash
# Simplicio MCP route hook for Codex.
# It nudges host reads/edits toward the local Simplicio MCP tools while keeping
# an explicit escape hatch for operations that must stay host-native.
set -uo pipefail

if [ "${SIMPLICIO_MCP_ROUTE:-on}" = "0" ] || [ "${SIMPLICIO_MCP_ROUTE:-on}" = "off" ]; then
  printf '%s\n' '{"decision":"allow"}'
  exit 0
fi

INPUT="$(cat 2>/dev/null || true)"
[ -n "$INPUT" ] || { printf '%s\n' '{"decision":"allow"}'; exit 0; }

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' '{"decision":"allow"}'
  exit 0
fi

export SIMPLICIO_MCP_ROUTE_INPUT="$INPUT"
python3 - <<'PY'
import json
import os
import re
import sys

raw = os.environ.get("SIMPLICIO_MCP_ROUTE_INPUT", "")
try:
    hook = json.loads(raw)
except Exception:
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

event = (
    hook.get("hookEventName")
    or hook.get("hook_event_name")
    or hook.get("event")
    or ""
).replace("-", "_").lower()
tool = hook.get("toolName") or hook.get("tool_name") or ""
tool_input = hook.get("toolInput") or hook.get("tool_input") or {}
if not isinstance(tool_input, dict):
    tool_input = {}

create_plan = (
    '{"file":"<relative-path>","operations":[{"op":"create",'
    '"content":"<file body>"}]}'
)
context = (
    "Use Simplicio MCP for this hop. "
    "Orient: simplicio_orient (or map --task). "
    "Create: simplicio_edit plan=" + create_plan + ". "
    "Read one file: simplicio_file_read. "
    "Do not run simplicio --help / edit --help / runtime map / search_tool for simplicio. "
    "Do not read SKILL.md / simplicio-orient / simplicio-runtime/src. "
    "Second pass on a file you just wrote: search_replace the tokens; do not re-read. "
    "Escape: SIMPLICIO_MCP_ROUTE=0 or # simplicio:allow."
)

context_events = {
    "sessionstart": "SessionStart",
    "session_start": "SessionStart",
    "userpromptsubmit": "UserPromptSubmit",
    "user_prompt_submit": "UserPromptSubmit",
    "subagentstart": "SubagentStart",
    "subagent_start": "SubagentStart",
}
if event in context_events:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": context_events[event],
            "additionalContext": context,
        }
    }))
    raise SystemExit(0)

lower = str(tool).lower()
if "simplicio" in lower:
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

command = str(tool_input.get("command") or "")
path = str(
    tool_input.get("target_file")
    or tool_input.get("file_path")
    or tool_input.get("path")
    or tool_input.get("file")
    or ""
)
blob = f"{command} {path}"
if "simplicio:allow" in blob or "SIMPLICIO_MCP_ROUTE=0" in blob:
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

bootstrap = (
    "AGENTS.md",
    "CLAUDE.md",
    "USER.md",
    "mcp-route.sh",
    "/.grok/docs/",
    "/.claude/hooks/",
    "/.simplicio/hooks/",
)
path_norm = path.replace("\\", "/")
if path_norm.endswith("/simplicio/SKILL.md") or any(token in path for token in bootstrap):
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)


def deny(reason: str) -> None:
    print(json.dumps({"decision": "deny", "reason": reason}))
    sys.stderr.write(reason + "\n")
    raise SystemExit(2)


reads = {
    "read", "grep", "glob", "readdirectory", "filesearch", "read_file",
    "readfile", "list_dir", "listdir",
}
edits = {
    "edit", "write", "multiedit", "strreplace", "search_replace",
    "searchreplace", "applypatch", "apply_patch",
}
base = re.sub(r"[^a-z0-9_]+", "", lower.split("__")[-1].split("/")[-1])

if base in {"list_dir", "listdir", "readdirectory"}:
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

if base in reads or lower.endswith("_read") or "read_file" in lower:
    deny("Use simplicio_file_read / simplicio_read / simplicio_search / simplicio_orient. " + context)

if base in {"write"} or lower.endswith("_write"):
    destination = path
    cwd = hook.get("cwd") or hook.get("cwd_path") or os.getcwd()
    if destination and not os.path.isabs(destination):
        destination = os.path.join(str(cwd), destination)
    if destination and not os.path.exists(destination):
        print(json.dumps({"decision": "allow"}))
        raise SystemExit(0)

if base in {"search_replace", "searchreplace", "strreplace"} or "search_replace" in lower:
    print(json.dumps({"decision": "allow"}))
    raise SystemExit(0)

if base in edits or lower.endswith("_write"):
    deny("Use simplicio_edit for mutations. Create: simplicio_edit plan=" + create_plan + ". " + context)

if base in {"bash", "run_terminal_command", "shell", "run"}:
    if re.search(
        r"(^|[;&|\n])\s*\S*simplicio(\s+--help|\s+-h|\s+serve\s+--help|\s+\S+\s+--help)\b",
        command,
    ):
        deny("Do not dump simplicio --help. " + context)
    if re.search(r"(?:^|[;&|\n])\s*(?:\S*/)?simplicio(?![\w./-])\s*(?:[;&\n]|$)", command):
        deny("Do not run bare simplicio (it dumps USAGE). " + context)
    runtime_source = (
        "simplicio-runtime/src", "simplicio-runtime/schemas", "simplicio-runtime/crates",
        "edit-plan.schema", "operations.rs",
    )
    if any(token in command for token in runtime_source):
        deny("Do not search Simplicio source to learn edit. " + context)
    tokens = command.strip().split()
    index = 0
    while index < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[index]):
        index += 1
    lead = os.path.basename(tokens[index]) if index < len(tokens) else ""
    if lead in {"cat", "head", "tail", "less", "more", "bat", "nl", "rg", "grep", "ag", "find"}:
        deny("Use simplicio_file_read / simplicio_search instead of " + lead + ". " + context)
    if lead in {"sed", "awk", "perl"}:
        deny("Use simplicio_edit instead of " + lead + ". " + context)
    if lead in {"simplicio", "git", "gh", "cargo", "npm", "python", "python3", "sqlite3", "rustfmt"}:
        print(json.dumps({"decision": "allow"}))
        raise SystemExit(0)

print(json.dumps({"decision": "allow"}))
PY

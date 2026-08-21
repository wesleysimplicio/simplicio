#!/usr/bin/env bash
# Simplicio MCP route — mandatory PreToolUse policy for every supported host.
# simplicio-hook-version: 3240-v1
set -uo pipefail

INPUT="$(cat 2>/dev/null || true)"
[ -n "$INPUT" ] || exit 0
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Simplicio MCP hook cannot run because python3 is unavailable.' >&2
  exit 2
fi
export SIMPLICIO_MCP_ROUTE_INPUT="$INPUT"
python3 - <<'PY'
import json, os, pathlib, re, subprocess, sys

raw = os.environ.get("SIMPLICIO_MCP_ROUTE_INPUT", "")
try:
    hook = json.loads(raw)
except Exception:
    print("Simplicio MCP hook received invalid input JSON.", file=sys.stderr)
    raise SystemExit(2)

event = str(hook.get("hookEventName") or hook.get("hook_event_name") or hook.get("event") or "").replace("-", "_").lower()
tool = str(hook.get("toolName") or hook.get("tool_name") or "")
tool_input = hook.get("toolInput") or hook.get("tool_input") or {}
if not isinstance(tool_input, dict): tool_input = {}
context = ("Simplicio MCP is mandatory. Use simplicio_map first, then simplicio_context for the bounded Fast context packet "
           "and simplicio_memory for recall; use simplicio_file_read or simplicio_read, simplicio_search, "
           "simplicio_edit, simplicio_run/simplicio_exec, and simplicio_validate. There is no host-tool escape hatch.")

def which(name):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = pathlib.Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK): return str(candidate)
    return None

def warm(root):
    root = pathlib.Path(root).expanduser()
    binary = which("simplicio")
    if not root.is_dir() or not binary: return
    state = root / ".simplicio" / "hook-context"
    try:
        state.mkdir(parents=True, exist_ok=True)
        marker = state / "warm.pid"
        if marker.is_file():
            try:
                os.kill(int(marker.read_text().strip()), 0); return
            except (ValueError, OSError): pass
        worker = (
            "import pathlib,subprocess,sys\n"
            "root=pathlib.Path(sys.argv[1]); state=root/'.simplicio'/'hook-context'; state.mkdir(parents=True,exist_ok=True); marker=state/'warm.pid'; marker.write_text(str(__import__('os').getpid()))\n"
            "def run(args,out):\n"
            "  tmp=out.with_suffix(out.suffix+'.tmp')\n"
            "  try:\n"
            "    with open(tmp,'w',encoding='utf-8') as f: subprocess.run(args,stdout=f,stderr=subprocess.DEVNULL,timeout=45,check=False)\n"
            "    tmp.replace(out)\n"
            "  except Exception:\n"
            "    try: tmp.unlink()\n"
            "    except OSError: pass\n"
            "try:\n"
            "  binary=sys.argv[2]\n"
            "  run([binary,'map','--repo',str(root),'--for-llm','markdown'],state/'map.md')\n"
            "  run([binary,'fast','build','--root',str(root),'--max-bytes','32000','--json'],state/'fast-build.json')\n"
            "  run([binary,'fast','context','--root',str(root),'--max-bytes','32000','--json'],state/'fast-context.json')\n"
            "finally:\n"
            "  try: marker.unlink()\n"
            "  except OSError: pass\n"
        )
        subprocess.Popen([sys.executable,"-c",worker,str(root),binary], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, ValueError): pass

def packet(root):
    state = pathlib.Path(root).expanduser()/".simplicio"/"hook-context"
    parts=[]
    for name,limit in (("map.md",24000),("fast-context.json",8000)):
        try:
            value=(state/name).read_text(encoding="utf-8",errors="replace")
            if value.strip(): parts.append(f"\nSimplicio {name} (background, bounded):\n{value[:limit]}")
        except OSError: pass
    return "".join(parts)

events={"sessionstart":"SessionStart","session_start":"SessionStart","userpromptsubmit":"UserPromptSubmit","user_prompt_submit":"UserPromptSubmit","subagentstart":"SubagentStart","subagent_start":"SubagentStart"}
pre_tool_use = event in {"pretooluse", "pre_tool_use"}
if event in events:
    workspace=hook.get("workspace") or {}
    root=str(hook.get("cwd") or hook.get("cwd_path") or (workspace.get("current_dir") if isinstance(workspace,dict) else "") or os.getcwd())
    warm(root)
    print(json.dumps({"hookSpecificOutput":{"hookEventName":events[event],"additionalContext":context+packet(root)}}))
    raise SystemExit(0)

def emit_decision(decision, reason=None):
    if pre_tool_use:
        specific = {"hookEventName": "PreToolUse", "permissionDecision": decision}
        if reason: specific["permissionDecisionReason"] = reason
        print(json.dumps({"hookSpecificOutput": specific}))
    else:
        result = {"decision": decision}
        if reason: result["reason"] = reason
        print(json.dumps(result))

def allow(): emit_decision("allow"); raise SystemExit(0)
def deny(detail):
    reason="[Simplicio MCP required] "+detail+" "+context
    emit_decision("deny", reason); sys.stderr.write(reason+"\n"); raise SystemExit(2)

if "simplicio" in tool.lower(): allow()
command=str(tool_input.get("command") or "")
path=str(tool_input.get("target_file") or tool_input.get("file_path") or tool_input.get("path") or tool_input.get("file") or "")
normalized=path.replace("\\","/")
if normalized.rsplit("/",1)[-1] in {"AGENTS.md","CLAUDE.md","GEMINI.md","USER.md"} or "/.simplicio/hooks/" in normalized: allow()

tokens=command.strip().split(); i=0
while i<len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=",tokens[i]): i+=1
lead=os.path.basename(tokens[i]) if i<len(tokens) else ""
base=re.sub(r"[^a-z0-9_]+","",tool.lower().split("__")[-1].split("/")[-1])
if base in {"bash","shell","run","runterminalcommand","run_terminal_command","terminal"}:
    if lead in {"simplicio","simplicio.exe"}:
        if re.search(r"(?:^|\s)(?:--help|-h)(?:\s|$)",command) or command.strip() in {"simplicio","simplicio.exe"}: deny("Use a specific Simplicio MCP tool; do not dump CLI help or run the bare CLI.")
        allow()
    if lead in {"sed", "awk", "perl"}:
        in_place = re.search(r"(?:^|\s)(?:--in-place|-i|-[A-Za-z]*i[A-Za-z]*)(?:\s|$)", command)
        if in_place:
            deny("Use simplicio_edit instead of " + lead + ".")
        deny("Use simplicio_file_read / simplicio_read / simplicio_search instead of " + lead + ".")
    deny("Native shell commands are disabled; use simplicio_exec, simplicio_run, or the matching Simplicio MCP tool.")
deny("Native host tool '"+(tool or "unknown")+"' is disabled; use the matching Simplicio MCP tool.")
PY

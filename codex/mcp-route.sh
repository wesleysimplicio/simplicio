#!/usr/bin/env bash
# Simplicio MCP route — advisory Map cache for every supported host.
# simplicio-hook-version: 3240-v8
#
# Native shell/terminal is denied unless it directly invokes Simplicio.
# Third-party MCP/apps and non-shell native tools remain allowed unchanged.
# The hook builds one complete Map artifact per repository generation and emits
# only a compact content-addressed receipt once per repository generation.
set -uo pipefail

SIMPLICIO_BIN="${SIMPLICIO_BIN:-${SIMPLICIO_BIN_DIR:-${HOME}/.simplicio/bin}/simplicio}"
export SIMPLICIO_BIN

INPUT="$(cat 2>/dev/null || true)"
# Codex 0.150.0 rejects an explicit PreToolUse allow without updatedInput.
# Empty stdout is the portable allow-unchanged contract.
[ -n "$INPUT" ] || exit 0

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

export SIMPLICIO_MCP_ROUTE_INPUT="$INPUT"
python3 - <<'PY'
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time

raw = os.environ.get("SIMPLICIO_MCP_ROUTE_INPUT", "")
RUNTIME_BIN = os.environ.get("SIMPLICIO_BIN") or str(
    pathlib.Path.home() / ".simplicio" / "bin" / "simplicio"
)
MAP_RECEIPT_SCHEMA = "simplicio.hook-map-receipt/v1"
INJECTION_RECEIPT_SCHEMA = "simplicio.hook-context-injection/v1"

try:
    hook = json.loads(raw)
except Exception:
    # Advisory hooks fail open for malformed third-party payloads.
    raise SystemExit(0)

event = (
    hook.get("hookEventName")
    or hook.get("hook_event_name")
    or hook.get("event")
    or ""
).replace("-", "_").lower()


def repo_from_hook() -> str:
    workspace = hook.get("workspace") or {}
    if not isinstance(workspace, dict):
        workspace = {}
    return str(
        hook.get("cwd")
        or hook.get("cwd_path")
        or workspace.get("current_dir")
        or os.getcwd()
    )


def hook_tool_name() -> str:
    return str(
        hook.get("toolName")
        or hook.get("tool_name")
        or hook.get("name")
        or ""
    )


def hook_tool_input() -> dict:
    value = hook.get("toolInput") or hook.get("tool_input") or hook.get("input") or {}
    return value if isinstance(value, dict) else {}


def is_native_shell_tool(name: str) -> bool:
    normalized = name.strip().lower().replace("-", "_")
    if not normalized or normalized.startswith(("mcp__", "app__", "plugin__")):
        return False
    leaf = re.split(r"(?:::|__|\.)", normalized)[-1]
    shell_names = {
        "bash",
        "cmd",
        "exec_command",
        "execute_command",
        "powershell",
        "pwsh",
        "run_command",
        "run_shell_command",
        "run_terminal_command",
        "shell",
        "shell_command",
        "terminal",
        "terminal_command",
        "write_stdin",
    }
    return normalized in shell_names or leaf in shell_names


def requested_command() -> str:
    values = hook_tool_input()
    for key in ("command", "cmd", "script"):
        value = values.get(key)
        if isinstance(value, str):
            return value
    return ""


def is_direct_simplicio_command(command: str) -> bool:
    value = command.strip()
    if not value:
        return False
    if value.startswith("&"):
        value = value[1:].lstrip()
    if not value or any(marker in value for marker in (
        "\r", "\n", ";", "&&", "||", "|", "`", "$(", ">", "<", "&"
    )):
        return False
    if value[0] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        if end < 2:
            return False
        executable = value[1:end]
    else:
        executable = value.split(None, 1)[0]
    leaf = re.split(r"[\\/]", executable)[-1].lower()
    return leaf in {"simplicio", "simplicio.exe"}


def deny_native_shell() -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Native shell/terminal is disabled; use a Simplicio MCP "
                        "tool or invoke the command directly through simplicio."
                    ),
                }
            },
            separators=(",", ":"),
        )
    )
    raise SystemExit(0)


def repository_generation(root: pathlib.Path) -> str:
    """Cheap content generation: HEAD plus visible non-Simplicio deltas."""
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        status = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "core.quotepath=false",
                "status",
                "--porcelain=v1",
                "--untracked-files=normal",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if head.returncode == 0 and status.returncode == 0:
            changed = []
            for row in status.stdout.splitlines():
                if len(row) < 4:
                    continue
                path_text = row[3:].strip()
                if " -> " in path_text:
                    path_text = path_text.rsplit(" -> ", 1)[1]
                path_text = path_text.strip('"')
                if path_text == ".simplicio" or path_text.startswith(".simplicio/"):
                    continue
                path = root / path_text
                try:
                    stat = path.stat()
                    identity = f"{stat.st_mtime_ns}:{stat.st_size}"
                except OSError:
                    identity = "missing"
                changed.append(f"{row[:2]}:{path_text}:{identity}")
            material = json.dumps(
                {"head": head.stdout.strip(), "changed": sorted(changed)},
                sort_keys=True,
                separators=(",", ":"),
            )
            return hashlib.sha256(material.encode("utf-8")).hexdigest()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        stat = root.stat()
        material = f"fallback:{root.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        material = f"fallback:{root}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def acquire_lock(lock_path: pathlib.Path, stale_after: int) -> bool:
    for _ in range(2):
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime < stale_after:
                    return False
                lock_path.unlink()
            except OSError:
                return False
            continue
        try:
            os.write(descriptor, f"{os.getpid()}:{int(time.time())}".encode("ascii"))
        finally:
            os.close(descriptor)
        return True
    return False


def read_ready_receipt(state: pathlib.Path, generation: str) -> dict | None:
    try:
        receipt = json.loads((state / "warm-receipt.json").read_text(encoding="utf-8"))
        map_path = state / "map.md"
        if (
            receipt.get("schema") == MAP_RECEIPT_SCHEMA
            and receipt.get("status") == "ready"
            and receipt.get("generation") == generation
            and isinstance(receipt.get("map_sha256"), str)
            and len(receipt["map_sha256"]) == 64
            and isinstance(receipt.get("map_bytes"), int)
            and receipt["map_bytes"] > 0
            and map_path.is_file()
            and map_path.stat().st_size == receipt["map_bytes"]
        ):
            return receipt
    except (OSError, ValueError, TypeError):
        pass
    return None


def warm_context(repo: str) -> tuple[pathlib.Path, str] | None:
    """Build one full Map artifact per generation; never run Fast here."""
    root = pathlib.Path(repo).expanduser()
    runtime = pathlib.Path(RUNTIME_BIN)
    if not root.is_dir():
        return None
    generation = repository_generation(root)
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        return root, generation
    state = root / ".simplicio" / "hook-context"
    try:
        state.mkdir(parents=True, exist_ok=True)
        if read_ready_receipt(state, generation) is not None:
            return root, generation
        try:
            receipt = json.loads(
                (state / "warm-receipt.json").read_text(encoding="utf-8")
            )
            if (
                receipt.get("schema") == MAP_RECEIPT_SCHEMA
                and receipt.get("generation") == generation
                and receipt.get("status") == "failed"
                and int(receipt.get("retry_after_unix", 0)) > int(time.time())
            ):
                return root, generation
        except (OSError, ValueError, TypeError):
            pass

        pid_path = state / "warm.pid"
        if pid_path.is_file():
            try:
                pid = int(pid_path.read_text().strip())
                os.kill(pid, 0)
                return root, generation
            except (ValueError, OSError):
                pass
        lock_path = state / "warm.lock"
        if not acquire_lock(lock_path, stale_after=300):
            return root, generation
        worker = (
            "import hashlib,json,os,pathlib,subprocess,sys,time\n"
            "root=pathlib.Path(sys.argv[1]); generation=sys.argv[2]; state=root/'.simplicio'/'hook-context'; state.mkdir(parents=True,exist_ok=True)\n"
            "pid=state/'warm.pid'; lock=state/'warm.lock'; pid.write_text(str(os.getpid()))\n"
            "out=state/'map.md'; tmp=state/'map.md.tmp'; success=False; digest=None; size=None\n"
            "try:\n"
            "  binary=os.environ['SIMPLICIO_BIN']\n"
            "  try:\n"
            "    with open(tmp,'wb') as stream: result=subprocess.run([binary,'map','--repo',str(root),'--for-llm','markdown'],stdout=stream,stderr=subprocess.DEVNULL,timeout=120,check=False)\n"
            "    success=result.returncode == 0 and tmp.stat().st_size > 0\n"
            "    if success:\n"
            "      data=tmp.read_bytes(); digest=hashlib.sha256(data).hexdigest(); size=len(data); tmp.replace(out)\n"
            "    else:\n"
            "      try: tmp.unlink()\n"
            "      except OSError: pass\n"
            "  except Exception:\n"
            "    try: tmp.unlink()\n"
            "    except OSError: pass\n"
            "  now=int(time.time()); receipt=state/'warm-receipt.json'; receipt_tmp=state/'warm-receipt.json.tmp'\n"
            "  payload={'schema':'simplicio.hook-map-receipt/v1','status':'ready' if success else 'failed','generation':generation,'completed_at_unix':now}\n"
            "  if success: payload.update({'map_sha256':digest,'map_bytes':size})\n"
            "  else: payload['retry_after_unix']=now+900\n"
            "  receipt_tmp.write_text(json.dumps(payload,sort_keys=True,separators=(',',':')),encoding='utf-8'); receipt_tmp.replace(receipt)\n"
            "finally:\n"
            "  try: pid.unlink()\n"
            "  except OSError: pass\n"
            "  try: lock.unlink()\n"
            "  except OSError: pass\n"
        )
        try:
            subprocess.Popen(
                [sys.executable, "-c", worker, str(root), generation],
                env={**os.environ, "SIMPLICIO_BIN": str(runtime)},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            try:
                lock_path.unlink()
            except OSError:
                pass
    except (OSError, ValueError):
        pass
    return root, generation


def compact_summary_once(root: pathlib.Path, generation: str) -> str:
    state = root / ".simplicio" / "hook-context"
    receipt = read_ready_receipt(state, generation)
    if receipt is None:
        return ""
    try:
        marker = state / "summary-receipt.json"
        lock = state / "summary-receipt.lock"
        if not acquire_lock(lock, stale_after=30):
            return ""
        try:
            try:
                prior = json.loads(marker.read_text(encoding="utf-8"))
                if (
                    prior.get("schema") == INJECTION_RECEIPT_SCHEMA
                    and prior.get("generation") == generation
                    and prior.get("map_sha256") == receipt["map_sha256"]
                ):
                    return ""
            except (OSError, ValueError, TypeError):
                pass
            marker_tmp = marker.with_suffix(".json.tmp")
            marker_tmp.write_text(
                json.dumps(
                    {
                        "schema": INJECTION_RECEIPT_SCHEMA,
                        "generation": generation,
                        "map_sha256": receipt["map_sha256"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            marker_tmp.replace(marker)
        finally:
            try:
                lock.unlink()
            except OSError:
                pass
    except OSError:
        return ""

    return (
        "Simplicio Map cache: "
        f"generation={generation} map_sha256={receipt['map_sha256']} "
        f"map_bytes={receipt['map_bytes']}. "
        "The complete generated Map is available on demand via simplicio_context; "
        "Map content is not injected into the prompt. Native shell/terminal tools "
        "are disabled unless routed directly through Simplicio; third-party MCP/apps "
        "and non-shell native tools remain allowed. Agent fan-out is off by default; "
        "one optional subagent may be used economically through Simplicio MCP."
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
    warmed = warm_context(repo_from_hook())
    if warmed is not None:
        root, generation = warmed
        summary = compact_summary_once(root, generation)
        if summary:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": context_events[event],
                            "additionalContext": summary,
                        }
                    },
                    separators=(",", ":"),
                )
            )
    raise SystemExit(0)


# PreToolUse blocks native terminal execution unless the command enters through
# the governed Simplicio CLI. Third-party MCP/apps and non-shell native tools pass.
if event in {"", "pretooluse", "pre_tool_use"} and is_native_shell_tool(hook_tool_name()):
    if not is_direct_simplicio_command(requested_command()):
        deny_native_shell()

warm_context(repo_from_hook())
raise SystemExit(0)
PY

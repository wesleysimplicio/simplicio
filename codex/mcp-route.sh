#!/usr/bin/env bash
# Simplicio MCP route — advisory PreToolUse context for every supported host.
# simplicio-hook-version: 3240-v6
#
# Simplicio starts first to warm bounded context, then the original native,
# user-requested, or third-party tool is always allowed unchanged.
set -uo pipefail

SIMPLICIO_BIN="${SIMPLICIO_BIN:-${SIMPLICIO_BIN_DIR:-${HOME}/.simplicio/bin}/simplicio}"
export SIMPLICIO_BIN

INPUT="$(cat 2>/dev/null || true)"
# Codex 0.150.0 rejects an explicit PreToolUse allow without updatedInput.
# Empty stdout is the portable allow-unchanged contract; deny remains JSON.
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
RUNTIME_BIN = os.environ.get("SIMPLICIO_BIN") or str(pathlib.Path.home() / ".simplicio" / "bin" / "simplicio")


try:
    hook = json.loads(raw)
except Exception:
    # Hooks are advisory: malformed third-party payloads must never block.
    raise SystemExit(0)

event = (
    hook.get("hookEventName")
    or hook.get("hook_event_name")
    or hook.get("event")
    or ""
).replace("-", "_").lower()
CONTEXT = (
    "Simplicio pre-hook ran before the requested tool. "
    "Use simplicio_map -> simplicio_context -> simplicio_edit when that improves "
    "the task, but preserve the user's explicit request and allow native and "
    "third-party tools unchanged."
)


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


def repository_generation(root: pathlib.Path) -> str:
    """Return a cheap generation that changes with HEAD or visible worktree deltas."""
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


def acquire_warm_lock(lock_path: pathlib.Path) -> bool:
    """Claim one warm worker before spawn; recover only demonstrably stale locks."""
    for _ in range(2):
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime < 120:
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


def warm_context(repo: str) -> None:
    """Warm Mapper/Fast at most once for each observable repository generation."""
    root = pathlib.Path(repo).expanduser()
    runtime = pathlib.Path(RUNTIME_BIN)
    if not root.is_dir() or not runtime.is_file() or not os.access(runtime, os.X_OK):
        return
    state = root / ".simplicio" / "hook-context"
    try:
        state.mkdir(parents=True, exist_ok=True)
        generation = repository_generation(root)
        receipt_path = state / "warm-receipt.json"
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if (
                receipt.get("schema") == "simplicio.hook-context-receipt/v1"
                and receipt.get("generation") == generation
                and (
                    receipt.get("status") == "ready"
                    or (
                        receipt.get("status") == "failed"
                        and int(receipt.get("retry_after_unix", 0)) > int(time.time())
                    )
                )
            ):
                return
        except (OSError, ValueError, TypeError):
            pass

        pid_path = state / "warm.pid"
        if pid_path.is_file():
            try:
                pid = int(pid_path.read_text().strip())
                os.kill(pid, 0)
                return
            except (ValueError, OSError):
                pass
        lock_path = state / "warm.lock"
        if not acquire_warm_lock(lock_path):
            return
        worker = (
            "import json,os,pathlib,subprocess,sys,time\n"
            "root=pathlib.Path(sys.argv[1]); generation=sys.argv[2]; state=root/'.simplicio'/'hook-context'; state.mkdir(parents=True,exist_ok=True)\n"
            "pid=state/'warm.pid'; lock=state/'warm.lock'; pid.write_text(str(os.getpid()))\n"
            "def run(args,out):\n"
            "  tmp=out.with_suffix(out.suffix+'.tmp')\n"
            "  try:\n"
            "    with open(tmp,'w',encoding='utf-8') as f: result=subprocess.run(args,stdout=f,stderr=subprocess.DEVNULL,timeout=45,check=False)\n"
            "    tmp.replace(out)\n"
            "    return result\n"
            "  except Exception:\n"
            "    try: tmp.unlink()\n"
            "    except OSError: pass\n"
            "    return None\n"
            "try:\n"
            "  binary=os.environ['SIMPLICIO_BIN']\n"
            "  results=[\n"
            "    run([binary,'map','--repo',str(root),'--for-llm','markdown'],state/'map.md'),\n"
            "    run([binary,'fast','build','--root',str(root),'--max-bytes','32000','--json'],state/'fast-build.json'),\n"
            "    run([binary,'fast','context','simplicio','--root',str(root),'--max-bytes','32000','--json'],state/'fast-context.json'),\n"
            "  ]\n"
            "  success=all(result is not None and result.returncode == 0 for result in results)\n"
            "  now=int(time.time()); receipt=state/'warm-receipt.json'; tmp=state/'warm-receipt.json.tmp'\n"
            "  payload={'schema':'simplicio.hook-context-receipt/v1','status':'ready' if success else 'failed','generation':generation,'completed_at_unix':now}\n"
            "  if not success: payload['retry_after_unix']=now+60\n"
            "  tmp.write_text(json.dumps(payload,sort_keys=True),encoding='utf-8')\n"
            "  tmp.replace(receipt)\n"
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
            raise
    except (OSError, ValueError):
        return


def context_packet(repo: str) -> str:
    root = pathlib.Path(repo).expanduser()
    state = root / ".simplicio" / "hook-context"
    parts = []
    map_path = state / "map.md"
    fast_path = state / "fast-context.json"
    try:
        if map_path.is_file():
            text = map_path.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                parts.append("\nSimplicio map (background, bounded):\n" + text[:24000])
        if fast_path.is_file():
            text = fast_path.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                parts.append("\nSimplicio context packet (background):\n" + text[:8000])
    except OSError:
        pass
    return "".join(parts)

context_events = {
    "sessionstart": "SessionStart",
    "session_start": "SessionStart",
    "userpromptsubmit": "UserPromptSubmit",
    "user_prompt_submit": "UserPromptSubmit",
    "subagentstart": "SubagentStart",
    "subagent_start": "SubagentStart",
}
if event in context_events:
    repo = repo_from_hook()
    warm_context(repo)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": context_events[event],
            "additionalContext": CONTEXT + context_packet(repo),
        }
    }))
    raise SystemExit(0)


def allow() -> None:
    # No decision means allow unchanged on Codex and other supported hosts.
    raise SystemExit(0)


# Advisory pre-hook: begin bounded Simplicio context work before the host tool,
# then preserve the original native, third-party, or user-requested operation.
warm_context(repo_from_hook())
allow()
PY

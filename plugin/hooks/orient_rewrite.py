#!/usr/bin/env python3
"""simplicio-orient — auto-rewrite hook (PreToolUse, best-effort, fail-open).

Transparently routes a bare heavy READ-ONLY command through `orient_clamp.py` so its
output is reduced before it reaches context — rtk's `init -g` idea. Guarantees adoption
across the main agent AND subagents at zero token overhead, where the host supports
PreToolUse input rewriting (newer Claude Code; Cursor).

CONSERVATIVE BY DESIGN (safety > savings):
  • Only wraps a small allowlist of read-only commands (git status/log/diff/show, ls,
    rg, cat/type, and known test/build runners).
  • NEVER touches writes, excluded commands, or compound commands (&&, ||, |, ;, >, <,
    backticks, $()) — those run unchanged.
  • Fail-open: on ANY error or unknown protocol, allow the command unchanged. If the host
    ignores the rewrite, the command simply runs raw — never broken.

Disabled unless wired explicitly (see hooks/README.md). Honest note: where a runtime
cannot rewrite tool input, this no-ops; use `orient_clamp.py` as a manual wrapper instead.
"""
import json
import os
import re
import sys

CLAMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orient_clamp.py")
CONFIG = os.path.join(".simplicio/orchestrator", "orient.toml")
DEFAULT_EXCLUDES = ["curl", "wget", "playwright", "ssh", "vim", "less", "top", "htop"]


def _project_relevant():
    """Project-relevance gate: this PreToolUse hook acts ONLY inside an active
    simplicio-loop project, never on unrelated repos. Relevant when the opt-in env var
    SIMPLICIO_LOOP (or SIMPLICIO_ORCHESTRATOR) is set, or a `.simplicio/orchestrator/` marker dir
    exists in the current working directory or an ancestor. Outside such a project the
    hook no-ops and the command runs raw."""
    if os.environ.get("SIMPLICIO_LOOP") or os.environ.get("SIMPLICIO_ORCHESTRATOR"):
        return True
    home = os.path.realpath(os.path.expanduser("~"))
    d = os.path.realpath(os.getcwd())
    for _ in range(40):  # depth backstop so an off-home tree can't climb forever
        parent = os.path.dirname(d)
        # Never treat the home dir or a drive/filesystem root as a project marker location:
        # a stray ~/.simplicio/orchestrator, or a marker at a drive root, must not widen the scope.
        if d == home or parent == d:
            return False
        if os.path.isdir(os.path.join(d, ".simplicio/orchestrator")):
            return True
        d = parent
    return False

# read-only, output-heavy commands worth clamping (prefix match on the first token(s))
ALLOW = [
    "git status", "git log", "git diff", "git show", "git branch",
    "ls", "ll", "dir", "rg ", "grep ", "cat ", "type ", "tree",
    "npm test", "npm run", "pnpm test", "yarn test", "jest", "vitest",
    "go test", "go build", "go vet", "pytest", "python -m pytest",
    "mvn ", "gradle ", "tsc", "eslint", "ruff", "golangci-lint",
]
UNSAFE = re.compile(r"[|&;><`]|\$\(|>>|<<")  # compound / redirect / substitution


def allow_unchanged():
    # Emit a permissive decision that does not modify anything; host runs the command raw.
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}
    }))
    sys.exit(0)


def load_excludes():
    excludes = list(DEFAULT_EXCLUDES)
    try:
        if os.path.exists(CONFIG):
            m = re.search(r"exclude_commands\s*=\s*\[(.*?)\]",
                          open(CONFIG, encoding="utf-8").read(), re.S)
            if m:
                excludes = re.findall(r'"([^"]+)"', m.group(1)) or excludes
    except Exception:
        pass
    return excludes


def main():
    try:
        if not _project_relevant():
            allow_unchanged()  # outside a simplicio-loop project → no-op (project-relevance gate)
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        ti = data.get("tool_input", data.get("toolInput", {})) or {}
        cmd = (ti.get("command") or ti.get("cmd") or "").strip()
        if not cmd:
            allow_unchanged()
        low = cmd.lower()
        # already wrapped, unsafe-shape, or excluded → leave raw
        if "orient_clamp" in low or UNSAFE.search(cmd):
            allow_unchanged()
        if any(low.startswith(x.lower()) or (" " + x.lower()) in (" " + low)
               for x in load_excludes()):
            allow_unchanged()
        if not any(low.startswith(a.lower()) for a in ALLOW):
            allow_unchanged()
        # eligible → rewrite to route through the clamp wrapper
        new_cmd = 'python3 "%s" -- %s' % (CLAMP, cmd)
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"command": new_cmd},   # newer Claude Code
            },
            "updatedInput": {"command": new_cmd},        # alt schema; ignored if unknown
        }
        print(json.dumps(out))
        sys.exit(0)
    except Exception:
        allow_unchanged()  # fail-open, always


if __name__ == "__main__":
    main()

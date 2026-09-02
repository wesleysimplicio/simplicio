#!/usr/bin/env python3
"""simplicio-loop — stop hook (cross-runtime, cross-platform).

Fires when an agent turn ends. Decides whether to RE-FEED the goal (continue the
Ralph loop) or let the agent STOP. Works under Claude Code (Stop hook) and Cursor
(stop hook); detects the runtime from env and emits the matching control object.

SAFETY: fail-open. On ANY error, ambiguity, or missing state, ALLOW STOP — a buggy
hook must never trap the agent in an endless loop. The real guards are the
`max_iterations` cap, explicit STOP, and evidence gates, never this script's cleverness.

State (single source of truth): .simplicio/orchestrator/loop/scratchpad.md  (+ sibling `done` flag)
Reads stdin JSON from the host (Claude: {transcript_path,...}; Cursor: {text,...}).

Cross-agent handoff: an INCOMPLETE stop (iteration cap, manual STOP signal, or spindle
handoff) writes `.simplicio/orchestrator/loop/HANDOFF.md` before clearing the scratchpad, so a
different agent/runtime picking up this repo cold can resume without re-deriving the
goal, the verified acceptance criteria, or the dead-end attempts. A successful
(promise-fulfilled) stop needs no handoff.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:  # Windows consoles default to cp1252; hook protocols and evidence are UTF-8.
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LOOP_DIR = os.path.join(".simplicio/orchestrator", "loop")
SCRATCHPAD = os.path.join(LOOP_DIR, "scratchpad.md")
DONE_FLAG = os.path.join(LOOP_DIR, "done.flag")
LEGACY_DONE_FLAG = os.path.join(LOOP_DIR, "done")
LAST_RESP = os.path.join(LOOP_DIR, "last_response.txt")
ANCHOR = os.path.join(LOOP_DIR, "anchor.json")
JOURNAL = os.path.join(LOOP_DIR, "journal.jsonl")
HANDOFF = os.path.join(LOOP_DIR, "HANDOFF.md")
STOP_SIGNAL = os.path.join(".simplicio/orchestrator", "STOP")
GATE_LOCK = os.path.join(LOOP_DIR, "gate.lock")
GATE_TTL_SEC = 1800  # 30 min — a stale lock must NEVER permanently trap the loop (fail-open)
WATCHER_STATE = os.path.join(LOOP_DIR, "watcher_state.json")
WATCHER_CHALLENGE = os.path.join(LOOP_DIR, "watcher_challenge.json")
SPINDLE_STATE = os.path.join(LOOP_DIR, "spindle_state.json")
PHASE_FILE = os.path.join(LOOP_DIR, "phase.json")
FLOW_AUDIT_RECEIPT = os.path.join(".simplicio/orchestrator", "flow-audit.json")
SIMPLICIO_LOOP_SKILL_MARKER = os.path.join(".claude", "skills", "simplicio-loop", "SKILL.md")
ORIENTATION_BEGIN = "<!-- SIMPLICIO-LLM-ORIENTATION:BEGIN -->"
ORIENTATION_END = "<!-- SIMPLICIO-LLM-ORIENTATION:END -->"
ORIENTATION_LABEL = "[simplicio-loop startup orientation]"
# Core operate/survey pair — always required when the simplicio-loop skill is present.
BOUND_OPERATORS = ("simplicio-mapper", "simplicio-dev-cli")
# Adaptive: Runtime (simplicio) is required only when operational (or forced).
RUNTIME_BINARY = "simplicio"
WEB_EXTS = {".tsx", ".jsx", ".vue", ".svelte", ".html"}
_TRUE = frozenset({"1", "true", "yes", "on", "strict", "full-stack", "required"})
_FALSE = frozenset({"0", "false", "no", "off", "disabled", "standalone", "legacy"})

EVIDENCE_RE = re.compile(
    r"(https?://\S+/pull/\d+)"          # a PR URL
    r"|(\b(pass|passed|passing|green|ok)\b)"  # a gate verdict
    r"|([\w./-]+:\d+)"                   # a file:line receipt
    r"|([✓✅])",
    re.IGNORECASE,
)
PROMISE_RE = re.compile(r"<promise>\s*(.*?)\s*</promise>", re.IGNORECASE | re.DOTALL)


def allow_stop():
    """Emit nothing actionable → the agent is allowed to stop. Always exit 0."""
    sys.exit(0)


def _loop_progress_module():
    """Best-effort import of scripts/loop_progress.py — same pattern as _flow_audit_module()."""
    try:
        repo_root = os.getcwd()
        scripts_dir = os.path.join(repo_root, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import loop_progress as _lp  # noqa: local import, optional dependency
        return _lp
    except Exception:
        return None


def _emit_final_progress(reason, outcome):
    """Fail-open final progress event (#301 § 4) — the F3/`refeed_exit` event that closes out
    `progress.json`'s `run_state` (running -> done|capped|handoff|stopped) so it never stays
    "in progress" forever after the run actually ended."""
    try:
        lp = _loop_progress_module()
        if lp is None:
            return
        lp.emit_event("refeed_exit", status="end", outcome=outcome, detail=reason,
                      source="loop_stop.py")
    except Exception:
        pass


def _progress_header_prefix(nxt, max_iter):
    """#302 § 2 — a short ` · fase F1 · etapa 5/9 operate · item T3 · ACs 1/3 · 42% geral` prefix
    for the re-feed header. Fail-open: any error -> "" (header identical to before this feature).
    Also regenerates PROGRESS.md (1 call/turn, zero token cost — a file, not context, per #302
    § 2.3)."""
    try:
        lp = _loop_progress_module()
        if lp is None:
            return ""
        snap = lp.build_snapshot(cap=(max_iter or None))
        try:
            lp.write_snapshot(snap)
            _, md = lp.render_full(snap)
            lp._atomic_write(lp._md_path(), md)
        except Exception:
            pass
        line = lp.render_turn_header(snap)
        rest = line.split("|", 1)[1] if "|" in line else line
        rest = rest.replace("[simplicio-loop] ", "").strip()
        rest = re.sub(r"\s*·\s*iter\s+\S+$", "", rest)  # drop trailing "· iter N/cap" (redundant)
        return " · " + rest if rest else ""
    except Exception:
        return ""


def _orientation_skill_paths():
    """Return likely canonical/mirrored skill paths for startup orientation lookup."""
    paths = []
    configured = os.environ.get("SIMPLICIO_LOOP_ORIENTATION_FILE", "").strip()
    if configured:
        paths.append(Path(configured))

    cwd = Path.cwd()
    paths.extend((
        cwd / ".claude/skills/simplicio-loop/SKILL.md",
        cwd / "plugin/skills/simplicio-loop/SKILL.md",
        cwd / "simplicio_loop/_bundle/skills/simplicio-loop/SKILL.md",
    ))

    hook_dir = Path(__file__).resolve().parent
    for root in (hook_dir.parent, hook_dir):
        paths.extend((
            root / ".claude/skills/simplicio-loop/SKILL.md",
            root / "plugin/skills/simplicio-loop/SKILL.md",
            root / "skills/simplicio-loop/SKILL.md",
            root / "_bundle/skills/simplicio-loop/SKILL.md",
        ))

    seen = set()
    unique = []
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _llm_startup_orientation():
    """Extract the marked canonical orientation; missing/corrupt files fail open."""
    for path in _orientation_skill_paths():
        try:
            text = path.read_text(encoding="utf-8")
            start = text.find(ORIENTATION_BEGIN)
            if start < 0:
                continue
            end = text.find(ORIENTATION_END, start + len(ORIENTATION_BEGIN))
            if end < 0:
                continue
            block = text[start:end + len(ORIENTATION_END)].strip()
            if block:
                return block
        except (OSError, UnicodeError):
            continue
    return ""


def _refeed_message(header, body):
    """Prepend startup orientation once, without growing the task body each turn."""
    orientation = _llm_startup_orientation()
    existing = body or ""
    if not orientation or (ORIENTATION_BEGIN in existing and ORIENTATION_END in existing):
        return header + "\n\n" + existing
    return ORIENTATION_LABEL + "\n" + orientation + "\n\n" + header + "\n\n" + existing


def cleanup_and_stop(reason=None, outcome=None):
    if reason:
        _emit_final_progress(reason, outcome)
    for p in (SCRATCHPAD, DONE_FLAG, LEGACY_DONE_FLAG, LAST_RESP, WATCHER_STATE, WATCHER_CHALLENGE):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    allow_stop()


def read_stdin_json():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def parse_frontmatter(text):
    """Return (meta dict, body str) or (None, None) on corruption."""
    if not text.startswith("---"):
        return None, None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, None
    meta = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta, parts[2].strip()


def last_assistant_text(stdin):
    # Cursor passes the response text inline.
    if isinstance(stdin.get("text"), str):
        return stdin["text"]
    # Cursor capture hook may have stashed it.
    if os.path.exists(LAST_RESP):
        try:
            with open(LAST_RESP, encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass
    # Claude passes a transcript path (JSONL); read the last assistant message.
    tp = stdin.get("transcript_path")
    if tp and os.path.exists(tp):
        try:
            txt = ""
            with open(tp, encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if ev.get("role") == "assistant" or ev.get("type") == "assistant":
                        msg = ev.get("message", ev)
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                c.get("text", "") for c in content if isinstance(c, dict)
                            )
                        txt = content or txt
            return txt
        except OSError:
            return ""
    return ""


def gate_running():
    """True when a background gate (verification workflow / CI / long task) is in flight + fresh.

    The orchestrator touches `.simplicio/orchestrator/loop/gate.lock` before launching a background gate and
    removes it on completion. While present AND fresh, the turn ended because we are WAITING on that
    gate — not because the loop is idle — so the Stop hook must NOT re-feed the goal. A stale lock
    (older than the TTL) is ignored so a leftover file can never trap the agent (fail-open).
    """
    try:
        if not os.path.exists(GATE_LOCK):
            return False
        return (time.time() - os.path.getmtime(GATE_LOCK)) < GATE_TTL_SEC
    except Exception:
        return False


def read_anchor():
    """Return the parsed task anchor dict, or None if absent/corrupt. Fail-open."""
    try:
        with open(ANCHOR, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def anchor_pending():
    """Return the unverified acceptance-criteria ids from the task anchor, or [].

    The mechanical anti-drift gate: a `<promise>` must not end the loop while the frozen task anchor
    still has criteria that are not `done`. FAIL-OPEN: a missing / unreadable / empty anchor, or one
    with no criteria, returns [] so the gate never blocks — a buggy anchor must never trap the loop.
    """
    data = read_anchor()
    if not data:
        return []
    crit = data.get("criteria") or []
    return [c.get("id") for c in crit
            if isinstance(c, dict) and c.get("status") != "done"]


def _delivery_stop_guard(cwd, iteration):
    """Enforce the frozen delivery contract against the real end-of-turn diff.

    The baseline is persisted after each clean turn. The first observation uses HEAD as the
    conservative baseline, so an untracked or newly staged file cannot silently pass. This is
    deliberately fail-closed only when a valid contract exists; absent or unreadable loop state
    keeps the historic stop-hook fail-open behavior.
    """
    try:
        anchor_path = os.path.join(cwd, ANCHOR)
        with open(anchor_path, encoding="utf-8") as handle:
            anchor = json.load(handle)
        contract = anchor.get("delivery")
        if not contract:
            return None
        if cwd not in sys.path:
            sys.path.insert(0, cwd)
        from simplicio_loop.delivery_contract import normalize_contract
        contract = normalize_contract(contract)

        baseline_path = os.path.join(cwd, ".simplicio/orchestrator", "loop", "delivery_baseline.json")
        baseline = {}
        if os.path.exists(baseline_path):
            with open(baseline_path, encoding="utf-8") as handle:
                baseline = json.load(handle)

        def git(*args):
            result = subprocess.run(
                ["git", *args],
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )
            return result.stdout if result.returncode == 0 else ""

        current_head = git("rev-parse", "HEAD").strip()
        status = git("status", "--porcelain=v1", "--untracked-files=all")
        current_paths = set()
        for line in status.splitlines():
            if len(line) >= 4:
                path = line[3:].strip()
                if " -> " in path:
                    path = path.rsplit(" -> ", 1)[1]
                path = path.strip('"')
                if path.replace("\\", "/").startswith(".simplicio/orchestrator/"):
                    continue
                current_paths.add(path)
        baseline_paths = set(baseline.get("paths") or [])
        new_paths = sorted(current_paths - baseline_paths)
        violations = []
        if not contract["allow_new_files_in_repo"] and new_paths:
            violations.append("new files: %s" % ", ".join(new_paths))

        if not contract["allow_comments_in_code"]:
            base_head = baseline.get("head") or "HEAD"
            committed_diff = git("diff", "%s..%s" % (base_head, current_head), "--unified=0") if current_head else ""
            working_diff = git("diff", "HEAD", "--unified=0")
            diff = committed_diff + "\n" + working_diff
            code_paths = {
                line[6:].strip() for line in diff.splitlines() if line.startswith("+++ b/")
            }
            suffixes = (".cs", ".js", ".jsx", ".ts", ".tsx", ".py")
            if any(path.lower().endswith(suffixes) for path in code_paths):
                comments = []
                for line in diff.splitlines():
                    if not line.startswith("+") or line.startswith("+++"):
                        continue
                    added = line[1:].lstrip()
                    if added.startswith(("#", "//", "/*", "*", '"""')):
                        comments.append(added[:80])
                if comments:
                    violations.append("new code comments: %d" % len(comments))

        if violations:
            reason = "delivery contract violation at stop (iteration %s): %s" % (
                iteration, "; ".join(violations)
            )
            journal_path = os.path.join(cwd, JOURNAL)
            os.makedirs(os.path.dirname(journal_path), exist_ok=True)
            with open(journal_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "iteration": int(iteration), "action": "delivery contract guard",
                    "gate": "block", "reason": reason, "source": "loop_stop",
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }, ensure_ascii=False, sort_keys=True) + "\n")
            return reason

        os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
        with open(baseline_path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump({"head": current_head, "paths": sorted(current_paths), "iteration": int(iteration)}, handle)
        os.replace(baseline_path + ".tmp", baseline_path)
        return None
    except Exception:
        return None


def tail_journal(n=8):
    """Last N attempt records from the journal, oldest first. [] on any read error."""
    try:
        with open(JOURNAL, encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        out = []
        for ln in lines[-n:]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def attempt_suffix(a):
    bits = []
    if a.get("execution_state"):
        bits.append("state=%s" % a["execution_state"])
    if a.get("stage_id"):
        bits.append("stage=%s" % a["stage_id"])
    if a.get("decision"):
        bits.append("decision=%s" % a["decision"])
    if a.get("validator"):
        bits.append("validator=%s" % a["validator"])
    if a.get("retry_count") is not None:
        bits.append("retry=%s" % a["retry_count"])
    if a.get("chunk_id"):
        bits.append("chunk=%s" % a["chunk_id"])
    if a.get("source_artifact"):
        bits.append("source=%s" % a["source_artifact"])
    if a.get("next_action"):
        bits.append("next=%s" % a["next_action"])
    if a.get("blocked_reason"):
        bits.append("blocked=%s" % a["blocked_reason"])
    return (" — " + " | ".join(bits)) if bits else ""


def write_handoff(reason, meta=None, body=None):
    """Write the cross-agent continuation artifact before an INCOMPLETE stop.

    Aggregates the frozen task anchor (goal + acceptance criteria + evidence), the last journal
    attempts (what was already tried, to avoid re-running a dead end), and the live scratchpad
    iteration/promise — everything a fresh agent needs to resume cold, without this conversation.
    Fail-open: any error here must never block the stop itself.
    """
    try:
        anchor = read_anchor() or {}
        criteria = anchor.get("criteria") or []
        attempts = tail_journal()
        completion = latest_completion_receipt() or {}
        lines = [
            "# simplicio-loop handoff",
            "",
            "Stop reason: %s" % reason,
            "Stopped at: %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ]
        if meta:
            lines += [
                "Iteration: %s / %s" % (meta.get("iteration", "?"), meta.get("max_iterations", "?")),
                "Completion promise: %s" % (meta.get("completion_promise") or "(none set)"),
            ]
        if anchor.get("goal"):
            lines += ["", "## Frozen goal", "", anchor["goal"]]
        elif body:
            lines += ["", "## Goal (from scratchpad, no anchor set)", "", body]
        if criteria:
            lines += ["", "## Acceptance criteria"]
            for c in criteria:
                if not isinstance(c, dict):
                    continue
                mark = "x" if c.get("status") == "done" else " "
                ev = (" — %s" % c["evidence"]) if c.get("evidence") else ""
                lines.append(
                    "- [%s] %s (%s)%s"
                    % (mark, c.get("text", c.get("id", "?")), c.get("status", "pending"), ev)
                )
        if attempts:
            lines += ["", "## Last attempts (`scripts/loop_journal.py resume` for the full read)"]
            for a in attempts:
                lines.append(
                    "- iter %s: %s -> %s (fp %s)%s%s"
                    % (
                        a.get("iteration", "?"),
                        a.get("action", "?"),
                        a.get("gate", "?"),
                        (a.get("fingerprint") or "")[:12],
                        (" — %s" % a["note"]) if a.get("note") else "",
                        attempt_suffix(a),
                    )
                )
        if completion:
            lines += [
                "",
                "## Completion oracle",
                "",
                "- verdict: %s" % completion.get("verdict", "DELIVERY_PENDING"),
                "- reason_code: %s" % completion.get("reason_code", "oracle_incomplete"),
                "- tag: %s" % completion.get("tag", "UNVERIFIED"),
                "- receipt: %s" % completion.get("_path", "(unknown)"),
            ]
        lines += [
            "",
            "## Resume",
            "",
            "1. `python3 scripts/task_anchor.py status` (or `gate --exit-code`) — verified vs open.",
            "2. `python3 scripts/loop_journal.py resume` — dead-end actions to avoid.",
            "3. `git log --oneline -10` / `git diff` — what already landed.",
            "4. Re-arm the loop once the stop cause (cap/manual/spindle) is resolved.",
            "",
        ]
        tmp = HANDOFF + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        os.replace(tmp, HANDOFF)
        # include_handoff=False: this function just wrote the RICH handoff (frozen goal + AC
        # checklist + last attempts) directly above. cross_agent_wiki.py's own `handoff` command
        # writes the SAME path with a thinner layout — calling it here would immediately clobber
        # what we just wrote (the three-writer bug, #68). Only capture + summary run; HANDOFF.md
        # keeps a single owner for an INCOMPLETE stop.
        refresh_cross_agent_wiki(include_handoff=False)
    except Exception:
        pass  # fail-open: a broken handoff write must never block the stop


def _env_flag(name, default=""):
    return str(os.environ.get(name, default) or "").strip().lower()


def _strict_loop_enabled():
    if _env_flag("SIMPLICIO_LOOP_STRICT") in _TRUE:
        return True
    return _env_flag("SIMPLICIO_LOOP_MODE") in {"strict", "full-stack"}


def _binary_operational(binary, args=("--version",)):
    """True when binary is on PATH and a cheap probe exits 0."""
    try:
        path = shutil.which(binary)
        if not path:
            return False
        completed = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def _action_operator_operational():
    # Either public name satisfies the operate role.
    if _binary_operational("simplicio-dev-cli", ("--help",)):
        return True
    if _binary_operational("simplicio-py", ("--version",)):
        return True
    return False


def required_bound_operators():
    """Binaries this running loop must keep available.

    Always (skill present): mapper + operate.
    Runtime (``simplicio``): when SIMPLICIO_LOOP_REQUIRE_RUNTIME=required, always;
    when auto (default), only if currently operational — then it is required so a
    mid-run disappearance cannot silently drop to standalone.
    Fast is a project-consultation skill, never a lifecycle-hook dependency.
    """
    required = list(BOUND_OPERATORS)
    rt_mode = _env_flag("SIMPLICIO_LOOP_REQUIRE_RUNTIME", "off") or "off"
    if rt_mode in _FALSE:
        rt_mode = "off"
    elif rt_mode in _TRUE:
        rt_mode = "required"
    elif rt_mode not in {"auto", "off", "required"}:
        rt_mode = "off"
    runtime_ok = _binary_operational(RUNTIME_BINARY, ("--version",))
    if rt_mode == "required" or (rt_mode == "auto" and runtime_ok):
        required.append(RUNTIME_BINARY)
    # de-dupe
    seen = set()
    ordered = []
    for name in required:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def missing_bound_operators():
    """Return the bound-operator binaries missing/non-operational, or [] if not applicable.

    CLAUDE.md / `simplicio-loop` SKILL.md: when a body-of-work loop is driven by the
    `simplicio-loop` companion skill, `simplicio-mapper` (survey) and `simplicio-dev-cli`
    (operate) are REQUIRED — "the loop BLOCKS if either is absent". That contract was previously
    enforced only at install/doctor time (#83); the running driver never checked it, so a
    marketplace install, a PATH mismatch, or an operator uninstalled after setup silently
    degraded to LLM hand-survey/hand-edit — exactly what the operators exist to prevent.

    Runtime (``simplicio`` from simplicio-runtime) is adaptive: if available and operational
    (or forced via SIMPLICIO_LOOP_REQUIRE_RUNTIME=1 / strict+required), it is part of the
    required set and mid-run disappearance BLOCKS. If it is not installed, the core
    mapper → dev-cli loop continues.

    Scoped to repos that actually ship the `simplicio-loop` skill (its SKILL.md is the marker) —
    a bare `simplicio-tasks` loop with no `simplicio-loop` companion has no operator requirement.
    Fail-open: any probe error is treated as "present" (never trap the loop over a probe bug).
    """
    try:
        if not os.path.exists(SIMPLICIO_LOOP_SKILL_MARKER):
            return []
        missing = []
        for binary in required_bound_operators():
            if binary == "simplicio-dev-cli":
                if not _action_operator_operational():
                    missing.append("simplicio-dev-cli")
                continue
            if binary == RUNTIME_BINARY:
                if not _binary_operational(RUNTIME_BINARY, ("--version",)):
                    missing.append(RUNTIME_BINARY)
                continue
            if shutil.which(binary) is None or not _binary_operational(binary, ("--version",)):
                missing.append(binary)
        return missing
    except Exception:
        return []


def _flow_audit_module():
    """Best-effort import of scripts/flow_audit.py for its FRONT_HINTS/BACK_HINTS. None on failure."""
    try:
        repo_root = os.getcwd()
        scripts_dir = os.path.join(repo_root, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import flow_audit as _fa  # noqa: local import, optional dependency
        return _fa
    except Exception:
        return None


def _delivery_contract_module():
    """Best-effort import of scripts/delivery_contract.py — same pattern as
    `_flow_audit_module()`. None when the sibling script is absent (an install that predates
    #526 Etapa 4), so the new-file guard below is a pure no-op rather than a hard failure."""
    try:
        repo_root = os.getcwd()
        scripts_dir = os.path.join(repo_root, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import delivery_contract as _dc  # noqa: local import, optional dependency
        return _dc
    except Exception:
        return None


def delivery_new_file_violation():
    """Return the delivery-contract new-file-guard violation reason for THIS turn, or None
    (#526 Etapa 4). Consumes the frozen `allow_new_files_in_repo` clause against the
    per-contract baseline (`delivery_contract.new_file_guard`). Fail-open: any error (module
    missing, git unavailable, corrupt anchor) -> None — a plumbing failure here must never trap
    the loop; only a genuinely detected unauthorized new file blocks the turn.
    """
    try:
        dc = _delivery_contract_module()
        if dc is None:
            return None
        return dc.new_file_guard(read_anchor(), root=os.getcwd())
    except Exception:
        return None


def _record_delivery_violation_journal(iteration, reason):
    """Journal the delivery-contract block (#526 Etapa 4 AC: "violação = turno bloqueado + "
    "registro no journal"). Fail-open, best-effort — same pattern as `auto_record_journal`."""
    try:
        repo_root = os.getcwd()
        script = os.path.join(repo_root, "scripts", "loop_journal.py")
        if not os.path.exists(script):
            return
        subprocess.run(
            [sys.executable, script, "record",
             "--iteration", str(iteration),
             "--action", "delivery contract: new-file guard",
             "--gate", "blocked",
             "--note", reason],
            capture_output=True, timeout=10, cwd=repo_root,
        )
    except Exception:
        pass


def _changed_files():
    """Best-effort set of files touched in the working tree (uncommitted + untracked + last
    commit). A heuristic, not a precise "since loop start" diff — fail-open: {} on any error.

    Excludes `.simplicio/orchestrator/` (the loop's own state files — never source, and would otherwise
    make the receipt's own write, or a sibling state write, look like a "later" source change),
    `.simplicio/` (the simplicio runtime/dev-cli's own state — checkpoints, events.jsonl, survey
    artifacts — written by this very hook's fire-and-forget CLI callouts mid-turn, the same
    self-inflicted false-positive class), and build/cache noise (`__pycache__`, `.pyc`) that this
    very check's own module import can create — those false-positives are exactly why all three
    are filtered here.
    """
    out = set()
    for args in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                out.update(ln.strip() for ln in r.stdout.splitlines() if ln.strip())
        except Exception:
            continue
    return {
        f for f in out
        if not f.startswith((".simplicio/orchestrator/", ".simplicio/"))
        and "__pycache__" not in f and not f.endswith((".pyc", ".pyo"))
    }


def _touches_web_surface(files):
    fa = _flow_audit_module()
    front = tuple(getattr(fa, "FRONT_HINTS", ()) or ())
    back = tuple(getattr(fa, "BACK_HINTS", ()) or ())
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in WEB_EXTS:
            return True
        fl = "/" + f.replace(os.sep, "/").lower()
        if any(h in fl for h in front) or any(h in fl for h in back):
            return True
    return False


def flow_audit_gap():
    """Return a human-readable gap string when a web-touching diff lacks a fresh, passing
    `.simplicio/orchestrator/flow-audit.json` receipt; None when there is nothing to require (#80).

    Mechanizes what was previously prose-only (SKILL.md instructions the agent could skip under
    context pressure): the anchor gate, watcher gate, and cap are all enforced IN this
    hook — the front→back integration gate now is too. Fail-open only when `flow_audit.py` itself
    is absent (a bare `simplicio-tasks` repo with no flow_audit worker) or the diff/receipt can't
    be read — never trap the loop over an audit-plumbing error.
    """
    try:
        fa = _flow_audit_module()
        if fa is None:
            return None
        files = _changed_files()
        if not _touches_web_surface(files):
            return None
        if not os.path.exists(FLOW_AUDIT_RECEIPT):
            return ("flow audit missing — run `python3 scripts/flow_audit.py audit . "
                     "--fail-on high --json > .simplicio/orchestrator/flow-audit.json`")
        receipt_mtime = os.path.getmtime(FLOW_AUDIT_RECEIPT)
        for f in files:
            try:
                if os.path.getmtime(f) > receipt_mtime:
                    return ("flow audit stale — re-run `python3 scripts/flow_audit.py audit . "
                             "--fail-on high --json > .simplicio/orchestrator/flow-audit.json`")
            except OSError:
                continue
        with open(FLOW_AUDIT_RECEIPT, encoding="utf-8") as f:
            receipt = json.load(f)
        if not receipt.get("ok", False):
            high = receipt.get("counts", {}).get("high_issues", "?")
            return "flow audit failing (%s high issue(s)) — fix and re-run flow_audit.py" % high
        return None
    except Exception:
        return None  # fail-open: a broken audit read must never trap the loop


def auto_record_journal(iteration, has_evidence):
    """Fallback journal record so the hierarchical planner is never blind (#67).

    `scripts/hierarchical_planner.py` derives `iterations_run` from
    `.simplicio/orchestrator/loop/journal.jsonl` — but nothing auto-writes that file; only the manual
    `loop_journal.py record` call (SKILL.md Step 4) does. An agent that forgets it leaves the
    planner permanently frozen at "no history". This writes a minimal fallback record for THIS
    iteration if — and only if — the agent hasn't already recorded one itself this turn (checked
    by inspecting the last row), so a rich manual record is never overwritten or double-counted.
    Gate is intentionally "blocked", never "fail": this is a presence signal for phase timing, not
    a substitute for the real attempt-memory the agent records on a genuine failure. Fail-open.
    """
    try:
        if os.path.exists(JOURNAL):
            with open(JOURNAL, encoding="utf-8") as f:
                lines = [ln for ln in f if ln.strip()]
            if lines:
                try:
                    last = json.loads(lines[-1])
                    if int(last.get("iteration", -1)) == iteration:
                        return  # agent already recorded this turn manually
                except Exception:
                    pass
        repo_root = os.getcwd()
        script = os.path.join(repo_root, "scripts", "loop_journal.py")
        if not os.path.exists(script):
            return
        gate = "pass" if has_evidence else "blocked"
        subprocess.run(
            [sys.executable, script, "record",
             "--iteration", str(iteration),
             "--action", "auto: turn %d (no manual loop_journal record)" % iteration,
             "--gate", gate,
             "--note", "auto-recorded fallback"],
            capture_output=True, timeout=10, cwd=repo_root,
        )
    except Exception:
        pass


def _discover_simplicio_cli():
    """Probe for simplicio CLI in priority order. Returns (binary, sub) or (None, None).
    Silent-fail: any probe error returns (None, None) — never blocks.
    """
    candidates = [
        ("simplicio", "claims"),
        ("simplicio-py", "claims"),
        ("python3", ["-m", "simplicio.cli", "claims"]),
    ]
    for binary, sub in candidates:
        try:
            args = [binary] + (sub if isinstance(sub, list) else [sub, "--help"])
            subprocess.run(args, capture_output=True, timeout=5)
            return binary, sub
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None, None


def _call_simplicio_claims():
    """Run ``simplicio claims check`` silently. Fail-open."""
    binary, _ = _discover_simplicio_cli()
    if not binary:
        return
    try:
        subprocess.run(
            [binary, "claims", "check"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass


def _call_simplicio_nest():
    """Run ``simplicio nest verify`` silently. Fail-open."""
    candidates = [
        ("simplicio", "nest"),
        ("simplicio-py", "nest"),
        ("python3", ["-m", "simplicio.cli", "nest"]),
    ]
    for binary, sub in candidates:
        try:
            args = [binary] + (sub if isinstance(sub, list) else [sub, "--help"])
            subprocess.run(args, capture_output=True, timeout=5)
            nest_binary = binary
            try:
                subprocess.run(
                    [nest_binary, "nest", "verify"],
                    capture_output=True, timeout=15,
                )
            except Exception:
                pass
            return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue


def _call_simplicio_checkpoint(iteration):
    """Snapshot a `simplicio checkpoint` (git-stash-backed, restorable) at this loop
    boundary, when the native `simplicio` Rust runtime is on PATH. Fail-open, best-effort:
    unlike claims/nest above, this is `simplicio`-only (dev-cli has no checkpoint
    equivalent), so it silently no-ops when the binary is absent — no fallback candidate
    list, no error surfaced. Gives the loop real undo (`simplicio checkpoint restore`)
    that its own scratchpad-only state doesn't provide on its own.
    """
    binary = shutil.which("simplicio")
    if not binary:
        return
    try:
        subprocess.run(
            [binary, "checkpoint", "save", "--desc", "simplicio-loop iteration %s" % iteration,
             "--json"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass


def _call_simplicio_hbp_append_topic(topic, payload_dict):
    """Generic fail-open append into the runtime's HBP tamper-evident hash chain
    (`simplicio hbp append`), when the native `simplicio` binary is on PATH (#128).

    Same contract as the promise-verified append below: `simplicio`-only, best-effort — absent
    binary or any failure is a silent no-op that never blocks the caller's own decision. Every
    new HBP point in this hook family (stall detected, gate blocked, run blocked) goes through
    here so the topics all carry the same provenance and failure discipline.
    """
    binary = shutil.which("simplicio")
    if not binary:
        return
    try:
        subprocess.run(
            [binary, "hbp", "append",
             "--topic", topic,
             "--payload", json.dumps(payload_dict),
             "--provenance", "simplicio-loop",
             "--json"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass


def _call_simplicio_hbp_append(iteration, promise, watcher_tag):
    """Record the promise-verification decision into the runtime's HBP
    tamper-evident hash chain (`simplicio hbp append`), when the native
    `simplicio` binary is on PATH. Fail-open, best-effort, `simplicio`-only.

    This is what makes "evidence-gated exit" auditable rather than
    self-reported: the watcher already independently recomputed the truth
    (`watcher_verify()`) before this is ever called (only on the honored-
    promise path) — appending it here means a later `simplicio hbp verify`
    can prove this exact iteration/promise/watcher-tag combination was
    recorded in order, without trusting this process's own say-so after the
    fact. Absent binary or any failure: silent no-op, never blocks the stop.
    """
    try:
        anchor = read_anchor() or {}
        _call_simplicio_hbp_append_topic("loop-promise-verified", {
            "iteration": iteration,
            "promise": promise,
            "watcher_tag": watcher_tag,
            "goal_fp": anchor.get("goal_fp", ""),
        })
    except Exception:
        pass


def _journal_stall(k=3):
    """Trailing same-fingerprint failure streak from the journal — (fingerprint, streak).

    Mirrors `scripts/loop_journal.py`'s `analyze()` trailing-streak math over the tail of the
    journal, locally and fail-open (("", 0) on any error) — the hook must never import the
    worker to decide whether to emit the `loop-stall-detected` HBP record (#128).
    """
    try:
        rows = tail_journal(n=max(k * 3, 12))
        if not rows:
            return "", 0
        last = rows[-1]
        fp = last.get("fingerprint", "")
        if last.get("gate") == "pass" or not fp:
            return "", 0
        streak = 0
        for r in reversed(rows):
            if r.get("gate") != "pass" and r.get("fingerprint") == fp:
                streak += 1
            else:
                break
        return fp, streak
    except Exception:
        return "", 0


def read_watcher_challenge():
    """Return the current per-iteration watcher challenge dict, or None. Fail-open."""
    try:
        with open(WATCHER_CHALLENGE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_watcher_challenge(iteration):
    """Issue a fresh per-iteration nonce the watcher receipt must echo (#82 challenge binding).

    Written at the END of a turn that re-feeds (so it is on disk BEFORE the next turn's agent
    acts, letting `scripts/watcher_verify.py` — run mid-turn, before the Stop hook fires — read
    and echo it). A promise turn's receipt is checked against whatever challenge is on disk when
    THIS Stop hook runs; a receipt that predates the challenge, or answers a different one, fails
    the gate. This is what makes the watcher gate more than a plain unauthenticated JSON write:
    the agent would have to notice, read, and correctly echo a value it does not control the
    timing of — a visible, journaled action, not a silent one-call spoof. Fail-open: any write
    error must never block the re-feed itself.
    """
    try:
        anchor = read_anchor() or {}
        os.makedirs(LOOP_DIR, exist_ok=True)
        payload = {
            "challenge": uuid.uuid4().hex[:20],
            "iteration": iteration,
            "goal_fp": anchor.get("goal_fp", ""),
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        tmp = WATCHER_CHALLENGE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, WATCHER_CHALLENGE)
    except Exception:
        pass


def watcher_verify():
    """Run pre-promise watcher verification per Asolaria N-Nest Corrective Gate pattern.

    Reads `.simplicio/orchestrator/loop/watcher_state.json` written by the watcher process (a separate
    agent/PID that independently re-executes the work and compares results against the agent's
    reported output). Gate: `reported == watcher.recomputed_truth`.

    Challenge binding (#82): a receipt must additionally echo the CURRENT per-iteration
    `watcher_challenge.json` nonce (and the frozen anchor's `goal_fp`, when an anchor exists) —
    otherwise it is rejected even if `match: true`. This closes the plain self-attestation gap: a
    receipt hand-written once at iteration 1 (or copied from a stale run) can no longer satisfy the
    gate on a later, different iteration/goal.

    Returns (passed: bool, tag: str) where tag is "MEASURED" (verified) or "UNVERIFIED" (not
    verified or mismatch). If no watcher state exists → UNVERIFIED (gate fails). Fail-open:
    a corrupt or missing watcher state NEVER traps the loop — it simply gates the promise.
    """
    try:
        if not os.path.exists(WATCHER_STATE):
            return False, "UNVERIFIED"
        with open(WATCHER_STATE, encoding="utf-8") as f:
            state = json.load(f)
        match = bool(state.get("match", False))
        status = str(state.get("status", "UNVERIFIED"))
        if not (match and status == "MEASURED"):
            return False, "UNVERIFIED"
        challenge = read_watcher_challenge()
        if not challenge:
            return False, "UNVERIFIED"  # no challenge on disk — nothing valid to echo yet
        if state.get("challenge") != challenge.get("challenge"):
            return False, "UNVERIFIED"
        expected_fp = challenge.get("goal_fp") or ""
        if expected_fp and state.get("goal_fp") != expected_fp:
            return False, "UNVERIFIED"
        checked_at = state.get("checked_at") or ""
        written_at = challenge.get("written_at") or ""
        if checked_at and written_at and checked_at < written_at:
            return False, "UNVERIFIED"  # receipt predates the challenge it claims to answer
        return True, "MEASURED"
    except Exception:
        return False, "UNVERIFIED"


def latest_run_dir():
    try:
        runs = Path(".simplicio/orchestrator") / "runs"
        if not runs.exists():
            return ""
        candidates = sorted([p for p in runs.iterdir() if p.is_dir()], key=lambda p: p.name)
        return str(candidates[-1]) if candidates else ""
    except Exception:
        return ""


def latest_completion_receipt():
    try:
        run_dir = latest_run_dir()
        if not run_dir:
            return None
        path = Path(run_dir) / "completion-receipt.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        payload["_path"] = str(path)
        return payload
    except Exception:
        return None


def maintenance_deferred_receipt():
    """Return the active maintenance-deferred completion receipt, if any.

    Backlog-only maintenance is explicitly incomplete: the loop must hand off
    with the durable receipt instead of honoring a fresh completion promise.
    Unreadable or unrelated receipts are treated as absent.
    """
    try:
        receipt = latest_completion_receipt() or {}
        if receipt.get("ready") is False and receipt.get("reason_code") == "maintenance_deferred":
            return receipt
    except Exception:
        pass
    return None


def completion_oracle_payload(response_text="", flow_gap=""):
    try:
        repo_root = os.getcwd()
        script = os.path.join(repo_root, "scripts", "completion_oracle.py")
        if not os.path.exists(script):
            source_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script = os.path.join(source_repo, "scripts", "completion_oracle.py")
        if not os.path.exists(script):
            return {"ready": False, "reason_code": "oracle_script_missing", "tag": "UNVERIFIED"}
        run_dir = latest_run_dir()
        cmd = [sys.executable, script, "--loop-dir", LOOP_DIR]
        if run_dir:
            cmd += ["--run-dir", run_dir]
        if response_text:
            cmd += ["--response-text", response_text]
        if flow_gap:
            cmd += ["--flow-gap", flow_gap]
        if run_dir:
            cmd += ["--write-receipt"]
        r = subprocess.run(
            cmd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            cwd=repo_root,
        )
        payload = json.loads(r.stdout) if (r.stdout or "").strip() else {}
        if isinstance(payload, dict):
            return payload
        return {"ready": False, "reason_code": "oracle_invalid_payload", "tag": "UNVERIFIED"}
    except Exception:
        return {"ready": False, "reason_code": "oracle_error", "tag": "UNVERIFIED"}


def spindle_latched():
    """True when a spindle handoff exists with an unreleased latch.

    A latched handoff means agent A handed off to agent B and is waiting for B to
    confirm receipt. When latched, the loop must NOT re-feed the goal — the handoff
    target will pick up. Fail-open: unreadable/missing file → False (never trap).
    """
    try:
        if not os.path.exists(SPINDLE_STATE):
            return False
        with open(SPINDLE_STATE, encoding="utf-8") as f:
            s = json.load(f)
        return bool(s.get("latch", False))
    except Exception:
        return False


def spindle_active():
    """True when a spindle handoff exists and IS confirmed (current agent is processing).

    An active (confirmed) handoff means the receiving agent confirmed receipt and is
    working. The loop can continue normally for this agent. Fail-open: unreadable/missing
    file → False (never trap).
    """
    try:
        if not os.path.exists(SPINDLE_STATE):
            return False
        with open(SPINDLE_STATE, encoding="utf-8") as f:
            s = json.load(f)
        return bool(s.get("current_agent")) and not bool(s.get("latch", False))
    except Exception:
        return False


def read_phase():
    """Read the current hierarchical phase, if any. Fail-open."""
    try:
        if not os.path.exists(PHASE_FILE):
            return None
        with open(PHASE_FILE, encoding="utf-8") as f:
            phase = json.load(f)
        return phase if isinstance(phase, dict) else None
    except Exception:
        return None


def _call_cross_agent_wiki(command):
    """Capture/refresh the shared wiki used for cross-agent continuity. Fail-open."""
    try:
        repo_root = os.getcwd()
        script = os.path.join(repo_root, "scripts", "cross_agent_wiki.py")
        if not os.path.exists(script):
            return
        subprocess.run(
            [sys.executable, script, command],
            capture_output=True, timeout=15,
            cwd=repo_root,
        )
    except Exception:
        pass


def refresh_cross_agent_wiki(include_handoff=False):
    """Best-effort wiki maintenance at loop boundaries. Fail-open."""
    _call_cross_agent_wiki("capture")
    _call_cross_agent_wiki("summary")
    if include_handoff:
        _call_cross_agent_wiki("handoff")


def phase_header_hint():
    """Render a short phase hint for the next iteration header. Empty when flat."""
    phase = read_phase()
    if not phase:
        return ""
    bits = [" phase=%s" % phase.get("phase", "?")]
    strategy = str(phase.get("strategy", "")).strip()
    guard = str(phase.get("tactical_guard", "")).strip()
    if strategy:
        bits.append(" strategy=%s" % strategy[:120])
    if guard:
        bits.append(" guard=%s" % guard[:120])
    return "".join(bits)


def emit_refeed(followup):
    """Emit the re-feed in BOTH schemas; each runtime reads its own key."""
    out = {
        "followup_message": followup,            # Cursor
        "decision": "block",                      # Claude Code Stop hook
        "reason": followup,
    }
    sys.stdout.write(json.dumps(out))
    sys.exit(0)


def main():
    try:
        meta, body = None, None
        if os.path.exists(SCRATCHPAD):
            try:
                with open(SCRATCHPAD, encoding="utf-8") as f:
                    meta, body = parse_frontmatter(f.read())
            except OSError:
                meta, body = None, None

        # Fire-and-forget simplicio CLI callout: verify claims and nest tree, and
        # checkpoint this loop boundary. Disabled when no scratchpad exists (no active
        # loop). Silent failure if the CLI is not installed — the loop proceeds either way.
        if os.path.exists(SCRATCHPAD):
            _call_simplicio_claims()
            _call_simplicio_nest()
            _call_simplicio_checkpoint((meta or {}).get("iteration", "?"))

        # Explicit STOP signal beats everything — but still hand off if there was live state.
        if os.path.exists(STOP_SIGNAL):
            if meta is not None:
                write_handoff("manual STOP signal", meta, body)
            cleanup_and_stop("STOP: manual STOP signal", "blocked")
        # Waiting on a background gate (workflow / CI / long task)? Let the turn end WITHOUT
        # consuming an iteration or re-feeding — we are blocked on that gate, not idle. The gate's
        # completion re-invokes the agent; the loop resumes then (lock is gone). Preserves state.
        if gate_running():
            allow_stop()
        # (1) No active loop.
        if not os.path.exists(SCRATCHPAD):
            allow_stop()
        # (2) Corrupt state.
        if meta is None:
            cleanup_and_stop("corrupt loop state (unparseable frontmatter)", "blocked")
        try:
            iteration = int(meta.get("iteration", "1"))
            max_iter = int(meta.get("max_iterations", "0"))
        except ValueError:
            cleanup_and_stop("corrupt loop state (bad iteration/max_iterations)", "blocked")
        promise = meta.get("completion_promise", "null")
        promise = None if promise in (None, "null", "") else promise
        evidence_required = str(meta.get("evidence_required", "true")).lower() != "false"
        # Strict mode locks evidence_required=true — agents cannot opt out via scratchpad.
        if _strict_loop_enabled():
            evidence_required = True

        # (2b) Bound operators required (#83) — when this repo ships the simplicio-loop
        # companion skill, `simplicio-mapper`/`simplicio-dev-cli` are hard deps of the running
        # loop, not just the installer. Runtime joins the set when operational (or forced);
        # project retrieval accelerators are not lifecycle-hook dependencies.
        # A genuine BLOCK (handoff + stop), mirroring the cap gate, so a marketplace install /
        # PATH gap can never silently degrade to LLM hand-survey/hand-edit.
        missing_ops = missing_bound_operators()
        if missing_ops:
            reason = "bound operator missing: %s" % ", ".join(missing_ops)
            _call_simplicio_hbp_append_topic("loop-run-blocked", {
                "fingerprint": _journal_stall()[0], "attempt": iteration, "reason": reason,
            })
            write_handoff(reason, meta, body)
            cleanup_and_stop(reason, "blocked")

        # (2c) Delivery contract — new-file guard (#526 Etapa 4). `allow_new_files_in_repo:
        # false` blocks the turn the instant an unauthorized new file appears in the repo — a
        # client-mandated, non-negotiable restriction, same hard-block severity as a missing
        # bound operator. Journaled so the violation is auditable, never silent.
        delivery_violation = delivery_new_file_violation()
        if delivery_violation:
            _record_delivery_violation_journal(iteration, delivery_violation)
            _call_simplicio_hbp_append_topic("loop-run-blocked", {
                "fingerprint": _journal_stall()[0], "attempt": iteration,
                "reason": delivery_violation,
            })
            write_handoff(delivery_violation, meta, body)
            cleanup_and_stop(delivery_violation, "blocked")

        stdin = read_stdin_json()
        resp = last_assistant_text(stdin)
        has_evidence = bool(resp and EVIDENCE_RE.search(resp))

        # Fallback attempt-memory record (#67) so the hierarchical planner is never blind to
        # this turn even if the agent forgot the manual `loop_journal.py record` call.
        auto_record_journal(iteration, has_evidence)

        # HBP point: stall detected (#128) — when the trailing journal streak crosses the same
        # K=3 threshold the stall detector/planner use, record it into the tamper-evident chain
        # so a later `simplicio hbp verify` can prove WHEN the loop knew it was stuck. Fail-open.
        stall_fp, stall_streak = _journal_stall()
        if stall_streak >= 3:
            _call_simplicio_hbp_append_topic("loop-stall-detected", {
                "fingerprint": stall_fp, "attempt": iteration, "streak": stall_streak,
            })

        # HRM-style hierarchical planner: re-assess phase on stall or every N iterations.
        # Runs BEFORE the promise gate so the phase context is available.
        _call_hierarchical_planner()

        # Pre-promise: watcher-gate — independent verification before any promise is honored.
        # Per Asolaria N-Nest Corrective Gate: each agent PID has a watcher PID that
        # independently re-computes the truth. Gate: reported == watcher.recomputed_truth.
        watcher_pass, watcher_tag = watcher_verify()

        # Pre-promise: front→back flow-audit gate (#80) — mechanical, not prose-only.
        flow_gap = flow_audit_gap()

        # Delivery contract is checked at the real turn boundary, not only at commit time.
        delivery_gap = _delivery_stop_guard(os.getcwd(), iteration)
        if delivery_gap:
            flow_gap = flow_gap or delivery_gap

        # Completion detection is centralized in the shared oracle (#138). The stop hook can still
        # surface watcher/flow state in the re-feed header below, but it no longer decides COMPLETE
        # on its own.
        deferred_receipt = maintenance_deferred_receipt()
        if deferred_receipt:
            write_handoff("maintenance deferred (backlog-only mode active)", meta, body)
            cleanup_and_stop("maintenance deferred (backlog-only mode active)", "blocked")
        if promise and resp:
            oracle = completion_oracle_payload(resp, flow_gap or "")
            if oracle.get("ready") and os.path.exists(str(oracle.get("receipt_path") or "")):
                _call_simplicio_hbp_append(iteration, promise, watcher_tag)
                refresh_cross_agent_wiki(include_handoff=False)
                cleanup_and_stop("promise verificada", "pass")  # (3) promise fulfilled → stop
            elif PROMISE_RE.search(resp):
                # (#302 § 3) a promise WAS typed this turn but the oracle refused it (no in-turn
                # evidence / no receipt) — the loop continues, but this is high-signal for the
                # user ("the model thought it was done, the gate disagreed"). Fail-open, never
                # blocks the turn.
                _emit_final_progress("promise REJEITADA: sem evidência no turno", "blocked")
            # A promise is never sufficient without a persisted run receipt.  The old
            # lightweight fallback was a fail-open completion bypass (#138); missing run
            # artifacts remain DELIVERY_PENDING and the loop continues or hands off at cap.
        # (3') Cursor capture may have raised the flag.
        if os.path.exists(DONE_FLAG) or os.path.exists(LEGACY_DONE_FLAG):
            oracle = completion_oracle_payload(flow_gap=flow_gap or "")
            if oracle.get("ready") and os.path.exists(str(oracle.get("receipt_path") or "")):
                cleanup_and_stop("promise verificada (done flag)", "pass")
        # (4) Iteration cap — incomplete stop, hand off.
        if max_iter > 0 and iteration >= max_iter:
            _call_simplicio_hbp_append_topic("loop-run-blocked", {
                "fingerprint": _journal_stall()[0], "attempt": iteration,
                "reason": "max_iterations cap reached",
            })
            write_handoff("max_iterations cap reached", meta, body)
            cleanup_and_stop("cap atingido: max_iterations cap reached", "blocked")
        # (5) Spindle handoff — latched handoff overrides re-feed.
        if spindle_latched():
            next_agent = "?"
            try:
                with open(SPINDLE_STATE, encoding="utf-8") as _f:
                    _s = json.load(_f)
                    next_agent = _s.get("next_agent", "?")
            except Exception:
                pass
            write_handoff("spindle handoff (latched — waiting for '%s')" % next_agent, meta, body)
            cleanup_and_stop("handoff latched (waiting for '%s')" % next_agent, "blocked")
        # (6) Continue: bump iteration in place, re-feed the goal body.
        nxt = iteration + 1
        with open(SCRATCHPAD, encoding="utf-8") as f:
            raw = f.read()
        new_content = re.sub(
            r"^iteration:\s*\d+", "iteration: %d" % nxt, raw, count=1, flags=re.M
        )
        try:
            tmp = SCRATCHPAD + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(new_content)
            os.replace(tmp, SCRATCHPAD)
        except OSError:
            allow_stop()  # can't persist progress → don't risk an unbounded loop
        promise_hint = (
            " To finish: output <promise>%s</promise> ONLY when genuinely true AND "
            "backed by a passing gate." % promise
            if promise
            else ""
        )
        # Surface the still-open acceptance criteria so the next turn knows exactly what blocks
        # "done" — the anchor gate is why a promise would be ignored, so name the gap.
        pending = anchor_pending()
        ac_hint = (
            " Open acceptance criteria (verify each before the promise): %s."
            % ", ".join(p for p in pending if p)
            if pending
            else ""
        )
        flow_hint = " Flow-audit gap: %s." % flow_gap if flow_gap else ""
        # #302 — prefix the re-feed header with the progress snapshot (fase/etapa/item/ACs/%),
        # so the user sees WHERE the loop is even when the model forgets to narrate it. Fail-open:
        # any error -> empty prefix, header identical to before this feature existed.
        progress_prefix = _progress_header_prefix(nxt, max_iter)
        header = "[simplicio-loop iteration %d.%s%s%s%s%s %s]" % (
            nxt, progress_prefix, promise_hint, ac_hint, flow_hint, phase_header_hint(), watcher_tag
        )
        # Issue the NEXT iteration's watcher challenge before re-feeding (#82) — must be on disk
        # before the next turn's agent acts, so a mid-turn `watcher_verify.py` run can read and
        # echo it.
        write_watcher_challenge(nxt)
        refresh_cross_agent_wiki(include_handoff=False)
        emit_refeed(_refeed_message(header, body))
    except Exception:
        allow_stop()  # fail-open, always


def _call_hierarchical_planner():
    """Run the HRM-style hierarchical planner if a scratchpad exists. Fail-open.

    The planner reads the journal and current phase, then MAY write a new phase
    (`.simplicio/orchestrator/loop/phase.json`) on stall detection or every N iterations.
    The phase context is consumed by the re-feed header or the loop's decision logic.
    Fail-open: any error here must never trap the loop; the loop runs in flat mode
    if the planner is missing or broken.
    """
    try:
        if os.path.exists(SCRATCHPAD):
            repo_root = os.getcwd()
            script = os.path.join(repo_root, "scripts", "hierarchical_planner.py")
            if not os.path.exists(script):
                return
            subprocess.run(
                [sys.executable, script, "plan"],
                capture_output=True, timeout=15,
                cwd=repo_root,
            )
    except Exception:
        pass  # fail-open


if __name__ == "__main__":
    main()

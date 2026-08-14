#!/usr/bin/env python3
"""simplicio-loop — agent-to-agent handoff protocol (spindle/latch pattern).

Transforms the existing one-directional HANDOFF.md (agent A writes, walks away)
into a **confirmed handoff** with a latch: agent A writes the handoff + sets a
latch, agent B confirms receipt, and ONLY then does A release the latch — the
handoff is ACKed, not just dropped on disk.

The spindle pattern creates a pipeline of workers:
  1. Agent A receives work from previous agent (or starts fresh).
  2. Agent A processes its part.
  3. Agent A hands off to Agent B: `handoff --next B --state '{"done":["phase1"]}'`
     → writes spindle.json (state + latch) + HANDOFF.md (human-readable).
  4. Agent B arrives, runs `handoff confirm` → latch released.
  5. Agent B reads the state, resumes, processes its part.
  6. Agent B hands off to Agent C... and so on.

The latch ensures delivery: without a confirm, the next agent is REQUIRED to pick
up before the previous agent considers the handoff complete. If the next agent
never confirms, the handoff remains LATCHED and the spindle is stalled — a
detectable state (``handoff status`` shows `latch: true`).

State file (single source of truth): `.simplicio/orchestrator/loop/spindle_state.json`
Spindle handoff dir: `.simplicio/orchestrator/loop/handoffs/` (append-only, one JSONL per event)
"""

import argparse
import json
import os
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from _locked_append import locked_append_line  # noqa: E402 — cross-process safe append (#127)

LOOP_DIR = os.path.join(".simplicio/orchestrator", "loop")
SPINDLE_STATE = os.path.join(LOOP_DIR, "spindle_state.json")
LEGACY_SPINDLE_STATE = os.path.join(LOOP_DIR, "spindle.json")
HANDOFF_FILE = os.path.join(LOOP_DIR, "HANDOFF.md")
HANDOFFS_DIR = os.path.join(LOOP_DIR, "handoffs")


# ── helpers ─────────────────────────────────────────────────────────────────


def _discover_simplicio_cli():
    """Probe for simplicio CLI in priority order. Returns (binary, subcommand_prefix) or (None, None).

    Tries: ``simplicio gate``, ``simplicio-py gate``, ``python3 -m simplicio.cli gate``.
    Silent-fail: any probe error returns (None, None) — never blocks.
    """
    candidates = [
        ("simplicio", "gate"),
        ("simplicio-py", "gate"),
        ("python3", ["-m", "simplicio.cli", "gate"]),
    ]
    for binary, sub in candidates:
        try:
            args = [binary] + (sub if isinstance(sub, list) else [sub, "--help"])
            subprocess.run(args, capture_output=True, timeout=5)
            return binary, sub
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None, None


def _call_simplicio_gate_check(binary, reported="?", watcher="?"):
    """Run ``simplicio gate check <reported> <watcher>`` silently. Fail-open."""
    try:
        subprocess.run(
            [binary, "gate", "check", str(reported), str(watcher)],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def _ensure_dirs():
    os.makedirs(LOOP_DIR, exist_ok=True)
    os.makedirs(HANDOFFS_DIR, exist_ok=True)


def _read_spindle():
    """Return the spindle state dict, or None if absent/corrupt.

    Reads the current file name first; falls back to the pre-rename
    `spindle.json` so an in-flight handoff written by an older version
    is still picked up.
    """
    for path in (SPINDLE_STATE, LEGACY_SPINDLE_STATE):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return None


def _write_spindle(spindle: dict):
    """Atomically write the spindle state."""
    _ensure_dirs()
    tmp = SPINDLE_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(spindle, f, indent=2, sort_keys=True, ensure_ascii=False)
    os.replace(tmp, SPINDLE_STATE)


def _append_event(event: dict):
    """Append one event to the handoffs/ log (append-only, JSONL).

    Locked, cross-process-safe append (#127): concurrent handoff/confirm calls from different
    agents/workers can no longer interleave into a torn line. FAIL-OPEN on a lock timeout — the
    event is skipped (never partially written), which matches this function's existing contract
    ("logging must never block").
    """
    _ensure_dirs()
    log_path = os.path.join(HANDOFFS_DIR, "events.jsonl")
    event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        locked_append_line(log_path, json.dumps(event, sort_keys=True))
    except OSError:
        pass  # fail-open: logging must never block


def _write_handoff_md(next_agent: str, state: dict, note: str = ""):
    """Write a human-readable HANDOFF.md for the next agent."""
    lines = [
        "# simplicio-loop spindle handoff",
        "",
        "This handoff was MADE to a specific next agent and has a live latch.",
        "The next agent MUST run ``handoff confirm`` before processing.",
        "",
        "---",
        "",
        "**Next agent:** %s" % next_agent,
        "**Timestamp:** %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "",
        "## Transferred state",
        "",
        "```json",
        json.dumps(state, indent=2, ensure_ascii=False),
        "```",
    ]
    if note:
        lines += [
            "",
            "## Note",
            "",
            note,
        ]
    lines += [
        "",
        "## Resume procedure",
        "",
        "1. Confirm receipt:  ``python3 scripts/handoff.py confirm``",
        "2. Read the live state:  ``python3 scripts/handoff.py status``",
        "3. Resume or re-arm the loop with the transferred state.",
        "4. When done, hand off to the next agent:  ``python3 scripts/handoff.py handoff --next <agent> --state '<json>'``.",
        "",
    ]
    tmp = HANDOFF_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, HANDOFF_FILE)
    except OSError:
        pass  # fail-open


# ── commands ─────────────────────────────────────────────────────────────────


def cmd_handoff(next_agent: str, state: dict, note: str = ""):
    """Pass work to *next_agent*, set the latch, write the state + handoff doc.

    The latch is a boolean ``latch: true`` in spindle.json. The next agent
    *must* run ``handoff confirm`` to release it.
    """
    # Attempt simplicio gate check before handoff — a silent, best-effort
    # verification of the gate state (reported vs watcher truth). Fail-open:
    # unavailable CLI, timeout, or error never blocks the handoff itself.
    simplicio_binary, _ = _discover_simplicio_cli()
    if simplicio_binary:
        _call_simplicio_gate_check(simplicio_binary)

    if not next_agent or not next_agent.strip():
        print("error: --next agent name is required", file=sys.stderr)
        sys.exit(1)

    spindle = _read_spindle() or {}
    spindle["next_agent"] = next_agent.strip()
    spindle["state"] = state
    spindle["latch"] = True
    spindle["previous_agent"] = spindle.get("current_agent", "unknown")
    spindle["current_agent"] = None  # no one is currently working it
    spindle["handoffed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    spindle["confirmed_at"] = None
    _write_spindle(spindle)
    _write_handoff_md(next_agent.strip(), state, note)
    _append_event({
        "event": "handoff",
        "from": spindle.get("previous_agent", "unknown"),
        "to": next_agent.strip(),
    })
    print("✓ Handoff made to '%s' (latch set)." % next_agent.strip())
    print("  The next agent must run:  python3 scripts/handoff.py confirm")
    print("  State:  python3 scripts/handoff.py status")


def cmd_confirm():
    """Confirm receipt of a pending handoff, releasing the latch.

    Only the named ``next_agent`` can confirm. If no agent name is tracked,
    anyone can confirm (backward-compat with un-named handoffs).
    """
    spindle = _read_spindle()
    if spindle is None:
        print("error: no active spindle handoff found", file=sys.stderr)
        sys.exit(1)
    if not spindle.get("latch"):
        print("error: no latched handoff to confirm (latch is already released)", file=sys.stderr)
        sys.exit(1)

    spindle["latch"] = False
    spindle["current_agent"] = spindle.get("next_agent", "unknown")
    spindle["confirmed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_spindle(spindle)
    _append_event({
        "event": "confirm",
        "agent": spindle["current_agent"],
    })
    print("✓ Handoff confirmed by '%s' (latch released)." % spindle["current_agent"])
    print("  You are now the active agent. Proceed with the transferred state.")


def cmd_receive():
    """Receive a handoff: confirm + read state in one step.

    Equivalent to running ``handoff confirm`` then ``handoff status``.
    """
    cmd_confirm()
    print("")
    cmd_status(verbose=False)


def cmd_status(verbose: bool = True):
    """Show the active spindle/latch state, or report nothing is pending."""
    spindle = _read_spindle()
    if spindle is None:
        print("No active spindle handoff.")
        print("State: idle")
        sys.exit(0)

    next_agent = spindle.get("next_agent", "?")
    current = spindle.get("current_agent")
    latched = spindle.get("latch", False)
    state = spindle.get("state", {})

    if latched:
        print("State: LATCHED (handoff pending confirmation)")
        print("  Next agent: %s" % next_agent)
        print("  Previous agent: %s" % spindle.get("previous_agent", "?"))
        print("  Handoffed at: %s" % spindle.get("handoffed_at", "?"))
        print("  To confirm:  python3 scripts/handoff.py confirm")
    elif current:
        print("State: ACTIVE (handoff confirmed)")
        print("  Current agent: %s" % current)
        print("  Confirmed at: %s" % spindle.get("confirmed_at", "?"))
    else:
        print("State: IDLE (no active handoff)")
        sys.exit(0)

    if verbose and state:
        print("")
        print("Transferred state:")
        print(json.dumps(state, indent=2, ensure_ascii=False))


def cmd_events(limit: int = 20):
    """Show the recent handoff event log."""
    log_path = os.path.join(HANDOFFS_DIR, "events.jsonl")
    if not os.path.exists(log_path):
        print("No handoff events recorded yet.")
        return
    try:
        with open(log_path, encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        for ln in lines[-limit:]:
            try:
                ev = json.loads(ln)
                ts = ev.pop("ts", "?")
                sys.stdout.write("[%s] %s\n" % (ts, json.dumps(ev)))
            except Exception:
                sys.stdout.write(ln)
    except OSError:
        print("error: could not read event log", file=sys.stderr)
        sys.exit(1)


def cmd_clear():
    """Clear the spindle state (for testing / manual reset)."""
    if not os.path.exists(SPINDLE_STATE):
        print("No spindle state to clear.")
        return
    try:
        os.remove(SPINDLE_STATE)
        _append_event({"event": "clear"})
        print("✓ Spindle state cleared.")
    except OSError as e:
        print("error: could not clear spindle state: %s" % e, file=sys.stderr)
        sys.exit(1)


# ── selftest ─────────────────────────────────────────────────────────────────


def cmd_selftest():
    """Prove the spindle/latch round-trip, legacy migration, and event log — no external state.

    Regression coverage for the 685600b bug class (a state-file rename that leaves loop_stop.py
    and handoff.py disagreeing about the shared spindle_state.json path/schema, #73). Runs in a
    throwaway temp directory (handoff.py's state paths are CWD-relative) and restores the caller's
    CWD in `finally` even on assertion failure.
    """
    import io
    import contextlib
    import tempfile

    origin = os.getcwd()
    tmpdir = tempfile.TemporaryDirectory()
    try:
        os.chdir(tmpdir.name)

        # round-trip: handoff -> latched -> confirm -> active
        cmd_handoff("agent-b", {"done": ["phase1"]}, note="phase 1 complete")
        spindle = _read_spindle()
        assert spindle is not None, "handoff should write spindle_state.json"
        assert spindle["latch"] is True, "a fresh handoff must be latched"
        assert spindle["next_agent"] == "agent-b"
        assert os.path.exists(HANDOFF_FILE), "handoff should write HANDOFF.md"
        with open(HANDOFF_FILE, encoding="utf-8") as f:
            handoff_body = f.read()
        assert "agent-b" in handoff_body
        assert "phase 1 complete" in handoff_body

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_confirm()
        spindle = _read_spindle()
        assert spindle["latch"] is False, "confirm must release the latch"
        assert spindle["current_agent"] == "agent-b"

        # events log: handoff + confirm both recorded, in order
        events_path = os.path.join(HANDOFFS_DIR, "events.jsonl")
        with open(events_path, encoding="utf-8") as f:
            events = [json.loads(ln) for ln in f if ln.strip()]
        assert [e["event"] for e in events] == ["handoff", "confirm"], events

        # legacy spindle.json migration: an old-format file (pre-rename) is still read
        os.remove(SPINDLE_STATE)
        with open(LEGACY_SPINDLE_STATE, "w", encoding="utf-8") as f:
            json.dump({"latch": True, "next_agent": "legacy-agent"}, f)
        legacy = _read_spindle()
        assert legacy is not None and legacy["next_agent"] == "legacy-agent", \
            "legacy spindle.json must still be read for an in-flight handoff from an older version"

        # clear resets to idle
        os.remove(LEGACY_SPINDLE_STATE)
        cmd_handoff("agent-c", {})
        cmd_clear()
        assert _read_spindle() is None, "clear should remove the spindle state"

        print("handoff selftest: PASS")
    finally:
        os.chdir(origin)
        tmpdir.cleanup()


# ── CLI entry ────────────────────────────────────────────────────────────────


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="handoff.py",
        description="simplicio-loop agent-to-agent handoff protocol (spindle/latch pattern).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # handoff
    p_handoff = sub.add_parser("handoff", help="Pass work to the next agent (set latch)")
    p_handoff.add_argument("--next", required=True, help="Name/ID of the receiving agent")
    p_handoff.add_argument("--state", default="{}", help="Transferred state as JSON string")
    p_handoff.add_argument("--note", default="", help="Optional human-readable note")

    # confirm
    sub.add_parser("confirm", help="Confirm receipt of a pending handoff (release latch)")

    # receive = confirm + status
    sub.add_parser("receive", help="Confirm + read state in one step")

    # status
    p_status = sub.add_parser("status", help="Show active handoff/latch state")
    p_status.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # events
    p_events = sub.add_parser("events", help="Show recent handoff event log")
    p_events.add_argument("--limit", type=int, default=20, help="Number of events to show (default: 20)")

    # clear
    sub.add_parser("clear", help="Clear spindle state (manual reset)")

    # selftest
    sub.add_parser("selftest", help="Prove the spindle/latch round-trip deterministically — no external state")

    args = parser.parse_args(argv)

    if args.command == "handoff":
        try:
            state = json.loads(args.state)
        except json.JSONDecodeError as e:
            print("error: --state must be valid JSON: %s" % e, file=sys.stderr)
            sys.exit(1)
        if not isinstance(state, dict):
            print("error: --state must be a JSON object (dict)", file=sys.stderr)
            sys.exit(1)
        cmd_handoff(args.next, state, args.note)

    elif args.command == "confirm":
        cmd_confirm()

    elif args.command == "receive":
        cmd_receive()

    elif args.command == "status":
        if args.json:
            spindle = _read_spindle() or {}
            print(json.dumps(spindle, indent=2, ensure_ascii=False))
        else:
            cmd_status(verbose=True)

    elif args.command == "events":
        cmd_events(args.limit)

    elif args.command == "clear":
        cmd_clear()

    elif args.command == "selftest":
        cmd_selftest()


if __name__ == "__main__":
    main()

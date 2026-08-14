#!/usr/bin/env python3
"""simplicio-loop — hierarchical planner (HRM-style two-level reasoning).

Inspired by the Hierarchical Reasoning Model (HRM) paper (arXiv:2506.21734,
JesseBrown1980/HRM). The flat Ralph loop re-feeds the same goal every turn;
this adds a HIGH-LEVEL planner that runs periodically (every N iterations or
on stall) to re-assess ABSTRACT strategy, then writes a PHASE PLAN that
guides the next N low-level iterations.

Architecture:
  High-level (slow, abstract) — every K turns or on STALLED detection:
    - Re-read the full goal, journal, and current phase plan
    - Output a new phase: {"phase": "refactor|debug|harden|explore",
      "strategy": "...", "scope": [files/dirs], "max_iterations": N,
      "tactical_guard": "what NOT to do"}
    - Only the high-level can change the phase

  Low-level (fast, detailed) — every turn:
    - Execute within the current phase plan
    - Never change the phase
    - Record to journal as usual

State: `.simplicio/orchestrator/loop/phase.json`
  {"phase": "...", "strategy": "...", "scope": [...], "created_at": "...",
   "iteration": N, "max_iterations": N, "tactical_guard": "...",
   "stall_count_at_creation": 0}

Usage:
  python3 scripts/hierarchical_planner.py plan    -- read journal + phase → maybe write a new phase
  python3 scripts/hierarchical_planner.py status  -- show current phase
  python3 scripts/hierarchical_planner.py clear   -- reset to no phase (fresh start)
  python3 scripts/hierarchical_planner.py phase-info -- dump phase.json as JSON
"""

import json
import os
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
PHASE_FILE = os.path.join(LOOP_DIR, "phase.json")
JOURNAL = os.path.join(LOOP_DIR, "journal.jsonl")
SCRATCHPAD = os.path.join(LOOP_DIR, "scratchpad.md")


def _set_repo(repo):
    """Rebind repo-relative state paths. Used by selftest and temp-repo tests."""
    global REPO, LOOP_DIR, PHASE_FILE, JOURNAL, SCRATCHPAD
    REPO = repo
    LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
    PHASE_FILE = os.path.join(LOOP_DIR, "phase.json")
    JOURNAL = os.path.join(LOOP_DIR, "journal.jsonl")
    SCRATCHPAD = os.path.join(LOOP_DIR, "scratchpad.md")


# Default: re-plan every N iterations
DEFAULT_PLAN_INTERVAL = 5
# Rerun planner when stall count >= this
STALL_RETHRESHOLD = 3


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_phase():
    try:
        with open(PHASE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_phase(phase_data):
    os.makedirs(LOOP_DIR, exist_ok=True)
    tmp = PHASE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(phase_data, f, indent=2)
    os.replace(tmp, PHASE_FILE)


def clear_phase():
    try:
        os.remove(PHASE_FILE)
    except FileNotFoundError:
        pass


def load_journal():
    rows = []
    if not os.path.exists(JOURNAL):
        return rows
    with open(JOURNAL) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def read_scratchpad_goal():
    """Return the goal body from scratchpad.md, or None."""
    try:
        with open(SCRATCHPAD) as f:
            text = f.read()
        # strip YAML frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return text.strip() or None
    except FileNotFoundError:
        return None


def compute_stall_count(rows):
    """Count trailing consecutive failures with same fingerprint."""
    if not rows:
        return 0
    last = rows[-1]
    if last.get("gate") == "pass":
        return 0
    fp = last.get("fingerprint", "")
    if not fp:
        return 0
    streak = 0
    for r in reversed(rows):
        if r.get("gate") != "pass" and r.get("fingerprint") == fp:
            streak += 1
        else:
            break
    return streak


def compute_execution_state(rows):
    """Derive execution state from journal.

    Returns one of: "planned", "executed", "verified", "stalled".
    """
    if not rows:
        return "planned"
    last = rows[-1]
    gate = last.get("gate", "")
    if gate == "pass":
        return "verified"
    if gate == "fail":
        sc = compute_stall_count(rows)
        if sc >= STALL_RETHRESHOLD:
            return "stalled"
        return "executed"
    if gate == "blocked":
        return "planned"
    return "executed"


PHASE_PLANS = {
    "explore": {
        "strategy": "Survey the codebase, read logs, understand the failure — do NOT mutate yet",
        "tactical_guard": "No edits in explore phase — only read, grep, and log analysis",
    },
    "debug": {
        "strategy": "Add instrumentation, narrow the failure range, prove root cause",
        "tactical_guard": "Do not fix yet — isolate and prove the root cause first",
    },
    "harden": {
        "strategy": "Add tests, edge cases, error handling — make the current code provably correct",
        "tactical_guard": "Do not add features — only safety nets and boundary checks",
    },
    "refactor": {
        "strategy": "Restructure without changing behavior — extract, rename, deduplicate",
        "tactical_guard": "Zero behavior change — tests must pass before AND after",
    },
    "implement": {
        "strategy": "Write new code against frozen ACs — one AC at a time, verify each",
        "tactical_guard": "Do not refactor existing working code — only add what the AC demands",
    },
    "escalate": {
        "strategy": "STOP making changes — gather all context for human handoff",
        "tactical_guard": "Zero mutations — only collect evidence, write HANDOFF.md",
    },
}


def recommend_phase(execution_state, stall_count, iterations_run, last_phase):
    """Recommend a phase based on execution state and history. Deterministic rules, no LLM."""

    # Escalate on deep stall
    if execution_state == "stalled" and stall_count >= STALL_RETHRESHOLD + 1:
        return "escalate"

    # After escalate, if we're still here (not escalated), try explore
    if execution_state == "stalled":
        if last_phase and last_phase.get("phase") != "explore":
            return "explore"
        # Already in explore and still stalled → escalate
        return "escalate"

    # Fresh start
    if not last_phase:
        return "implement" if iterations_run == 0 else "debug"

    # If we switched phase recently and it didn't help, escalate
    if last_phase.get("phase") in ("debug", "harden"):
        stall_at_create = last_phase.get("stall_count_at_creation", 0)
        if stall_count > stall_at_create + 1:
            # Current phase not working → try next
            if last_phase["phase"] == "debug":
                return "explore"
            return "escalate"

    # Stay in current phase if it's working
    if execution_state == "verified":
        return last_phase["phase"]

    return last_phase["phase"] if last_phase else "implement"


def cmd_plan():
    """High-level planner: read state, maybe write a new phase. Deterministic."""
    rows = load_journal()
    current_phase = read_phase()
    goal = read_scratchpad_goal()
    iterations_run = len(rows)
    stall_count = compute_stall_count(rows)
    execution_state = compute_execution_state(rows)

    # Determine if we need to re-plan
    needs_replan = False
    reason = ""

    if current_phase is None:
        needs_replan = True
        reason = "no phase set"
    else:
        phase_iter = current_phase.get("iteration", 0)
        phase_max = current_phase.get("max_iterations", DEFAULT_PLAN_INTERVAL)
        phase_age = iterations_run - phase_iter
        if phase_age >= phase_max:
            needs_replan = True
            reason = f"phase age ({phase_age}) >= max ({phase_max})"
        elif execution_state == "stalled":
            needs_replan = True
            reason = f"stalled (count={stall_count})"
        elif current_phase.get("phase") == "escalate":
            # Stay in escalate — don't re-plan
            needs_replan = False

    if not needs_replan and current_phase:
        print("MEASURED|phase unchanged: %s (iter %d, age %d)" % (
            current_phase["phase"], current_phase.get("iteration", 0), iterations_run - current_phase.get("iteration", 0)))
        return

    # Re-plan
    new_phase_name = recommend_phase(execution_state, stall_count, iterations_run, current_phase)
    phase_def = PHASE_PLANS.get(new_phase_name, PHASE_PLANS["implement"])
    if goal and new_phase_name == "implement" and (
        "bug" in goal.lower() or "fix" in goal.lower() or "error" in goal.lower()
    ):
        new_phase_name = "debug"
        phase_def = PHASE_PLANS["debug"]

    phase_data = {
        "phase": new_phase_name,
        "strategy": phase_def["strategy"],
        "tactical_guard": phase_def["tactical_guard"],
        "created_at": _now(),
        "iteration": iterations_run,
        "max_iterations": DEFAULT_PLAN_INTERVAL,
        "stall_count_at_creation": stall_count,
        "reason": reason,
        "execution_state": execution_state,
    }
    write_phase(phase_data)
    print("MEASURED|phase changed: %s → %s (reason: %s, state: %s, stall: %d)" % (
        current_phase["phase"] if current_phase else "(none)",
        new_phase_name,
        reason,
        execution_state,
        stall_count,
    ))
    print("MEASURED|strategy: %s" % phase_def["strategy"])
    print("MEASURED|tactical_guard: %s" % phase_def["tactical_guard"])
    if stall_count >= STALL_RETHRESHOLD:
        print("UNVERIFIED|STALLED: last %d identical fingerprints — avoid retrying the same action" % stall_count)


def cmd_status():
    phase = read_phase()
    if not phase:
        print("UNVERIFIED|phase: none (flat loop mode)")
        return
    print("MEASURED|phase: %s" % phase.get("phase", "?"))
    print("MEASURED|created: %s" % phase.get("created_at", "?"))
    print("MEASURED|started at iter: %d" % phase.get("iteration", 0))
    print("MEASURED|max iters in phase: %d" % phase.get("max_iterations", DEFAULT_PLAN_INTERVAL))
    print("MEASURED|reason: %s" % phase.get("reason", "?"))
    print("MEASURED|execution_state: %s" % phase.get("execution_state", "?"))
    print("MEASURED|strategy: %s" % phase.get("strategy", "?"))
    print("MEASURED|tactical_guard: %s" % phase.get("tactical_guard", "?"))
    rows = load_journal()
    sc = compute_stall_count(rows)
    if sc >= STALL_RETHRESHOLD:
        print("UNVERIFIED|STALLED: %d identical fingerprints in journal" % sc)


def cmd_clear():
    clear_phase()
    print("MEASURED|phase cleared")


def cmd_phase_info():
    phase = read_phase()
    print(json.dumps(phase or {"phase": None}, indent=2))


def cmd_selftest():
    origin = REPO
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _set_repo(tmp)
            os.makedirs(LOOP_DIR, exist_ok=True)
            with open(SCRATCHPAD, "w", encoding="utf-8") as f:
                f.write("---\niteration: 1\nmax_iterations: 5\n---\nFix the loop regression.\n")

            cmd_plan()
            phase = read_phase() or {}
            assert phase.get("phase") == "debug", "bug/fix goal should bias initial plan to debug"

            with open(JOURNAL, "w", encoding="utf-8") as f:
                for i in range(1, 4):
                    f.write(json.dumps({
                        "iteration": i,
                        "action": "retry flaky test",
                        "gate": "fail",
                        "fingerprint": "same-fp",
                    }) + "\n")
            cmd_plan()
            phase = read_phase() or {}
            assert phase.get("phase") == "explore", "first stall should replan to explore"

            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "iteration": 4,
                    "action": "retry flaky test",
                    "gate": "fail",
                    "fingerprint": "same-fp",
                }) + "\n")
            cmd_plan()
            phase = read_phase() or {}
            assert phase.get("phase") == "escalate", "deep stall should escalate"

            cmd_clear()
            assert read_phase() is None, "clear should remove phase file"
            print("hierarchical_planner selftest: PASS")
    finally:
        _set_repo(origin)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/hierarchical_planner.py plan|status|clear|phase-info|selftest")
        sys.exit(1)

    command = sys.argv[1]
    if command == "plan":
        cmd_plan()
    elif command == "status":
        cmd_status()
    elif command == "clear":
        cmd_clear()
    elif command == "phase-info":
        cmd_phase_info()
    elif command == "selftest":
        cmd_selftest()
    else:
        print("UNVERIFIED|unknown command: %s" % command)
        sys.exit(1)


if __name__ == "__main__":
    main()

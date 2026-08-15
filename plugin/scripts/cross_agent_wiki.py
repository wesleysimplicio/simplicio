#!/usr/bin/env python3
"""simplicio-loop — cross-agent persistent wiki (ai-memory inspired).

Evolved from the one-shot HANDOFF.md pattern. Instead of a single handoff
text file, every turn's key decisions, findings, and dead-ends are captured
into a persistent markdown wiki at `.simplicio/orchestrator/wiki/`.

A fresh agent arriving in the repo — from any runtime (Hermes, Claude Code,
Codex, Cursor) — reads the wiki and sees "where we left off" without needing
the prior conversation transcript.

Architecture (ai-memory inspired, JesseBrown1980/ai-memory):
  - Zero-friction capture: lifecycle hooks call this script at turn boundaries
  - Per-project isolation: wiki lives at `.simplicio/orchestrator/wiki/` inside the repo
  - Cross-agent handoffs: wiki is plain markdown, readable by any agent/editor
  - No vector DB: plain markdown in a git-ignored directory, grep-able

State:
  .simplicio/orchestrator/wiki/
    SUMMARY.md          — "where we left off" — regenerated each turn
    journal/            — per-turn entries (YYYY-MM-DD_HH-MM-SS.md)
    decisions/          — accepted ACs, rejected approaches, settled facts
    artifacts/          — links to evidence files, PRs, run IDs

Usage:
  python3 scripts/cross_agent_wiki.py capture    — capture this turn's key info from env + files
  python3 scripts/cross_agent_wiki.py summary    — regenerate SUMMARY.md from all entries
  python3 scripts/cross_agent_wiki.py handoff    — write a handoff summary for the next agent
  python3 scripts/cross_agent_wiki.py status     — show wiki stats
"""

import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WIKI_DIR = os.path.join(REPO, ".simplicio/orchestrator", "wiki")
SUMMARY_FILE = os.path.join(WIKI_DIR, "SUMMARY.md")
JOURNAL_DIR = os.path.join(WIKI_DIR, "journal")
DECISIONS_DIR = os.path.join(WIKI_DIR, "decisions")
ARTIFACTS_DIR = os.path.join(WIKI_DIR, "artifacts")
JOURNAL_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "journal.jsonl")
PHASE_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "phase.json")
SCRATCHPAD = os.path.join(REPO, ".simplicio/orchestrator", "loop", "scratchpad.md")
HANDOFF_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "HANDOFF.md")
WATCHER_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "watcher_state.json")


def _set_repo(repo):
    """Rebind repo-relative paths. Used by selftest and temp-repo tests."""
    global REPO, WIKI_DIR, SUMMARY_FILE, JOURNAL_DIR, DECISIONS_DIR, ARTIFACTS_DIR
    global JOURNAL_FILE, PHASE_FILE, SCRATCHPAD, HANDOFF_FILE, WATCHER_FILE
    REPO = repo
    WIKI_DIR = os.path.join(REPO, ".simplicio/orchestrator", "wiki")
    SUMMARY_FILE = os.path.join(WIKI_DIR, "SUMMARY.md")
    JOURNAL_DIR = os.path.join(WIKI_DIR, "journal")
    DECISIONS_DIR = os.path.join(WIKI_DIR, "decisions")
    ARTIFACTS_DIR = os.path.join(WIKI_DIR, "artifacts")
    JOURNAL_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "journal.jsonl")
    PHASE_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "phase.json")
    SCRATCHPAD = os.path.join(REPO, ".simplicio/orchestrator", "loop", "scratchpad.md")
    HANDOFF_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "HANDOFF.md")
    WATCHER_FILE = os.path.join(REPO, ".simplicio/orchestrator", "loop", "watcher_state.json")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stamp():
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def _ensure_dirs():
    for d in (WIKI_DIR, JOURNAL_DIR, DECISIONS_DIR, ARTIFACTS_DIR):
        os.makedirs(d, exist_ok=True)


def _read_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except (FileNotFoundError, OSError):
        return ""


def _write_file(path, content):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def _load_journal():
    rows = []
    if not os.path.exists(JOURNAL_FILE):
        return rows
    with open(JOURNAL_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _read_phase():
    try:
        with open(PHASE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _read_watcher_state():
    try:
        with open(WATCHER_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except FileNotFoundError:
        return {
            "state": "missing",
            "line": "UNVERIFIED|watcher: no receipt (producer: `python3 scripts/watcher_verify.py "
                    "verify` — not yet run this turn, or the challenge hasn't been issued yet)",
        }
    except (OSError, json.JSONDecodeError):
        return {
            "state": "corrupt",
            "line": "UNVERIFIED|watcher: unreadable receipt (.simplicio/orchestrator/loop/watcher_state.json)",
        }

    measured = bool(state.get("match")) and str(state.get("status", "")).upper() == "MEASURED"
    checked_at = state.get("checked_at") or "?"
    verdict = "MEASURED|" if measured else "UNVERIFIED|"
    label = "verified match" if measured else "receipt present but not verified"
    detail = [
        "status=%s" % state.get("status", "?"),
        "match=%s" % state.get("match", False),
        "checked_at=%s" % checked_at,
    ]
    if state.get("reported") is not None:
        detail.append("reported=%s" % state.get("reported"))
    if state.get("recomputed_truth") is not None:
        detail.append("recomputed_truth=%s" % state.get("recomputed_truth"))
    return {
        "state": "verified" if measured else "unverified",
        "checked_at": checked_at,
        "status": state.get("status", "?"),
        "match": bool(state.get("match", False)),
        "raw": state,
        "line": "%swatcher: %s (%s)" % (verdict, label, ", ".join(detail)),
    }


def _distinct_recent(items, limit=5):
    out = []
    seen = set()
    for item in items:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _journal_blockers(journal, limit=5):
    return _distinct_recent((r.get("blocked_reason", "") for r in reversed(journal)), limit)


def _journal_next_actions(journal, limit=5):
    return _distinct_recent((r.get("next_action", "") for r in reversed(journal)), limit)


def _git_log(age=5):
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-n", str(age)],
            capture_output=True, text=True, timeout=10, cwd=REPO,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_diff_stat():
    try:
        r = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, timeout=10, cwd=REPO,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_branch():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=REPO,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def cmd_capture():
    """Capture this turn's state into a journal entry."""
    _ensure_dirs()
    journal = _load_journal()
    phase = _read_phase()
    scratchpad = _read_file(SCRATCHPAD)
    handoff = _read_file(HANDOFF_FILE)
    git_log = _git_log()
    git_diff = _git_diff_stat()
    branch = _git_branch()
    agent = os.environ.get("SIMPLICIO_AGENT_PROFILE",
                           os.environ.get("HERMES_PROFILE",  # legacy alias, compat window
                                          os.environ.get("CLAUDE_PROFILE", "unknown")))

    # Extract goal from scratchpad
    goal = scratchpad
    if scratchpad.startswith("---"):
        parts = scratchpad.split("---", 2)
        if len(parts) >= 3:
            goal = parts[2].strip()[:300]

    # Latest journal entry info
    last_entry = journal[-1] if journal else {}
    last_action = last_entry.get("action", "(none)")
    last_gate = last_entry.get("gate", "?")
    last_fp = last_entry.get("fingerprint", "")[:12]

    entry = [
        "# Turn capture — %s" % _now(),
        "",
        "**Agent:** %s" % agent,
        "**Branch:** %s" % branch,
        "**Last action:** %s" % last_action,
        "**Last gate:** %s" % last_gate,
        "**Fingerprint:** %s" % (last_fp or "-"),
        "",
    ]
    if phase:
        entry.append("**Phase:** %s — %s" % (phase.get("phase", "?"), phase.get("strategy", "")[:120]))
        entry.append("**Tactical guard:** %s" % phase.get("tactical_guard", ""))
        entry.append("")
    if journal:
        n_pass = sum(1 for r in journal if r.get("gate") == "pass")
        n_fail = sum(1 for r in journal if r.get("gate") == "fail")
        entry.append("**Journal:** %d entries (%d pass, %d fail)" % (len(journal), n_pass, n_fail))
        entry.append("")
    if goal:
        entry.append("## Goal")
        entry.append("")
        entry.append(goal[:500])
        entry.append("")
    if git_log:
        entry.append("## Recent commits")
        entry.append("")
        entry.append("```")
        entry.append(git_log[:500])
        entry.append("```")
        entry.append("")
    if git_diff:
        entry.append("## Working tree changes")
        entry.append("")
        entry.append("```")
        entry.append(git_diff[:500])
        entry.append("```")
        entry.append("")
    if handoff:
        entry.append("## Handoff note")
        entry.append("")
        entry.append(handoff[:500])
        entry.append("")

    stamp = _stamp()
    _write_file(os.path.join(JOURNAL_DIR, "%s.md" % stamp), "\n".join(entry))
    print("MEASURED|captured turn to wiki/journal/%s.md" % stamp)


def cmd_summary():
    """Regenerate SUMMARY.md from all wiki content."""
    _ensure_dirs()
    journal_files = sorted(os.listdir(JOURNAL_DIR)) if os.path.isdir(JOURNAL_DIR) else []
    decision_files = sorted(os.listdir(DECISIONS_DIR)) if os.path.isdir(DECISIONS_DIR) else []
    artifact_files = sorted(os.listdir(ARTIFACTS_DIR)) if os.path.isdir(ARTIFACTS_DIR) else []

    journal = _load_journal()
    phase = _read_phase()
    watcher = _read_watcher_state()
    branch = _git_branch()

    summary = [
        "# simplicio-loop wiki summary",
        "",
        "**Generated:** %s" % _now(),
        "**Branch:** %s" % branch,
        "**Journal entries:** %d" % len(journal),
        "**Wiki journal files:** %d" % len(journal_files),
        "**Decision files:** %d" % len(decision_files),
        "**Artifact files:** %d" % len(artifact_files),
        "",
    ]

    if phase:
        summary.append("## Current phase")
        summary.append("")
        summary.append("- **Phase:** %s" % phase.get("phase", "?"))
        summary.append("- **Strategy:** %s" % phase.get("strategy", ""))
        summary.append("- **Guard:** %s" % phase.get("tactical_guard", ""))
        summary.append("- **Since iteration:** %d" % phase.get("iteration", 0))
        summary.append("")

    summary.append("## Watcher verification")
    summary.append("")
    summary.append("- **Watcher state:** %s" % watcher.get("state", "unknown"))
    summary.append("- **Receipt:** `.simplicio/orchestrator/loop/watcher_state.json`")
    if watcher.get("state") not in ("missing", "corrupt"):
        summary.append("- **Status:** %s" % watcher.get("status", "?"))
        summary.append("- **Match:** %s" % watcher.get("match", False))
        summary.append("- **Checked at:** %s" % watcher.get("checked_at", "?"))
    summary.append("")

    if journal:
        n_pass = sum(1 for r in journal if r.get("gate") == "pass")
        n_fail = sum(1 for r in journal if r.get("gate") == "fail")
        n_blocked = sum(1 for r in journal if r.get("gate") == "blocked")
        summary.append("## Journal summary")
        summary.append("")
        summary.append("| Metric | Value |")
        summary.append("|--------|-------|")
        summary.append("| Total entries | %d |" % len(journal))
        summary.append("| Pass | %d |" % n_pass)
        summary.append("| Fail | %d |" % n_fail)
        summary.append("| Blocked | %d |" % n_blocked)
        summary.append("")

        # Distinct fingerprints (unique failures encountered)
        fps = set()
        for r in journal:
            fp = r.get("fingerprint", "")
            if fp and r.get("gate") != "pass":
                fps.add(fp)
        if fps:
            summary.append("**Unique failure fingerprints:** %d" % len(fps))
            for fp in sorted(fps)[:10]:
                summary.append("  - `%s`" % fp)
            summary.append("")

        # Distinct actions tried
        actions = set()
        for r in journal:
            a = r.get("action", "")
            if a:
                actions.add(a[:60])
        if actions:
            summary.append("**Actions tried (%d):**" % len(actions))
            for a in sorted(actions)[:15]:
                summary.append("  - %s" % a)
            summary.append("")

        blockers = _journal_blockers(journal)
        if blockers:
            summary.append("## Open questions / blockers")
            summary.append("")
            for item in blockers:
                summary.append("- %s" % item[:160])
            summary.append("")

        next_actions = _journal_next_actions(journal)
        if next_actions:
            summary.append("## Suggested next actions")
            summary.append("")
            for item in next_actions:
                summary.append("- %s" % item[:160])
            summary.append("")

    if journal_files:
        summary.append("## Recent journal files")
        summary.append("")
        for f in journal_files[-10:]:
            summary.append("- `%s`" % f)
        summary.append("")

    if decision_files:
        summary.append("## Decision files")
        for f in decision_files[-10:]:
            summary.append("- `%s`" % f)

    if artifact_files:
        summary.append("## Artifact files")
        for f in artifact_files[-10:]:
            summary.append("- `%s`" % f)

    # Handoff note for cross-agent continuity
    handoff = _read_file(HANDOFF_FILE)
    if handoff:
        summary.append("")
        summary.append("## Handoff (cross-agent)")
        summary.append("")
        summary.append("```")
        summary.append(handoff[:800])
        summary.append("```")
        summary.append("")

    _write_file(SUMMARY_FILE, "\n".join(summary))
    print("MEASURED|wiki summary regenerated (%d journal entries, %d files)" % (
        len(journal), len(journal_files)))


def cmd_handoff():
    """Write a handoff summary for the next agent/ runtime."""
    _ensure_dirs()
    journal = _load_journal()
    phase = _read_phase()
    branch = _git_branch()
    git_log = _git_log(10)
    git_diff = _git_diff_stat()

    # Extract last 3 distinct actions (anti-oscillation handoff)
    last_actions = []
    seen = set()
    for r in reversed(journal):
        a = r.get("action", "")
        if a and a not in seen:
            last_actions.append(a)
            seen.add(a)
            if len(last_actions) >= 3:
                break

    lines = [
        "# simplicio-loop handoff (cross-agent wiki)",
        "",
        "**Generated:** %s" % _now(),
        "**Branch:** %s" % (branch or "(detached)"),
        "**Journal entries:** %d" % len(journal),
        "",
        "## Current state",
        "",
    ]

    if phase:
        lines.append("- Phase: **%s**" % phase.get("phase", "?"))
        lines.append("- Strategy: %s" % phase.get("strategy", ""))
        lines.append("- Tactical guard: %s" % phase.get("tactical_guard", ""))
        lines.append("- Started at iteration: %d" % phase.get("iteration", 0))
    else:
        lines.append("- Phase: *(none — flat loop)*")

    if last_actions:
        lines.append("")
        lines.append("## Last distinct actions attempted")
        for a in last_actions:
            lines.append("- %s" % a[:100])

    blockers = _journal_blockers(journal)
    if blockers:
        lines.append("")
        lines.append("## Open questions / blockers")
        for item in blockers:
            lines.append("- %s" % item[:160])

    next_actions = _journal_next_actions(journal)
    if next_actions:
        lines.append("")
        lines.append("## Suggested next actions")
        for item in next_actions:
            lines.append("- %s" % item[:160])

    lines.append("")
    lines.append("## Resume instructions for the next agent")
    lines.append("")
    lines.append("1. Read `.simplicio/orchestrator/wiki/SUMMARY.md` — the full journal and artifact index.")
    lines.append("2. Read `scripts/loop_journal.py resume` — dead-end actions to avoid.")
    lines.append("3. Check `.simplicio/orchestrator/loop/phase.json` — current HRM phase and tactical guard.")
    lines.append("4. Do NOT re-try actions already marked as dead-ends (fingerprint collision).")
    lines.append("5. If this is a different runtime (Codex → Claude, etc.), the wiki at `.simplicio/orchestrator/wiki/` is the shared context.")

    if git_log:
        lines.append("")
        lines.append("## Recent commits")
        lines.append("```")
        lines.append(git_log)
        lines.append("```")

    if git_diff:
        lines.append("")
        lines.append("## Working tree changes")
        lines.append("```")
        lines.append(git_diff[:500])
        lines.append("```")

    _write_file(HANDOFF_FILE, "\n".join(lines))
    print("MEASURED|handoff written (%d journal entries)" % len(journal))


def cmd_status():
    _ensure_dirs()
    journal = _load_journal()
    phase = _read_phase()
    watcher = _read_watcher_state()
    journal_files = sorted(os.listdir(JOURNAL_DIR)) if os.path.isdir(JOURNAL_DIR) else []
    decision_files = sorted(os.listdir(DECISIONS_DIR)) if os.path.isdir(DECISIONS_DIR) else []

    print("MEASURED|wiki: %d journal entries, %d journal files, %d decision files" % (
        len(journal), len(journal_files), len(decision_files)))
    if os.path.exists(SUMMARY_FILE):
        print("MEASURED|summary: %s (%d bytes)" % (
            SUMMARY_FILE, os.path.getsize(SUMMARY_FILE)))
    if phase:
        print("MEASURED|phase: %s (iter %d)" % (phase.get("phase", "?"), phase.get("iteration", 0)))
    if os.path.exists(HANDOFF_FILE):
        hsize = os.path.getsize(HANDOFF_FILE)
        print("MEASURED|handoff: %d bytes (cross-agent ready)" % hsize)
    print(watcher["line"])


def cmd_selftest():
    origin = REPO
    prior_env = os.environ.get("SIMPLICIO_AGENT_PROFILE")
    prior_legacy_env = os.environ.get("HERMES_PROFILE")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _set_repo(tmp)
            loop = os.path.join(tmp, ".simplicio/orchestrator", "loop")
            os.makedirs(loop, exist_ok=True)
            _write_file(SCRATCHPAD, "---\niteration: 2\nmax_iterations: 5\n---\nShip a verified fix.\n")
            _write_file(HANDOFF_FILE, "Existing handoff note")
            with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "iteration": 1,
                    "action": "add regression test",
                    "gate": "fail",
                    "fingerprint": "abc123deadbe",
                }) + "\n")
                f.write(json.dumps({
                    "iteration": 2,
                    "action": "tighten watcher gate",
                    "gate": "pass",
                    "fingerprint": "",
                }) + "\n")
            _write_file(PHASE_FILE, json.dumps({
                "phase": "debug",
                "strategy": "Prove the failure before fixing it",
                "tactical_guard": "Do not refactor unrelated code",
                "iteration": 2,
            }))
            _write_file(WATCHER_FILE, json.dumps({
                "match": True,
                "status": "MEASURED",
                "checked_at": "2026-07-01T00:00:00Z",
            }))
            os.environ["SIMPLICIO_AGENT_PROFILE"] = "selftest"
            os.environ.pop("HERMES_PROFILE", None)

            cmd_capture()
            cmd_summary()
            cmd_handoff()

            journal_files = sorted(os.listdir(JOURNAL_DIR))
            assert journal_files, "capture did not create wiki journal entry"
            summary = _read_file(SUMMARY_FILE)
            handoff = _read_file(HANDOFF_FILE)
            assert "Current phase" in summary, "summary missing phase section"
            assert "debug" in summary, "summary missing phase value"
            assert "Last distinct actions attempted" in handoff, "handoff missing anti-oscillation section"
            assert "tighten watcher gate" in handoff, "handoff missing recent action"

            print("cross_agent_wiki selftest: PASS")
    finally:
        _set_repo(origin)
        if prior_env is None:
            os.environ.pop("SIMPLICIO_AGENT_PROFILE", None)
        else:
            os.environ["SIMPLICIO_AGENT_PROFILE"] = prior_env
        if prior_legacy_env is None:
            os.environ.pop("HERMES_PROFILE", None)
        else:
            os.environ["HERMES_PROFILE"] = prior_legacy_env


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/cross_agent_wiki.py capture|summary|handoff|status|selftest")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "capture":
        cmd_capture()
    elif cmd == "summary":
        cmd_summary()
    elif cmd == "handoff":
        cmd_handoff()
    elif cmd == "status":
        cmd_status()
    elif cmd == "selftest":
        cmd_selftest()
    else:
        print("UNVERIFIED|unknown command: %s" % cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""simplicio-loop — pre-commit hook: auto-sync plugin/ and _bundle/ from source (#98).

Triggered by git pre-commit. Detects staged changes in the monitored source paths
(defined in mirror_manifest.py as the single source of truth) and runs BOTH
`sync_plugin.py` (writes plugin/) and `sync_bundle.py` (writes simplicio_loop/_bundle/)
automatically, adding the regenerated files to the same commit.

Fail-open, per syncer: if either sync fails (e.g. python3 unavailable in the hook, a bug in one
of the two scripts), the commit proceeds silently regardless — a failure in one syncer does not
skip the other — and `python3 scripts/check.py` (via `scripts/claims_audit.py`) catches the
resulting drift as a backstop.

Install (project-local; git hooks are per-repo, so this is a no-op for a --global install):
    # Via installer:
    bash scripts/install.sh <runtime>            # wires this hook into .git/hooks/pre-commit

    # Manual:
    cp hooks/pre-commit.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Verify: `python3 scripts/doctor.py` reports it under the RECOMMENDED tier (a missing hook never
fails the gate — claims_audit.py still catches drift on the next check/CI run).

Refs: #98 (auto-sync), #74 (mirror_manifest.py single source of truth).
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# Watched source directories — the SINGLE source of truth is mirror_manifest.py's
# WATCHED_SOURCE_DIRS (#98). This hook does not hard-code its own copy of that list; if the
# import fails (e.g. run standalone, python3 unresolvable oddities), fall back to the same
# directories mirror_manifest.py declares today, so the hook still degrades sanely rather than
# silently watching nothing.
try:
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    from mirror_manifest import WATCHED_SOURCE_DIRS
except Exception:
    WATCHED_SOURCE_DIRS = [os.path.join(".claude", "skills"), "hooks", "scripts", "tests"]

# The two syncers this hook runs when a watched path is staged — writes plugin/ and
# simplicio_loop/_bundle/ respectively (#98: previously only sync_plugin.py ran here, leaving
# _bundle/ a manually-maintained mirror — see docs/adr/0001-keep-versioned-mirrors-over-build-
# time-vendoring.md "Known gap").
SYNC_SCRIPTS = ["sync_plugin.py", "sync_bundle.py"]
# The mirror output trees to `git add` after a successful (or partially successful) sync.
GENERATED_TREES = ["plugin", os.path.join("simplicio_loop", "_bundle")]


def _monitored_paths():
    """Return set of absolute paths under REPO that are monitored."""
    watched = set()
    for prefix in WATCHED_SOURCE_DIRS:
        full = os.path.join(REPO, prefix)
        if os.path.exists(full):
            # Normalize separators before commonpath on Windows.  A manifest entry
            # may use POSIX-style `/` while git emits `\\`; mixed forms caused the
            # hook to silently miss staged skill changes on Windows.
            watched.add(os.path.abspath(os.path.normpath(full)))
    return watched


def _staged_changes_touch_monitored():
    """Check if any staged file is under a monitored path."""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=REPO, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False  # can't check → don't block (fail-open)

    if r.returncode != 0:
        return False

    for rel_path in r.stdout.splitlines():
        for watched in _monitored_paths():
            abs_path = os.path.abspath(os.path.normpath(os.path.join(REPO, rel_path)))
            if os.path.commonpath([abs_path, watched]) == watched:
                return True
    return False


def _run_sync():
    """Run each SYNC_SCRIPTS entry; returns True only if every one that exists succeeded.

    Fail-open per-script: a failure in one syncer (e.g. sync_bundle.py) doesn't skip the other
    (sync_plugin.py) — each runs independently and any failure is just logged, never raised.
    """
    all_ok = True
    for name in SYNC_SCRIPTS:
        sync_path = os.path.join(REPO, "scripts", name)
        if not os.path.exists(sync_path):
            continue  # nothing to sync for this one
        try:
            r = subprocess.run(
                [sys.executable, sync_path],
                capture_output=True, text=True, cwd=REPO, timeout=60,
            )
            if r.returncode != 0:
                print("[pre-commit] %s warning: %s" % (name, (r.stderr or r.stdout)[:200]))
                all_ok = False
        except (subprocess.TimeoutExpired, OSError) as e:
            print("[pre-commit] %s error (fail-open): %s" % (name, e))
            all_ok = False
    return all_ok


def _stage_generated_files():
    """Stage any files under the regenerated mirror trees (plugin/, simplicio_loop/_bundle/)."""
    for rel in GENERATED_TREES:
        full = os.path.join(REPO, rel)
        if not os.path.exists(full):
            continue
        try:
            subprocess.run(
                ["git", "add", full],
                capture_output=True, cwd=REPO, timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # fail-open


def main():
    if not _staged_changes_touch_monitored():
        return 0  # nothing to sync — pass

    print("[pre-commit] simplicio-loop: source files changed — syncing plugin/ + "
          "simplicio_loop/_bundle/...")
    _run_sync()
    _stage_generated_files()
    return 0  # always exit 0 (fail-open — check.py/claims_audit.py are the backstop)


if __name__ == "__main__":
    sys.exit(main())

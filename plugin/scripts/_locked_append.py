#!/usr/bin/env python3
"""simplicio-loop — locked JSONL append + tolerant-count helpers (issue #127).

Multiple concurrent workers append to the SAME shared JSONL logs — the run journal
(`.simplicio/orchestrator/loop/journal.jsonl`, `scripts/loop_journal.py`), the handoff event log
(`.simplicio/orchestrator/handoffs/events.jsonl`, `scripts/handoff.py`), and (written by the external
`simplicio` runtime, only ever READ here) the savings ledger
(`.simplicio/ledger/savings-events.jsonl`, `hooks/simplicio_watch.py`). Without a lock, two
processes racing an ``open(path, "a").write()`` can interleave partial writes and corrupt a
line — a single torn line silently breaks every downstream reader (the stall detector, the
hierarchical planner, `pr_evidence.py`).

``locked_append_line`` is the ONE place any worker in this repo appends a line to a shared JSONL
log. Underscore-prefixed on purpose: it is an internal library helper, not a worker script — it
has no CLI, is not doc-cited, and is intentionally exempt from the `claims_audit.py` "every
`scripts/*.py` is either doc-cited or selftest-registered" sweep (leading `_` is the existing
convention for that, see `check_commands_run()`'s orphan scan).

Locking: POSIX uses ``fcntl.flock`` on a small sidecar ``<path>.lock`` file; Windows uses
``msvcrt.locking`` on the same sidecar. A sidecar (not the growing data file itself) keeps the
byte-range lock stable regardless of the data file's size. The write is ``flush()`` +
``os.fsync()`` BEFORE the lock is released, so a reader can never observe a half-flushed line.

Acquisition is bounded (default 2000ms) and FAIL-OPEN on timeout: the write is skipped entirely
(never partially written, never written without the lock) and a one-line degrade note goes to
stderr — a stuck/leaked lock must never wedge the caller.

``count_jsonl_lines`` is the matching tolerant-reader half: it counts valid vs. corrupt
(truncated/illegible) lines in a JSONL file without ever raising, for a summary line a reader can
surface instead of silently dropping the bad lines.

Usage (library only, no CLI):
    from _locked_append import locked_append_line, count_jsonl_lines
    ok = locked_append_line("/path/to/journal.jsonl", json.dumps(rec))
    valid, corrupt = count_jsonl_lines("/path/to/journal.jsonl")
"""
import json
import os
import sys
import time

try:
    import fcntl
except ImportError:  # pragma: no cover — Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover — POSIX
    msvcrt = None

DEFAULT_TIMEOUT_MS = 2000
_POLL_INTERVAL_S = 0.02


def _degrade(path, reason):
    """Fail-open degrade note — stderr only, never raises, never blocks the caller."""
    try:
        sys.stderr.write(
            "_locked_append: DEGRADE — skipped write to %s (%s)\n" % (path, reason)
        )
    except Exception:
        pass


def _lock_path(path):
    return path + ".lock"


def _ensure_lock_file(lock_path):
    """Create the sidecar lock file (+ parent dirs) if missing. Windows byte-range locking
    needs at least one byte on disk to lock against."""
    d = os.path.dirname(lock_path)
    if d:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
    if not os.path.exists(lock_path):
        try:
            with open(lock_path, "ab") as f:
                if f.tell() == 0:
                    f.write(b"\0")
                    f.flush()
        except OSError:
            pass


def _acquire_posix(fh, timeout_ms):
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(_POLL_INTERVAL_S)


def _release_posix(fh):
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


def _acquire_windows(fh, timeout_ms):
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while True:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(_POLL_INTERVAL_S)


def _release_windows(fh):
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass


def _append_locked_body(path, text):
    """Write *text* (already newline-terminated) to *path* and fsync before returning."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def locked_append_line(path, line, timeout_ms=DEFAULT_TIMEOUT_MS):
    """Append one line + trailing newline to *path* under an exclusive cross-process lock.

    Returns True on success. FAIL-OPEN on a timed-out (or otherwise unavailable) lock: the write
    is SKIPPED — never attempted partially, never attempted without the lock — a degrade note is
    written to stderr, and False is returned so the caller can decide whether to retry/report.
    """
    lock_path = _lock_path(path)
    _ensure_lock_file(lock_path)
    text = line if line.endswith("\n") else line + "\n"

    if fcntl is not None:
        try:
            with open(lock_path, "a+b") as lockf:
                if not _acquire_posix(lockf, timeout_ms):
                    _degrade(path, "lock acquisition timed out after %dms" % timeout_ms)
                    return False
                try:
                    _append_locked_body(path, text)
                    return True
                finally:
                    _release_posix(lockf)
        except OSError as e:
            _degrade(path, "posix lock error: %s" % e)
            return False
    elif msvcrt is not None:
        try:
            with open(lock_path, "r+b") as lockf:
                if not _acquire_windows(lockf, timeout_ms):
                    _degrade(path, "lock acquisition timed out after %dms" % timeout_ms)
                    return False
                try:
                    _append_locked_body(path, text)
                    return True
                finally:
                    _release_windows(lockf)
        except OSError as e:
            _degrade(path, "windows lock error: %s" % e)
            return False
    else:  # pragma: no cover — no locking primitive on this platform at all
        _degrade(path, "no locking primitive available (fcntl/msvcrt missing) — write skipped")
        return False


def count_jsonl_lines(path):
    """Tolerant JSONL reader: return (valid_count, corrupt_count). Never raises.

    A truncated/illegible line (partial write that slipped past a lock, or a foreign writer that
    doesn't use one) is COUNTED, not silently dropped — callers surface `corrupt_count` in a
    summary line instead of pretending the file is pristine. Missing file -> (0, 0).
    """
    valid = corrupt = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                    valid += 1
                except ValueError:
                    corrupt += 1
    except OSError:
        return 0, 0
    return valid, corrupt

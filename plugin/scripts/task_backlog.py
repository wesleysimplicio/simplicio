#!/usr/bin/env python3
"""simplicio-loop — Phase-0 backlog freeze for body-of-work runs.

Freezes a body-of-work backlog once, lets the loop claim the next item deterministically, and
renders a markdown checklist table that can be embedded in PR evidence. The backlog lives at
`.simplicio/orchestrator/backlog/backlog.jsonl` (override with $SIMPLICIO_BACKLOG_FILE) as one master record
plus one record per item; `task_anchor.py` remains the per-item source of truth for AC receipts.

Verbs:
  init       Freeze the master goal plus backlog items. Items come from --item JSON (repeatable),
             --item-file FILE (JSON array or JSONL of {"id","goal","acs"} objects), or
             --task-file FILE (Markdown task description(s) compiled via task_contract).
             Default lint rejects vague ACs; `--lint` also rejects short ACs (<3 words) unless
             they declare `:: verify: ...`.
  next       Claim the next ready item deterministically and print id, goal and a fencing token.
  done       Mark an item done from the current anchor when the anchor is READY and its goal_fp
             matches the item; copies the anchor receipts into the backlog so PR evidence can still
             show them after the anchor is cleared for the next drain turn.
  skip       Mark an item skipped with a reason.
  block      Mark an item blocked with a reason code.
  fail       Record a failed attempt; distinct failures can escalate to dead-letter.
  transition Apply a compare-and-swap task-state transition with the current lease fence.
  status     Show queue counts, dependency blockers and active leases.
  checklist  Emit the body-of-work table. With no backlog, prints `backlog: none frozen`.
  selftest   Prove linting, claim/done propagation, and table rendering deterministically.

Lock tuning:
  --lock-timeout SECONDS and --lock-retry SECONDS override
  SIMPLICIO_BACKLOG_LOCK_TIMEOUT / SIMPLICIO_BACKLOG_LOCK_RETRY for one command.

Usage:
    python3 scripts/task_backlog.py init --goal "Drain Phase 0" --item-file backlog.json
    python3 scripts/task_backlog.py next
    python3 scripts/task_backlog.py done --item T1
    python3 scripts/task_backlog.py checklist
"""
import json
import os
import sys
import time
import calendar
import hashlib
import tempfile
import uuid
from contextlib import contextmanager
from functools import wraps

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BACKLOG = (os.environ.get("SIMPLICIO_BACKLOG_FILE") or
           os.path.join(REPO, ".simplicio/orchestrator", "backlog", "backlog.jsonl"))

# The Windows CRT lock API can report a transient ``PermissionError`` (and on
# some Python/CRT combinations a plain ``OSError``) while another process
# owns the one-byte lock range.  Keep the retry policy explicit and tunable so
# a busy host does not either spin forever or fail on the first transient
# collision.  CLI flags override these environment defaults per transaction.
_LOCK_TIMEOUT_ENV = "SIMPLICIO_BACKLOG_LOCK_TIMEOUT"
_LOCK_RETRY_ENV = "SIMPLICIO_BACKLOG_LOCK_RETRY"
_DEFAULT_LOCK_TIMEOUT = 30.0
_DEFAULT_LOCK_RETRY = 0.05


class BacklogLockTimeout(TimeoutError):
    """Raised when a backlog transaction cannot acquire its sidecar lock."""


def _lock_seconds(value, default, minimum=0.0):
    """Parse a finite lock duration, falling back safely on bad input."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if number != number or number in (float("inf"), float("-inf")):
        number = float(default)
    return max(float(minimum), number)

if HERE not in sys.path:
    sys.path.insert(0, HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)
try:
    from task_anchor import ANCHOR as ANCHOR_DEFAULT, coverage, goal_fingerprint, lint_criteria
except Exception:  # pragma: no cover
    ANCHOR_DEFAULT = os.path.join(REPO, ".simplicio/orchestrator", "loop", "anchor.json")

    def goal_fingerprint(goal):
        return (goal or "").strip().lower()

    def coverage(criteria):
        total = len(criteria)
        done = sum(1 for c in criteria if c.get("status") == "done")
        return done, total, [c.get("id") for c in criteria if c.get("status") != "done"]

    def lint_criteria(texts, strict=False):
        return []

try:
    from simplicio_loop.task_contract import compile_many
except Exception:  # pragma: no cover
    compile_many = None

try:
    from agent_identity import ensure_identity, identity_matches, lease_identity
except Exception:  # pragma: no cover
    ensure_identity = identity_matches = lease_identity = None


def _emit_progress(step, status, **kw):
    """Fail-open progress-feedback hook (#299) — never raises, never blocks the backlog worker."""
    try:
        import loop_progress
        loop_progress.emit_event(step, status=status, source="task_backlog.py", **kw)
    except Exception:
        pass


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_utc(value):
    try:
        return int(calendar.timegm(time.strptime((value or "").strip(), "%Y-%m-%dT%H:%M:%SZ")))
    except Exception:
        return 0


def _lease_expires(ttl_seconds):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + max(1, ttl_seconds)))


@contextmanager
def _state_lock(path=None, timeout=None, retry=None):
    """Serialize backlog state transitions across processes.

    JSONL remains the portable interchange format, but every command that can
    mutate the graph holds this sidecar lock for its complete read/modify/write
    transaction.  The lock implementation is deliberately stdlib-only so it
    works on Windows (the primary supported host) and POSIX runners alike.
    """
    path = path or BACKLOG
    lock_path = path + ".lock"
    directory = os.path.dirname(lock_path) or "."
    os.makedirs(directory, exist_ok=True)
    timeout = _lock_seconds(
        timeout if timeout is not None else os.environ.get(_LOCK_TIMEOUT_ENV),
        _DEFAULT_LOCK_TIMEOUT,
    )
    retry = _lock_seconds(
        retry if retry is not None else os.environ.get(_LOCK_RETRY_ENV),
        _DEFAULT_LOCK_RETRY,
        minimum=0.001,
    )
    with open(lock_path, "a+b") as stream:
        if os.name == "nt":
            import msvcrt
            # msvcrt.locking requires at least one byte in the locked range.
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            # LK_NBLCK is deliberately used in a bounded loop.  LK_LOCK has
            # implementation-defined retries and can surface WinError 6/50
            # without giving callers a way to bound the wait.
            deadline = time.monotonic() + timeout
            acquired = False
            while True:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except (OSError, IOError) as exc:
                    if time.monotonic() >= deadline:
                        detail = " (%s)" % exc if exc else ""
                        raise BacklogLockTimeout(
                            "timeout acquiring backlog lock after %.3fs%s" %
                            (timeout, detail)
                        )
                    time.sleep(min(retry, max(0.001, deadline - time.monotonic())))
            try:
                yield
            finally:
                if acquired:
                    try:
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    except (OSError, IOError):
                        # Do not mask the command's real exception while
                        # releasing a lock whose handle is already closing.
                        pass
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _transactional(func):
    """Run one CLI command under the cross-process backlog transaction lock."""
    @wraps(func)
    def wrapped(opts):
        try:
            with _state_lock(
                timeout=(opts or {}).get("lock-timeout"),
                retry=(opts or {}).get("lock-retry"),
            ):
                return func(opts)
        except BacklogLockTimeout as exc:
            print("backlog: BLOCKED — %s" % exc)
            sys.exit(12)
    return wrapped


def _bump_revision(master):
    master["revision"] = int(master.get("revision", 0)) + 1
    master["updated_at"] = _now()
    return master["revision"]


def _new_fencing_token(master):
    """Issue a never-reused lease fence while holding the state lock."""
    generation = int(master.get("fence_counter", 0)) + 1
    master["fence_counter"] = generation
    _bump_revision(master)
    return "fence-%d-%s" % (generation, uuid.uuid4().hex)


def _lease_fence(lease):
    lease = lease or {}
    return str(lease.get("fencing_token") or lease.get("fence") or "")


def _record_attempt(item, lease):
    """Append one immutable attempt record when a WorkItem is claimed."""
    attempt_id = "attempt-%s" % uuid.uuid4().hex
    lease["attempt_id"] = attempt_id
    item.setdefault("attempts", []).append({
        "attempt_id": attempt_id,
        "worker": lease.get("worker", ""),
        "identity": dict(lease.get("identity") or {}),
        "fencing_token": _lease_fence(lease),
        "claimed_at": lease.get("claimed_at", ""),
        "status": "active",
    })
    return attempt_id


def _finish_attempt(item, status, **fields):
    """Close the current attempt without rewriting prior attempt history."""
    lease = item.get("lease") or {}
    attempt_id = lease.get("attempt_id")
    if not attempt_id:
        return
    for attempt in reversed(item.get("attempts") or []):
        if attempt.get("attempt_id") == attempt_id:
            attempt["status"] = status
            attempt["finished_at"] = _now()
            attempt.update(fields)
            return


def _lease_matches(item, worker="", fence="", require=False, identity=None):
    """Validate owner/fence credentials and reject expired leases.

    A missing or malformed expiry is fail-closed.  This matters during crash
    recovery: an old worker must not renew or close an item simply because its
    worker id still matches the record.
    """
    worker = (worker or "").strip()
    fence = (fence or "").strip()
    lease = item.get("lease") or {}
    if require and (not worker or not fence):
        return False
    if worker and lease.get("worker") != worker:
        return False
    if fence and _lease_fence(lease) != fence:
        return False
    if identity is not None and not identity_matches(lease.get("identity"), identity):
        return False
    expires_at = str(lease.get("expires_at") or "").strip()
    if not expires_at or _parse_utc(expires_at) <= int(time.time()):
        return False
    return True


def _check_expected_revision(master, opts):
    """Compare the caller's graph revision while holding the state lock."""
    raw = (opts or {}).get("expected-revision")
    if raw is None or raw is True or str(raw).strip() == "":
        return
    try:
        expected = int(raw)
    except (TypeError, ValueError):
        print("backlog: --expected-revision must be an integer")
        sys.exit(2)
    actual = int(master.get("revision", 0))
    if expected != actual:
        print("backlog: BLOCKED — expected revision %d, found %d" % (expected, actual))
        sys.exit(12)


def _lease_error(worker, item_id):
    label = worker or "worker"
    print("backlog: BLOCKED — %s does not hold item %s (stale lease/fence)" % (label, item_id))
    sys.exit(12)


def _load(path=None):
    path = path or BACKLOG
    if not os.path.exists(path):
        return None, []
    master = None
    items = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                obj = json.loads(s)
                if obj.get("kind") == "master":
                    master = obj
                elif obj.get("kind") == "item":
                    items.append(obj)
    except (OSError, ValueError):
        return None, []
    return master, items


def _save(master, items, path=None):
    path = path or BACKLOG
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    # Replace atomically so readers never observe a partially-written JSONL
    # document.  The command-level lock above provides writer serialization.
    fd, tmp_path = tempfile.mkstemp(prefix=".backlog-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(master, ensure_ascii=False) + "\n")
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _load_anchor(path=None):
    path = path or ANCHOR_DEFAULT
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _backlog_root(path=None):
    path = path or BACKLOG
    return os.path.dirname(path)


def _item_run_dir(item, path=None):
    return os.path.join(_backlog_root(path), "items", item.get("id", ""), "run")


def _source_snapshot(paths):
    out = []
    for raw in paths or []:
        ref = str(raw or "").strip()
        if not ref:
            continue
        abs_path = ref if os.path.isabs(ref) else os.path.abspath(ref)
        entry = {"path": ref, "abs_path": abs_path, "exists": os.path.exists(abs_path)}
        if entry["exists"]:
            try:
                st = os.stat(abs_path)
                entry["size"] = int(st.st_size)
                entry["mtime"] = int(st.st_mtime)
                entry["sha1"] = _sha1_file(abs_path)
            except OSError:
                entry["exists"] = False
        out.append(entry)
    return out


def _source_changed(item):
    refs = item.get("source_refs") or []
    if not refs:
        return False, []
    changed = []
    for ref in refs:
        abs_path = ref.get("abs_path") or ref.get("path") or ""
        exists_now = os.path.exists(abs_path)
        if bool(ref.get("exists")) != bool(exists_now):
            changed.append(ref.get("path") or abs_path)
            continue
        if not exists_now:
            continue
        try:
            st = os.stat(abs_path)
            size_now = int(st.st_size)
            mtime_now = int(st.st_mtime)
            sha_now = _sha1_file(abs_path)
        except OSError:
            changed.append(ref.get("path") or abs_path)
            continue
        if (size_now != int(ref.get("size", -1)) or
                mtime_now != int(ref.get("mtime", -1)) or
                sha_now != ref.get("sha1")):
            changed.append(ref.get("path") or abs_path)
    return bool(changed), changed


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _freeze_item_workspace(item, master, path=None):
    run_dir = _item_run_dir(item, path=path)
    loop_dir = os.path.join(run_dir, "loop")
    os.makedirs(loop_dir, exist_ok=True)
    acs = item.get("acs") or []
    criteria = [{"id": "AC%d" % (i + 1), "text": text, "verify": "", "status": "pending",
                 "evidence": "", "verified_at": ""} for i, text in enumerate(acs)]
    anchor = {
        "item": item.get("id"),
        "goal": item.get("goal"),
        "goal_fp": item.get("goal_fp"),
        "frozen_at": item.get("frozen_at") or _now(),
        "criteria": criteria,
    }
    contract = {
        "schema": "simplicio.backlog-item-contract/v1",
        "item_id": item.get("id"),
        "goal": item.get("goal"),
        "goal_fp": item.get("goal_fp"),
        "acs": acs,
        "depends_on": item.get("depends_on") or [],
        "plan_files": item.get("plan_files") or [],
        "source_refs": item.get("source_refs") or [],
        "risks": item.get("risks") or [],
        "required_evidence": item.get("required_evidence") or [],
        "estimate": item.get("estimate"),
        "scheduling_hints": item.get("scheduling_hints") or {},
        "frozen_at": item.get("frozen_at") or _now(),
    }
    manifest = {
        "schema": "simplicio.backlog-item-run/v1",
        "item_id": item.get("id"),
        "goal": item.get("goal"),
        "goal_fp": item.get("goal_fp"),
        "created_at": _now(),
        "master_goal_fp": master.get("goal_fp"),
        "source_refs": item.get("source_refs") or [],
    }
    state = {
        "schema": "simplicio.backlog-item-state/v1",
        "item_id": item.get("id"),
        "phase": "frozen",
        "status": item.get("status"),
        "updated_at": _now(),
    }
    _write_json(os.path.join(run_dir, "manifest.json"), manifest)
    _write_json(os.path.join(run_dir, "state.json"), state)
    _write_json(os.path.join(run_dir, "task-contract.json"), contract)
    _write_json(os.path.join(loop_dir, "anchor.json"), anchor)
    _write_jsonl(os.path.join(loop_dir, "journal.jsonl"), [])
    for name, payload in (
        ("operator-receipt.json", {"schema": "simplicio.operator-receipt/v0", "status": "pending"}),
        ("evidence-receipt.json", {"schema": "simplicio.evidence-receipt/v1", "status": "UNVERIFIED"}),
        ("delivery-receipt.json", {"schema": "simplicio.delivery-receipt/v1", "target": "verified",
                                   "current_state": "planned", "ready": False,
                                   "source_kind": "backlog-item", "source_payload": {}}),
    ):
        _write_json(os.path.join(run_dir, name), payload)
    item["run_dir"] = run_dir


def _invalidate_item_workspace(item, changed_paths):
    run_dir = item.get("run_dir") or _item_run_dir(item)
    for name in ("operator-receipt.json", "evidence-receipt.json", "delivery-receipt.json"):
        target = os.path.join(run_dir, name)
        if os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                pass
    state_path = os.path.join(run_dir, "state.json")
    if os.path.exists(state_path):
        _write_json(state_path, {
            "schema": "simplicio.backlog-item-state/v1",
            "item_id": item.get("id"),
            "phase": "awaiting_refresh",
            "status": "invalidated",
            "updated_at": _now(),
            "changed_paths": changed_paths,
        })
    item["status"] = "invalidated"
    item["lease"] = {}
    item["blocked_reason"] = "source changed after freeze: %s" % ", ".join(changed_paths)
    item["reason_code"] = "source-changed"
    item["invalidated_at"] = _now()


def _escape_cell(text):
    return (text or "").replace("|", r"\|").replace("\n", " ").strip()


def _truncate(text, limit=80):
    text = _escape_cell(text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _criterion_total(item):
    return len(item.get("acs") or [])


def _coverage_for_item(item, anchor=None):
    if item.get("status") == "done":
        return item.get("done_criteria", 0), item.get("total_criteria", _criterion_total(item))
    if anchor and anchor.get("goal_fp") == item.get("goal_fp"):
        done, total, _pending = coverage(anchor.get("criteria", []))
        return done, total
    return 0, _criterion_total(item)


def _evidence_snippet(item, anchor=None):
    if item.get("status") == "skipped":
        return "skipped: %s" % (item.get("skip_reason") or "no reason recorded")
    if item.get("status") == "done":
        snippets = item.get("evidence") or []
        return "; ".join(snippets) if snippets else "done via anchor"
    if anchor and anchor.get("goal_fp") == item.get("goal_fp"):
        ev = [c.get("evidence", "").strip() for c in anchor.get("criteria", [])
              if c.get("status") == "done" and c.get("evidence")]
        return "; ".join(ev[:2]) if ev else "live anchor"
    return "—"


def render_backlog_table(master, items, anchor=None, heading="Body of work (Phase 0 backlog)"):
    """Render the master goal plus one markdown table row per backlog item."""
    lines = ["### %s" % heading]
    if master and master.get("goal"):
        lines += ["", "**Master goal:** %s" % _truncate(master.get("goal"), 160), ""]
    lines += ["| Item | State | Goal | ACs verified | Evidence |",
              "|---|---|---|---|---|"]
    done_items = skipped = 0
    for item in items:
        state = item.get("status", "open")
        if state == "done":
            done_items += 1
        elif state == "skipped":
            skipped += 1
        done, total = _coverage_for_item(item, anchor=anchor)
        cov = "%d/%d" % (done, total)
        lines.append("| %s | %s | %s | %s | %s |" % (
            _escape_cell(item.get("id", "")),
            _escape_cell(state),
            _truncate(item.get("goal", "")),
            _escape_cell(cov),
            _truncate(_evidence_snippet(item, anchor=anchor), 120),
        ))
    lines += ["", "**%d/%d items done · %d skipped.**" % (done_items, len(items), skipped)]
    return "\n".join(lines)


def render_backlog_status(master, items):
    counts = {}
    leases = []
    chains = []
    for item in items:
        state = item.get("status", "unknown")
        counts[state] = counts.get(state, 0) + 1
        lease = item.get("lease") or {}
        if lease.get("worker"):
            leases.append("%s:%s→%s" % (item.get("id"), lease.get("worker"), lease.get("expires_at", "")))
        chain = _dependency_chain(item)
        if chain and item.get("status") == "blocked":
            chains.append(chain)
    lines = [
        "items: %d" % len(items),
        "ready: %d" % counts.get("ready", 0),
        "claimed: %d" % counts.get("claimed", 0),
        "blocked: %d" % counts.get("blocked", 0),
        "invalidated: %d" % counts.get("invalidated", 0),
        "dead-letter: %d" % counts.get("dead-letter", 0),
        "done: %d" % counts.get("done", 0),
    ]
    if master:
        lines.append("empty-polls: %d" % int(master.get("empty_polls", 0)))
    if leases:
        lines.append("leases: " + "; ".join(sorted(leases)))
    if chains:
        lines.append("blocked-chains: " + "; ".join(sorted(chains)))
    return "\n".join(lines)


def _parse_item_obj(obj):
    if not isinstance(obj, dict):
        raise ValueError("item must be a JSON object")
    iid = str(obj.get("id") or "").strip()
    goal = str(obj.get("goal") or "").strip()
    acs = obj.get("acs") or []
    depends_on = obj.get("depends_on") or []
    related = obj.get("related") or []
    blocks = obj.get("blocks") or []
    plan_files = obj.get("plan_files") or []
    source_refs = obj.get("source_refs") or plan_files
    risks = obj.get("risks") or []
    required_evidence = obj.get("required_evidence") or []
    scheduling_hints = obj.get("scheduling_hints") or {}
    if (not iid or not goal or not isinstance(acs, list) or not isinstance(depends_on, list)
            or not isinstance(related, list) or not isinstance(blocks, list)
            or not isinstance(plan_files, list) or not isinstance(source_refs, list)
            or not isinstance(risks, list) or not isinstance(required_evidence, list)
            or not isinstance(scheduling_hints, dict)):
        raise ValueError("item must contain id, goal, acs[] and optional list fields")
    return {"kind": "item", "id": iid, "goal": goal, "goal_fp": goal_fingerprint(goal),
            "acs": [str(a) for a in acs], "status": "ready", "skip_reason": "",
            "blocked_reason": "", "reason_code": "", "evidence": [], "done_criteria": 0,
            "total_criteria": len(acs), "depends_on": [str(x) for x in depends_on],
            "related": [str(x) for x in related], "blocks": [str(x) for x in blocks],
            "priority": int(obj.get("priority", 100)),
            "plan_files": [str(x) for x in plan_files], "lease": {}, "failures": [], "frozen_at": _now(),
            "source_refs": _source_snapshot([str(x) for x in source_refs]),
            "risks": [str(x) for x in risks],
            "required_evidence": [str(x) for x in required_evidence],
            "estimate": obj.get("estimate"),
            "scheduling_hints": dict(scheduling_hints)}


def _dependency_chain(item):
    deps = item.get("depends_on") or []
    if not deps:
        return ""
    return "%s <- %s" % (item.get("id"), ", ".join(deps))


def _contract_goal(contract, index):
    identity = contract.get("identity") or {}
    story = contract.get("story") or {}
    title = (identity.get("title") or identity.get("feature") or identity.get("system") or
             "Task %d" % index).strip()
    desire = (story.get("desire") or "").strip().rstrip(".")
    if desire and desire.lower() not in title.lower():
        return "%s — %s" % (title, desire)
    return title


def _contract_acs(contract):
    acs = []
    for scenario in contract.get("scenarios") or []:
        then_parts = [part.strip() for part in (scenario.get("then") or []) if part.strip()]
        summary = " ".join(then_parts).strip()
        if summary:
            label = " ".join(part for part in [
                (scenario.get("id") or "").strip(),
                (scenario.get("title") or "").strip(),
            ] if part).strip()
            acs.append("%s: %s" % (label or "SCN", summary))
    if acs:
        return acs
    for rule in contract.get("rules") or []:
        text = (rule.get("text") or "").strip()
        if text:
            acs.append("%s: %s" % ((rule.get("id") or "RULE").strip(), text))
    return acs


def _items_from_task_markdown(path):
    if compile_many is None:
        raise ValueError("task contract compiler unavailable")
    if not os.path.exists(path):
        raise ValueError("task file not found: %s" % path)
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    payload = compile_many(raw, source_path=path)
    tasks = payload.get("tasks") or []
    out = []
    for idx, contract in enumerate(tasks, start=1):
        goal = _contract_goal(contract, idx)
        acs = _contract_acs(contract)
        obj = {
            "id": "T%d" % idx,
            "goal": goal,
            "acs": acs,
            "priority": idx * 10,
            "plan_files": [path],
        }
        out.append(_parse_item_obj(obj))
    return out


def _item_index(items):
    return {item.get("id"): item for item in items}


def _detect_cycles(items):
    graph = {item.get("id"): list(item.get("depends_on") or []) for item in items}
    seen = set()
    active = []

    def visit(node):
        if node in active:
            return active[active.index(node):] + [node]
        if node in seen:
            return []
        seen.add(node)
        active.append(node)
        for dep in graph.get(node, []):
            if dep not in graph:
                continue
            cycle = visit(dep)
            if cycle:
                return cycle
        active.pop()
        return []

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def _validate_graph(items):
    """Validate the frozen WorkItem graph before it can become a contract.

    A missing dependency is not a permanently blocked item: it is malformed input
    and must fail at freeze time.  Likewise, an item without acceptance criteria
    cannot be independently verified, so accepting it would create an
    unfinishable card.  Keep the errors deterministic for callers and migrations.
    """
    errors = []
    ids = [str(item.get("id") or "") for item in items]
    known = set(ids)
    for item in items:
        item_id = str(item.get("id") or "")
        acs = item.get("acs") or []
        if not acs:
            errors.append("item %s has no acceptance criteria" % item_id)
        deps = [str(dep) for dep in (item.get("depends_on") or [])]
        unknown = sorted({dep for dep in deps if dep not in known})
        if unknown:
            errors.append("item %s references unknown dependencies: %s" % (item_id, ", ".join(unknown)))
        if len(deps) != len(set(deps)):
            errors.append("item %s has duplicate dependencies" % item_id)
    cycle = _detect_cycles(items)
    if cycle:
        errors.append("dependency cycle detected: %s" % " -> ".join(cycle))
    return errors


def _graph_fingerprint(items):
    """Stable hash of the normalized frozen WorkItem graph (order-independent)."""
    rows = []
    for item in sorted(items, key=lambda row: str(row.get("id") or "")):
        rows.append({
            "id": item.get("id"), "goal_fp": item.get("goal_fp"),
            "acs": list(item.get("acs") or []),
            "depends_on": sorted(str(dep) for dep in (item.get("depends_on") or [])),
            "priority": int(item.get("priority", 100)),
            "source_refs": [ref.get("path") or ref.get("abs_path") for ref in (item.get("source_refs") or [])],
            "required_evidence": list(item.get("required_evidence") or []),
            "risks": list(item.get("risks") or []),
            "scheduling_hints": item.get("scheduling_hints") or {},
        })
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _blocked_by_dependencies(item, items_by_id):
    pending = []
    for dep in item.get("depends_on") or []:
        other = items_by_id.get(dep)
        if not other or other.get("status") != "done":
            pending.append(dep)
    return pending


def _conflicts(a, b):
    left = set(a.get("plan_files") or [])
    right = set(b.get("plan_files") or [])
    return bool(left and right and left.intersection(right))


def _refresh_ready_states(items):
    items_by_id = _item_index(items)
    now_ts = int(time.time())
    for item in items:
        if item.get("status") in ("done", "skipped", "cancelled", "failed", "dead-letter"):
            continue
        changed, changed_paths = _source_changed(item)
        if changed:
            _invalidate_item_workspace(item, changed_paths)
            continue
        lease = item.get("lease") or {}
        lease_expires = _parse_utc(lease.get("expires_at"))
        if item.get("status") in ("claimed", "running", "verification", "delivery"):
            if not lease.get("worker"):
                item["status"] = "ready"
            elif lease_expires and lease_expires <= now_ts:
                item["status"] = "ready"
                item["lease"] = {}
        pending = _blocked_by_dependencies(item, items_by_id)
        if pending:
            item["status"] = "blocked"
            item["blocked_reason"] = "waiting on dependencies: %s" % ", ".join(pending)
            item["reason_code"] = "dependency-pending"
        elif item.get("status") == "blocked" and item.get("reason_code") == "dependency-pending":
            item["status"] = "ready"
            item["blocked_reason"] = ""
            item["reason_code"] = ""
        elif item.get("status") in ("open", "invalidated") and item.get("reason_code") != "source-changed":
            item["status"] = "ready"


def _pick_next_ready(items):
    _refresh_ready_states(items)
    ready = [item for item in items if item.get("status") == "ready"]
    ready.sort(key=lambda item: (int(item.get("priority", 100)), item.get("id", "")))
    claimed = [item for item in items if item.get("status") in ("claimed", "running", "verification", "delivery")]
    for candidate in ready:
        if any(_conflicts(candidate, other) for other in claimed):
            continue
        return candidate
    return None


def _collect_items(opts):
    raw_items = []
    one = opts.get("item")
    if isinstance(one, list):
        raw_items.extend(one)
    elif isinstance(one, str):
        raw_items.append(one)
    item_file = opts.get("item-file")
    if isinstance(item_file, str) and os.path.exists(item_file):
        with open(item_file, encoding="utf-8", errors="replace") as f:
            blob = f.read().strip()
        if blob:
            if blob[0] == "[":
                raw_items.extend(json.loads(blob))
            else:
                for line in blob.splitlines():
                    s = line.strip()
                    if s:
                        raw_items.append(json.loads(s))
    task_file = opts.get("task-file")
    task_items = []
    if isinstance(task_file, str):
        task_items.extend(_items_from_task_markdown(task_file))
    out = []
    for raw in raw_items:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        out.append(_parse_item_obj(obj))
    out.extend(task_items)
    return out


@_transactional
def cmd_init(opts):
    goal = (opts.get("goal") or "").strip()
    if not goal:
        print("backlog: refusing to freeze — --goal is required")
        sys.exit(2)
    items = _collect_items(opts)
    if not items:
        print("backlog: refusing to freeze — provide --item JSON or --item-file")
        sys.exit(2)
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        print("backlog: refusing to freeze — duplicate item ids detected")
        sys.exit(2)
    graph_errors = _validate_graph(items)
    if graph_errors:
        for error in graph_errors:
            print("backlog: refusing to freeze — %s" % error)
        sys.exit(2)
    strict = bool(opts.get("lint"))
    for item in items:
        errors = lint_criteria(item.get("acs", []), strict=strict)
        if errors:
            for err in errors:
                print("backlog: item %s — %s" % (item["id"], err))
            sys.exit(2)
    master = {"kind": "master", "schema": "simplicio.backlog/v2",
              "goal": goal, "goal_fp": goal_fingerprint(goal), "frozen_at": _now(),
              "empty_polls": 0, "revision": 0, "fence_counter": 0, "updated_at": _now()}
    master["graph_hash"] = _graph_fingerprint(items)
    master["contract"] = {"name": "simplicio.work-items/v1", "graph_hash": master["graph_hash"]}
    _refresh_ready_states(items)
    backlog_path = os.environ.get("SIMPLICIO_BACKLOG_FILE") or BACKLOG
    rebaseline = os.path.exists(backlog_path)  # re-freeze over an existing backlog (#299 AC6)
    for item in items:
        _freeze_item_workspace(item, master, path=backlog_path)
    _save(master, items, path=backlog_path)
    total_acs = sum(len(item.get("acs", [])) for item in items)
    print("frozen %d item(s)" % len(items))
    _emit_progress("triage", "end",
                  detail="backlog congelado: %d itens, %d ACs, modo drain" % (len(items), total_acs),
                  rebaseline=rebaseline)


@_transactional
def cmd_next(_opts):
    opts = _opts or {}
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        return
    identity_requested = any(opts.get(name) for name in
                             ("agent-id", "runtime", "session-id", "device-id"))
    identity = (ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                                agent_id=opts.get("agent-id"), device_id=opts.get("device-id"))
                if ensure_identity and identity_requested else {})
    worker = (opts.get("worker") or identity.get("agent_id") or "").strip()
    ttl = int(opts.get("lease-ttl") or 900)
    if worker:
        for item in items:
            lease = item.get("lease") or {}
            active_lease = item.get("status") in ("claimed", "running", "verification", "delivery")
            not_expired = (not lease.get("expires_at") or
                           _parse_utc(lease.get("expires_at")) > int(time.time()))
            if (active_lease and not_expired and lease.get("worker") == worker and
                    (not identity or identity_matches(lease.get("identity"), identity))):
                lease["heartbeat_at"] = _now()
                lease["expires_at"] = _lease_expires(ttl)
                item["lease"] = lease
                _bump_revision(master)
                _save(master, items)
                print("%s\t%s\t%s" % (item.get("id"), item.get("goal"), _lease_fence(lease)))
                return
    item = _pick_next_ready(items)
    if item:
        master["empty_polls"] = 0
        item["status"] = "claimed"
        item["claimed_at"] = _now()
        fence = _new_fencing_token(master)
        item["lease"] = {
            "worker": worker or "__anonymous__",
            "claimed_at": item["claimed_at"],
            "heartbeat_at": item["claimed_at"],
            "ttl_seconds": ttl,
            "expires_at": _lease_expires(ttl),
            # Keep both names during the v1/v2 transition; consumers should
            # send either value back on every mutating transition.
            "fencing_token": fence,
            "fence": fence,
            "generation": int(master.get("fence_counter", 0)),
            "identity": lease_identity(identity) if identity and lease_identity else {},
        }
        _record_attempt(item, item["lease"])
        _save(master, items)
        print("%s\t%s\t%s" % (item.get("id"), item.get("goal"), fence))
        _emit_progress("triage", "begin", item=item.get("id"),
                       detail="item claimado: %s (lease %s)" % (
                           (item.get("goal") or "")[:80], item["lease"].get("worker") or "-"))
        return
    _refresh_ready_states(items)
    if master:
        master["empty_polls"] = int(master.get("empty_polls", 0))
    _save(master, items)
    print("backlog: no ready items")


@_transactional
def cmd_done(opts):
    item_id = (opts.get("item") or "").strip()
    if not item_id:
        print("backlog: --item is required")
        sys.exit(2)
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        sys.exit(2)
    _check_expected_revision(master, opts)
    anchor = _load_anchor(opts.get("anchor") if isinstance(opts.get("anchor"), str) else None)
    if not anchor.get("goal_fp"):
        print("backlog: BLOCKED — no anchor set for this item")
        sys.exit(12)
    hit = None
    for item in items:
        if item.get("id") == item_id:
            hit = item
            break
    if not hit:
        print("backlog: no such item %r" % item_id)
        sys.exit(2)
    worker = (opts.get("worker") or "").strip()
    identity = ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                               agent_id=opts.get("agent-id"), device_id=opts.get("device-id")) if opts.get("agent-id") else None
    fence = (opts.get("fence") or opts.get("fencing-token") or "").strip()
    # Closing an item is irreversible at the backlog layer: require both the
    # current owner and its lease fence, and fail closed on an expired lease.
    if not _lease_matches(hit, worker=worker, fence=fence, require=True, identity=identity):
        _lease_error(worker, item_id)
    if hit.get("goal_fp") != anchor.get("goal_fp"):
        print("backlog: BLOCKED — anchor goal does not match item %s" % item_id)
        sys.exit(12)
    done, total, pending = coverage(anchor.get("criteria", []))
    if total == 0 or pending:
        print("backlog: BLOCKED — anchor is not READY for item %s" % item_id)
        sys.exit(12)
    _finish_attempt(hit, "done", evidence_count=len(anchor.get("criteria", [])))
    hit["status"] = "done"
    hit["done_at"] = _now()
    hit["lease"] = {}
    hit["done_criteria"] = done
    hit["total_criteria"] = total
    hit["evidence"] = [c.get("evidence", "").strip() for c in anchor.get("criteria", [])
                       if c.get("status") == "done" and c.get("evidence")]
    _bump_revision(master)
    state_path = os.path.join(hit.get("run_dir") or _item_run_dir(hit), "state.json")
    if os.path.exists(state_path):
        _write_json(state_path, {
            "schema": "simplicio.backlog-item-state/v1",
            "item_id": hit.get("id"),
            "phase": "done",
            "status": "done",
            "updated_at": _now(),
        })
    _save(master, items)
    print("done %s" % item_id)
    _emit_progress("triage", "end", item=item_id, outcome="pass",
                   detail="item done (%d/%d ACs)" % (done, total))


@_transactional
def cmd_skip(opts):
    item_id = (opts.get("item") or "").strip()
    reason = (opts.get("reason") or "").strip()
    worker = (opts.get("worker") or "").strip()
    identity = ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                               agent_id=opts.get("agent-id"), device_id=opts.get("device-id")) if opts.get("agent-id") else None
    fence = (opts.get("fence") or opts.get("fencing-token") or "").strip()
    if not item_id or not reason:
        print("backlog: --item and --reason are required")
        sys.exit(2)
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        sys.exit(2)
    for item in items:
        if item.get("id") == item_id:
            active = item.get("status") in ("claimed", "running", "verification", "delivery")
            if (active and not _lease_matches(item, worker=worker, fence=fence, identity=identity, require=True)) or \
                    (not active and (worker or fence or identity) and not _lease_matches(item, worker=worker, fence=fence, identity=identity)):
                _lease_error(worker, item_id)
            _finish_attempt(item, "skipped", reason=reason)
            item["status"] = "skipped"
            item["skip_reason"] = reason
            item["lease"] = {}
            item["skipped_at"] = _now()
            _bump_revision(master)
            _save(master, items)
            print("skipped %s" % item_id)
            _emit_progress("triage", "skipped", item=item_id, detail=reason)
            return
    print("backlog: no such item %r" % item_id)
    sys.exit(2)


@_transactional
def cmd_block(opts):
    item_id = (opts.get("item") or "").strip()
    reason = (opts.get("reason") or "").strip()
    code = (opts.get("code") or "").strip()
    worker = (opts.get("worker") or "").strip()
    identity = ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                               agent_id=opts.get("agent-id"), device_id=opts.get("device-id")) if opts.get("agent-id") else None
    fence = (opts.get("fence") or opts.get("fencing-token") or "").strip()
    if not item_id or not reason or not code:
        print("backlog: --item, --reason and --code are required")
        sys.exit(2)
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        sys.exit(2)
    for item in items:
        if item.get("id") == item_id:
            active = item.get("status") in ("claimed", "running", "verification", "delivery")
            if (active and not _lease_matches(item, worker=worker, fence=fence, identity=identity, require=True)) or \
                    (not active and (worker or fence or identity) and not _lease_matches(item, worker=worker, fence=fence, identity=identity)):
                _lease_error(worker, item_id)
            _finish_attempt(item, "blocked", reason=reason, reason_code=code)
            item["status"] = "blocked"
            item["blocked_reason"] = reason
            item["reason_code"] = code
            item["lease"] = {}
            item["blocked_at"] = _now()
            _bump_revision(master)
            _save(master, items)
            print("blocked %s" % item_id)
            _emit_progress("triage", "blocked", item=item_id, outcome="blocked",
                           detail="%s (%s)" % (reason, code))
            return
    print("backlog: no such item %r" % item_id)
    sys.exit(2)


@_transactional
def cmd_fail(opts):
    item_id = (opts.get("item") or "").strip()
    reason = (opts.get("reason") or "").strip()
    code = (opts.get("code") or "").strip()
    fingerprint = (opts.get("fingerprint") or "").strip()
    worker = (opts.get("worker") or "").strip()
    identity = ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                               agent_id=opts.get("agent-id"), device_id=opts.get("device-id")) if opts.get("agent-id") else None
    fence = (opts.get("fence") or opts.get("fencing-token") or "").strip()
    max_failures = int(opts.get("max-failures") or 3)
    if not item_id or not reason or not code or not fingerprint:
        print("backlog: --item, --reason, --code and --fingerprint are required")
        sys.exit(2)
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        sys.exit(2)
    for item in items:
        if item.get("id") != item_id:
            continue
        active = item.get("status") in ("claimed", "running", "verification", "delivery")
        if (active and not _lease_matches(item, worker=worker, fence=fence, identity=identity, require=True)) or \
                (not active and (worker or fence or identity) and not _lease_matches(item, worker=worker, fence=fence, identity=identity)):
            _lease_error(worker, item_id)
        _finish_attempt(item, "failed", reason=reason, reason_code=code, fingerprint=fingerprint)
        failures = item.setdefault("failures", [])
        if not any(f.get("fingerprint") == fingerprint for f in failures):
            failures.append({
                "at": _now(),
                "reason": reason,
                "reason_code": code,
                "fingerprint": fingerprint,
            })
        item["lease"] = {}
        if len(failures) >= max_failures:
            item["status"] = "dead-letter"
            item["reason_code"] = "dead-letter"
            item["blocked_reason"] = "distinct failure threshold reached"
            item["dead_letter_at"] = _now()
            _bump_revision(master)
            _save(master, items)
            print("dead-letter %s" % item_id)
            _emit_progress("triage", "blocked", item=item_id, outcome="blocked",
                           detail="dead-letter: %s" % reason)
            return
        item["status"] = "ready"
        item["blocked_reason"] = ""
        item["reason_code"] = code
        item["failed_at"] = _now()
        _bump_revision(master)
        _save(master, items)
        print("failed %s (%d/%d)" % (item_id, len(failures), max_failures))
        _emit_progress("triage", "end", item=item_id, outcome="fail",
                       detail="%s (%d/%d distinct failures)" % (reason, len(failures), max_failures))
        return
    print("backlog: no such item %r" % item_id)
    sys.exit(2)


@_transactional
def cmd_checklist(opts):
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        return
    anchor = _load_anchor(opts.get("anchor") if isinstance(opts.get("anchor"), str) else None)
    _refresh_ready_states(items)
    print(render_backlog_table(master, items, anchor=anchor))


@_transactional
def cmd_status(_opts):
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        return
    _refresh_ready_states(items)
    _save(master, items)
    print(render_backlog_status(master, items))


def _active_workers(items):
    seen = set()
    for item in items:
        if item.get("status") in ("claimed", "running", "verification", "delivery"):
            worker = ((item.get("lease") or {}).get("worker") or "").strip()
            if worker:
                seen.add(worker)
    return len(seen)


@_transactional
def cmd_poll(opts):
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        return
    k = int(opts.get("empty-polls") or 2)
    _refresh_ready_states(items)
    ready = [item for item in items if item.get("status") == "ready"]
    workers = _active_workers(items)
    if ready or workers:
        master["empty_polls"] = 0
        _save(master, items)
        if ready:
            print("ready")
        else:
            print("busy")
        return
    master["empty_polls"] = int(master.get("empty_polls", 0)) + 1
    _save(master, items)
    if int(master.get("empty_polls", 0)) >= max(1, k):
        print("drained")
        return
    print("empty %d/%d" % (int(master.get("empty_polls", 0)), max(1, k)))


@_transactional
def cmd_heartbeat(opts):
    item_id = (opts.get("item") or "").strip()
    identity = ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                               agent_id=opts.get("agent-id"), device_id=opts.get("device-id")) if opts.get("agent-id") else None
    worker = (opts.get("worker") or (identity or {}).get("agent_id") or "").strip()
    fence = (opts.get("fence") or opts.get("fencing-token") or "").strip()
    ttl = int(opts.get("lease-ttl") or 900)
    if not item_id or not worker:
        print("backlog: --item and --worker are required")
        sys.exit(2)
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        sys.exit(2)
    _check_expected_revision(master, opts)
    _refresh_ready_states(items)
    for item in items:
        if item.get("id") != item_id:
            continue
        lease = item.get("lease") or {}
        if (item.get("status") not in ("claimed", "running", "verification", "delivery") or
                not _lease_matches(item, worker=worker, fence=fence, identity=identity)):
            _lease_error(worker, item_id)
        lease["heartbeat_at"] = _now()
        lease["ttl_seconds"] = ttl
        lease["expires_at"] = _lease_expires(ttl)
        item["lease"] = lease
        _bump_revision(master)
        _save(master, items)
        print("heartbeat %s" % item_id)
        return
    print("backlog: no such item %r" % item_id)
    sys.exit(2)


# State transitions accepted by the durable task graph.  Terminal `done` is
# intentionally handled by `done`, which performs the independent anchor/AC
# gate before closing an item.
_TRANSITIONS = {
    "ready": {"claimed", "blocked", "cancelled"},
    "claimed": {"running", "verification", "delivery", "ready", "failed", "blocked", "cancelled"},
    "running": {"verification", "delivery", "ready", "failed", "blocked", "cancelled"},
    "verification": {"delivery", "running", "ready", "failed", "blocked", "cancelled"},
    "delivery": {"verification", "running", "ready", "failed", "blocked", "cancelled"},
    # blocked recovery: infra-dependent blocks (e.g. Orca down) may be lifted once the
    # external precondition is resolved; terminal failures escalate to quarantined.
    "blocked": {"ready", "failed", "quarantined", "cancelled"},
    "failed": {"ready", "dead-letter", "cancelled"},
}


@_transactional
def cmd_transition(opts):
    """Apply one fenced task-state transition as a compare-and-swap."""
    item_id = (opts.get("item") or "").strip()
    target = (opts.get("to") or opts.get("status") or "").strip().lower()
    expected = (opts.get("from") or "").strip().lower()
    identity = ensure_identity(runtime=opts.get("runtime"), session_id=opts.get("session-id"),
                               agent_id=opts.get("agent-id")) if opts.get("agent-id") else None
    worker = (opts.get("worker") or (identity or {}).get("agent_id") or "").strip()
    fence = (opts.get("fence") or opts.get("fencing-token") or "").strip()
    if not item_id or not target:
        print("backlog: --item and --to/--status are required")
        sys.exit(2)
    if target == "done":
        print("backlog: BLOCKED — use done after the verified anchor gate")
        sys.exit(12)
    master, items = _load()
    if not master or not items:
        print("backlog: none frozen")
        sys.exit(2)
    _check_expected_revision(master, opts)
    hit = next((item for item in items if item.get("id") == item_id), None)
    if hit is None:
        print("backlog: no such item %r" % item_id)
        sys.exit(2)
    current = (hit.get("status") or "").lower()
    if expected and current != expected:
        print("backlog: BLOCKED — compare-and-swap expected %s, found %s" % (expected, current))
        sys.exit(12)
    if target not in _TRANSITIONS.get(current, set()):
        print("backlog: BLOCKED — invalid transition %s -> %s" % (current, target))
        sys.exit(12)
    active = {"claimed", "running", "verification", "delivery"}
    # Every transition out of an active lease is fenced.  For compatibility,
    # legacy callers may omit credentials only while transitioning an unleased
    # item; a claimed/running item cannot be mutated anonymously.
    if current in active and not _lease_matches(hit, worker=worker, fence=fence, require=True, identity=identity):
        _lease_error(worker, item_id)
    if target in active and not _lease_matches(hit, worker=worker, fence=fence, require=True, identity=identity):
        _lease_error(worker, item_id)
    hit["status"] = target
    hit["transitioned_at"] = _now()
    if opts.get("reason"):
        hit["blocked_reason"] = str(opts.get("reason"))
    if opts.get("code"):
        hit["reason_code"] = str(opts.get("code"))
    if target not in active:
        hit["lease"] = {}
    _bump_revision(master)
    _save(master, items)
    print("transitioned %s %s -> %s" % (item_id, current, target))


def cmd_selftest(_opts):
    checks = []

    def chk(name, cond):
        checks.append(bool(cond))
        print("  [%s] %s" % ("ok" if cond else "XX", name))

    master = {"kind": "master", "goal": "Drain Phase 0"}
    items = [
        {"kind": "item", "id": "T1", "goal": "Fix pipes | safely", "goal_fp": "fp1",
         "acs": ["One AC"], "status": "done", "evidence": ["shot.png"], "done_criteria": 1,
         "total_criteria": 1, "skip_reason": "", "depends_on": [], "related": [], "blocks": [],
         "priority": 20, "plan_files": []},
        {"kind": "item", "id": "T2", "goal": "Skip me", "goal_fp": "fp2", "acs": ["Another AC"],
         "status": "skipped", "evidence": [], "done_criteria": 0, "total_criteria": 1,
         "skip_reason": "out of scope", "depends_on": ["T1"], "related": [], "blocks": [],
         "priority": 10, "plan_files": []},
    ]
    table = render_backlog_table(master, items, anchor={})
    chk("heading", "Body of work" in table)
    chk("one-row-per-item", table.count("| T") >= 2)
    chk("counts", "**1/2 items done · 1 skipped.**" in table)
    chk("escaping", r"Fix pipes \| safely" in table)
    chk("skip-reason", "out of scope" in table)
    chk("lint.shared_helper", bool(lint_criteria(["works"])))
    chk("cycle.detected", bool(_detect_cycles([
        {"id": "A", "depends_on": ["B"]},
        {"id": "B", "depends_on": ["A"]},
    ])))
    ready = _pick_next_ready([
        {"id": "A", "status": "ready", "priority": 20, "depends_on": [], "plan_files": []},
        {"id": "B", "status": "ready", "priority": 10, "depends_on": [], "plan_files": []},
    ])
    chk("priority.pick", ready and ready.get("id") == "B")
    lease_items = [
        {"id": "A", "status": "claimed", "priority": 20, "depends_on": [], "plan_files": [],
         "lease": {"worker": "w1", "expires_at": "2000-01-01T00:00:00Z"}},
        {"id": "B", "status": "ready", "priority": 10, "depends_on": [], "plan_files": [], "lease": {}},
    ]
    _refresh_ready_states(lease_items)
    chk("stale.claim.released", lease_items[0]["status"] == "ready")
    poll_master = {"kind": "master", "goal": "Drain", "empty_polls": 1}
    chk("status.empty_polls", "empty-polls: 1" in render_backlog_status(poll_master, items))

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    sys.exit(0 if ok else 1)


def _parse(args):
    opts = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                val = args[i + 1]
                if key in opts:
                    if not isinstance(opts[key], list):
                        opts[key] = [opts[key]]
                    opts[key].append(val)
                else:
                    opts[key] = val
                i += 2
            else:
                opts[key] = True
                i += 1
        else:
            i += 1
    return opts


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        sys.exit(2)
    if argv[0] == "--describe-cli":
        print(json.dumps({
            "verbs": ["init", "next", "done", "skip", "block", "fail", "heartbeat", "transition", "status", "poll", "checklist", "selftest"],
            "flags": ["--anchor", "--agent-id", "--code", "--device-id", "--goal", "--help", "--item", "--item-file", "--lint",
                      "--reason", "--task-file", "--worker", "--fence", "--fencing-token", "--from", "--to", "--status", "--expected-revision",
                      "--lease-ttl", "--fingerprint", "--max-failures", "--empty-polls",
                      "--runtime", "--session-id",
                      "--lock-timeout", "--lock-retry"],
        }))
        sys.exit(0)
    sub, opts = argv[0], _parse(argv[1:])
    {"init": cmd_init, "next": cmd_next, "done": cmd_done, "skip": cmd_skip, "block": cmd_block,
     "fail": cmd_fail, "heartbeat": cmd_heartbeat, "transition": cmd_transition, "status": cmd_status, "poll": cmd_poll,
     "checklist": cmd_checklist, "selftest": cmd_selftest}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: init next done skip block fail heartbeat transition status poll checklist "
                               "selftest" % sub), sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""simplicio-loop — run-journal + stall/progress detector (the loop's working memory).

The two highest-leverage upgrades to a loop orchestrator, made runnable. The classic re-feed loop
remembers nothing between turns except the git tree — so it can (a) re-derive the same triage every
turn and (b) OSCILLATE: try X, fail, try X again, forever, until the cap burns. This worker gives
the loop an explicit, durable **attempt memory** and a **stall detector** so it changes strategy or
escalates instead of re-feeding the same goal into the same failure.

It is deterministic and model-free — the fingerprint + stall math never call an LLM, so a resume is
reproducible from the on-disk journal (same discipline as `savings_harness`/`billing_aggregator`).

State: `.simplicio/orchestrator/loop/journal.jsonl` — one append-only record per attempt:
    {"iteration", "action", "hypothesis", "gate": "pass|fail|blocked",
     "fingerprint": "<stable hash of the failure signature>", "note", "ts",
     "execution_state"?, "stage_id"?, "source_artifact"?, "chunk_id"?,
     "validator"?, "decision"?, "retry_count"?, "blocked_reason"?, "next_action"?}

Verbs:
  |  record      Append one attempt. Pass --gate pass|fail|blocked and (on fail) the gate output via
  |              --gate-output FILE or stdin; the failure FINGERPRINT is computed deterministically
  |              (line-numbers / paths / hex / timestamps normalized away) so the SAME failure hashes
  |              the SAME across turns. Optional lineage flags (`--execution-state`, `--stage-id`,
  |              `--source-artifact`, `--chunk-id`, `--validator`, `--decision`, `--retry-count`,
  |              `--blocked-reason`, `--next-action`) make extraction / validation / retry flow
  |              explicit without losing append-only history. Pass `--bh-address R.0` to tag this
  |              attempt with a **Brown-Hilbert port.port.port** delegation tree address so the
  |              `delegation` command can reconstruct the agent hierarchy.
  |              Output is tagged `MEASURED|` on --gate pass, `UNVERIFIED|` on fail/blocked.
    fingerprint Print the stable fingerprint of a failure text (FILE or stdin). Standalone helper.
    stall       Read the journal -> verdict PROGRESS | STALLED. STALLED when the last K consecutive
  |             attempts all failed with the SAME fingerprint (default K=3). Also folds in the
  |             dev-cli's own `.simplicio/events.jsonl` (schema `simplicio.dev-cli-event/v1`,
  |             `--events-root DIR` overrides the repo root) — a repeated `validation_fail` on the
  |             same target streaks like a repeated journal failure; `edit_applied`/`task_complete`
  |             reset the streak. Fail-open: no events file = behavior unchanged (#128).
  |             Prints the recommended
  |             action (switch-strategy | escalate) and the dead-end actions to avoid. Exit 10 when
  |             stalled (for `if:` gating), 0 otherwise — unless --exit-code is omitted (always 0).
  |             Every output line is prefixed `MEASURED|` (concrete fingerprint data) or
  |             `UNVERIFIED|` (recommendations). --format text (default) | json | toon — `toon`
  |             renders the SAME verdict payload as `--json` in TOON (Token-Oriented Object
  |             Notation, github.com/toon-format/toon) for the per-turn prompt re-feed (#92,
  |             mirrors `task_anchor.py check --format toon`). `--json` remains a working alias
  |             for `--format json`.
    suggest     Consult simplicio-learn lessons for strategy recommendations.
  |             Reads `.simplicio/orchestrator/lessons.jsonl` and `.simplicio/orchestrator/patterns.jsonl`,
  |             filters by repo/task-type tags, and emits discouraged strategies (with
  |             lesson citations) and untried strategies. Deterministic and model-free.
  |             Fail-open: if lesson files don't exist, emits empty suggestions.
  |             Output: MEASURED| for concrete lesson data, UNVERIFIED| for recommendations.
    resume      The anti-oscillation read: distinct actions already tried + their outcomes + the
  |             current stall count + the live error fingerprint. Print THIS at the top of each turn
  |             so the loop never retries a known dead-end. Every line tagged MEASURED| or
  |             UNVERIFIED|.
    status      Compact tail of the journal (last N records). Each record line tagged.
    since       Incremental triage: the delta (git diff --stat + working tree) since the last
  |             recorded turn's commit — so a turn reads only what changed, not a full re-scan.
  |             Output tagged UNVERIFIED| (delta is a derived view, not live proof of the change).
    delegation  Print the Brown-Hilbert delegation tree reconstructed from all journal records
  |             that carry a `--bh-address` — shows the sub-agent hierarchy. See `bh_address()`
  |             in this module for the address format.
    selftest    Prove the fingerprint + stall logic deterministically — no files.
  claims-gate Audit a text blob for untagged claims. Reads FILE (or stdin). Every
              line should start with `MEASURED|` or `UNVERIFIED|`; lines without
              a tag are reported. Exit 1 when untagged claims exist, 0 otherwise.
              Use `--check` to verify loop output compliance.

Usage:
    python3 scripts/loop_journal.py record --iteration 3 --action "add retry to fetch" \\
        --hypothesis "timeout is transient" --gate fail --gate-output test.log \\
        --execution-state planned --stage-id validate --validator pytest \\
        --decision retry --retry-count 1 --next-action "split provider adapter"
    python3 scripts/loop_journal.py stall  [--k 3] [--format text|json|toon] [--exit-code]
    python3 scripts/loop_journal.py resume
    python3 scripts/loop_journal.py status [--n 10]
    python3 scripts/loop_journal.py claims-gate --check <FILE>
    python3 scripts/loop_journal.py selftest
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

try:  # Windows consoles default to cp1252 and choke on non-ASCII — force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("SIMPLICIO_REPO") or os.path.dirname(HERE))
LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
JOURNAL = os.environ.get("SIMPLICIO_JOURNAL_FILE") or os.path.join(LOOP_DIR, "journal.jsonl")
DEFAULT_K = 3

# The dev-cli's own structured event log (#128) — `<repo>/.simplicio/events.jsonl`, schema
# `simplicio.dev-cli-event/v1`, written by `simplicio/observability.py:emit_event` in the
# separate `simplicio-cli` pip package. This module does NOT import dev-cli code — it only reads
# the documented JSONL shape, optionally and fail-open, so a repo without the dev-cli installed
# (or with no events recorded yet) behaves exactly as before.
DEV_CLI_EVENTS_SCHEMA = "simplicio.dev-cli-event/v1"
# Event types folded into the attempt fingerprint + stall detector: a target the dev-cli's OWN
# verify loop keeps failing (`validation_fail`) is a stall signal even when the agent never
# called `loop_journal.py record` for those turns; `edit_applied`/`task_complete` count as
# progress and reset the streak the same way a `record --gate pass` would.
DEV_CLI_STALL_EVENTS = frozenset(["validation_fail", "edit_applied", "task_complete"])

if HERE not in sys.path:
    sys.path.insert(0, HERE)
from toon_codec import encode_toon, decode_toon  # noqa: E402 — prompt-facing render only, same pattern as task_anchor.py
from _locked_append import locked_append_line  # noqa: E402 — cross-process safe append (#127)

# Brown-Hilbert port.port.port addressing for the delegation tree.
# Root is "R". Children append their index: bh_address("R", 0) -> "R.0".
# Nested: bh_address("R.0", 3) -> "R.0.3". Supports arbitrary depth.
BH_ROOT = "R"


def bh_address(parent=None, index=0):
    """Generate a Brown-Hilbert port.port.port address for a delegation tree node.

    Root agents (no parent) get ``R``. Every child appends its zero-based
    port number onto the parent address so the delegation path is recoverable
    from the address alone::

        R                  orchestrator / root agent
        R.0                first sub-agent
        R.0.0              first sub-agent of R.0
        R.0.1              second sub-agent of R.0
        R.1                second sub-agent of the root
        R.1.0              first sub-agent of R.1

    Parameters
    ----------
    parent : str or None
        BH address of the parent node.  ``None`` (or omitted) produces the
        root address ``R``.
    index : int
        Zero-based child index.  Ignored when *parent* is ``None``.

    Returns
    -------
    str
        The BH address string.
    """
    if parent is None:
        return BH_ROOT
    return "%s.%d" % (parent, index)


EXECUTION_STATES = (
    "proposed",
    "planned",
    "dry_run",
    "authorized",
    "executed",
    "verified",
    "rejected",
)

# Lines that carry the actual failure signal — we fingerprint THESE, not the whole log.
SIGNAL_RE = re.compile(
    r"(error|fail|failed|assert|assertion|exception|traceback|panic|fatal|"
    r"undefined|not found|cannot|unexpected|✗|✘|×)", re.I)

# Volatile tokens that differ run-to-run for the SAME bug — normalized away so the hash is stable.
_NORMALIZERS = [
    (re.compile(r"0x[0-9a-fA-F]+"), "0xADDR"),                      # pointers/addresses
    (re.compile(r"\b[0-9a-f]{7,40}\b"), "HEX"),                     # sha/uuid-ish
    (re.compile(r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}:\d{2}\S*", re.I), "TS"),  # ISO timestamps
    (re.compile(r"(:|line )\s*\d+(:\d+)?"), r"\1N"),                # file:line:col / "line 42"
    (re.compile(r"[/\\][\w./\\-]+/(\w+\.\w+)"), r"PATH/\1"),        # dir paths, keep basename
    (re.compile(r"0\.\d+s|\d+(\.\d+)?\s*(ms|s|sec|seconds)", re.I), "DUR"),  # durations
    (re.compile(r"\b\d+\b"), "N"),                                  # any remaining bare integer
    (re.compile(r"\s+"), " "),                                      # collapse whitespace
]


def log(msg):
    print("  " + msg)


def _emit_progress(step, status, **kw):
    """Fail-open progress-feedback hook (#300) — in-process (no subprocess startup cost per
    event, AC8), never raises, never changes this worker's own exit code."""
    try:
        import loop_progress
        loop_progress.emit_event(step, status=status, source="loop_journal.py", **kw)
    except Exception:
        pass


def _read_source(spec):
    if spec is None:
        return ""
    if spec == "-" or spec is True:
        return sys.stdin.read()
    try:
        with open(spec, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def fingerprint(text):
    """Stable, model-free hash of a failure's SIGNATURE. Empty text -> '' (no failure)."""
    if not text or not text.strip():
        return ""
    signal = [ln.strip() for ln in text.splitlines() if SIGNAL_RE.search(ln)]
    # fall back to the last few non-empty lines if nothing matched the signal regex
    if not signal:
        signal = [ln.strip() for ln in text.splitlines() if ln.strip()][-5:]
    blob = "\n".join(signal[:20]).lower()
    for rx, repl in _NORMALIZERS:
        blob = rx.sub(repl, blob)
    return hashlib.sha1(blob.strip().encode("utf-8")).hexdigest()[:12]


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _git(args):
    import subprocess
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=REPO, close_fds=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except (FileNotFoundError, OSError):
        return None


def _git_head():
    return _git(["rev-parse", "HEAD"]) or ""


def _load():
    """Return (rows, corrupt_count). A truncated/illegible line (e.g. a torn write from a
    pre-lock era, or a foreign writer) is COUNTED, never silently dropped — callers surface
    `corrupt_count` in their summary output instead of pretending the journal is pristine (#127).
    """
    rows = []
    corrupt = 0
    if not os.path.exists(JOURNAL):
        return rows, corrupt
    with open(JOURNAL, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                corrupt += 1  # one corrupt record must not lose the journal
    return rows, corrupt


def _warn_corrupt(corrupt):
    """Fail-open stderr warning when the journal has corrupt lines — never silent, never fatal."""
    if corrupt:
        log("UNVERIFIED|journal: %d corrupt/truncated line(s) skipped (see stderr)" % corrupt)
        try:
            sys.stderr.write(
                "loop_journal: WARNING — %d corrupt/truncated journal line(s) skipped\n" % corrupt
            )
        except Exception:
            pass


def load_dev_cli_events(root=None):
    """Optional, fail-open, read-only consumption of the dev-cli's own event log (#128).

    Returns (events, corrupt_count) — `events` are the raw `simplicio.dev-cli-event/v1` records
    whose `event` is in DEV_CLI_STALL_EVENTS, oldest-first. `corrupt_count` mirrors `_load()`'s
    tolerant-reader contract (#127): a truncated/illegible line is counted, never silently
    dropped.

    Fail-open in every direction: missing file, unreadable directory, or a record that isn't a
    dict / doesn't carry the expected schema is simply skipped (not counted as corrupt — a
    foreign or future-schema line is not a torn write) — this integration must never make the
    journal/stall detector less reliable than it was before dev-cli events existed.
    """
    path = os.path.join(root or REPO, ".simplicio", "events.jsonl")
    events, corrupt = [], 0
    if not os.path.exists(path):
        return events, corrupt
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    corrupt += 1
                    continue
                if not isinstance(rec, dict) or rec.get("schema") != DEV_CLI_EVENTS_SCHEMA:
                    continue  # not a dev-cli event (old/foreign format) — ignore, not corrupt
                if rec.get("event") in DEV_CLI_STALL_EVENTS:
                    events.append(rec)
    except OSError:
        return [], 0
    return events, corrupt


def _dev_cli_fingerprint(rec):
    """Stable fingerprint for a dev-cli event, reusing the SAME normalized-signature hash as a
    journal failure — same target + same warning signature -> same hash, so a target repeatedly
    failing the dev-cli's own verify loop streaks exactly like a repeated journal failure would.
    """
    payload = rec.get("payload") or {}
    target = str(payload.get("target", "")).strip()
    warnings = payload.get("warnings") or []
    text = "\n".join(["dev-cli validation_fail target=%s" % target] + [str(w) for w in warnings])
    return fingerprint(text)


def _dev_cli_to_attempt(rec):
    """Adapt one dev-cli event into a journal-row-shaped dict `analyze()` consumes directly,
    so the stall/progress math never grows a second code path (#128)."""
    event = rec.get("event", "")
    payload = rec.get("payload") or {}
    gate = "fail" if event == "validation_fail" else "pass"
    return {
        "iteration": payload.get("attempt") or payload.get("attempts") or 0,
        "action": "dev-cli:%s target=%s" % (event, payload.get("target", "?")),
        "gate": gate,
        "fingerprint": _dev_cli_fingerprint(rec) if gate != "pass" else "",
        "note": "",
        "ts": rec.get("ts", ""),
        "source": "dev-cli",
    }


def merge_dev_cli(rows, dev_cli_events):
    """Merge journal rows with dev-cli-derived synthetic attempts, chronologically by `ts` (both
    sides use the same `%Y-%m-%dT%H:%M:%SZ` format, lexically sortable) — so a repeated
    `validation_fail` on one target counts toward the SAME trailing stall streak as a repeated
    journal failure, whichever side recorded it (#128). Stable sort: ties keep journal rows
    before the events appended after them, preserving today's ordering when timestamps repeat.
    """
    if not dev_cli_events:
        return rows
    merged = list(rows) + [_dev_cli_to_attempt(r) for r in dev_cli_events]
    merged.sort(key=lambda r: r.get("ts") or "")
    return merged


def _rows_with_dev_cli(opts):
    """(merged rows, journal corrupt, events corrupt) honoring --events-root; fail-open."""
    rows, corrupt = _load()
    try:
        root = opts.get("events-root")
        events, ev_corrupt = load_dev_cli_events(root if isinstance(root, str) else None)
    except Exception:
        events, ev_corrupt = [], 0
    return merge_dev_cli(rows, events), corrupt, ev_corrupt


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _optional_int(value):
    text = _clean(value)
    if not text:
        return None
    try:
        return max(0, int(text))
    except ValueError:
        return None


def _maybe_put(rec, key, value):
    text = _clean(value)
    if text:
        rec[key] = text


def _build_record(opts, gate_output_text, commit, now):
    gate = opts.get("gate", "fail")
    fp = ""
    if gate != "pass":
        fp = fingerprint(gate_output_text)
    rec = {
        "iteration": int(opts.get("iteration", 0)),
        "action": opts.get("action", ""),
        "hypothesis": opts.get("hypothesis", ""),
        "gate": gate,
        "fingerprint": fp,
        "note": opts.get("note", ""),
        "commit": commit,
        "ts": now,
    }
    _maybe_put(rec, "source_artifact", opts.get("source-artifact"))
    _maybe_put(rec, "chunk_id", opts.get("chunk-id"))
    _maybe_put(rec, "stage_id", opts.get("stage-id"))
    _maybe_put(rec, "validator", opts.get("validator"))
    _maybe_put(rec, "decision", opts.get("decision"))
    _maybe_put(rec, "blocked_reason", opts.get("blocked-reason"))
    _maybe_put(rec, "next_action", opts.get("next-action"))
    _maybe_put(rec, "bh_address", opts.get("bh-address"))
    execution_state = _clean(opts.get("execution-state"))
    if execution_state:
        rec["execution_state"] = execution_state
    retry_count = _optional_int(opts.get("retry-count"))
    if retry_count is not None:
        rec["retry_count"] = retry_count
    return rec


def _lineage_summary(rec):
    bits = []
    if rec.get("execution_state"):
        bits.append("state=%s" % rec["execution_state"])
    if rec.get("stage_id"):
        bits.append("stage=%s" % rec["stage_id"])
    if rec.get("decision"):
        bits.append("decision=%s" % rec["decision"])
    if rec.get("validator"):
        bits.append("validator=%s" % rec["validator"])
    if rec.get("retry_count") is not None:
        bits.append("retry=%s" % rec["retry_count"])
    if rec.get("chunk_id"):
        bits.append("chunk=%s" % rec["chunk_id"])
    if rec.get("source_artifact"):
        bits.append("source=%s" % rec["source_artifact"])
    if rec.get("bh_address"):
        bits.append("BH=%s" % rec["bh_address"])
    return " | ".join(bits)


def _emit_loop_observability(rec, wrote, duration_ms):
    """Record bounded journal-write metrics without affecting loop semantics."""
    try:
        from simplicio_loop.telemetry import TelemetryWriter, metric

        writer = TelemetryWriter.for_component(
            "loop",
            root=REPO,
            project="simplicio-loop",
            operation="journal_record",
        )
        writer.emit(
            correlation={"run_id": "iteration:%s" % rec.get("iteration", 0)},
            metrics={
                "duration_ms": metric(
                    round(float(duration_ms), 4),
                    "milliseconds",
                    "time.perf_counter",
                ),
                "journal_written": metric(
                    1 if wrote else 0,
                    "count",
                    "loop_journal.locked_append",
                ),
            },
            labels={
                "stage": "journal",
                "status": "passed" if wrote else "failed",
                "reason_code": "ok" if wrote else "journal_lock_unavailable",
            },
        )
    except Exception:
        # Observability is explicitly fail-open and never changes the loop verdict.
        pass


def cmd_record(opts):
    os.makedirs(LOOP_DIR, exist_ok=True)
    started = time.perf_counter()
    rec = _build_record(
        opts,
        _read_source(opts.get("gate-output")),
        opts.get("_commit") or _git_head(),  # for incremental triage (`since`)
        opts.get("_now") or _now(),
    )
    tag = "MEASURED|" if rec["gate"] == "pass" else "UNVERIFIED|"
    # locked, cross-process-safe append (#127): flush+fsync before the lock releases, so a
    # concurrent reader never observes a half-written line. FAIL-OPEN on a lock timeout — the
    # write is SKIPPED (never partial, never unlocked), never silently pretended to have happened.
    wrote = locked_append_line(JOURNAL, json.dumps(rec, ensure_ascii=False))
    _emit_loop_observability(
        rec,
        wrote,
        (time.perf_counter() - started) * 1000,
    )
    if not wrote:
        log("UNVERIFIED|record: SKIPPED — could not acquire the journal lock in time")
    log("%srecorded iter=%d gate=%s fp=%s action=%r" % (
        tag, rec["iteration"], rec["gate"], rec["fingerprint"] or "-", rec["action"][:50]))
    lineage = _lineage_summary(rec)
    if lineage:
        log("%slineage: %s" % (tag, lineage))
    if rec.get("blocked_reason"):
        log("%sblocked: %s" % (tag, rec["blocked_reason"][:96]))
    if rec.get("next_action"):
        log("%snext: %s" % (tag, rec["next_action"][:96]))
    print("%srecorded" % tag if wrote else "UNVERIFIED|record-skipped")
    fp_repeat = ""
    if rec["gate"] != "pass" and rec.get("fingerprint"):
        try:
            prior = [json.loads(line) for line in open(JOURNAL, encoding="utf-8", errors="replace")
                    if line.strip()]
            k = sum(1 for r in prior if r.get("fingerprint") == rec.get("fingerprint"))
            if k > 1:
                fp_repeat = "fingerprint repetido (%d)" % k
        except Exception:
            pass
    _emit_progress("journal", "end", iteration=rec.get("iteration"),
                   outcome=rec["gate"] if rec["gate"] in ("pass", "fail", "blocked") else None,
                   detail=fp_repeat or ("gate=%s" % rec["gate"]))


def cmd_fingerprint(opts):
    src = opts.get("file") or opts.get("input") or "-"
    fp = fingerprint(_read_source(src)) or "(no-failure)"
    print("UNVERIFIED|%s" % fp)


def analyze(rows, k=DEFAULT_K):
    """Pure: journal rows -> stall verdict. Deterministic, no I/O.

    STALLED  = the last `k` attempts all failed with the SAME non-empty fingerprint.
    Also surfaces oscillation: actions tried >1x under that same fingerprint (the dead-ends).
    """
    if not rows:
        return {"verdict": "PROGRESS", "stall_count": 0, "fingerprint": "",
                "recommend": "continue", "dead_ends": [], "reason": "empty journal"}

    last = rows[-1]
    fp = last.get("fingerprint", "")
    if last.get("gate") == "pass" or not fp:
        return {"verdict": "PROGRESS", "stall_count": 0, "fingerprint": fp,
                "recommend": "continue", "dead_ends": [],
                "reason": "last attempt passed or had no failure signature"}

    # count the trailing run of consecutive failures sharing THIS fingerprint
    streak = 0
    for r in reversed(rows):
        if r.get("gate") != "pass" and r.get("fingerprint") == fp:
            streak += 1
        else:
            break

    # dead-end actions: actions that appear >1x under this exact fingerprint
    seen, dups = {}, []
    for r in rows:
        if r.get("fingerprint") == fp and r.get("gate") != "pass":
            a = (r.get("action") or "").strip()
            if not a:
                continue
            seen[a] = seen.get(a, 0) + 1
    dups = sorted([a for a, n in seen.items() if n > 1])

    if streak >= k:
        recommend = "escalate" if streak >= k + 1 else "switch-strategy"
        return {"verdict": "STALLED", "stall_count": streak, "fingerprint": fp,
                "recommend": recommend, "dead_ends": dups,
                "reason": "%d consecutive failures with the same fingerprint %s" % (streak, fp)}
    return {"verdict": "PROGRESS", "stall_count": streak, "fingerprint": fp,
            "recommend": "continue", "dead_ends": dups,
            "reason": "failing, but under the stall threshold (%d/%d)" % (streak, k)}


def cmd_stall(opts):
    k = int(opts.get("k", DEFAULT_K))
    rows, corrupt, _ = _rows_with_dev_cli(opts)  # dev-cli events fold into the streak (#128)
    a = analyze(rows, k)
    fmt = (opts.get("format") or ("json" if opts.get("json") else "text")).strip().lower()
    display = dict(a, corrupt_lines=corrupt)  # display-only copy — analyze()'s own contract is untouched
    if fmt == "toon":
        # TOON (Token-Oriented Object Notation, github.com/toon-format/toon): same verdict payload
        # as --format json, rendered leaner for the per-turn prompt re-feed (#92, mirrors
        # task_anchor.py check --format toon, #88/#91). Never changes the on-disk journal itself.
        print(encode_toon(display))
    elif fmt == "json":
        print(json.dumps(display, indent=2))
    else:
        # verdict is MEASURED (concrete fingerprint data from the journal)
        print("MEASURED|%s" % a["verdict"].lower())
        log("MEASURED|%s" % a["reason"])
        if a["verdict"] == "STALLED":
            # the recommendation is UNVERIFIED (it's a derived inference)
            log("UNVERIFIED|recommend: %s — do NOT re-feed the same goal into the same failure" % a["recommend"])
            if a["dead_ends"]:
                log("MEASURED|dead-end actions (already tried, same failure): %s" % "; ".join(a["dead_ends"]))
        _warn_corrupt(corrupt)
    if a["verdict"] == "STALLED":
        _emit_progress("journal", "blocked", outcome="blocked",
                       detail="STALLED: %d falhas com mesmo fingerprint — mudar estratégia" %
                       a["stall_count"])
    if opts.get("exit-code") and a["verdict"] == "STALLED":
        sys.exit(10)


def cmd_resume(opts):
    """The read every turn should START with — what was tried, so we never repeat a dead-end."""
    _emit_progress("triage", "begin", detail="iter %s: triage incremental" %
                   (opts.get("iteration") or "?"))
    rows, corrupt, _ = _rows_with_dev_cli(opts)  # dev-cli events fold into the streak (#128)
    if not rows:
        print("UNVERIFIED|resume: fresh loop — no prior attempts")
        _warn_corrupt(corrupt)
        _emit_progress("triage", "end", outcome="pass", detail="0 tentativas anteriores")
        return
    a = analyze(rows, int(opts.get("k", DEFAULT_K)))
    passed = [r for r in rows if r.get("gate") == "pass"]
    print("MEASURED|resume: %d attempts · last gate=%s · stall=%s/%s · live_fp=%s" % (
        len(rows), rows[-1].get("gate"), a["stall_count"], opts.get("k", DEFAULT_K),
        a["fingerprint"] or "-"))
    log("MEASURED|verdict: %s — recommend: %s" % (a["verdict"], a["recommend"]))
    lineage = _lineage_summary(rows[-1])
    if lineage:
        log("UNVERIFIED|last lineage: %s" % lineage)
    if rows[-1].get("blocked_reason"):
        log("UNVERIFIED|last blocked reason: %s" % rows[-1]["blocked_reason"][:120])
    if rows[-1].get("next_action"):
        log("UNVERIFIED|last next action: %s" % rows[-1]["next_action"][:120])
    # distinct actions tried + their last outcome (anti-oscillation memory)
    last_outcome = {}
    for r in rows:
        act = (r.get("action") or "").strip()
        if act:
            last_outcome[act] = r.get("gate")
    for act, gate in list(last_outcome.items())[-12:]:
        log("MEASURED|tried [%s] %s" % (gate, act[:70]))
    if a["dead_ends"]:
        log("MEASURED|AVOID (dead-ends): %s" % "; ".join(a["dead_ends"]))
    if passed:
        log("MEASURED|resolved fingerprints so far: %d" % len({r.get("fingerprint") for r in passed}))
    _warn_corrupt(corrupt)
    _emit_progress("triage", "end", outcome="pass",
                   detail="%d tentativas distintas, %d dead-ends a evitar" %
                   (len(last_outcome), len(a["dead_ends"])))


def cmd_status(opts):
    rows, corrupt = _load()
    n = int(opts.get("n", 10))
    if not rows:
        print("UNVERIFIED|journal empty")
        _warn_corrupt(corrupt)
        return
    print("MEASURED|journal: %d records (last %d)%s:" % (
        len(rows), min(n, len(rows)),
        " · %d corrupt line(s) skipped" % corrupt if corrupt else ""))
    for r in rows[-n:]:
        suffix = _lineage_summary(r)
        if r.get("next_action"):
            suffix = (suffix + " | " if suffix else "") + "next=%s" % r["next_action"]
        if r.get("blocked_reason"):
            suffix = (suffix + " | " if suffix else "") + "blocked=%s" % r["blocked_reason"]
        tag = "MEASURED|" if r.get("gate") == "pass" else "UNVERIFIED|"
        msg = "%siter=%-3s %-7s fp=%-12s %s" % (
            tag, r.get("iteration"), r.get("gate"), r.get("fingerprint") or "-",
            (r.get("action") or "")[:56])
        if suffix:
            msg += " [" + suffix[:160] + "]"
        log(msg)


def cmd_since(opts):
    """Incremental triage: show ONLY the delta since the last recorded turn, not a full re-scan.

    The last journal record stamped the HEAD commit; `since` diffs that commit -> now plus the
    working-tree changes. A turn reads this instead of re-surveying the whole tree every time.
    """
    rows, corrupt = _load()
    _warn_corrupt(corrupt)
    base = ""
    for r in reversed(rows):
        if r.get("commit"):
            base = r["commit"]
            break
    if not base:
        print("UNVERIFIED|since: no prior commit recorded — full working-tree state:")
        print(_git(["status", "--short"]) or "  (git unavailable)")
        return
    print("UNVERIFIED|since: delta vs last recorded turn (%s):" % base[:12])
    stat = _git(["diff", "--stat", "%s..HEAD" % base])
    if stat:
        for ln in stat.splitlines():
            log("UNVERIFIED|" + ln)
    wt = _git(["status", "--short"])
    if wt:
        log("UNVERIFIED|working tree:")
        for ln in wt.splitlines():
            log("UNVERIFIED|  " + ln)
    if not stat and not wt:
        log("UNVERIFIED|no change since last turn — triage can skip a full re-scan")


def _bh_sort_key(addr):
    """Sort helper for BH addresses like R, R.0, R.0.1, R.1, R.10, ...

    Each segment is compared numerically so R.10 sorts after R.9, not after R.1.
    """
    if not addr:
        return (0,)
    parts = addr.split(".")
    # Root 'R' -> (0,); 'R.0' -> (0, 0); 'R.12' -> (0, 12)
    return tuple(int(p) if p.isdigit() else 0 for p in parts)


def cmd_delegation(opts):
    """Print the Brown-Hilbert delegation tree reconstructed from journal records.

    Every journal record that carries a ``bh_address`` is a node in the delegation
    tree.  This command walks those nodes, builds the tree top-down, and prints
    it in an indented tree view so you can see which sub-agent was responsible
    for which attempt.

    Records **without** a ``bh_address`` are grouped under an ``(unassigned)``
    pseudo-root.
    """
    rows, corrupt = _load()
    _warn_corrupt(corrupt)
    # Collect records that have a BH address
    nodes = {}  # addr -> list of records
    unnamed = []
    for r in rows:
        addr = r.get("bh_address")
        if addr:
            nodes.setdefault(addr, []).append(r)
        else:
            unnamed.append(r)

    out_lines = []

    def _render_tree(prefix, addr, depth=0):
        """Recursively render the subtree rooted at *addr*."""
        indent = "  " * depth
        records = nodes.get(addr, [])
        # Build the tree label
        label_parts = ["[%s]" % addr]
        if records:
            last = records[-1]
            label_parts.append(
                "iter=%s gate=%s fp=%s action=%s"
                % (
                    last.get("iteration", "?"),
                    last.get("gate", "?"),
                    (last.get("fingerprint") or "-")[:8],
                    (last.get("action") or "")[:40],
                )
            )
        out_lines.append("%s%s %s" % (indent, prefix, "  ".join(label_parts)))

        # Find and render children (addr.X where X is integer)
        child_addrs = sorted(
            [a for a in nodes if a.startswith(addr + ".") and a.count(".") == addr.count(".") + 1],
            key=_bh_sort_key,
        )
        for i, child_addr in enumerate(child_addrs):
            branch = "+--" if i == len(child_addrs) - 1 else "|--"
            _render_tree(branch, child_addr, depth + 1)

    # Start from root(s)
    roots = sorted([a for a in nodes if a.count(".") == 0], key=_bh_sort_key)
    if not roots and unnamed:
        # No BH-addressed records at all — just a flat list
        print("UNVERIFIED|delegation tree: no BH-addressed records found")
        print("  UNVERIFIED|use: loop_journal.py record --bh-address <addr> ...")
        print("")
        print("UNVERIFIED|unaddressed records: %d" % len(unnamed))
        return
    for i, root_addr in enumerate(roots):
        prefix = "+--" if i == len(roots) - 1 else "|--"
        _render_tree(prefix, root_addr)

    if unnamed:
        out_lines.append("%s(unassigned) — %d record(s) without BH address" % (
            "  " * (max(1, len(roots))) + "+--", len(unnamed)))

    print("MEASURED|delegation tree (%d nodes):" % len(nodes))
    for ln in out_lines:
        print("MEASURED|  " + ln)
    print("")
    total = len(rows)
    addressed = sum(len(v) for v in nodes.values())
    log("MEASURED|%d/%d records carry BH addresses" % (addressed, total))


def cmd_claims_gate(opts):
    """Audit a text blob for untagged claims.

    Every line should start with `MEASURED|` or `UNVERIFIED|`. Lines that don't
    are reported as untagged claims. Reads FILE (or stdin with --check and no FILE).
    Exit 1 when untagged claims exist, 0 otherwise.
    """
    src = None
    for a in sys.argv[2:]:
        if not a.startswith("--"):
            src = a
            break
    text = _read_source(src)
    if not text.strip():
        print("MEASURED|claims-gate: empty input — nothing to check")
        sys.exit(0)

    lines = text.splitlines()
    untagged = []
    for i, ln in enumerate(lines, 1):
        stripped = ln.strip()
        if not stripped:
            continue
        # Skip lines that are markdown formatting, code fences, or tables
        if stripped.startswith(("```", "|", "---", "**")):
            continue
        # Lines starting with a claims-gate tag are good
        if stripped.startswith(("MEASURED|", "UNVERIFIED|")):
            continue
        untagged.append((i, ln))

    if untagged:
        for line_no, ln in untagged[:20]:
            log("UNVERIFIED|line %d: %s" % (line_no, ln[:80]))
        count = len(untagged)
        print("UNVERIFIED|claims-gate: %d untagged claim(s) found — FAIL" % count)
        sys.exit(1)
    else:
        print("MEASURED|claims-gate: all lines properly tagged — PASS")


def cmd_suggest(opts):
    """Consult simplicio-learn lessons for strategy recommendations.

    Reads `.simplicio/orchestrator/lessons.jsonl` and `.simplicio/orchestrator/patterns.jsonl`,
    filters by repo/task-type tags, and emits discouraged strategies.
    Fail-open: if files don't exist, emits empty suggestions.
    """
    import json as _json

    root = opts.get("root", ".")
    repo_tag = opts.get("repo", "")
    task_type = opts.get("task-type", "")

    lessons_file = Path(root) / ".simplicio/orchestrator" / "lessons.jsonl"
    patterns_file = Path(root) / ".simplicio/orchestrator" / "patterns.jsonl"

    discouraged: list[dict] = []
    strategies_failed: set[str] = set()

    # Read lessons
    if lessons_file.exists():
        try:
            for line in lessons_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                lesson = _json.loads(line)
                strategy = lesson.get("strategy", "").lower().strip()
                if strategy:
                    strategies_failed.add(strategy)
                    discouraged.append({
                        "strategy": strategy,
                        "reason": lesson.get("note", lesson.get("root_cause", "failed in previous run")),
                        "source": f"lessons.jsonl@{lesson.get('fingerprint', '?')[:12]}",
                    })
        except Exception:
            log("UNVERIFIED|suggest: error reading lessons.jsonl — skipping")
    else:
        log("UNVERIFIED|suggest: no lessons.jsonl found — no prior learn data")

    # Read patterns
    if patterns_file.exists():
        try:
            for line in patterns_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                pattern = _json.loads(line)
                if pattern.get("hit_count", 0) > 1:
                    strategy = pattern.get("root_cause", "").lower().strip()
                    if strategy and strategy not in strategies_failed:
                        strategies_failed.add(strategy)
                        discouraged.append({
                            "strategy": strategy,
                            "reason": f"recurring bug pattern (hit_count={pattern['hit_count']})",
                            "source": f"patterns.jsonl@{pattern.get('fingerprint', '?')[:12]}",
                        })
        except Exception:
            log("UNVERIFIED|suggest: error reading patterns.jsonl — skipping")

    # Build output
    if discouraged:
        log("MEASURED|suggest: %d discouraged strategies from prior learning" % len(discouraged))
        for d in discouraged:
            log("MEASURED|  avoid '%s': %s [%s]" % (d["strategy"], d["reason"], d["source"]))
    else:
        log("UNVERIFIED|suggest: no discouraged strategies found — all options available")

    # Emit JSON for programmatic consumption
    if opts.get("format", "").lower() in ("json", "toon"):
        payload = {
            "verdict": "SUGGEST",
            "discouraged": discouraged,
            "count": len(discouraged),
        }
        print(_json.dumps(payload, indent=2) if opts.get("format") == "json" else _json.dumps(payload))


def cmd_selftest(_opts):
    checks = []

    def chk(name, got, want):
        ok = got == want
        checks.append(ok)
        print("  [%s] %-30s got=%s want=%s" % ("ok" if ok else "XX", name, got, want))

    # fingerprint stability: same bug with different line numbers / addresses / timestamps -> same hash
    a = fingerprint("FAILED test_login at app/auth.py:42  (0x7ffd, 2026-06-24T10:00:00Z) 1.3s")
    b = fingerprint("FAILED test_login at app/auth.py:99  (0x1abc, 2026-06-25T11:22:33Z) 0.4s")
    chk("fingerprint.stable", a == b and a != "", True)
    # a DIFFERENT failure -> different hash
    c = fingerprint("AssertionError: expected 3 got 4 in test_math")
    chk("fingerprint.distinct", c != a, True)
    chk("fingerprint.empty", fingerprint(""), "")
    chk("execution_state.enum", "verified" in EXECUTION_STATES, True)

    base = {"hypothesis": "", "note": "", "ts": "t"}
    # 3 identical failures -> STALLED at k=3
    rows = [dict(base, iteration=i, action="retry fetch", gate="fail", fingerprint="deadbeef0001")
            for i in (1, 2, 3)]
    v = analyze(rows, 3)
    chk("stall.detected", v["verdict"], "STALLED")
    chk("stall.count", v["stall_count"], 3)
    chk("stall.deadend", v["dead_ends"], ["retry fetch"])
    # --format toon (#92): the stall verdict must round-trip through TOON exactly like --format
    # json, since it's the same payload rendered leaner for the per-turn prompt re-feed.
    chk("stall.toon_roundtrip", decode_toon(encode_toon(v)) == v, True)
    # a pass on the latest turn -> PROGRESS, streak resets
    rows2 = rows + [dict(base, iteration=4, action="fix root cause", gate="pass", fingerprint="")]
    chk("progress.after_pass", analyze(rows2, 3)["verdict"], "PROGRESS")
    # two fails, different fingerprints -> not stalled (it's moving)
    rows3 = [dict(base, iteration=1, action="a", gate="fail", fingerprint="aaa1"),
             dict(base, iteration=2, action="b", gate="fail", fingerprint="bbb2")]
    chk("progress.moving", analyze(rows3, 3)["verdict"], "PROGRESS")
    # below threshold -> PROGRESS but streak counted
    chk("progress.under_k", analyze(rows[:2], 3)["stall_count"], 2)
    rec = _build_record(
        {
            "iteration": "4",
            "action": "split provider adapter",
            "gate": "blocked",
            "execution-state": "authorized",
            "stage-id": "validate",
            "source-artifact": "audit.md",
            "chunk-id": "audit:2",
            "validator": "pytest",
            "decision": "retry",
            "retry-count": "2",
            "blocked-reason": "missing fixture",
            "next-action": "add fixture",
        },
        "FAILED fixture missing at test_runtime.py:42",
        "abc123",
        "t2",
    )
    chk("record.metadata.stage", rec.get("stage_id"), "validate")
    chk("record.metadata.retry", rec.get("retry_count"), 2)
    chk("record.metadata.summary", "state=authorized" in _lineage_summary(rec), True)

    # claims-gate check
    chk("claims_gate.clean", cmd_claims_gate_selftest_ok(), True)
    chk("claims_gate.dirty", cmd_claims_gate_selftest_fail(), True)

    # dev-cli event adapter (#128): repeated validation_fail on ONE target streaks to STALLED;
    # a task_complete resets it. Pure — no files, the fixture is in-memory records.
    def _ev(event, target, ts, warnings=None):
        return {"schema": DEV_CLI_EVENTS_SCHEMA, "ts": ts, "event": event, "level": "info",
                "payload": {"target": target, "attempt": 1, "warnings": warnings or []}}
    fails = [_ev("validation_fail", "src/app.py", "2026-07-09T00:00:0%dZ" % i,
                 ["tests failed"]) for i in (1, 2, 3)]
    merged = merge_dev_cli([], fails)
    chk("devcli.stall", analyze(merged, 3)["verdict"], "STALLED")
    fp1 = _dev_cli_fingerprint(fails[0])
    chk("devcli.fp_stable", fp1 == _dev_cli_fingerprint(fails[1]) and fp1 != "", True)
    chk("devcli.fp_distinct",
        fp1 != _dev_cli_fingerprint(_ev("validation_fail", "other.py", "t", ["boom"])), True)
    done = merged + [_dev_cli_to_attempt(_ev("task_complete", "src/app.py", "2026-07-09T00:00:04Z"))]
    chk("devcli.reset_on_complete", analyze(done, 3)["verdict"], "PROGRESS")
    chk("devcli.merge_noop", merge_dev_cli(rows, []) == rows, True)

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    sys.exit(0 if ok else 1)


def cmd_claims_gate_selftest_ok():
    """Helper: check that cleanly tagged text passes claims-gate."""
    text = "MEASURED|all tests pass\nUNVERIFIED|hypothesis: race condition\n"
    lines = text.splitlines()
    for ln in lines:
        stripped = ln.strip()
        if stripped and not stripped.startswith(("MEASURED|", "UNVERIFIED|")):
            return False
    return True


def cmd_claims_gate_selftest_fail():
    """Helper: check that untagged text fails claims-gate."""
    text = "some untagged claim\nMEASURED|tagged line\n"
    lines = text.splitlines()
    untagged = 0
    for ln in lines:
        stripped = ln.strip()
        if stripped and not stripped.startswith(("MEASURED|", "UNVERIFIED|")):
            untagged += 1
    return untagged > 0


def _parse(args):
    opts = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[key] = args[i + 1]
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
    # --describe-cli: emit JSON spec of accepted verbs + flags
    if argv[0] == "--describe-cli":
        import json
        print(json.dumps({
            "verbs": ["record", "fingerprint", "stall", "resume", "status", "since",
                      "delegation", "claims-gate", "suggest", "selftest"],
            "flags": ["--iteration", "--action", "--hypothesis", "--gate", "--gate-output",
                      "--note", "--k", "--exit-code", "--execution-state", "--stage-id",
                      "--source-artifact", "--chunk-id", "--validator", "--decision",
                      "--retry-count", "--blocked-reason", "--next-action", "--bh-address",
                      "--json", "--format", "--events-root", "--help"],
        }))
        sys.exit(0)
    sub, opts = argv[0], _parse(argv[1:])
    {"record": cmd_record, "fingerprint": cmd_fingerprint, "stall": cmd_stall,
     "resume": cmd_resume, "status": cmd_status, "since": cmd_since,
     "delegation": cmd_delegation, "claims-gate": cmd_claims_gate,
     "suggest": cmd_suggest,
     "selftest": cmd_selftest}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: record fingerprint stall resume "
                               "status since delegation claims-gate suggest selftest" % sub), sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

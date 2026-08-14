#!/usr/bin/env python3
"""simplicio-loop — progress feedback núcleo (issue #298, EPIC #296).

Deterministic, model-free worker that turns "onde estamos / quanto falta" into a computed fact
instead of a vibe. Every stage of the loop (preflight, survey, triage, decide, operate, watcher,
journal, evidence, refeed_exit) calls `emit` at begin/end; this worker composes the % of
completion from the SAME three sources the loop already trusts — `task_backlog.py` (drain-level
items), `task_anchor.py` (per-item acceptance criteria) and the `progress.jsonl` event trail itself
(turn position) — and renders it for three audiences: a human (`PROGRESS.md`), a transcript
(`render --turn-header`, one line) and a machine (`status --json`).

State (new, `.simplicio/orchestrator/loop/`, override the directory with $SIMPLICIO_PROGRESS_DIR):
    progress.jsonl   append-only events (locked via `_locked_append.py`, same discipline as
                     `loop_journal.py`/`handoff.py`)
    progress.json    derived snapshot (never authoritative — see invariant below)
    PROGRESS.md      human render: table + text progress bar + last 5 transitions

Invariant (AC7): this worker is a PROJECTION, never an AUTHORITY. `status`/`render` always
recompute `pct_*` fresh from the backlog + anchor + event trail; they never read `progress.json*`
to decide a number. Deleting the snapshot before `status` yields the identical %.

Canonical stage machine (frozen here, importable as STEPS/PHASES):
    PHASES = F0 intake, F1 execução, F2 entrega, F3 encerramento
    STEPS  = preflight, survey, triage, decide, operate, watcher, journal, evidence, refeed_exit
    (exactly the turn in SKILL.md § Bound operators: preflight -> survey -> triage -> DECIDE ->
    operate -> watcher-gate -> promise, bracketed by evidence + refeed/exit)

% formula (documented, deterministic, no fabricated numbers):
    pct_item    = acs_verificados / acs_totais           (task_anchor.py status --json equivalent)
    drain       pct_overall = (itens_done + pct_item_do_item_ativo) / itens_totais
                (task_backlog present with >=1 item)
    converge    pct_overall = pct_item * 0.9 + (step_index / steps_total) * 0.1
                (no backlog, but an anchor exists — the step fraction gives visible in-turn motion
                without ever dominating the AC-gated number)
    unknown     Neither backlog nor anchor on disk -> pct_overall is None; every render prints
                `UNVERIFIED|pct=?` — a fabricated number is prohibited.

CLI:
    python3 scripts/loop_progress.py emit --step operate --status begin --item T3 [--detail "..."] \\
        [--outcome pass] [--iteration 7] [--source watcher_verify.py] [--rebaseline]
    python3 scripts/loop_progress.py status [--json]
    python3 scripts/loop_progress.py render [--turn-header|--full] [--cap N]
    python3 scripts/loop_progress.py selftest
"""
import json
import os
import sys
import tempfile
import time

try:  # Windows consoles default to cp1252 and choke on non-ASCII — force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("SIMPLICIO_REPO") or os.path.dirname(HERE))
LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
from _locked_append import locked_append_line  # noqa: E402

PHASES = ["F0", "F1", "F2", "F3"]
PHASE_LABEL = {"F0": "intake", "F1": "execução", "F2": "entrega", "F3": "encerramento"}
STEPS = ["preflight", "survey", "triage", "decide", "operate", "watcher", "journal",
         "evidence", "refeed_exit"]
STEP_PHASE = {
    "preflight": "F0", "survey": "F0",
    "triage": "F1", "decide": "F1", "operate": "F1", "watcher": "F1", "journal": "F1",
    "evidence": "F2",
    "refeed_exit": "F3",
}
STATUSES = ("begin", "end", "blocked", "skipped")
OUTCOMES = ("pass", "fail", "blocked", None)


def log(msg):
    print("  " + msg)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _progress_dir():
    return os.environ.get("SIMPLICIO_PROGRESS_DIR") or LOOP_DIR


def _events_path():
    return os.path.join(_progress_dir(), "progress.jsonl")


def _snapshot_path():
    return os.path.join(_progress_dir(), "progress.json")


def _md_path():
    return os.path.join(_progress_dir(), "PROGRESS.md")


def _anchor_path():
    return os.environ.get("SIMPLICIO_ANCHOR_FILE") or os.path.join(LOOP_DIR, "anchor.json")


def _backlog_path():
    return (os.environ.get("SIMPLICIO_BACKLOG_FILE") or
            os.path.join(REPO, ".simplicio/orchestrator", "backlog", "backlog.jsonl"))


# ----- tolerant source readers (never raise, missing/corrupt -> None) -----------------------------

def read_anchor_state():
    """{'item','done','total'} from the frozen anchor, or None if absent/empty/corrupt."""
    path = _anchor_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    criteria = data.get("criteria") or []
    total = len(criteria)
    if not total:
        return None
    done = sum(1 for c in criteria if isinstance(c, dict) and c.get("status") == "done")
    return {"item": data.get("item"), "done": done, "total": total, "route_mode": data.get("route_mode")}


def read_backlog_state():
    """{'items_total','items_done','active_item'} from the backlog, or None if absent/empty."""
    path = _backlog_path()
    if not os.path.exists(path):
        return None
    items = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except ValueError:
                    continue
                if isinstance(obj, dict) and obj.get("kind") == "item":
                    items.append(obj)
    except OSError:
        return None
    if not items:
        return None
    total = len(items)
    done = sum(1 for it in items if it.get("status") == "done")
    active = None
    for it in items:
        if it.get("status") in ("claimed", "running", "verification", "delivery"):
            active = it.get("id")
            break
    return {"items_total": total, "items_done": done, "active_item": active}


def read_last_event():
    """Last syntactically valid line of progress.jsonl, or {} if absent/empty/all corrupt."""
    path = _events_path()
    if not os.path.exists(path):
        return {}
    last = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    last = obj
    except OSError:
        return {}
    return last


# ----- pure formula (selftest exercises this directly, no I/O) ------------------------------------

def compute_pct(anchor_state, backlog_state, step_index, steps_total):
    """Return (pct_item, pct_overall, mode). mode in {'drain','converge','none'}.

    pct_item is the active item's AC coverage (or None if no anchor). pct_overall is None only
    when NEITHER source is available — the "fabricated number is prohibited" case.
    """
    pct_item = None
    if anchor_state and anchor_state.get("total"):
        pct_item = anchor_state["done"] / float(anchor_state["total"])

    if backlog_state and backlog_state.get("items_total"):
        items_total = backlog_state["items_total"]
        items_done = backlog_state["items_done"]
        active_item = backlog_state.get("active_item")
        anchor_item = (anchor_state or {}).get("item")
        # Only fold the anchor's pct_item into the active-item fraction when the anchor is
        # ACTUALLY anchored to the currently-claimed backlog item. A stale anchor left over from
        # the PREVIOUS item (already counted in items_done) must not double-count its progress —
        # that would make pct_overall regress the moment the next item resets the anchor, which
        # looks like fabricated backsliding instead of the deterministic re-baseline it needs to
        # be tagged as (#304 AC3 — this is exactly the monotonicity bug the e2e test catches).
        anchor_matches_active = (active_item is None and anchor_item is None) or (
            active_item is not None and anchor_item == active_item)
        active_pct = pct_item if (pct_item is not None and anchor_matches_active) else 0.0
        pct_overall = (items_done + active_pct) / float(items_total)
        return pct_item, pct_overall, "drain"

    if pct_item is not None:
        frac_step = (step_index / float(steps_total)) if steps_total else 0.0
        pct_overall = pct_item * 0.9 + frac_step * 0.1
        return pct_item, pct_overall, "converge"

    return None, None, "none"


def step_index_of(step):
    try:
        return STEPS.index(step) + 1
    except ValueError:
        return 0


# ----- snapshot assembly ---------------------------------------------------------------------

def build_snapshot(cap=None):
    """Recompute the full snapshot from sources + the last event (turn position only). Never
    reads progress.json* to decide a number (AC7)."""
    anchor_state = read_anchor_state()
    backlog_state = read_backlog_state()
    last = read_last_event()
    step = last.get("step") or ""
    idx = last.get("step_index") or step_index_of(step)
    steps_total = last.get("steps_total") or len(STEPS)
    phase = last.get("phase") or STEP_PHASE.get(step, "F1")
    iteration = last.get("iteration") or 0
    item_id = (backlog_state or {}).get("active_item") or last.get("item_id") or (anchor_state or {}).get("item")

    pct_item, pct_overall, mode = compute_pct(anchor_state, backlog_state, idx, steps_total)

    return {
        "ts": _now(),
        "phase": phase,
        "phase_label": PHASE_LABEL.get(phase, phase),
        "step": step or None,
        "step_index": idx,
        "steps_total": steps_total,
        "iteration": iteration,
        "cap": cap,
        "item_id": item_id,
        "items_done": (backlog_state or {}).get("items_done"),
        "items_total": (backlog_state or {}).get("items_total"),
        "ac_done": (anchor_state or {}).get("done"),
        "ac_total": (anchor_state or {}).get("total"),
        "pct_item": pct_item,
        "pct_overall": pct_overall,
        "mode": mode,
        "route_mode": (anchor_state or {}).get("route_mode"),
        "last_status": last.get("status"),
        "last_outcome": last.get("outcome"),
        "last_detail": last.get("detail") or "",
        "last_source": last.get("source") or "",
        "run_state": _run_state(last),
    }


def _run_state(last):
    """Derive the F3 (encerramento) run_state purely from the last event (#301 § 4). A run stays
    "running" until a `refeed_exit` event closes it out — never left "in progress" forever."""
    if (last.get("step") or "") != "refeed_exit":
        return "running"
    detail = (last.get("detail") or "").lower()
    if last.get("outcome") == "pass":
        return "done"
    if "cap" in detail:
        return "capped"
    if "handoff" in detail:
        return "handoff"
    if "stop" in detail:
        return "stopped"
    return "blocked"


def _get_output_encoding():
    """Best available output encoding for stdout/stderr (portable, Windows-safe)."""
    for stream in (sys.stdout, sys.stderr):
        enc = getattr(stream, "encoding", None)
        if enc:
            return enc
    try:
        import locale
        return locale.getpreferredencoding(False)
    except Exception:
        return "utf-8"


def _warning_banner(snapshot):
    """DRIFT/STALLED are the two most important turn-level events (#300 AC2/AC3) — they must lead
    the render, not get lost in the transcript. Derived only from the last event's own fields.
    Returns ASCII-safe output when the terminal encoding cannot represent the Unicode warning sign."""
    if snapshot.get("last_status") != "blocked":
        return ""
    detail = snapshot.get("last_detail") or ""
    if "DRIFT" in detail:
        label = "DRIFT"
    elif "STALLED" in detail:
        label = "STALLED"
    else:
        return ""
    symbol = "\u26a0"  # ⚠ WARNING SIGN
    try:
        symbol.encode(_get_output_encoding())
    except (UnicodeEncodeError, LookupError):
        symbol = "!!"
    return f"{symbol} {label} "


def _atomic_write(path, text):
    d = os.path.dirname(path) or "."
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    fd, tmp = tempfile.mkstemp(prefix=".loop_progress-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def write_snapshot(snapshot):
    try:
        _atomic_write(_snapshot_path(), json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    except Exception:
        pass


def _pct_str(pct):
    return "?" if pct is None else "%d%%" % round(pct * 100)


def _tag(pct_overall):
    return "MEASURED" if pct_overall is not None else "UNVERIFIED"

def render_turn_header(snapshot):
    phase = snapshot.get("phase") or "F0"
    idx = snapshot.get("step_index") or 0
    total = snapshot.get("steps_total") or len(STEPS)
    step = snapshot.get("step") or "-"
    item = snapshot.get("item_id") or "-"
    items_done = snapshot.get("items_done")
    items_total = snapshot.get("items_total")
    items_part = ("%s/%s itens" % (items_done, items_total)
                  if items_total is not None else "sem backlog")
    ac_done = snapshot.get("ac_done")
    ac_total = snapshot.get("ac_total")
    ac_part = ("%s/%s" % (ac_done, ac_total) if ac_total is not None else "?/?")
    pct = snapshot.get("pct_overall")
    tag = _tag(pct)
    iteration = snapshot.get("iteration") or 0
    cap = snapshot.get("cap")
    iter_part = ("iter %s/%s" % (iteration, cap)) if cap else ("iter %s" % iteration)
    banner = _warning_banner(snapshot)
    route = snapshot.get("route_mode") or {}
    route_part = ""
    if isinstance(route, dict) and route.get("mode") and route.get("justification"):
        route_part = " \u00b7 mode=%s: %s" % (route["mode"], route["justification"])
    if pct is None:
        return "%s|%spct=?%s" % (tag, banner, route_part)
    return ("%s|%s[simplicio-loop] fase %s \u00b7 etapa %s/%s %s \u00b7 item %s (%s) \u00b7 "
            "ACs %s \u00b7 %s geral \u00b7 %s%s" % (
                tag, banner, phase, idx, total, step, item, items_part, ac_part,
                _pct_str(pct), iter_part, route_part))


def render_full(snapshot):
    pct = snapshot.get("pct_overall")
    tag = _tag(pct)
    lines = []
    lines.append("# simplicio-loop — progress")
    lines.append("")
    lines.append("_atualizado: %s_" % snapshot.get("ts"))
    lines.append("")
    lines.append(render_turn_header(snapshot))
    lines.append("")
    bar_pct = pct if pct is not None else 0.0
    filled = int(round(bar_pct * 20))
    bar = "[" + ("#" * filled) + ("-" * (20 - filled)) + "]"
    lines.append("%s %s" % (bar, _pct_str(pct)))
    lines.append("")
    lines.append("| campo | valor |")
    lines.append("|---|---|")
    lines.append("| fase | %s (%s) |" % (snapshot.get("phase"), snapshot.get("phase_label")))
    lines.append("| etapa | %s/%s %s |" % (
        snapshot.get("step_index"), snapshot.get("steps_total"), snapshot.get("step") or "-"))
    lines.append("| item ativo | %s |" % (snapshot.get("item_id") or "-"))
    lines.append("| itens do backlog | %s/%s |" % (
        snapshot.get("items_done"), snapshot.get("items_total"))
        if snapshot.get("items_total") is not None else "| itens do backlog | sem backlog |")
    lines.append("| ACs do item ativo | %s/%s |" % (
        snapshot.get("ac_done"), snapshot.get("ac_total"))
        if snapshot.get("ac_total") is not None else "| ACs do item ativo | sem anchor |")
    lines.append("| modo de cálculo | %s |" % snapshot.get("mode"))
    lines.append("| run_state | %s |" % snapshot.get("run_state"))
    lines.append("| iteração | %s%s |" % (
        snapshot.get("iteration"), ("/%s" % snapshot["cap"]) if snapshot.get("cap") else ""))
    lines.append("")
    lines.append("## últimas transições")
    for rec in _last_n_events(5):
        lines.append("- %s · %s %s · %s%s" % (
            rec.get("ts", "-"), rec.get("step", "-"), rec.get("status", "-"),
            rec.get("item_id") or "-",
            ("  <%s>" % rec.get("detail")) if rec.get("detail") else ""))
    lines.append("")
    return tag, "\n".join(lines) + "\n"


def _last_n_events(n):
    path = _events_path()
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
    except OSError:
        return []
    return out[-n:]


# ----- library entry point (other workers import this directly, in-process) -----------------

def emit_event(step, status="begin", item=None, detail=None, outcome=None, source=None,
              iteration=None, cap=None, phase=None, rebaseline=False):
    """Append one progress event + refresh the snapshot/PROGRESS.md. Returns the record dict, or
    None if `step`/`status`/`outcome` are invalid (caller decides whether that's fatal).

    This is the SAME code path `emit` (CLI) uses — callers embedding this in-process (task_backlog,
    task_anchor, preflight) should wrap the call in try/except for fail-open behavior (AC7 of #299:
    a progress-instrumentation failure must never fail the underlying worker).
    """
    step = (step or "").strip()
    if step not in STEPS:
        return None
    status = (status or "begin").strip()
    if status not in STATUSES:
        return None
    if isinstance(outcome, str):
        outcome = outcome.strip() or None
    if outcome not in OUTCOMES:
        return None

    idx = step_index_of(step)
    steps_total = len(STEPS)
    resolved_phase = phase or STEP_PHASE.get(step, "F1")
    try:
        iteration = int(iteration if iteration is not None else (read_last_event().get("iteration") or 0))
    except (TypeError, ValueError):
        iteration = 0

    anchor_state = read_anchor_state()
    backlog_state = read_backlog_state()
    pct_item, pct_overall, mode = compute_pct(anchor_state, backlog_state, idx, steps_total)

    rec = {
        "ts": _now(),
        "iteration": iteration,
        "phase": resolved_phase,
        "step": step,
        "step_index": idx,
        "steps_total": steps_total,
        "status": status,
        "outcome": outcome,
        "item_id": item,
        "detail": (detail or "")[:500],
        "source": source or "",
        "pct_item": pct_item,
        "pct_overall": pct_overall,
        "rebaseline": bool(rebaseline),
    }
    locked_append_line(_events_path(), json.dumps(rec, ensure_ascii=False))

    try:
        cap_int = int(cap) if cap else None
    except (TypeError, ValueError):
        cap_int = None
    snapshot = build_snapshot(cap=cap_int)
    write_snapshot(snapshot)
    _, md = render_full(snapshot)
    _atomic_write(_md_path(), md)
    return rec


# ----- CLI verbs -----------------------------------------------------------------------------

def cmd_emit(opts):
    step = (opts.get("step") or "").strip()
    if step not in STEPS:
        print("loop_progress: --step must be one of %s" % ", ".join(STEPS))
        sys.exit(2)
    status = (opts.get("status") or "begin").strip()
    if status not in STATUSES:
        print("loop_progress: --status must be one of %s" % ", ".join(STATUSES))
        sys.exit(2)
    outcome = opts.get("outcome")
    if isinstance(outcome, str):
        outcome = outcome.strip() or None
    if outcome not in OUTCOMES:
        print("loop_progress: --outcome must be one of pass|fail|blocked")
        sys.exit(2)

    cap = None
    try:
        cap = int(opts.get("cap")) if opts.get("cap") else None
    except (TypeError, ValueError):
        cap = None

    rec = emit_event(step, status=status, item=opts.get("item"), detail=opts.get("detail"),
                     outcome=outcome, source=opts.get("source"), iteration=opts.get("iteration"),
                     cap=cap, phase=opts.get("phase"), rebaseline=bool(opts.get("rebaseline")))

    tag = _tag(rec["pct_overall"])
    pct_item, pct_overall, mode = compute_pct(read_anchor_state(), read_backlog_state(),
                                              rec["step_index"], rec["steps_total"])
    print("%s|emitted step=%s status=%s item=%s pct_overall=%s mode=%s" % (
        tag, step, status, rec["item_id"] or "-", _pct_str(rec["pct_overall"]), mode))


def cmd_status(opts):
    cap = None
    try:
        cap = int(opts.get("cap")) if opts.get("cap") else None
    except (TypeError, ValueError):
        cap = None
    snapshot = build_snapshot(cap=cap)
    if opts.get("json"):
        print(json.dumps(snapshot, ensure_ascii=False))
        return
    tag = _tag(snapshot.get("pct_overall"))
    if snapshot.get("pct_overall") is None:
        print("%s|pct=?" % tag)
        log("no backlog and no anchor on disk — nothing to compute yet")
        return
    print("%s|%s" % (tag, render_turn_header(snapshot)[len(tag) + 1:]))
    log("mode=%s · fase=%s · etapa=%s/%s %s" % (
        snapshot.get("mode"), snapshot.get("phase"), snapshot.get("step_index"),
        snapshot.get("steps_total"), snapshot.get("step")))


def cmd_render(opts):
    cap = None
    try:
        cap = int(opts.get("cap")) if opts.get("cap") else None
    except (TypeError, ValueError):
        cap = None
    snapshot = build_snapshot(cap=cap)
    if opts.get("full"):
        tag, md = render_full(snapshot)
        _atomic_write(_md_path(), md)
        print(md)
        return
    print(render_turn_header(snapshot))


def cmd_selftest(_opts):
    checks = []

    def chk(name, got, want):
        ok = (got == want)
        checks.append((name, ok, got, want))

    def close(name, got, want, eps=0.001):
        ok = got is not None and want is not None and abs(got - want) < eps
        checks.append((name, ok, got, want))

    # --- pure formula tests (no I/O) ---
    pct_item, pct_overall, mode = compute_pct(
        {"done": 1, "total": 3}, {"items_total": 5, "items_done": 2}, 5, 9)
    chk("drain.mode", mode, "drain")
    close("drain.pct_item", pct_item, 1 / 3.0)
    close("drain.pct_overall", pct_overall, (2 + 1 / 3.0) / 5)

    pct_item, pct_overall, mode = compute_pct({"done": 3, "total": 3}, None, 9, 9)
    chk("converge.mode", mode, "converge")
    close("converge.pct_overall", pct_overall, 1.0 * 0.9 + 1.0 * 0.1)

    pct_item, pct_overall, mode = compute_pct(None, None, 0, 9)
    chk("none.mode", mode, "none")
    chk("none.pct_overall", pct_overall, None)

    pct_item, pct_overall, mode = compute_pct(None, {"items_total": 5, "items_done": 0}, 1, 9)
    chk("drain.no_anchor.pct_item", pct_item, None)
    close("drain.no_anchor.pct_overall", pct_overall, 0.0)

    chk("step_index.operate", step_index_of("operate"), 5)
    chk("step_index.unknown", step_index_of("nope"), 0)
    chk("steps_total", len(STEPS), 9)

    # --- filesystem round-trip in an isolated temp dir ---
    with tempfile.TemporaryDirectory(prefix="loop_progress_selftest_") as tmp:
        old_env = {k: os.environ.get(k) for k in
                   ("SIMPLICIO_PROGRESS_DIR", "SIMPLICIO_ANCHOR_FILE", "SIMPLICIO_BACKLOG_FILE")}
        try:
            os.environ["SIMPLICIO_PROGRESS_DIR"] = tmp
            os.environ["SIMPLICIO_ANCHOR_FILE"] = os.path.join(tmp, "anchor.json")
            os.environ["SIMPLICIO_BACKLOG_FILE"] = os.path.join(tmp, "backlog.jsonl")

            # AC3 — no sources at all -> UNVERIFIED|pct=?
            snap = build_snapshot()
            chk("AC3.pct_overall_none", snap["pct_overall"], None)
            header = render_turn_header(snap)
            chk("AC3.header_tag", header.startswith("UNVERIFIED|"), True)

            # write a synthetic anchor: 1/3 ACs done
            with open(os.environ["SIMPLICIO_ANCHOR_FILE"], "w", encoding="utf-8") as f:
                json.dump({"item": "T3", "criteria": [
                    {"id": "AC1", "status": "done"},
                    {"id": "AC2", "status": "pending"},
                    {"id": "AC3", "status": "pending"},
                ]}, f)

            # write a synthetic backlog: 5 items, 2 done, T3 running
            with open(os.environ["SIMPLICIO_BACKLOG_FILE"], "w", encoding="utf-8") as f:
                f.write(json.dumps({"kind": "master", "goal": "selftest"}) + "\n")
                for i, st in enumerate(["done", "done", "running", "ready", "ready"], start=1):
                    f.write(json.dumps({"kind": "item", "id": "T%d" % i, "status": st}) + "\n")

            opts = {"step": "operate", "status": "begin", "item": "T3", "detail": "selftest",
                    "outcome": None}
            cmd_emit(opts)
            snap2 = build_snapshot()
            close("AC2.pct_overall", snap2["pct_overall"], (2 + 1 / 3.0) / 5)
            chk("AC2.mode", snap2["mode"], "drain")
            header2 = render_turn_header(snap2)
            chk("AC2.header_tag", header2.startswith("MEASURED|"), True)
            chk("AC2.header_has_phase", "fase F1" in header2, True)

            # AC7 — deleting the snapshot yields the identical % (worker never trusts it)
            os.remove(_snapshot_path())
            snap3 = build_snapshot()
            close("AC7.pct_stable_without_snapshot", snap3["pct_overall"], snap2["pct_overall"])

            # AC4 — corrupted/truncated JSONL still degrades gracefully (exit 0, snapshot rebuilt)
            with open(_events_path(), "a", encoding="utf-8") as f:
                f.write("{not json\n")
            try:
                snap4 = build_snapshot()
                ok4 = True
            except Exception:
                ok4 = False
            chk("AC4.corrupt_jsonl_no_raise", ok4, True)
            close("AC4.pct_after_corruption", snap4["pct_overall"], snap2["pct_overall"])

            # AC5 — concurrent emits don't corrupt the JSONL
            import threading
            errors = []

            def _worker(n):
                try:
                    cmd_emit({"step": "journal", "status": "end", "item": "T%d" % (n % 5 + 1),
                              "outcome": "pass"})
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=_worker, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
            chk("AC5.no_thread_exceptions", errors, [])
            from _locked_append import count_jsonl_lines
            valid, corrupt_after = count_jsonl_lines(_events_path())
            # the earlier deliberate corrupt line is expected; no NEW corruption from concurrency
            chk("AC5.no_new_corruption", corrupt_after <= 1, True)
            chk("AC5.valid_lines_present", valid >= 12, True)

            # AC6-equivalent — every render/status line is tagged
            for line in cmd_status_capture({"json": False}).splitlines():
                if line.strip():
                    chk("claims_gate.tagged:%s" % line[:24],
                        line.startswith(("MEASURED|", "UNVERIFIED|")) or line.startswith("  "),
                        True)
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    failed = [c for c in checks if not c[1]]
    for name, ok, got, want in checks:
        print("  [%s] %s (got=%r want=%r)" % ("PASS" if ok else "FAIL", name, got, want))
    if failed:
        print("UNVERIFIED|loop_progress selftest: %d/%d checks failed" % (len(failed), len(checks)))
        sys.exit(1)
    print("MEASURED|loop_progress selftest: %d/%d checks passed" % (len(checks), len(checks)))


def cmd_status_capture(opts):
    """Helper for selftest: run cmd_status but capture stdout as a string."""
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_status(opts)
    return buf.getvalue()


def _parse(args):
    """Parse --k v / --flag pairs (same convention as task_anchor.py / task_backlog.py)."""
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
    if argv[0] == "--describe-cli":
        print(json.dumps({
            "verbs": ["emit", "status", "render", "selftest"],
            "flags": ["--step", "--status", "--outcome", "--item", "--detail", "--source",
                      "--iteration", "--cap", "--rebaseline", "--json", "--turn-header", "--full"],
            "steps": STEPS, "phases": PHASES,
        }))
        sys.exit(0)
    sub, opts = argv[0], _parse(argv[1:])
    {"emit": cmd_emit, "status": cmd_status, "render": cmd_render,
     "selftest": cmd_selftest}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: emit status render selftest" % sub),
                         sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

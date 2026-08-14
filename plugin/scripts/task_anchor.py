#!/usr/bin/env python3
"""simplicio-loop — task anchor + drift guard (the loop's working memory for SCOPE).

`loop_journal.py` is the loop's memory of WHAT WAS TRIED (anti-oscillation). This is its sibling:
the loop's memory of WHAT THE TASK ACTUALLY IS (anti-DRIFT). A re-feed loop that remembers neither
can wander off the task ("desvio de tarefas") — it re-interprets the goal each turn, drops an
acceptance criterion, or declares "done" while items are still unaddressed. This worker freezes the
task's acceptance criteria at intake and makes three things deterministic and model-free:

  1. **Anchor** — freeze the goal + its acceptance criteria once, so every later turn re-reads the
     SAME contract instead of re-deriving it (and silently narrowing it).
  2. **Drift guard** — flag when the goal being worked this turn no longer matches the frozen goal,
     or when criteria remain unaddressed. The loop must re-anchor explicitly, never drift silently.
  3. **Done gate** — refuse to declare the task done / open a PR while ANY criterion is still
     pending. This is the evidence-gate for SCOPE: "done" requires every AC verified, with a
     receipt (file:line / command output / screenshot path) recorded per criterion.

It also renders the **item-by-item checklist** that `pr_evidence.py` drops into the PR body and the
source-item comment — so the PR shows a line per acceptance criterion with its status + evidence.

Deterministic and model-free: the fingerprint + coverage + drift math never call an LLM, so a resume
is reproducible from the on-disk anchor (same discipline as `loop_journal.py`).

State: `.simplicio/orchestrator/loop/anchor.json` (override with $SIMPLICIO_ANCHOR_FILE):
    {"item", "goal", "goal_fp", "frozen_at",
     "criteria": [{"id","text","verify",
                   "status":"pending|partial|done|waived:no-infra",
                   "evidence","verified_at","waived_reason"}]}

#526 Etapa 3: a criterion can also be `waived:no-infra` — structurally impossible in THIS repo
(e.g. coverage without coverage tooling), per `test_infra_probe.py`'s MEASURED `test_infra` fact.
Requires a `waived_reason`; counts as neither `pending` nor `done`; ALWAYS shown in `gate`'s output
and the checklist. Full contract incl. the 3-artifact "external harness" evidence form:
`references/test-infra-probe.md`.

Verbs:
  set        Freeze the goal + criteria. Criteria from --ac "text" (repeatable), --ac-file FILE
             (one per line; markdown `- [ ]`/`- [x]` lists understood), or stdin. RE-SET is
             idempotent: same goal → existing per-AC status/evidence are PRESERVED (progress is not
             reset). A CHANGED goal is refused unless --force (a silent goal swap IS drift).
             Inline verification can be declared as `--ac "text :: verify: <command or artifact>"`.
             Default lint rejects vague ACs like "works"; `--lint` also rejects short ACs (<3 words)
             unless a `verify:` method is declared. `--delivery FILE` (#526 Etapa 4) freezes a
             client delivery contract (open_pr/push_branch/allow_new_files_in_repo/
             allow_comments_in_code/commit_message_convention — schema:
             references/delivery-contract.md, enforced by scripts/delivery_contract.py) onto the
             SAME anchor; may be combined with --goal/--ac or passed alone to re-freeze onto an
             already-anchored item. Same re-freeze semantics as the goal: a CHANGED contract
             needs --force.
  mark       Record progress on one criterion: --id ACk --status done|partial [--evidence "..."].
             `--status waived:no-infra --reason "..."` excuses a structurally-impossible dimension
             (--reason mandatory).
  status     Print the criteria table + coverage summary (e.g. "3/5 verified").
  checklist  Emit the markdown item-by-item checklist (for the PR body / evidence comment).
  check      Drift verdict for THIS turn: pass --goal "<goal worked now>"; ANCHORED (all verified) |
             INCOMPLETE (criteria pending) | DRIFT (goal changed / no anchor). --exit-code → 11 on DRIFT.
             --format text (default) | json | toon — `toon` renders the SAME verdict payload as
             `--json` in TOON (Token-Oriented Object Notation, github.com/toon-format/toon) instead
             of JSON, for the per-turn re-feed into the LLM's prompt (this is the "check every turn"
             call — quality-safety-delivery.md Step 4a). The on-disk anchor.json itself is unaffected
             — only this prompt-facing render can switch encoding.
  gate       The done/PR-open gate: READY only when every criterion is `done` or `waived:no-infra`
             (zero genuinely `pending`); else BLOCKED with the pending list. Every `waived:no-infra`
             criterion is ALWAYS printed (ready or not) with its reason — a waiver is never
             invisible. --exit-code → 12 when BLOCKED. --json for a machine-readable verdict.
  verify_harness
             Validate the "external harness" evidence form: 3 artifacts — --harness-source PATH,
             --harness-log PATH (named PASS/FAIL cases), --harness-hash PATH (sha256 of the
             replicated snippet) — or --harness-dir DIR (convention filenames). Missing/empty ANY
             of the 3 invalidates the evidence. --snippet PATH additionally requires the hash to
             match that real file's sha256. Prints `harness-ok`/`harness-invalid`; --exit-code →
             12 on invalid. Full contract: references/test-infra-probe.md.
  selftest   Prove freeze/preserve/drift/coverage/gate/checklist/waived/harness deterministically —
             no files (harness validation uses its pure in-memory helper).

Usage:
    python3 scripts/task_anchor.py set --item 12 --goal "Add SSO login" \\
        --ac "Login page renders an SSO button" --ac "Clicking it redirects to the IdP"
    python3 scripts/task_anchor.py mark --id AC1 --status done --evidence "web_verify .simplicio/orchestrator/tee/web/login.png"
    python3 scripts/task_anchor.py mark --id AC2 --status waived:no-infra --reason "no coverage tooling detected (test_infra_probe)"
    python3 scripts/task_anchor.py check --goal "Add SSO login" --exit-code
    python3 scripts/task_anchor.py check --goal "Add SSO login" --format toon
    python3 scripts/task_anchor.py gate --exit-code
    python3 scripts/task_anchor.py set --item 12 --goal "..." --delivery delivery.json --ac "..."
    python3 scripts/task_anchor.py checklist
    python3 scripts/task_anchor.py verify_harness --harness-dir /scratch/harness --snippet src/Calc.cs
"""
import hashlib
import json
import os
import re
import sys

try:  # Windows consoles default to cp1252 and choke on non-ASCII — force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("SIMPLICIO_REPO") or os.path.dirname(HERE))
LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
ANCHOR = os.environ.get("SIMPLICIO_ANCHOR_FILE") or os.path.join(LOOP_DIR, "anchor.json")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
from toon_codec import encode_toon  # noqa: E402 — prompt-facing render only, never the on-disk format

STATUSES = ("pending", "partial", "done", "waived:no-infra")
# external-harness evidence: a run-log line names a case + verdict; a hash artifact is a sha256.
HARNESS_CASE_RE = re.compile(r"^\s*(?P<name>[A-Za-z0-9_./:\\-]+)\s*[:\-]?\s*(?P<result>PASS|FAIL)\b",
                             re.M)
HARNESS_HASH_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
_MD_CHECK = re.compile(r"^\s*[-*]\s*\[(?P<box>[ xX])\]\s*(?P<text>.+?)\s*$")
_MD_BULLET = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
_WS = re.compile(r"\s+")
VERIFY_RE = re.compile(r"^(?P<text>.*?)(?:\s*::\s*verify:\s*(?P<verify>.+))?$", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9À-ÿ]+")
VAGUE_AC_RES = [
    re.compile(r"^(?:it\s+)?works$", re.I),
    re.compile(r"^properly$", re.I),
    re.compile(r"^ok(?:ay)?$", re.I),
    re.compile(r"^done$", re.I),
    re.compile(r"^(?:tudo\s+)?funciona(?:\s+corretamente)?$", re.I),
    re.compile(r"^est[aá]\s+(?:bom|ok)$", re.I),
]


def log(msg):
    print("  " + msg)


def _emit_progress(step, status, **kw):
    """Fail-open progress-feedback hook (#299) — never raises, never blocks the anchor worker."""
    try:
        import loop_progress
        loop_progress.emit_event(step, status=status, source="task_anchor.py", **kw)
    except Exception:
        pass


def _now():
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ----- pure helpers (selftest exercises these directly, no I/O) -----------------------------------

def goal_fingerprint(goal):
    """Stable, model-free hash of a goal's normalized text. Empty -> ''."""
    if not goal or not goal.strip():
        return ""
    norm = _WS.sub(" ", goal.strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def split_verify(raw):
    """Split `text :: verify: ...` into (text, verify). Missing suffix -> ('text', '')."""
    m = VERIFY_RE.match((raw or "").strip())
    text = (m.group("text") if m else (raw or "")).strip()
    verify = (m.group("verify") if m and m.group("verify") else "").strip()
    return text, verify


def parse_criteria(lines):
    """Turn raw lines (plain, or markdown checklist/bullets) into AC texts, in order, deduped."""
    out, seen = [], set()
    for raw in lines:
        if raw is None:
            continue
        m = _MD_CHECK.match(raw) or _MD_BULLET.match(raw)
        text = (m.group("text") if m else raw).strip()
        if not text:
            continue
        bare, _verify = split_verify(text)
        if not bare:
            continue
        key = _WS.sub(" ", bare.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def lint_criteria(texts, strict=False):
    """Return a list of lint errors for AC text. Default rejects vague ACs; strict also rejects
    short ACs (<3 words) unless a verify method is declared."""
    failures = []
    for raw in texts or []:
        text, verify = split_verify(raw)
        norm = text.strip().rstrip(".!?").strip()
        if not norm:
            continue
        if any(rx.match(norm) for rx in VAGUE_AC_RES):
            failures.append("vague acceptance criterion refused: %r" % text)
            continue
        words = WORD_RE.findall(norm)
        if strict and len(words) < 3 and not verify:
            failures.append("strict lint refused short acceptance criterion without verify: %r" %
                            text)
    return failures


def freeze_criteria(texts):
    """Build the criteria list with stable AC ids and a pending status each."""
    out = []
    for i, raw in enumerate(texts):
        text, verify = split_verify(raw)
        out.append({"id": "AC%d" % (i + 1), "text": text, "verify": verify, "status": "pending",
                    "evidence": "", "verified_at": ""})
    return out


def merge_preserving(old, new_texts):
    """Re-freeze to new_texts but PRESERVE status/evidence for criteria whose text is unchanged.

    Progress is keyed by normalized text, not position, so reordering/adding ACs keeps prior work.
    """
    by_text = {_WS.sub(" ", c.get("text", "").lower()): c for c in (old or [])}
    merged = []
    for i, raw in enumerate(new_texts):
        text, verify = split_verify(raw)
        prev = by_text.get(_WS.sub(" ", text.lower()))
        if prev:
            merged.append({"id": "AC%d" % (i + 1), "text": text,
                           "verify": verify or prev.get("verify", ""),
                           "status": prev.get("status", "pending"),
                           "evidence": prev.get("evidence", ""),
                           "verified_at": prev.get("verified_at", "")})
        else:
            merged.append({"id": "AC%d" % (i + 1), "text": text, "verify": verify,
                           "status": "pending",
                           "evidence": "", "verified_at": ""})
    return merged


def coverage(criteria):
    """(done, total, pending_ids). 'done' counts only fully-verified criteria; `waived:no-infra`
    is excused — neither done nor pending (see the `waived()` accessor below)."""
    total = len(criteria)
    done = sum(1 for c in criteria if c.get("status") == "done")
    pending = [c.get("id") for c in criteria
              if c.get("status") not in ("done", "waived:no-infra")]
    return done, total, pending


def waived(criteria):
    """Criteria marked `waived:no-infra` — used by `gate`/`render_checklist` so a waiver is
    ALWAYS surfaced, never silently dropped."""
    return [c for c in (criteria or []) if c.get("status") == "waived:no-infra"]


def drift_verdict(anchor, goal_now):
    """Pure: anchor + the goal being worked now -> verdict dict."""
    if not anchor or not anchor.get("goal_fp"):
        return {"verdict": "DRIFT", "reason": "no task anchor set — freeze the ACs first (set)",
                "pending": [], "coverage": "0/0"}
    fp_now = goal_fingerprint(goal_now) if goal_now is not None else anchor["goal_fp"]
    if goal_now is not None and fp_now != anchor["goal_fp"]:
        return {"verdict": "DRIFT",
                "reason": "the goal worked this turn != the frozen goal (re-anchor with --force "
                          "if the task genuinely changed)",
                "pending": [c.get("id") for c in anchor.get("criteria", [])
                            if c.get("status") != "done"],
                "coverage": "%d/%d" % coverage(anchor.get("criteria", []))[:2]}
    done, total, pending = coverage(anchor.get("criteria", []))
    if total and not pending:
        return {"verdict": "ANCHORED", "reason": "every acceptance criterion verified",
                "pending": [], "coverage": "%d/%d" % (done, total)}
    return {"verdict": "INCOMPLETE",
            "reason": "%d/%d criteria verified — %d still open" % (done, total, len(pending)),
            "pending": pending, "coverage": "%d/%d" % (done, total)}


def render_checklist(criteria, heading="Acceptance criteria (item-by-item)"):
    """Markdown item-by-item checklist. A `waived:no-infra` criterion gets its own marker and
    ALWAYS shows the reason (or "no reason recorded" — never blank)."""
    mark = {"done": "x", "partial": "~", "waived:no-infra": "w", "pending": " "}
    lines = ["### %s" % heading] if heading else []
    if not criteria:
        lines.append("- _(no acceptance criteria were anchored for this item)_")
        return "\n".join(lines)
    for c in criteria:
        status = c.get("status")
        box = mark.get(status, " ")
        line = "- [%s] **%s** %s" % (box, c.get("id"), c.get("text"))
        verify = (c.get("verify") or "").strip()
        if verify:
            line += " — _verify:_ %s" % verify
        if status == "waived:no-infra":
            line += " — _waived:no-infra:_ %s" % (
                (c.get("waived_reason") or "").strip() or "(no reason recorded)")
        else:
            ev = (c.get("evidence") or "").strip()
            if ev:
                line += " — _evidence:_ %s" % ev
            elif status != "done":
                line += " — _pending_"
        lines.append(line)
    done, total, _ = coverage(criteria)
    waived_items = waived(criteria)
    lines.append("")
    suffix = " · %d waived:no-infra" % len(waived_items) if waived_items else ""
    lines.append("**Coverage:** %d/%d criteria verified%s." % (done, total, suffix))
    return "\n".join(lines)


def parse_harness_log(log_text):
    """Pure: extract (name, PASS|FAIL) named cases from a harness run-log's text."""
    return HARNESS_CASE_RE.findall(log_text or "")


def extract_harness_hash(hash_text):
    """Pure: pull the first 64-hex sha256 digest out of a hash artifact's text (lowercased),
    or '' if none is present."""
    m = HARNESS_HASH_RE.search(hash_text or "")
    return m.group(0).lower() if m else ""


def verify_harness_content(source_text, log_text, hash_text, snippet_bytes=None):
    """Pure (in-memory) validation of the "external harness" evidence form: 3 required artifacts —
    (1) the harness's own source, (2) an execution log with >=1 NAMED PASS/FAIL case, (3) a sha256
    hash of the replicated code snippet. Missing/empty ANY of the 3 invalidates the whole evidence
    (never 2-out-of-3). If `snippet_bytes` is given (the real file mirrored), the hash MUST match
    its actual sha256 — proof the harness isn't testing air. Returns (ok, reason, detail)."""
    if not (source_text or "").strip():
        return False, "harness source artifact is missing/empty", {}
    if not (log_text or "").strip():
        return False, "harness log artifact is missing/empty", {}
    if not (hash_text or "").strip():
        return False, "harness hash artifact is missing/empty", {}
    cases = parse_harness_log(log_text)
    if not cases:
        return False, "harness log has no named PASS/FAIL cases", {}
    failed = [name for name, result in cases if result.upper() == "FAIL"]
    claimed_hash = extract_harness_hash(hash_text)
    if not claimed_hash:
        return False, "harness hash artifact does not contain a sha256 hex digest", {}
    detail = {"cases": len(cases), "failed": failed, "hash": claimed_hash}
    if snippet_bytes is not None:
        real_hash = hashlib.sha256(snippet_bytes).hexdigest()
        detail["snippet_hash"] = real_hash
        if real_hash != claimed_hash:
            return False, ("harness hash does not match sha256 of the replicated snippet "
                          "(%s != %s) — the harness does not provably mirror the real diff" %
                          (real_hash, claimed_hash)), detail
    if failed:
        return False, ("harness log records %d FAILED case(s): %s" %
                       (len(failed), ", ".join(failed))), detail
    return True, "%d named case(s), all PASS, hash %s" % (len(cases), claimed_hash), detail


# ----- I/O + commands ----------------------------------------------------------------------------

def _load():
    if not os.path.exists(ANCHOR):
        return {}
    try:
        with open(ANCHOR, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(anchor):
    os.makedirs(os.path.dirname(ANCHOR), exist_ok=True)
    with open(ANCHOR, "w", encoding="utf-8") as f:
        json.dump(anchor, f, ensure_ascii=False, indent=2)


def _collect_ac(opts):
    lines = []
    ac = opts.get("ac")
    if isinstance(ac, list):
        lines += ac
    elif isinstance(ac, str):
        lines.append(ac)
    f = opts.get("ac-file")
    if isinstance(f, str) and os.path.exists(f):
        with open(f, encoding="utf-8", errors="replace") as fh:
            lines += fh.read().splitlines()
    if opts.get("stdin") or (not lines and not sys.stdin.isatty()):
        try:
            lines += sys.stdin.read().splitlines()
        except Exception:
            pass
    return parse_criteria(lines)


def _apply_delivery(anchor, path, force=False):
    """Validate+freeze a `--delivery FILE` onto `anchor` (mutates it), or exit BLOCKED (#526
    Etapa 4). Kept as a thin wrapper so the schema/enforcement logic itself lives in
    `scripts/delivery_contract.py`, not duplicated here."""
    try:
        import delivery_contract as dc
    except Exception as exc:  # pragma: no cover - only if the sibling script goes missing
        print("anchor: BLOCKED — could not load scripts/delivery_contract.py: %s" % exc)
        sys.exit(2)
    try:
        data = dc.load_contract_file(path)
    except ValueError as exc:
        print("anchor: %s" % exc)
        sys.exit(2)
    errors = dc.validate(data)
    if errors:
        for e in errors:
            print("anchor: delivery contract: %s" % e)
        sys.exit(2)
    frozen, err = dc.freeze(anchor.get("delivery"), data, force=force)
    if err:
        print("anchor: BLOCKED — %s" % err)
        sys.exit(12)
    anchor["delivery"] = frozen
    if not frozen.get("allow_new_files_in_repo", True):
        try:
            dc.capture_baseline(".", None)
        except Exception:
            pass  # best-effort — the new-file guard fails CLOSED anyway if no baseline exists
    log("delivery contract frozen: open_pr=%s push_branch=%s allow_new_files_in_repo=%s "
        "allow_comments_in_code=%s commit_message_convention=%r" % (
            frozen["open_pr"], frozen["push_branch"], frozen["allow_new_files_in_repo"],
            frozen["allow_comments_in_code"], frozen["commit_message_convention"]))


def cmd_set(opts):
    delivery_path = opts.get("delivery")
    goal = opts.get("goal") or ""
    existing = _load()

    if not goal.strip():
        # `set --delivery FILE` alone (no --goal): attach/re-freeze the delivery contract onto
        # whatever anchor already exists. Requires an anchor to attach to -- delivery is
        # "congelado junto do anchor", never a standalone artifact (#526 Etapa 4).
        if not delivery_path:
            print("anchor: refusing to freeze — --goal is required")
            sys.exit(2)
        if not existing.get("goal_fp"):
            print("anchor: refusing to freeze a delivery contract — no task anchor set yet. "
                  "Freeze the goal + acceptance criteria first (`set --goal ... --ac ...`), or "
                  "pass --goal/--ac together with --delivery.")
            sys.exit(2)
        anchor = dict(existing)
        _apply_delivery(anchor, delivery_path, force=bool(opts.get("force")))
        _save(anchor)
        print("anchored")
        return

    texts = _collect_ac(opts)
    if not texts:
        print("anchor: refusing to freeze — no acceptance criteria given "
              "(--ac / --ac-file / stdin). An item with no AC is itself a drift risk.")
        sys.exit(2)
    lint_errors = lint_criteria(texts, strict=bool(opts.get("lint")))
    if lint_errors:
        for msg in lint_errors:
            print("anchor: %s" % msg)
        sys.exit(2)
    fp = goal_fingerprint(goal)
    if existing and existing.get("goal_fp") and existing["goal_fp"] != fp and not opts.get("force"):
        print("anchor: BLOCKED — a different goal is already anchored (goal changed). "
              "This is exactly the drift signal. Re-anchor with --force only if the task "
              "genuinely changed.")
        sys.exit(12)
    criteria = (merge_preserving(existing.get("criteria"), texts)
                if existing.get("goal_fp") == fp else freeze_criteria(texts))
    delivery_path = opts.get("delivery")
    anchor = {"item": opts.get("item") or existing.get("item", ""), "goal": goal, "goal_fp": fp,
              "frozen_at": existing.get("frozen_at") or _now(), "criteria": criteria}
    if existing.get("delivery"):
        anchor["delivery"] = existing["delivery"]  # preserved across an ordinary goal re-set
    if delivery_path:
        _apply_delivery(anchor, delivery_path, force=bool(opts.get("force")))
    _save(anchor)
    done, total, _ = coverage(criteria)
    log("anchored item=%s · %d criteria (%d already verified) · fp=%s" % (
        anchor["item"] or "-", total, done, fp))
    print("anchored")
    _emit_progress("triage", "end", item=anchor.get("item") or None,
                   detail="anchor congelado: %d ACs" % total)


def cmd_mark(opts):
    anchor = _load()
    if not anchor.get("criteria"):
        print("anchor: no anchor set — run `set` first")
        sys.exit(2)
    cid = (opts.get("id") or "").strip()
    status = (opts.get("status") or "").strip().lower()
    if status not in STATUSES:
        print("anchor: --status must be one of %s" % ", ".join(STATUSES))
        sys.exit(2)
    hit = None
    for c in anchor["criteria"]:
        if c.get("id") == cid:
            hit = c
            break
    if not hit:
        print("anchor: no criterion %r (have %s)" % (
            cid, ", ".join(c.get("id") for c in anchor["criteria"])))
        sys.exit(2)
    if status == "done" and not (opts.get("evidence") or "").strip():
        print("anchor: BLOCKED — marking %s done requires --evidence "
              "(file:line / command output / screenshot path). No receipt, no done." % cid)
        sys.exit(12)
    reason = (opts.get("reason") or "").strip()
    if status == "waived:no-infra" and not reason:
        print("anchor: BLOCKED — marking %s waived:no-infra requires --reason (why this "
              "dimension is structurally impossible here). No reason, no waiver." % cid)
        sys.exit(12)
    hit["status"] = status
    hit["evidence"] = (opts.get("evidence") or hit.get("evidence") or "").strip()
    hit["verified_at"] = _now() if status == "done" else ""
    if reason:
        hit["waived_reason"] = reason
    _save(anchor)
    done, total, _ = coverage(anchor["criteria"])
    log("%s -> %s (%d/%d verified)" % (cid, status, done, total))
    print("marked")
    if status == "done":
        _emit_progress("journal", "end", item=anchor.get("item") or None, outcome="pass",
                       detail="AC %s verificado (%d/%d)" % (cid, done, total))
    elif status == "waived:no-infra":
        _emit_progress("journal", "end", item=anchor.get("item") or None, outcome="waived",
                       detail="AC %s waived:no-infra — %s" % (cid, reason))


def cmd_status(opts):
    anchor = _load()
    as_json = bool(opts.get("json"))
    if not anchor.get("criteria"):
        if as_json:
            print(json.dumps({"set": False, "item": None, "goal_fp": None, "frozen_at": None,
                              "criteria": [], "done": 0, "total": 0, "pending": []},
                             ensure_ascii=False))
        else:
            print("anchor: none set")
        return
    done, total, pending = coverage(anchor["criteria"])
    if as_json:
        print(json.dumps({
            "set": True,
            "item": anchor.get("item") or None,
            "goal_fp": anchor.get("goal_fp"),
            "frozen_at": anchor.get("frozen_at"),
            "criteria": anchor["criteria"],
            "done": done, "total": total, "pending": pending,
            "delivery": anchor.get("delivery") or None,
        }, ensure_ascii=False))
        return
    print("anchor: item=%s · goal_fp=%s · frozen=%s" % (
        anchor.get("item") or "-", anchor.get("goal_fp"), anchor.get("frozen_at")))
    delivery = anchor.get("delivery")
    if isinstance(delivery, dict):
        log("delivery: open_pr=%s push_branch=%s allow_new_files_in_repo=%s "
            "allow_comments_in_code=%s commit_message_convention=%r" % (
                delivery.get("open_pr"), delivery.get("push_branch"),
                delivery.get("allow_new_files_in_repo"), delivery.get("allow_comments_in_code"),
                delivery.get("commit_message_convention")))
    for c in anchor["criteria"]:
        detail = c.get("text")
        if c.get("verify"):
            detail += " [verify: %s]" % c.get("verify")
        if c.get("status") == "waived:no-infra":
            detail += "  [waived: %s]" % (c.get("waived_reason") or "(no reason recorded)")
        elif c.get("evidence"):
            detail += "  <%s>" % c["evidence"]
        log("[%-7s] %-4s %s" % (c.get("status"), c.get("id"), detail))
    log("coverage: %d/%d verified%s" % (
        done, total, ("" if not pending else " · pending: " + ", ".join(pending))))


def cmd_checklist(opts):
    print(render_checklist(_load().get("criteria", [])))


def cmd_check(opts):
    anchor = _load()
    goal_now = opts.get("goal")
    v = drift_verdict(anchor, goal_now if isinstance(goal_now, str) else None)
    fmt = (opts.get("format") or ("json" if opts.get("json") else "text")).strip().lower()
    if fmt == "toon":
        # TOON (Token-Oriented Object Notation, github.com/toon-format/toon): same verdict payload
        # as --format json, rendered leaner for the per-turn prompt re-feed. The on-disk anchor.json
        # stays plain JSON — only this prompt-facing render switches encoding (#88).
        print(encode_toon(v))
    elif fmt == "json":
        print(json.dumps(v, indent=2, ensure_ascii=False))
    else:
        print(v["verdict"].lower())
        log(v["reason"])
        if v["pending"]:
            log("pending criteria: %s" % ", ".join(v["pending"]))
    if v["verdict"] == "DRIFT":
        _emit_progress("triage", "blocked", outcome="blocked",
                       detail="DRIFT detectado — re-anchor necessário: %s" % v["reason"])
    if opts.get("exit-code") and v["verdict"] == "DRIFT":
        sys.exit(11)


def _prototype_gate_status(anchor):
    """#568 P0 slice: the Prototype-First gate's own done-gate integration point. A work item
    with a TRACKED, unresolved prototype-necessity flow (`simplicio_loop.prototype_gate`,
    `.simplicio/orchestrator/loop/prototype/<item>.json`) also blocks "done" here, alongside the
    acceptance-criteria coverage this gate already enforces. Fail-open: an item with no
    tracked flow, or a repo where the prototype module is unavailable, is never blocked by
    this check — it is additive, not a new hard requirement for repos that never opted in."""
    item = anchor.get("item")
    if not item:
        return None
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    try:
        from simplicio_loop.prototype_gate import gate_status
    except Exception:
        return None
    try:
        return gate_status(item, REPO)
    except Exception:
        return None


def cmd_gate(opts):
    """The done/PR-open gate: three states per dimension — done / waived:no-infra / pending.
    Waived criteria are printed unconditionally, ready or not."""
    anchor = _load()
    criteria = anchor.get("criteria", [])
    done, total, pending = coverage(criteria)
    waived_items = waived(criteria)
    proto_status = _prototype_gate_status(anchor)
    proto_ready = proto_status.get("ready", True) if proto_status else True
    ready = bool(total) and not pending and proto_ready
    if opts.get("json"):
        print(json.dumps({
            "ready": ready, "done": done, "total": total, "pending": pending,
            "waived": [{"id": c.get("id"), "text": c.get("text"),
                       "reason": c.get("waived_reason") or ""} for c in waived_items],
            "prototype_gate": proto_status,
        }, indent=2, ensure_ascii=False))
    else:
        if ready:
            print("ready")
            log("all %d acceptance criteria verified or waived — safe to declare done / open the PR"
                % total)
        else:
            print("blocked")
            if not total:
                log("no anchor set — freeze the acceptance criteria before declaring done")
            elif pending:
                log("%d/%d verified — do NOT declare done or open the PR yet" % (done, total))
                log("pending: %s" % ", ".join(pending))
            if proto_status and not proto_ready:
                log("prototype gate: %s" % proto_status.get("reason"))
        for c in waived_items:  # always printed, ready or blocked — never silently absent
            log("waived:no-infra %s %s — %s" % (
                c.get("id"), c.get("text"), c.get("waived_reason") or "(no reason recorded)"))
    if opts.get("exit-code") and not ready:
        sys.exit(12)


def _harness_paths(opts):
    """Resolve the 3 artifact paths either from --harness-dir (convention filenames) or from the
    explicit --harness-source/--harness-log/--harness-hash flags (explicit wins)."""
    base = opts.get("harness-dir")
    if isinstance(base, str) and base.strip():
        source = opts.get("harness-source") or os.path.join(base, "harness_source.py")
        logf = opts.get("harness-log") or os.path.join(base, "run.log")
        hashf = opts.get("harness-hash") or os.path.join(base, "snippet.sha256")
        return source, logf, hashf
    return opts.get("harness-source"), opts.get("harness-log"), opts.get("harness-hash")


def verify_harness_artifacts(source_path, log_path, hash_path, snippet_path=None):
    """I/O wrapper around `verify_harness_content`: read the 3 real artifact files (living in the
    caller's own scratchpad, never inside the target repo) and validate them. Missing/unreadable
    for ANY of the 3 invalidates the whole evidence. Returns (ok, reason, detail)."""
    def _read_or_none(path):
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return None
    source_text = _read_or_none(source_path)
    log_text = _read_or_none(log_path)
    hash_text = _read_or_none(hash_path)
    missing = [label for label, text in
              (("source", source_text), ("log", log_text), ("hash", hash_text)) if text is None]
    if missing:
        return False, "missing harness artifact(s): %s" % ", ".join(missing), {}
    snippet_bytes = None
    if snippet_path:
        if not os.path.isfile(snippet_path):
            return False, "--snippet path does not exist: %s" % snippet_path, {}
        with open(snippet_path, "rb") as f:
            snippet_bytes = f.read()
    return verify_harness_content(source_text, log_text, hash_text, snippet_bytes)


def cmd_verify_harness(opts):
    source_path, log_path, hash_path = _harness_paths(opts)
    ok, reason, detail = verify_harness_artifacts(
        source_path, log_path, hash_path, opts.get("snippet"))
    if ok:
        print("harness-ok")
        log(reason)
        print("EVIDENCE: external-harness source=%s log=%s hash=%s (%s)" % (
            source_path, log_path, hash_path, detail.get("hash", "")))
    else:
        print("harness-invalid")
        log(reason)
    if opts.get("exit-code") and not ok:
        sys.exit(12)


def cmd_selftest(_opts):
    checks = []

    def chk(name, got, want):
        ok = got == want
        checks.append(ok)
        print("  [%s] %-32s got=%r want=%r" % ("ok" if ok else "XX", name, got, want))

    # goal fingerprint: whitespace/case-insensitive, stable; different goal -> different hash
    chk("fp.stable", goal_fingerprint("Add SSO  login") == goal_fingerprint("add sso login"), True)
    chk("fp.distinct", goal_fingerprint("a") != goal_fingerprint("b"), True)
    chk("fp.empty", goal_fingerprint(""), "")

    # parse: plain + markdown checklist + bullets, deduped in order
    texts = parse_criteria(["Renders a button", "- [ ] Redirects to IdP",
                            "- [x] Logs the user in", "* plain bullet", "Renders a button"])
    chk("parse.count", len(texts), 4)
    chk("parse.strip_md", texts[1], "Redirects to IdP")

    crit = freeze_criteria(texts)
    chk("freeze.ids", [c["id"] for c in crit], ["AC1", "AC2", "AC3", "AC4"])
    chk("freeze.pending", all(c["status"] == "pending" for c in crit), True)
    chk("split.basic", split_verify("Works :: verify: python3 scripts/check.py"),
        ("Works", "python3 scripts/check.py"))
    chk("split.none", split_verify("One AC"), ("One AC", ""))

    # coverage + gate logic
    crit[0]["status"] = "done"
    crit[0]["evidence"] = "test.py:10"
    chk("coverage.partial", coverage(crit)[:2], (1, 4))
    chk("drift.incomplete", drift_verdict({"goal_fp": "x", "criteria": crit}, None)["verdict"],
        "INCOMPLETE")
    for c in crit:
        c["status"] = "done"
    chk("drift.anchored", drift_verdict({"goal_fp": "x", "criteria": crit}, None)["verdict"],
        "ANCHORED")

    # drift: a changed goal this turn is flagged DRIFT
    anc = {"goal_fp": goal_fingerprint("original task"), "criteria": crit}
    chk("drift.goal_changed", drift_verdict(anc, "a totally different task")["verdict"], "DRIFT")
    chk("drift.same_goal", drift_verdict(anc, "original task")["verdict"], "ANCHORED")
    chk("drift.no_anchor", drift_verdict({}, "x")["verdict"], "DRIFT")

    # merge preserves progress across a re-set that adds an AC
    old = [{"id": "AC1", "text": "Renders a button", "status": "done", "evidence": "e",
            "verified_at": "t", "verify": ""}]
    merged = merge_preserving(old, ["Renders a button :: verify: shot.png", "A new criterion"])
    chk("merge.preserve", merged[0]["status"], "done")
    chk("merge.new_pending", merged[1]["status"], "pending")
    chk("merge.verify_preserved", merged[0]["verify"], "shot.png")
    chk("freeze.verify_carried", freeze_criteria(["A :: verify: cmd"])[0]["verify"], "cmd")

    # checklist renders boxes + coverage
    cl = render_checklist(crit)
    chk("checklist.box", "[x]" in cl, True)
    chk("checklist.coverage", "Coverage:" in cl, True)
    chk("lint.vague_refused", bool(lint_criteria(["works"])), True)
    chk("lint.default_allows_short", lint_criteria(["a1"]), [])
    chk("lint.strict_refuses_short", bool(lint_criteria(["a1"], strict=True)), True)
    chk("lint.strict_allows_short_with_verify", lint_criteria(["a1 :: verify: shot.png"],
                                                              strict=True), [])

    # #526: waived:no-infra is neither done nor pending; gate reaches READY; reason always visible.
    # (Full matrix in tests/test_task_anchor_infra_gate_unit.py — this is the fast in-memory proof.)
    dims = freeze_criteria(["Unit tests pass", "Coverage >=85%", "Benchmark within budget"])
    dims[0]["status"] = "done"
    dims[1]["status"] = dims[2]["status"] = "waived:no-infra"
    dims[1]["waived_reason"] = "no coverage tooling detected"
    dims[2]["waived_reason"] = "no perf harness detected"
    _, wtotal, wpending = coverage(dims)
    chk("waived.gate_ready_math", bool(wtotal) and not wpending, True)
    chk("waived.accessor_count", len(waived(dims)), 2)
    wcl = render_checklist(dims)
    chk("waived.marker_and_reason_in_checklist",
        "waived:no-infra" in wcl and "no coverage tooling detected" in wcl, True)
    chk("waived.is_a_known_status", "waived:no-infra" in STATUSES, True)

    # external-harness evidence form: all-in-memory, no files (pure helper).
    good_log = "case_add_positive PASS\ncase_add_negative PASS\n"
    real_snippet = b"def add(a, b):\n    return a + b\n"
    good_hash = hashlib.sha256(real_snippet).hexdigest()
    ok_h, _, detail_h = verify_harness_content("def add(a,b): return a+b", good_log, good_hash)
    chk("harness.valid_all_pass", ok_h and detail_h.get("cases") == 2, True)
    chk("harness.missing_artifact_invalidates",
        verify_harness_content("", good_log, good_hash)[0], False)
    ok_fail, reason_fail, _ = verify_harness_content(
        "src", "case_one PASS\ncase_two FAIL\n", good_hash)
    chk("harness.any_fail_invalidates", not ok_fail and "case_two" in reason_fail, True)
    ok_mismatch, reason_mismatch, _ = verify_harness_content(
        "src", good_log, good_hash, snippet_bytes=b"different")
    chk("harness.hash_mismatch_invalidates",
        not ok_mismatch and "does not match" in reason_mismatch, True)
    chk("harness.hash_match_ok",
        verify_harness_content("src", good_log, good_hash, snippet_bytes=real_snippet)[0], True)
    chk("harness.log_parser", parse_harness_log(good_log),
        [("case_add_positive", "PASS"), ("case_add_negative", "PASS")])
    chk("harness.hash_extractor", extract_harness_hash("sha256: %s\n" % good_hash), good_hash)

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    sys.exit(0 if ok else 1)


def _parse(args):
    """Parse --k v / --flag, collecting repeated --ac into a list."""
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
    # --describe-cli: emit JSON spec of accepted verbs + flags
    if argv[0] == "--describe-cli":
        import json
        print(json.dumps({
            "verbs": ["set", "mark", "status", "checklist", "check", "gate", "verify_harness",
                      "selftest"],
            "flags": ["--item", "--goal", "--ac", "--ac-file", "--force", "--id", "--status",
                      "--evidence", "--reason", "--format", "--exit-code", "--lint",
                      "--require-evidence", "--out", "--json", "--harness-dir",
                      "--harness-source", "--harness-log", "--harness-hash", "--snippet",
                      "--delivery", "--help"],
        }))
        sys.exit(0)
    sub, opts = argv[0], _parse(argv[1:])
    {"set": cmd_set, "mark": cmd_mark, "status": cmd_status, "checklist": cmd_checklist,
     "check": cmd_check, "gate": cmd_gate, "verify_harness": cmd_verify_harness,
     "selftest": cmd_selftest}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: set mark status checklist check "
                               "gate verify_harness selftest" % sub), sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

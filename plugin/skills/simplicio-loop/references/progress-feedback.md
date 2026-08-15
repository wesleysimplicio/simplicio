# Progress feedback nucleus (issue #298, EPIC #296) — full detail

`scripts/loop_progress.py` is the ONE place "em que etapa estamos / quanto falta" is computed and
persisted. Every stage of the loop calls `emit` at begin/end; nothing else computes a %. All
sister issues (#299-#304 — intake, turn, delivery, transcript, runtimes, gates) are pure
instrumentation callers of this worker.

## State on disk (new, `.simplicio/orchestrator/loop/`, override the directory with `$SIMPLICIO_PROGRESS_DIR`)

| File | Role |
|---|---|
| `progress.jsonl` | append-only events, one line per `emit` call, locked via `scripts/_locked_append.py` (same discipline as `journal.jsonl`) |
| `progress.json` | derived snapshot (last phase/step, %, active item, timestamps) — **never authoritative**, see invariant below |
| `PROGRESS.md` | human render: turn-header line + text progress bar + table + last 5 transitions — the universal surface for hosts without hooks |

## Invariant — projection, never authority (AC7)

`status` and `render` always **recompute** `pct_*` fresh from `task_backlog.py`'s items +
`task_anchor.py`'s criteria + the event trail's turn position. They never read `progress.json*` to
decide a number — deleting the snapshot before `status` yields the identical %.

## Canonical stage machine (frozen, importable)

```python
PHASES = ["F0", "F1", "F2", "F3"]   # intake, execução, entrega, encerramento
STEPS  = ["preflight", "survey", "triage", "decide", "operate", "watcher", "journal",
          "evidence", "refeed_exit"]
```

This is exactly the turn described in `SKILL.md` § Bound operators: `preflight -> survey -> triage
-> DECIDE -> operate -> watcher-gate -> promise`, bracketed by `evidence` (PR/issue delivery) and
`refeed_exit` (the re-feed/exit decision).

## Event schema (one JSONL line)

```json
{
  "ts": "<ISO-8601>", "iteration": 7, "phase": "F1", "step": "operate",
  "step_index": 5, "steps_total": 9, "status": "begin|end|blocked|skipped",
  "outcome": "pass|fail|blocked|null", "item_id": "T3", "detail": "<short string>",
  "source": "task_backlog.py|watcher_verify.py|...",
  "pct_item": 0.33, "pct_overall": 0.42, "rebaseline": false
}
```

## % formula (deterministic, no fabricated numbers)

- `pct_item = acs_verificados / acs_totais` — the active item's AC coverage, read from the anchor.
- **drain** (a backlog with >=1 item exists): `pct_overall = (itens_done + pct_item_do_item_ativo) / itens_totais`.
- **converge** (no backlog, an anchor exists): `pct_overall = pct_item * 0.9 + (step_index / steps_total) * 0.1` — the step fraction gives visible in-turn motion without ever dominating the AC-gated number.
- **unknown** (neither source on disk): `pct_overall` is `None`; every render prints `UNVERIFIED|pct=?`.

## CLI

```bash
python3 scripts/loop_progress.py emit --step operate --status begin --item T3 \
    [--detail "..."] [--outcome pass] [--iteration 7] [--source watcher_verify.py] [--cap 24]
python3 scripts/loop_progress.py status [--json]
python3 scripts/loop_progress.py render [--turn-header|--full] [--cap 24]
python3 scripts/loop_progress.py selftest
```

`render --turn-header` (the contract #302 requires in every turn):

```
MEASURED|[simplicio-loop] fase F1 · etapa 5/9 operate · item T3 (2/5 itens) · ACs 1/3 · 42% geral · iter 7/24
```

## Fail-open

Every error path (missing/corrupt backlog, missing/corrupt anchor, truncated/corrupt
`progress.jsonl`, a `_locked_append` lock timeout) ends in exit 0 with `UNVERIFIED|...` output —
never an uncaught exception, never a fabricated %. Proven by `scripts/loop_progress.py selftest`
and `tests/test_loop_progress.py`.

## Turn × event table (issue #300)

Who calls `emit`, and how (in-process `loop_progress.emit_event()` vs. the CLI the agent runs):

| Turn step | Caller | Mechanism | status/outcome |
|---|---|---|---|
| preflight | `scripts/preflight.py: build_report()` | in-process | begin → end/pass or blocked/blocked |
| survey | agent (SKILL.md § Survey) | CLI | begin → end/pass or blocked/blocked |
| triage | `loop_journal.py: cmd_resume()` | in-process | begin → end/pass |
| triage (DRIFT) | `task_anchor.py: cmd_check()` | in-process | blocked/blocked, detail contains `DRIFT` |
| triage (backlog) | `task_backlog.py: init/next/done/skip/block/fail` | in-process | see #299 |
| decide | agent (SKILL.md § Decide step) | CLI | end, `source: "llm"`, never tagged `MEASURED|` |
| operate | agent (SKILL.md § Operate step) | CLI | begin → end/pass\|fail |
| watcher | `watcher_verify.py: cmd_verify()` | in-process, AFTER `watcher_state.json` is written | end/pass\|fail |
| journal | `loop_journal.py: cmd_record()` | in-process | end, outcome = gate |
| journal (STALLED) | `loop_journal.py: cmd_stall()` | in-process | blocked/blocked, detail contains `STALLED` |

DRIFT/STALLED are surfaced ahead of everything else: `render_turn_header`/`render_full` prepend
`⚠ DRIFT ` or `⚠ STALLED ` whenever the LAST event's `status` is `blocked` and its `detail`
contains that keyword — derived purely from the event trail, never a separate flag.

## Delivery/entrega instrumentation (issue #301)

| Producer | Emits | Notes |
|---|---|---|
| `web_verify.py: cmd_run()` | `evidence` begin → end/pass\|fail, or blocked/blocked (`_blocked()`) | in-process |
| `video_evidence.py: cmd_record()` | `evidence` begin → end/pass\|fail, or blocked/blocked | in-process, playwright engine only |
| `pr_evidence.py: cmd_build()` | `evidence` begin → end/pass, or blocked/blocked (`--require-evidence` gate) | in-process |
| `hooks/loop_stop.py: cleanup_and_stop()` | `refeed_exit` end/pass\|blocked | every stop path (STOP signal, corrupt state, missing operators, promise verified, done-flag, cap reached, spindle handoff) now passes a `(reason, outcome)` pair |

**PR body — `## Progresso do run`.** `pr_evidence.build_body()` calls
`render_progress_section()`, which calls `loop_progress.build_snapshot()` +
`render_turn_header()` directly (no subprocess) and always includes the section — with a backlog/
anchor present it shows the real `%`; with neither, it shows `UNVERIFIED|pct=?`, never a fabricated
number. This never affects the `--require-evidence` gate (`cmd_build`'s `has_evidence` check is
unchanged — the progress section does not count as evidence).

**Idempotent progress comment — `pr_evidence.py progress-comment --issue N [--pr N] [--min-interval S]`.**
Publishes/updates ONE comment per issue, matched by the invisible HTML anchor
`<!-- simplicio-loop:progress -->` (`find_existing_progress_comment()` greps `gh api
.../issues/N/comments` for the marker; a hit PATCHes that comment id, a miss POSTs a new one).
Rate-limited: `.simplicio/orchestrator/loop/progress_comment_state.json` records `last_posted_at`; a call
within `--min-interval` (default 60s) of the last one is a no-op (`skip`). Fully fail-open: no `gh`
on PATH, no `--issue`, or any `gh api` failure all resolve to exit 0 with a log line — remote
progress delivery must never block the loop. The `_gh_run()` call is an injectable function
(tests pass a fake in its place) so `find_existing_progress_comment`/rate-limit logic is unit-
tested without shelling out to a real `gh` or touching the network.

**Run-state closure (F3).** `hooks/loop_stop.py`'s `cleanup_and_stop(reason, outcome)` now emits
the final `refeed_exit` event (fail-open, best-effort import of `scripts/loop_progress.py`) BEFORE
deleting the scratchpad — `loop_progress._run_state()` derives `progress.json`'s `run_state` purely
from that last event: `done` (outcome pass), `capped`/`handoff`/`stopped` (blocked + a matching
keyword in `detail`), else `blocked`. Absent a `refeed_exit` event, `run_state` stays `"running"` —
a run's status file is never silently "eternally in progress" after the run genuinely ended.

## Transcript surfacing (issue #302)

The turn-header contract (SKILL.md § Output) makes progress visible where the user is actually
looking — the transcript — on all 12 runtimes, hook-bound or not.

- **Re-feed header.** `hooks/loop_stop.py`'s `_progress_header_prefix(nxt, max_iter)` builds a
  ` · fase F1 · etapa 5/9 operate · item T3 · ACs 1/3 · 42% geral` fragment (via
  `loop_progress.build_snapshot()` + `render_turn_header()`, stripping the `MEASURED|`/`UNVERIFIED|`
  tag and the trailing `· iter N` — the outer bracket already carries the iteration) and splices it
  into the existing `[simplicio-loop iteration N. ...]` re-feed header, right after the iteration
  number. Also regenerates `PROGRESS.md` (`render --full`) once per turn — a file write, not a
  context token. Fail-open: any error -> `""`, header identical to before this feature (this
  repo's implementation of the issue's `hooks/loop_capture.py` § 3 — in THIS codebase promise
  detection/rejection lives in `hooks/loop_stop.py`, not a separate capture hook; `loop_capture.py`
  here is Cursor-only stdin transport with no completion logic).
- **Promise-rejected signal.** When a turn types a `<promise>` but the completion oracle refuses it
  (no in-turn evidence / no persisted receipt), `loop_stop.py` emits `refeed_exit blocked` with
  `detail: "promise REJEITADA: sem evidência no turno"` — high-signal ("the model thought it was
  done, the gate disagreed") that the NEXT turn's `⚠` banner surfaces immediately, even though the
  loop itself simply continues (no state change beyond the event).
- **Self-paced tick.** Hostless runtimes call `render --turn-header` at tick-start (echoed) and
  `render --full` at tick-end (regenerates `PROGRESS.md`) — the identical surface, agent-driven
  instead of hook-driven.

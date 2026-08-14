# Control policy — RunProjection → LoopDecision (issue #261)

`simplicio_loop/control_policy.py` is a pure convergence policy, not a second control plane. It
takes an immutable `RunProjection` snapshot and returns a `LoopDecision`. It never opens a file,
runs a subprocess, or keeps a parallel ledger — every input and output is a plain dict, which is
what makes that guarantee structural rather than a convention to remember. The Runtime (or, in
this repo, whatever driver adopts this module) remains the sole owner of queue, lease, attempt
budget, effects, and the event log; this module only recommends a decision.

## V(t) — the drift candidate

```
V = a·acs_open + b·verifiers_failed + c·effects_unverified + d·backlog + e·retry_amplification
```

Weights live in `PolicyWeights` (`a,b,c,d,e`, default `1.0, 1.0, 1.0, 0.25, 1.0`) and are published
under `WEIGHTS_VERSION = "v1"` (`simplicio_loop.control_policy.WEIGHTS_VERSION`). Calibrate by
passing a different `PolicyWeights` instance to `decide()` — bump `WEIGHTS_VERSION` when the
calibrated set changes so a `LoopDecision`'s `weights_version` field stays meaningful across runs.

## `LoopDecision` vocabulary

`CONTINUE_SERIAL`, `CONTINUE_PARALLEL`, `OBSERVE_WAIT`, `REPLAN`, `ESCALATE`, `STOP_SUCCESS`,
`STOP_BLOCKED`, `STOP_BUDGET`, `STOP_UNSAFE` — evaluated in that priority order inside `decide()`:

1. **Hard constraints first, never traded off against V(t).** `hard_constraints.safe` /
   `authorized` / `privacy_ok` false → `STOP_UNSAFE` (`hard_constraint_violation`).
   `hard_constraints.within_budget` false → `STOP_BUDGET` (`budget_exhausted`). Safety, authority,
   privacy, and budget are constraints, not weights — no drift score can outrun them.
2. **Success**: `acs_open == 0 and verifiers_failed == 0 and effects_unverified == 0` →
   `STOP_SUCCESS` (`verified`).
3. **Explicit external block**: `projection.blocked` or a non-empty `blocked_reason` →
   `STOP_BLOCKED` (reason_code = the supplied `blocked_reason`, or `external_dependency_blocked`).
   This is the terminal state for "no drift is possible right now," distinct from a retryable stall.
4. **Drift classification** (`classify_drift`) over `history` + the current tick:
   - `PROGRESS` (negative delta, or no repeat yet) falls through to backpressure.
   - `STALL` past the hysteresis `cooldown` → `REPLAN` (`stall_escalation`).
   - `OSCILLATION` (a period-2..4 cycle of state signatures) past `cooldown` → `ESCALATE`
     (`oscillation_detected`) — this is the case a flat fingerprint-repeat check can never see:
     amplified retries whipsawing between two states without ever converging.
   - Either stall/oscillation signal *under* `cooldown` → `OBSERVE_WAIT` (`hysteresis_hold`): a
     single bad tick must never flip strategy immediately.
5. **Backpressure** (`group_candidates`): conflict-free grouping of pending candidates by
   read/write-set overlap, with a simple AIMD cap — a rising `capacity_signal` (errors/queue/
   memory/IO) shrinks the max group size to 1 (multiplicative decrease); a calm signal lets it grow
   by one (additive increase), never a fixed universal worker count. All-conflicting or empty
   candidates → `CONTINUE_SERIAL`; otherwise `CONTINUE_PARALLEL` with the computed `groups`.

## Reason-code vocabulary (reused, not reinvented)

`hard_constraint_violation`, `budget_exhausted`, `verified`, `external_dependency_blocked` (or a
caller-supplied `blocked_reason`), `hysteresis_hold`, `stall_escalation`, `oscillation_detected`,
`no_conflict_free_parallelism`, `conflict_free_groups`. `verified` and `stall_escalation` are
reused verbatim from `simplicio_loop/flow_semantics.py` rather than given synonyms.

## Baseline traces (issue #261 Step 0)

Six frozen fixtures under `tests/fixtures/control_policy/*.json`, replayed tick-by-tick by
`tests/test_control_policy.py`: `success` (monotonic negative drift to `STOP_SUCCESS`),
`flaky_test` (a repeat under the stall threshold that recovers), `blocked_dependency` (an explicit
`STOP_BLOCKED`, never a silent hang), `duplicate_effect` (never claims `STOP_SUCCESS` while an
effect is unverified), `overload` (a rising capacity signal shrinks `recommended_concurrency`), and
`oscillation` (a period-2 cycle that reaches `ESCALATE` within the cooldown window).

## Out of scope here — next steps in `simplicio-runtime`

This module is the pure policy layer only. It deliberately does **not** attempt the cross-repo
acceptance criteria from issue #261, which belong in
[simplicio-runtime](https://github.com/wesleysimplicio/simplicio-runtime) (parent:
simplicio-runtime#3134, related: simplicio-runtime#3042):

- Migrating the Runtime to be the sole owner of queue, lease, attempt budget, and fan-out — this
  repo's `runner.py`/`remote_queue.py` still run their own scheduling.
- Swapping full-repo fingerprints for Mapper revision/Merkle handles.
- Fixing the published package's Python-version support and fan-out packaging/capability manifest.
- The ≥40% duplicate-call-reduction benchmark (or its refutation) — this requires wiring the
  policy into a real driver loop and measuring call counts before/after.
- Fault injection (lost event, duplicate event, stale projection, crash, flaky verifier) at the
  Runtime's event-log/queue layer.

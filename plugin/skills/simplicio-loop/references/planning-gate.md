# Planning gate — task-intake contract + mutation authority (issue #284, full detail)

Moved out of `SKILL.md` § Planning gate (SKILL.md keeps the one-paragraph summary and the two
mandatory-by-default flags; this file has the schema, reason codes, and drift/replan mechanics).

## Why this exists

`simplicio_loop` had the pieces to plan deeply (`task_contract`, `task_anchor.py`,
`plan_contract.validate_plan()`, `work_item_claims.AttemptCoordinator`) before issue #284, but
nothing tied "the task was claimed" to "planning was proven complete" to "mutation may begin"
into one atomic, fail-closed contract. `simplicio_loop/planning_gate.py` and the wiring in
`simplicio_loop/runner.py` are that contract.

## The chain

```
arm_run()
  → task-contract.json (frozen, hash-bound)
  → mapper-context.json
  → plan.json (validated: validate_plan())
  → planning-receipt.json  (simplicio.planning-receipt/v1, auto-built — see below)
       ready_for_mutation: true|false
       mutation_authority: <single-use token>
  → execute_operator() / execute_operator_batch()
       refuses to run unless the receipt's mutation_authority matches the
       CURRENT run_id/attempt/task_contract_hash/plan_hash/lease/fence
       (and source_snapshot_hash, when a GitHub source is present)
```

## Two mandatory-by-default gates

| Env var | Function | Default (unset) | Explicit opt-out |
|---|---|---|---|
| `SIMPLICIO_REQUIRE_MUTATION_AUTHORITY` | `planning_gate.mutation_authority_required()` | **required** | `0`/`false`/`no`/`off`/`legacy` |
| `SIMPLICIO_LOOP_AUTO_PLANNING_RECEIPT` | `planning_gate.auto_planning_receipt_enabled()` | **auto-build ON** | `0`/`false`/`no`/`off`/`legacy` |

Both use the identical polarity-flip pattern: unset or blank means "on"; any other unrecognized
non-empty value is also treated as "on" (fail-closed — a typo cannot silently disable the gate).
The first flag was flipped in PR #360; the second (this round, see
`docs/adr/0004-planning-gate-rollout.md`) makes the real `arm_run()` dispatch path the thing that
actually produces the receipt the first flag checks for, closing the "mandatory to check, but
not mandatory to produce" gap.

`execute_operator_batch()` carries the same gate as the single-task path — both were wired in
#284's PR #350/#360, not only the single-task call.

## Reason codes (`evaluate_mutation_authority()`)

| `reason_code` | Meaning |
|---|---|
| `planning_receipt_missing` | No `planning-receipt.json` on disk (or unreadable) |
| `planning_receipt_schema_invalid` | Wrong/legacy schema string |
| `planning_not_ready` | Receipt exists but `ready_for_mutation` is `False` |
| `mutation_authority_invalid` | Token does not match the current run/attempt/contract/plan/lease/fence identity |
| `source_drift` | A GitHub issue was edited since planning; the current source-snapshot hash no longer matches the receipt's |
| `mutation_authority_verified` | OK — mutation may proceed |

Any non-OK verdict raises `RuntimeError` from `execute_operator()`/`execute_operator_batch()`
with the reason code and message embedded — never a silent pass.

## GitHub source drift and replanning

When a GitHub `source_issue` is present on the run state and
`SIMPLICIO_LOOP_GITHUB_LIFECYCLE_SYNC` is not explicitly falsy, the auto-build step also captures a fresh source
snapshot (`source_snapshot.py::capture_github_issue_snapshot()`) and folds its hash into the
mutation-authority identity, and publishes the receipt as a `PLANNED`/`BLOCKED` state on the
canonical issue comment via `publish_planning_receipt()`. An issue edited between planning and
execution invalidates the authority (`source_drift`) instead of being silently ignored.

The sanctioned recovery from any detected drift is `planning_gate.replan_on_drift()` — it bumps
`plan_revision`, records a semantic diff (`previous_plan_hash` → new), and mints a fresh
authority. `evaluate_mutation_authority()` itself never re-plans; it only ever says no until an
explicit replan call supersedes it. See `tests/test_284_lifecycle_dag_idempotence.py` for the
crash/resume/replan idempotence proofs (a crashed-then-resumed run reuses the same receipt and
`plan_revision` when nothing drifted; a genuine drift requires the explicit replan).

## Local / non-GitHub runs

A run with no `source_issue` on its state builds a purely local receipt (`"source"` key absent)
and never attempts a network call — auto-build being mandatory-by-default does not require
GitHub; it only means the LOCAL receipt is always produced, regardless of whether a source is
configured.

## Opting out (temporary, legacy callers only)

GitHub lifecycle coordination is enabled by default for every real run with a
`source_issue`, so different machines coordinate through the same canonical
idempotent issue comment. Set the following only for an intentionally offline or
legacy local run; the runtime records the missing remote coordination rather than
pretending that the issue was synchronized:

```bash
export SIMPLICIO_LOOP_GITHUB_LIFECYCLE_SYNC=0
```

```bash
export SIMPLICIO_LOOP_AUTO_PLANNING_RECEIPT=0   # arm_run() stops self-building the receipt
export SIMPLICIO_REQUIRE_MUTATION_AUTHORITY=0   # execute_operator()/batch stop requiring one
```

The two flags are independent. Disabling auto-build alone still requires a receipt from some
other source (`scripts/planning_gate.py build`, or a test's
`tests/planning_gate_fixtures.py::stage_valid_planning_receipt()`) if the mutation-authority
gate remains enabled.

## Still open on issue #284

This gate covers the mutation-authority boundary; it does not yet implement the full
`simplicio.task-intake/v1` envelope (scope in/out, dependencies, risks, rollback), a persisted
`impact-map.json`, the bidirectional AC↔step↔test↔evidence matrix as its own artifact, or
automatic (not opt-in) GitHub `CLAIMED`/`PLANNED` comment publishing on every real run. See the
issue for the remaining lifecycle states and full scope.

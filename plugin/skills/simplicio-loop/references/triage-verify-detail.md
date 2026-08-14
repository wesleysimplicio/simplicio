# The loop contract — triage (step 2) and verify (step 3) full detail

Moved out of `SKILL.md` § The loop contract as part of the #119 shrink (SKILL.md keeps the
five-step list with the essential commands; this file has the full elaboration on WHY each
sub-step matters and the extra flags for shared/public-contract changes).

## Step 2 — Triage the live state FIRST (mandatory), full detail

Before any action each turn, re-read the ground truth — the **`simplicio-mapper` survey**
(`.simplicio/*.json`; refresh it with `simplicio-mapper macro . --json` for an instant skeleton or
`scan . --json` if the tree changed), `git status`/`git diff`, the working tree, the scratchpad
notes, AND the source of record (re-query the open issues/PRs, existing branches, the
`.simplicio/orchestrator/loop/done` flag).

**Also read the attempt memory FIRST**: `python3 scripts/loop_journal.py resume` — it lists what
was already tried and the dead-end actions to AVOID, so the turn never re-runs a known-failing
approach. For **incremental triage** (don't re-scan the whole tree every turn), `loop_journal.py
since` shows only the delta since the last recorded turn's commit.

**And re-read the task anchor** — `python3 scripts/task_anchor.py check --goal "<the goal worked
this turn>" --exit-code` — so the turn stays on the SAME frozen acceptance criteria and cannot
drift: a `DRIFT` verdict (exit 11) means the goal moved; STOP and re-anchor explicitly (`--force`),
never wander silently.

Before deciding the next code change, refresh the local impact map for the planned seed files with
`python3 scripts/impact_audit.py audit <root> --file <seed> --cover <known-reviewed-file> --json >
.simplicio/orchestrator/impact-audit.json` so the turn sees callers, neighboring dependencies, and related
tests before it edits. For shared/public contracts or signature changes, tighten that gate to
`--fail-on medium`.

For mixed front/back/service workspaces or any cross-surface user flow, also refresh the flow map
with `python3 scripts/flow_audit.py audit <root> --fail-on high --json >
.simplicio/orchestrator/flow-audit.json` so triage sees UI actions, frontend calls, backend endpoints, and
service calls before deciding the next move.

The journal is the loop's memory for ATTEMPTS; the anchor is its memory for SCOPE; the impact
audit is its memory for BLAST RADIUS; the flow audit is its memory for INTEGRATION. Act only on
what is still genuinely open; never redo done work or act on a stale picture (idempotency).

## Step 3 — Work the goal, full detail

Work the goal each turn as if fresh, against the triaged state. The model DECIDES the AC-scoped
change; the **`simplicio-dev-cli` operator APPLIES and verifies it**
(`simplicio-dev-cli task "<change>" --target <file>`) — do not hand-edit inside the loop. End
EVERY iteration with a short, concrete verification — the operator's passing test run, or one gate
/ command / `file:line` receipt.

**After the operator passes, run the watcher producer**: `python3 scripts/watcher_verify.py
verify` — it reads the per-iteration challenge the stop-hook issued
(`.simplicio/orchestrator/loop/watcher_challenge.json`) and independently recomputes the frozen anchor's
done/pending state from disk (never trusting anything asserted in-context), then writes
`.simplicio/orchestrator/loop/watcher_state.json` with `{"match": true, "status": "MEASURED", "challenge":
..., "goal_fp": ...}` only when `reported == watcher.recomputed_truth` AND the receipt echoes the
current challenge.

**Never hand-write `watcher_state.json` directly** — a hand-written receipt cannot know the
current challenge and will be rejected by the gate; this is the mechanical fix for the
plain-unauthenticated-JSON self-attestation gap. A `match: false`, missing, or unchallenged watcher
state is treated as `UNVERIFIED` and gates the promise.

If the actual edit surface expands, rerun `impact_audit.py` with the new seeds/cover and treat
uncovered reverse dependents as failed verification; use `--fail-on medium` for shared/public
contracts or signature changes. If the change crosses UI/API/service boundaries, rerun
`flow_audit.py` after the edit and treat high gaps as failed verification; use `--fail-on medium`
when the AC promises backend integration for that UI flow.

**Then RECORD the attempt** in the journal: `loop_journal.py record --iteration N --action "<what
you changed>" --hypothesis "<why>" --gate pass|fail --gate-output <test.log>` — on a failure the
gate output is fingerprinted so the SAME failure is recognised next turn. Keep iterations small and
verifiable: a turn that only edits without verifying is incomplete.

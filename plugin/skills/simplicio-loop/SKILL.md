---
name: simplicio-loop
description: "Unified public entrypoint for Simplicio's body-of-work orchestration: core + loop in one command. Use when the user types /simplicio-loop, says \"ralph loop\", \"keep iterating until done\", \"finish all open issues\", or asks to drain a queue of work autonomously. Runtime-agnostic: binds a real stop-hook where the host supports hooks (Claude, Cursor); otherwise self-paces via the host scheduler. The older /simplicio-tasks surface is a legacy alias; never escape the loop with a false promise."
---

# /simplicio-loop — unified core + loop

A self-referential iteration primitive: the SAME goal is fed back after every turn, so
the agent sees its own prior edits and converges. It exits ONLY when a **typed
completion-promise** is genuinely true, or a hard `max_iterations` cap fires. This skill is now
the unified public surface for Simplicio's autonomous work orchestration: queue intake,
evidence-gated execution, and the hardened Ralph loop live behind the single command
`/simplicio-loop`. The older `simplicio-tasks` surface remains only as a compatibility alias.

Credit: the technique is Ralph Wiggum / cursor `ralph-loop`. We keep its best parts —
single human-readable state file, exact-match promise sentinel, two-hook split — and add
the simplicio safety spine (evidence-gated promise, max-iteration cap, cross-platform hook).

For queue/body-of-work runs, pair this file with the shared deep references under
`../simplicio-tasks/references/` for extension points, orchestration, token economy, delivery,
and safety details.

## GitHub coordination default

When the project remote is hosted on GitHub, GitHub is the default coordination and source-of-truth
surface for the loop: read and update Issues, publish progress in issue/PR comments, validate checks,
merge only through the repository's approved PR path, and re-query live state before closing. Do not
silently substitute another tracker or local scratchpad for GitHub; use another system only when the
user explicitly requests it or the repository's documented workflow requires it.

## Bounded delivery policy

Keep delivery finite and ownership explicit; a repository may set stricter limits, never looser
ones without a recorded human decision.

- **Bounded WIP:** one implementation issue and one delivery PR per worker/session. Finish,
  hand off, or mark the item blocked before claiming another; reviews do not transfer ownership.
- **Live intake and frozen scope:** immediately before freezing, re-query the canonical source and
  record its revision plus provenance in the anchor. Freeze that exact issue goal and acceptance
  criteria before mutation. A review finding may prove an AC incomplete, but cannot add an AC
  silently; source drift or scope changes require a fresh query, re-anchoring, and an explicit
  owner decision.
- **Finding categories:** classify every finding as `AC_BLOCKER` (violates a frozen AC),
  `REGRESSION_BLOCKER` (security, correctness, compatibility, or evidence regression caused by the
  patch), or `FOLLOW_UP` (valuable but outside the frozen scope). Only blockers hold the current
  delivery; follow-ups become separate work and are never smuggled into its diff.
- **Review limits:** use one implementation review and one final independent verification, with at
  most two AC-scoped repair rounds. If a blocker remains, stop `BLOCKED` with evidence and ownership
  instead of opening an unbounded review/fix loop.
- **Ownership and integration:** only the active owner mutates the delivery branch. Reviewers are
  read-only unless ownership is explicitly handed off. Before the first mutation, acquire and
  confirm the cross-session claim/lease/fence against the live source; a stale or conflicting
  authority blocks mutation. A handoff must update the authority record and the receiver must
  confirm the new claim/lease/fence before continuing. Rebase once onto the current canonical base
  immediately before final verification/merge; after any rebase, rerun the affected gates and
  prove ancestry/patch scope.
- **Release boundary:** merge, issue closure, packaging, and release are separate states. Do not
  close the issue before merged evidence satisfies the frozen ACs, and do not tag/publish a release
  unless the task or an authorized release owner explicitly includes it; re-query the canonical
  branch and release state immediately before publication.

Rationale and rollout: `docs/adr/0008-bounded-delivery-policy.md`.

## Normative contract (non-negotiable)

**Design principle (issue #526): always route to the fastest path the project's structure
allows.** Execution mode is never a contract obligation or a caller preference — it's a MEASURED
consequence of the project's structure and the goal's scope:

| Layer | Nature | Contents |
|---|---|---|
| **Safety floor** | mandatory, identical every mode, never loosens | in-turn evidence before `<promise>`; secret-scan; journal (1/turn); claims-gate MEASURED/UNVERIFIED |
| **Path** | automatic, decided by structure | run is born in the LIGHTEST mode the structure supports; full pipeline is an escalation destination, not an entry toll |
| **Escalation** | triggered ONLY by measured evidence | diff overshoot, new file, target is a hub, sensitive surface touched → auto-promotion to the heavy protocol, journaled |

A flag, if any, FORCES the heavy path from arming (opt-out of fast) — never "unlocks" fast-path.
Fast-path is never requested; escalation is never avoided. See §§ "Three loop modes" (route/
escalation), "Definition of Done" (adaptive DoD), "Delivery contract" (client constraints) —
all three instances of this shape; no future change to any may reintroduce all-or-nothing.

These invariants are MUST-level. Any runtime that loads this skill (Simplicio Agent, Claude, Cursor, or a
bare LLM) follows them mechanically — no paraphrase, no drift:

1. **Evidence-gated exit.** The loop MUST NOT terminate without concrete evidence, produced in the
   SAME turn, that the goal is met. No in-turn evidence → no exit.
2. **Exact promise.** Completion is gated by the EXACT sentinel `<promise>EXACT TEXT</promise>`
   equal to `completion_promise` verbatim. A paraphrase or a fuzzy "I'm done" never counts.
3. **Deterministic continuation.** If the promise is not satisfied, the next iteration MUST re-feed
   the current goal + state unchanged — a mechanical re-feed, never a manual "shall I continue?".
4. **Bounded by construction.** `max_iterations` MUST be set before iteration 1 unless the run is
   deliberately self-paced by a durable scheduler — the loop is NEVER accidentally unbounded — and
   the cap is checked BEFORE every continuation.
5. **Single source of truth.** All loop state lives in the one scratchpad below; the sibling
   `.simplicio/orchestrator/loop/done` flag is touched ONLY when the promise is verified.
6. **Fallback obeys the same contract.** When the host has no hooks, the self-paced scheduler mode
   is first-class and MUST honor invariants 1–5 identically.
7. **Definition-of-Done gate.** No issue/task item may be marked `done` (`task_backlog.py done`)
   or closed unless its frozen acceptance criteria cover all seven DoD dimensions — see
   "Definition of Done" below. A partial pass (e.g. unit tests green but no coverage number, or
   an implementation with no regression/perf evidence) is NOT done; keep iterating.

The rest of this file is the mechanism that enforces this contract.

## LLM startup orientation (canonical; every Loop turn)

The following marked block is the single source of truth for the short operating
instructions that must reach every LLM turn started or re-fed by `simplicio-loop`.
The stop hook extracts the block mechanically and prepends it to each re-feed. Keep
the block concise, stable, and free of task-specific details; update the ADR and
the focused hook tests when changing it.

<!-- SIMPLICIO-LLM-ORIENTATION:BEGIN -->
Orientação operacional do Loop (MAX SPEED — detail: docs/LLM_MAX_SPEED_ORIENTATION.md):
- Runtime first when available: consult `simplicio loop decide --json` and honor `.simplicio/runtime/loop-decision.json`; when Runtime is absent, continue through the standalone Loop operators and report Runtime integration as degraded (never claim Runtime authority).
- Economy-parallel: `simplicio-loop economy apply --json` + `preflight --strict` antes de trabalho autônomo.
- Hot path: Mapper (scan/handoff) → Fast (understand|plan|apply se up) → dev-cli/edit --plan (STRICT; sem hand-edit).
- Trabalhe só na tarefa/ACs atuais; menor alteração segura; preserve dirty work, lease e ownership.
- Paralelismo: 1–3 tasks = direct; >3 = Prism (`arm_drain_prism --slots 0 --batch-size N`, default/min 10); writes serializados; governor físico admite capacity.
- Gates mínimos que provam o AC; proibido full-repo fmt/test residual, review-panel×3 em metadata, reinstall operators.
- GitHub/gh só quando a tarefa exigir issue/PR/release (SoT do drain).
- Use o menor raciocínio suficiente; sem web genérica/subagentes/LLM local por padrão; seja conciso.
- Não edite com contexto stale, lock ativo, artifacts ausentes ou capacidade não verificada.
- Testes focados; saída com evidência da rodada + tags MEASURED| / UNVERIFIED| (nunca inventar métricas).
- Fim de mensagem: DONE | NEXT(<1 passo>) | BLOCKED(<código>) — act > narrate.
- Falha/ambiguidade: bloqueio real; não invente nem repita a mesma tentativa cegamente.
<!-- SIMPLICIO-LLM-ORIENTATION:END -->

## Definition of Done (DoD) — mandatory quality gate

Every task/issue anchored via `task_anchor.py set` MUST include, as explicit acceptance criteria
(besides any goal-specific ones), evidence for all seven of:

1. ✅ **Implementação** — the change itself, present and working.
2. ✅ **Testes unitários** — unit-level coverage of the new/changed logic.
3. ✅ **Testes de integração** — the change verified against its real collaborators (no mocks for
   the seam under test).
4. ✅ **Testes de sistema** — an end-to-end pass through the actual command/CLI/API surface a user
   or caller would hit.
5. ✅ **Testes de regressão** — the existing suite still green; no prior behavior silently broken.
6. ✅ **Benchmark de performance** — a measured number (latency/throughput/memory) for any change
   that touches a hot path, so a regression is caught by a number, not a feeling.
7. ✅ **Cobertura mínima** — line/branch coverage ≥ 85% (target 90% where the toolchain reports
   branch coverage) for the touched files, checked with the project's own coverage tool.

Freeze these as ACs at intake (`task_backlog.py init` / `task_anchor.py set`) so
`task_anchor.py gate` — the same worker already gating "done" on unverified ACs — refuses to let
the loop declare completion or open the PR (`pr_evidence.py build --require-evidence`) until every
one of the seven is verified with evidence, not asserted. When a goal is decomposed at Phase 0,
each backlog item's `plan.json` entry MUST carry all seven as ACs.

**Adaptive DoD — dimensioned by the repo's REAL infra (issue #526 Etapa 3).** No dimension is
silently skipped or blocked forever for lacking tooling an ideal repo would have. Flow: probe →
external harness → `waived:no-infra` — never the old vague "skip … and say why":

1. **Probe (intake, MEASURED, never hand-typed).** A deterministic infra probe checks, per
   ecosystem (.NET/Node/Python/Go/Rust/Java+): test project/runner on disk (`**/*Tests*.csproj`,
   `pytest.ini`, `jest.config.*`, `_test.go`…)? Coverage tooling? CI that runs tests? Result lands
   on the anchor as `test_infra: {unit, coverage, ci: present|absent}` — a filesystem fact, not an
   assumption. *(Worker `test_infra_probe.py`; see #526 Etapa 3.)*
2. **External harness = equivalent evidence.** When `unit: absent` AND the delivery contract
   (below) forbids new repo files, "testes" accepts a scratchpad-only harness (never committed) as
   evidence — gated on 3 artifacts together: harness source, a PASS/FAIL log with named cases, and
   a hash of the exact code fragment replicated (proves the harness mirrors the REAL diff). Missing
   any one invalidates the evidence.
3. **`waived:no-infra` for the structurally impossible** (≥85% coverage with no coverage tool;
   perf benchmark with no bench harness) — recorded with an explicit reason, never `pending`
   forever, never dropped in silence.
4. **Three gate states, not two.** `task_anchor.py gate` recognizes `verified` / `waived:no-infra`
   / `pending` *(gate implementation itself: #526 Etapa 3)*. READY requires zero `pending`; every
   `waived:no-infra` MUST appear in the final report — a silent waiver is a contract violation.

## Delivery contract — client delivery constraints, enforced mechanically (issue #526 Etapa 4)

`task_anchor.py set --delivery`, the schema validator (`scripts/delivery_contract.py`), the
stop-hook new-file guard, and the deterministic comment linter are implemented — see
`references/delivery-contract.md` and #526 Etapa 4 for the worker code.

Client constraints in plain language ("don't open a PR", "no test files", "no comments") don't
self-enforce — the default contract's operator could (and did) violate all three. Same
three-layer shape as § "Normative contract", for DELIVERY: stated constraints become a FROZEN
contract next to the anchor; mechanical gates consume it, the LLM never self-certifies.

**Freezing.** The LLM proposes `delivery.json` from the request; the user confirms; the worker
freezes it (`task_anchor.py set --delivery delivery.json`) — later changes need `--force`, same as
re-anchoring. An unknown field is a hard error at `set`, never a silent no-op:

```json
{
  "open_pr": false,
  "push_branch": true,
  "allow_new_files_in_repo": false,
  "allow_comments_in_code": false,
  "commit_message_convention": "<type>(<scope>): <subject>"
}
```

**Gates per clause:**

| Clause | Mechanical gate |
|---|---|
| `open_pr: false` | `pr_evidence.py build --local-report` — writes evidence to a local file, never calls the PR API |
| `allow_new_files_in_repo: false` | stop-hook diffs `git status --porcelain` vs the turn baseline, BLOCKS on an unauthorized new file |
| `allow_comments_in_code: false` | comment-syntax-aware diff linter runs pre-commit, fails on added comment lines (C#, TS/JS, Python — `//`, `/* */`, `#`, new docstrings) |
| `commit_message_convention` | checked against every commit the run produces |

Final report lists the contract + per-clause compliance, tagged `MEASURED`, never prose — the exact
`push_branch:true`+`open_pr:false`+no-test-files+no-comments combo that motivated this issue
(§ Context above) is now representable and enforced without inventing repo-side tests or a PR the
client refused.

## Adaptive infrastructure evidence and delivery contract

The DoD scales to measured repository infrastructure without lowering the safety floor. Run
`scripts/test_infra_probe.py` at intake: native tests and coverage are `verified` when detected;
missing tooling is `waived:no-infra` only with a recorded reason; missing unit evidence remains
`pending` until a complete external harness supplies source, named PASS/FAIL log, and code hash.
Client delivery restrictions are frozen as `simplicio.delivery-contract/v1`; unknown fields fail,
`open_pr=false` uses `pr_evidence.py build --local-report`, and new-file/comment guards are
enforced from the contract. `scripts/operator_preflight.py` separately pins operator versions and
gates upgrades by TTL.

## When to use

- "/simplicio-loop finish all the open issues", "clear the CI queue", "drain the Jira board".
- "run a ralph loop on X", "iterate until the tests pass", "keep going until done".
- As the unified public entrypoint for unattended queue-drain or converge-until-done runs.
- For body-of-work / Phase-0 drains, freeze the backlog once (`task_backlog.py init`) and use
  `task_backlog.py checklist` / `pr_evidence.py build --backlog ...` so the PR shows the whole
  backlog table above the per-item anchor checklist, not just the current item.
- NOT for a one-shot edit — use the host's normal flow.

## Bound operators (REQUIRED): survey + operate

This loop does NOT survey the repo with the LLM, and it does NOT hand-edit files with the LLM.
Two installed CLIs are the operators; the model only DECIDES, the operators DO. A normal
`pip install simplicio-loop` installs both direct operator dependencies: `simplicio-cli`
(exposes `simplicio-dev-cli`) and `simplicio-mapper` (exposes the survey binary).
Full mechanics (two-tier survey, evidence gate, context-pack, structured queries, docs-drift
gates, the operator dispatch table): **`references/bound-operators.md`**.

| Operator | CLI (binary) | Binds | Role in the loop |
|---|---|---|---|
| **simplicio-mapper** | `simplicio-mapper` | `orient` / `recall` | **Survey** — maps the repo(s) into `.simplicio/*.json` (project-map, precedent-index, symbol-index, call-graph, docs). This survey, not an ad-hoc LLM read, is what feeds the goal each turn. |
| **simplicio-dev-cli** | `simplicio-dev-cli` | `execute` / `deterministic_edit` / `validate` / `diagnostics` | **Operate** — applies a DECIDED change through its 6-layer contract (mapper context → precedent → prompt → diff → test → verify, ≤3 retries). The CLI edits and verifies; the AI does not hand-write the diff. |
| **simplicio-runtime** (adaptive) | `simplicio` | effects / HBP / contracts | **When available and operational**, the loop binds it (`SIMPLICIO_EXECUTION_PROFILE=runtime-backed`). When absent or unavailable, the core mapper→dev-cli/local operator path continues; only `SIMPLICIO_LOOP_REQUIRE_RUNTIME=1` makes it a hard prerequisite. |
| **simplicio-fast** (strict-adaptive) | `simplicio-fast` | understand / plan / apply | Under `SIMPLICIO_LOOP_STRICT=1`, if Fast is operational it becomes required so the session cannot silently drop it. |

### Local execution is the native fallback

Cloud workers and host adapters are accelerators, not prerequisites. If no cloud
environment/queue is configured, the queue is unavailable, or Orca is absent, the Loop
continues with isolated local worktrees and logically unbounded fan-out; physical workers remain
governed by measured machine capacity. `dispatch_operator_batch` admits local tasks through the native
`simplicio_loop.prism_scheduler.PrismScheduler` (dependencies, conflicts, leases, and worker
budget) and then runs the admitted work concurrently; it does not require a remote worker or
Orca client. Set `SIMPLICIO_LOOP_LOCAL_FALLBACK=0` only for deployments that explicitly require
remote claims. A remote task that was accepted is never duplicated locally after a timeout.

### Prism routing and slot policy

The deterministic router uses direct parallelism for one to three tasks. A request with more than
three tasks activates Prism. When the request does not specify a quantity, the default and minimum
logical batch is ten tasks per slot; an explicit larger batch is valid and there is no logical upper
limit on slot count, slot capacity, or Prism waves. This does not disable the physical governor:
CPU, memory, disk, provider, lease, worktree, and observed worker capacity can delay admission
without changing the logical plan. Fast is queried from the fresh Mapper snapshot before selecting
the route, and Runtime is added for native execution, gates, checkpoints, or receipts.

### Strict mode (force every AI onto the full stack)

Arm once per session / shell before any autonomous work:

```bash
export SIMPLICIO_LOOP=1
export SIMPLICIO_LOOP_STRICT=1
export SIMPLICIO_LOOP_REQUIRE_RUNTIME=auto   # bind Runtime if operational
export SIMPLICIO_REQUIRE_MUTATION_AUTHORITY=1
export SIMPLICIO_LOOP_AUTO_PLANNING_RECEIPT=1
export SIMPLICIO_LOOP_FORBID_HAND_EDIT=1
simplicio-loop preflight --strict --json
```

What strict changes mechanically:

1. **Stop-hook** refuses missing bound operators (mapper/dev-cli; Runtime/Fast when operational).
2. **`evidence_required` is locked true** — scratchpad cannot opt out.
3. **`action_gate` PreToolUse** blocks host Write/Edit/StrReplace tools — mutations must go through `simplicio-dev-cli` / `simplicio-py task`.
4. **Execution profile auto-selects `runtime-backed`** when Runtime probes clean.
5. **Preflight `--strict`** prints `recommended_env` and fails if any required operator is missing.

Without hooks + strict env, a free-form chat agent can still ignore the skill text. Strict is the enforceable floor.

**Preflight (MANDATORY, BLOCKING) — TTL-gated, never mid-run (issue #526 Etapa 6).** Before
iteration 1, announce the step; `scripts/operator_check.py` decides mechanically whether THIS
armada warrants a network round-trip:
```bash
python3 scripts/loop_progress.py emit --step preflight --status begin --detail "operadores: verificação/atualização (TTL-gated)"
python3 scripts/operator_check.py maybe-upgrade --json
simplicio-mapper --version   # survey operator (direct simplicio-loop dependency)
simplicio-dev-cli --help     # action operator (pkg simplicio-cli; exposes `simplicio-dev-cli`)
python3 scripts/operator_check.py pin --scratchpad .simplicio/orchestrator/loop/scratchpad.md \
  --versions "{\"simplicio-mapper\": \"<resolved-version>\", \"simplicio-dev-cli\": \"<resolved-version>\"}"
python3 scripts/loop_progress.py emit --step preflight --status end --outcome pass \
    --detail "simplicio-mapper X.Y.Z; simplicio-dev-cli OK"
```
`maybe-upgrade` only calls `pip install -qU simplicio-cli simplicio-mapper` when the last check in
`~/.simplicio/operator-check.json` is older than the TTL (default 7d, `--ttl-days` to override) OR
a binary is missing from PATH — inside the TTL: **zero network, zero subprocess**, pure cache read.
Best-effort/offline-safe: a failed/offline attempt still records the check (no retry-every-iteration
on a flaky network) and keeps the working version.

`pin` writes THIS armada's resolved version into the scratchpad frontmatter
(`operator_versions: {...}`) once — never re-pinned mid-run. A later iteration checks with
`operator_check.py check-pin --scratchpad ... --versions "{...current...}"`: mismatch prints
`WARNING:`, never a silent upgrade — the pin holds regardless.

The action binary is `simplicio-dev-cli` — NOT the bare `simplicio` (that's the separate
`simplicio-runtime`). If either runtime binary is missing/incompatible, the runner performs one
bounded repair with `pip install -U simplicio-cli simplicio-mapper`, validates identity/version/
capabilities, records `operator-bootstrap.json`, and retries the blocked stage once. A failed
repair remains `BLOCKED`; it never falls back to LLM survey/editing. The optional `simplicio`
runtime is reported as unavailable and its native integrations are skipped.

**Survey step (each loop start).** `python3 scripts/loop_progress.py emit --step survey --status begin`
→ `simplicio-mapper scan . --json` (instant macro skeleton + background deep index) → gate with
`inspect . --json` (artifacts exist on disk) → on a passing gate `emit --step survey --status end
--outcome pass --detail "context-pack pronto (pack_hash <hash8>)"` (on a failing gate, `--status
blocked --outcome blocked`) → feed the goal
from `handoff . --for-llm toon` (a pre-compressed context-pack: files/symbols/deps/`pack_hash`,
substitutes for re-reading the tree). For triage questions the map alone doesn't answer,
`simplicio-mapper ask . <impact|tests-for|callers|...> <arg> --json`. Verify-side docs gates:
`sync . --check --json` / `drift . --check --json` (BLOCK only when the AC itself is docs).

**Decide step (etapa 4/9 — the model's own step, no worker).** Immediately before delegating to the
operator: `python3 scripts/loop_progress.py emit --step decide --status end --source llm --detail
"<one-line summary of the decided change, target AC>"` — the only event whose `detail` comes from
the LLM; the render never tags it `MEASURED|` (it's a decision, not a measurement).

**Operate step (every turn that mutates code).** Delegate the DECIDED, AC-scoped change to the
operator — never hand-edit inside the loop:
```bash
python3 scripts/loop_progress.py emit --step operate --status begin --detail "operador: <target file>"
simplicio-dev-cli task "<the decided, AC-scoped change>" --target <file> [--json]
python3 scripts/loop_progress.py emit --step operate --status end --outcome pass|fail \
    --detail "verify do operador: <result>, tentativas usadas: n/3"
```
The operator applies the diff, runs the tests, and self-corrects up to 3× — its passing
verification IS the in-turn evidence the promise gate needs (below).

**Watcher step (etapa 6/9).** `scripts/watcher_verify.py verify` emits its own `end` event AFTER
`watcher_state.json` is written — never before (progress reports the gate, it never substitutes
for it).

**Journal step (etapa 7/9).** `scripts/loop_journal.py record` emits `end` with `outcome = gate`;
`scripts/loop_journal.py stall` on `STALLED` emits `blocked` — the NEXT turn's render opens with
`⚠ STALLED` (or `⚠ DRIFT`, from `task_anchor.py check`) ahead of everything else.

One turn: `preflight → survey (mapper) → triage (re-read survey, journal resume) → DECIDE (AI) →
operate (simplicio-dev-cli task: apply+test+retry ≤3×) → watcher-gate (independent re-execution) →
journal record → <promise> only if all gates passed`. `scripts/loop_journal.py`'s `cmd_resume`/
`cmd_record`/`cmd_stall` call `loop_progress.emit_event()` in-process (no subprocess per event) for
the `triage`/`journal` steps; `task_anchor.py check` does the same on `DRIFT`.

## Planning gate: task-intake contract + mutation authority (issue #284)

Between "claim the task" and "mutate the repo" the loop enforces a **fail-closed planning gate**
so deep planning is a mechanical barrier, not prompt guidance. `simplicio_loop/runner.py::arm_run()`
compiles the task contract, mapper context, and plan, then self-builds a
`planning-receipt.json` (`simplicio_loop/planning_gate.py::build_planning_receipt()`) binding
`run_id`/`attempt`/`task_contract_hash`/`plan_hash`/lease/fencing (and, on a GitHub source, the
source-snapshot hash) into a single-use `mutation_authority` token. `execute_operator()` and
`execute_operator_batch()` refuse to mutate without a receipt whose token matches the CURRENT
identity tuple — a stale plan hash, rotated lease/fence, or edited GitHub issue invalidates it
(`reason_code` in `planning_not_ready`/`mutation_authority_invalid`/`source_drift`).

Both halves of this gate are **mandatory by default**:
`SIMPLICIO_REQUIRE_MUTATION_AUTHORITY` (checking) and `SIMPLICIO_LOOP_AUTO_PLANNING_RECEIPT`
(the real dispatch path building the receipt the check needs) are unset-means-ON; only an
explicit falsy value (`0`/`false`/`no`/`off`/`legacy`) opts a caller out, and an unrecognized
value is treated as ON (fail-closed, never silently disabled by a typo). See
`docs/adr/0004-planning-gate-rollout.md` for the rollout/migration strategy and
**`references/planning-gate.md`** for the full schema, reason codes, and replan-on-drift
mechanics.

## Video evidence producer (hyperframes) — demo videos as proof

The loop can be asked to **create a demonstration video** of a screen/feature — e.g.
`/simplicio-loop make a demo video of the login screen` — and it uses that video as
in-turn evidence that the change works. The producer is **hyperframes**
(<https://github.com/heygen-com/hyperframes>): it renders HTML/CSS/media compositions to a
**deterministic MP4** ("same input, same frames, same output"), so the video is a CI-reproducible
artifact, not a one-off recording. No API keys; local render via headless Chrome + FFmpeg.

This is NOT a bound operator (it never BLOCKS the loop): it fires only when a turn's goal is a
video request, or when a UI change wants a moving proof. The runnable worker is
`scripts/video_evidence.py`; the full contract is `references/video-evidence.md`. One turn:

```bash
# 1. is this turn a video request?  (terminal intent gate, not the LLM)
python3 scripts/video_evidence.py detect --goal "<the re-fed goal body>"
# 2. capture the real screen (reuse web_verify — drives the UI, writes per-step PNGs)
python3 scripts/web_verify.py run --url <URL> --expect "<text>" --issue <N>
# 3. assemble those PNGs into a deterministic MP4 and attach it to the PR
python3 scripts/video_evidence.py verify --name <slug> --frames .simplicio/orchestrator/tee/web \
    --title "<screen>" --issue <N> [--upload --pr <N>]
```

The MP4 path + the `video_evidence: PASS …` ledger row is the in-turn evidence the promise gate
needs; a missing toolchain (Node 22+, FFmpeg, hyperframes) yields **BLOCKED**, never a fake pass —
so a video that never rendered can never satisfy the promise.

## State file (single source of truth)

`.simplicio/orchestrator/loop/scratchpad.md` — human-readable, trivially editable/cancellable:

```markdown
---
iteration: 1
max_iterations: <N or 0>          # 0 = scheduler-controlled; prefer a finite cap for manual runs
completion_promise: "<EXACT TEXT>" | null
evidence_required: true           # promise is rejected unless backed by a passing gate
mode: converge | drain | fast-path # which termination logic applies (see Three loop modes)
started_at: "<ISO-8601>"
---

<the task goal, verbatim — this body is re-fed every turn>
```

A sibling flag file `.simplicio/orchestrator/loop/done` is `touch`ed only when the promise is verified.

Alongside it, `.simplicio/orchestrator/loop/journal.jsonl` is the loop's **durable attempt memory** (one
append-only record per turn: `iteration`, `action`, `hypothesis`, `gate`, failure `fingerprint`).
The scratchpad holds the GOAL; the journal holds WHAT WAS TRIED — see § Run-journal + stall
detector below. It is the difference between a loop that converges and one that oscillates.

## The loop contract

1. **Write the scratchpad** with the goal, the cap, and the promise text. Always recommend a
   `max_iterations` safety net for manual runs; use `0` only when a durable scheduler and STOP
   signal own cancellation.
2. **Triage the live state FIRST (mandatory).** Before any action each turn, re-read the ground
   - If every open issue returns DEFER_ACTIVE_CLAIM (all claimed), do NOT idle — review open PRs against the 7-dimension DoD and the underlying issue frozen ACs using scripts/pr_dod_review.py, and comment what remains for the claiming agent (convention: references/multi-agent-coordination.md).
   truth — the **`simplicio-mapper` survey**, `git status`/`git diff`, the scratchpad, AND the
   source of record (issues/PRs, branches, `.simplicio/orchestrator/loop/done`). **Read the attempt memory
   FIRST**: `python3 scripts/loop_journal.py resume` (dead-ends to AVOID; `since` for incremental
   triage). **Re-read the task anchor**: `python3 scripts/task_anchor.py check --goal "<goal>"
   --exit-code` (a `DRIFT` verdict, exit 11, means STOP and re-anchor with `--force`, never wander).
   Before deciding the change, refresh the impact map (`python3 scripts/impact_audit.py audit <root>
   --file <seed> --cover <known-file> --json`, `--fail-on medium` for shared/public contracts) and,
   for cross-surface flows, the flow map (`python3 scripts/flow_audit.py audit <root> --fail-on
   high --json`). When a Phase 0 decomposition exists, also re-read the backlog (`python3
   scripts/task_backlog.py status`). Journal = memory for ATTEMPTS; anchor = SCOPE; backlog =
   THE DECOMPOSITION; impact audit = BLAST RADIUS; flow audit = INTEGRATION. Act only on what's
   still genuinely open (idempotency). Full rationale + extra flags:
   **`references/triage-verify-detail.md`**. On a multi-session/multi-worktree repo, also run
   `scripts/coordinator.py survey`+`decide` per candidate issue — `OWN`/`CONTINUE_OWN`/
   `RECLAIM_STALE` license work, `DEFER_ACTIVE_CLAIM` means don't duplicate a sibling session's
   claim. If EVERY issue comes back deferred, switch to reviewing open PRs against the DoD +
   issue ACs (`scripts/pr_dod_review.py check --post`) instead of idling. Full detail:
   **`references/multi-agent-coordination.md`**.
3. **Work the goal** each turn against that triaged state. The model DECIDES the AC-scoped change;
   the **`simplicio-dev-cli` operator APPLIES and verifies it** — never hand-edit inside the loop.
   End EVERY iteration with a concrete verification. **After the operator passes, run the watcher
   producer**: `python3 scripts/watcher_verify.py verify` — independently recomputes the frozen
   anchor's done/pending state from disk and writes `.simplicio/orchestrator/loop/watcher_state.json` with
   `{"match": true, "status": "MEASURED"}` only when it agrees AND echoes the current challenge.
   **Never hand-write `watcher_state.json`** — a missing/unchallenged/mismatched state is
   `UNVERIFIED` and gates the promise. Re-run `impact_audit.py`/`flow_audit.py` if the edit surface
   expands. **Then RECORD the attempt**: `loop_journal.py record --iteration N --action "<change>"
   --hypothesis "<why>" --gate pass|fail --gate-output <test.log>` (failure output is fingerprinted
   so the same failure is recognised next turn). A turn that only edits without verifying is
   incomplete. Full detail: **`references/triage-verify-detail.md`**. Launch the verification
   command (tests/selftest/`claims_audit.py`) in the **background** and keep working the next unit
   of work instead of idling on it — same evidence requirement, only WHEN you block on the result
   changes. Full detail: **`references/background-verification.md`**.
4. **Re-feed** happens at turn end via the stop-hook (below). Each re-fed turn is prefixed
   `[simplicio-loop iteration N. To finish: output <promise>TEXT</promise> ONLY when genuinely true.]`.
   Before re-feeding, the stop-hook (or the self-paced tick) runs the **stall check**
   (`loop_journal.py stall`): if the loop is STALLED, it does NOT blindly re-feed the same goal —
   it switches strategy or escalates (§ Run-journal + stall detector).
5. **Exit** by emitting the sentinel `<promise>EXACT TEXT</promise>` — and ONLY when every
   acceptance criterion is met AND a real gate passed **in the SAME turn** (`evidence_required`)
   AND the **watcher-gate** confirms the result (`watcher_state.json` with `match: true` /
   `status: MEASURED`). The watcher re-executes the work independently before the promise is
   honored — corrective gate per Asolaria N-Nest pattern.

## Three loop modes (termination dynamics + rigor level)

`converge`/`drain` answer WHEN a run is done (termination — unchanged here). `fast-path` (issue
#526 Etapas 1–2) answers a different question: how much PROCESS RIGOR does the current turn need.
Not a termination-axis peer of converge/drain — a reduced-rigor variant terminating under
converge's own rules. "Three loop modes" = three dynamics the scratchpad `mode` field + the
anchor's `route_mode` field jointly select, not three unrelated state machines.

A loop drains a queue and a loop converges a hard task — opposite dynamics, so the scratchpad
`mode` selects which termination logic the driver uses. Pick it when arming; default `converge`
for a single goal, `drain` for a work-queue, and `fast-path` only when mapper evidence proves a
small, low-fan-in, non-sensitive surface. Fast-path keeps the safety floor and promotes
monotonically to converge when the measured diff exceeds its limits.

| | `converge` (single hard task) | `drain` (a queue of items) | `fast-path` (measured small scope) |
|---|---|---|---|
| Wants | depth — keep changing strategy until ONE thing passes | breadth — clear many independent items, idempotently | lowest ceremony while the mapper evidence remains within limits |
| Each turn | triage `since` last turn (incremental) → one AC-scoped change → verify → watcher-gate → journal | claim next open item → implement → deliver → re-query source (the local Phase 0 backlog is a first-class source: re-query = `task_backlog.py next`; an `empty` print counts as a dry round, `dry≥2` unchanged) | preserve safety floor → edit → verify → measure real diff; promote on overflow |
| **Termination** | the evidence-gated `<promise>` fires, OR the **stall detector** says STALLED and escalates (below) | the source re-query returns empty for **K consecutive rounds** (`dry≥2`) AND the working set is idle | evidence-gated promise only after the same watcher/claims gates as converge |
| Anti-pattern it avoids | oscillation (retrying the same dead-end) | missing late-arriving work (stops too early) | ceremony bypass, unmeasured scope growth, and false fast-path claims |

Both still obey the universal exits (promise+evidence, `max_iterations`, STOP). The split
only changes WHEN "naturally done" is declared: `converge` is done when the one task is proven or
genuinely stuck; `drain` is done when the queue stays empty across rounds. Don't apply `drain`'s
"empty K times → done" to a single task (it would quit the moment a turn makes no visible change),
and don't apply `converge`'s stall-escalation to a queue (a stuck item should be quarantined, not
halt the whole drain).

### `fast-path` — the third mode: reduced rigor, decided by structure, escalated by evidence

At arming, `scripts/route_mode.py` (Etapa 1) reads ONLY the mapper survey (`project-map.json`/
`symbol-index.json`/`call-graph.json`) + the frozen goal — never an LLM guess. `fast-path` is
granted ONLY when the goal resolves to exactly one file, fan-in ≤1 (not a hub), no sensitive
surface (schema/migration/contract/lockfile globs). Vague/multi-file/hub/sensitive/no-survey all
fail closed to `converge` — no map, no hypothesis. Decision + numeric justification (`goal→1 file,
fan-in 1, no sensitive surface`) land on the anchor's `route_mode` and every turn-header. Only
supported flag forces `converge` from arming — none forces `fast-path`.

Every `fast-path` turn re-measures the hypothesis against the REAL diff (`scripts/diff_escalation.py`,
Etapa 2): `git diff --numstat` + `git status --porcelain` vs baseline, checked against configurable
limits (default ≤2 files, ≤80 lines, 0 new files, no sensitive surface). Overshoot **promotes** to
`converge` — same run/anchor/journal/scratchpad, contract just hardens — journaled with a
fingerprint. The reverse (`converge`→`fast-path` mid-run) never happens; promotion is monotonic.

| Gate | Full pipeline (`converge`/`drain`) | `fast-path` (until escalation) |
|---|---|---|
| In-turn evidence, secret-scan, journal, claims-gate | required | **identical** — safety floor never loosens |
| Full mapper survey | required every loop start | optional; incremental `scan` on demand |
| `simplicio-dev-cli task` (operator edit) | mandatory | waived — hand-edit OK IF a real verification gate (build/test/harness) runs same turn; edit w/o gate = incomplete turn, same severity as full pipeline |
| Watcher-gate | full anchor recomputation | re-execution of the turn's declared verification gate (cheaper, not absent) |
| DoD | full 7-dimension | adaptive per § "Definition of Done" above |

The same goal run in `fast-path` vs `converge` both reject an evidence-free `<promise>` identically
— only the PATH to that evidence narrows, never the requirement. `simplicio-tasks` Step 3 routes
fast-path/heavy-path on top of this mechanism.

## Phase 0 — intake & decomposition (no source / vague goal / genesis)

When the goal is vague and no external source (board/issues) supplies items, the LLM brainstorms
the decomposition — subtasks with ≥1 acceptance criterion each, `depends_on`, risks — and MUST
freeze it BEFORE any edit: `python3 scripts/task_backlog.py init --goal "<goal verbatim>"
--item-file plan.json` (the worker refuses an empty plan, a zero-AC item, or an unknown/cyclic
dependency — the AI decides, the worker freezes, orders and gates). State:
`.simplicio/orchestrator/backlog/backlog.jsonl`.

**Scaffolding a new repo.** Put exactly one explicit `scaffold` item first in `plan.json`
(structure + toolchain + one minimal green test as its ACs) and make every later item depend on
it. After that item passes, re-run `simplicio-mapper scan . --json` before claiming the next
item — the survey only becomes useful once there is code to map.

**Per-item cycle**: `python3 scripts/task_backlog.py next` claims one ready item and prints its id,
goal, lease owner, and fencing token → freeze that item's goal/ACs with `task_anchor.py set` → work
it under the normal converge contract → `python3 scripts/task_backlog.py done --item T1` (exit 12
unless the current anchor is this item with every AC verified) → `next` again. `status`/`poll`
provide the deterministic drain signal and active-lease view.
## HRM-style hierarchical planner (two-level reasoning loop)

Inspired by the **Hierarchical Reasoning Model** (arXiv:2506.21734, JesseBrown1980/HRM), the loop
runs a slow **high-level planner** (`scripts/hierarchical_planner.py plan`, called by
`loop_stop.py` before each re-feed) that MAY write a new **phase**
(`.simplicio/orchestrator/loop/phase.json`: `explore → debug → harden → refactor → implement → escalate`)
on top of the fast **low-level executor** (the normal per-turn re-feed, which executes one
AC-scoped change within the current phase and never changes it itself). Deterministic and
model-free; the loop runs flat if the planner script is missing. `hierarchical_planner.py status`
reads the current phase before deciding the next action; `plan` forces a replan; `clear` resets to
flat mode. Full phase table + usage: **`references/hierarchical-planner.md`**.

## Cross-agent persistent wiki (`.simplicio/orchestrator/wiki/`)

Every turn's key decisions, findings, and dead-ends are captured into a persistent markdown wiki
at `.simplicio/orchestrator/wiki/` (`scripts/cross_agent_wiki.py capture|summary|handoff|status`) — a
per-project, cross-agent, zero-friction knowledge base that survives across agent vendors (Simplicio Agent
→ Claude Code → Codex): a fresh agent reads it and sees "where we left off" with no transcript.
Plain markdown, no vector DB. Full structure + per-turn mechanics:
**`references/cross-agent-wiki.md`**.

## Run-journal + stall detector (the loop's working memory)

A re-feed loop with no memory of its own attempts **re-derives the same triage every turn** and
**oscillates** (tries X, fails, tries X again until the cap burns). `scripts/loop_journal.py`
closes both, deterministically: the **run-journal** (`.simplicio/orchestrator/loop/journal.jsonl`,
append-only, one record per turn with a normalized failure **fingerprint**) is the loop's memory
of WHAT WAS TRIED; the **stall detector** (`loop_journal.py stall`) returns `PROGRESS | STALLED` —
STALLED means the last **K** (default 3) attempts share the same fingerprint, and names the
dead-end actions to avoid. Full mechanics: **`references/run-journal-stall-detector.md`**.

```bash
python3 scripts/loop_journal.py resume            # triage: distinct actions tried + AVOID list
python3 scripts/loop_journal.py record --iteration N --action "<change>" \
    --hypothesis "<why>" --gate pass|fail --gate-output <test.log>
python3 scripts/loop_journal.py stall --k 3 --exit-code   # before re-feeding: PROGRESS or STALLED
```

STALLED means do NOT re-feed the same goal into the same failure — switch strategy, escalate to
the human_gate with the fingerprint + dead-ends, or (headless) stop blocked. This upgrades
invariant 3 (Deterministic continuation): the next iteration re-feeds the goal **and** the attempt
memory.

## Progress feedback (issue #298, EPIC #296)

`scripts/loop_progress.py` is the ONE place "onde estamos / quanto falta" is computed —
deterministically, from `task_backlog.py` items + `task_anchor.py` ACs + its own event trail, never
fabricated. It writes `.simplicio/orchestrator/loop/progress.jsonl` (events), `progress.json` (snapshot,
never authoritative — always recomputed) and `PROGRESS.md` (human render). Every stage calls
`emit`; the transcript re-feed header calls `render --turn-header`. Full contract:
**`references/progress-feedback.md`**.

```bash
python3 scripts/loop_progress.py emit --step operate --status begin --item T3
python3 scripts/loop_progress.py render --turn-header   # MEASURED|... 42% geral · iter 7/24
python3 scripts/loop_progress.py status --json          # machine-readable snapshot
```

Delivery/entrega (issue #301): `web_verify.py`/`video_evidence.py`/`pr_evidence.py build` all emit
`evidence` begin/end/blocked; `pr_evidence.py build` auto-includes a `## Progresso do run` section
whenever a backlog/anchor exists (never a fabricated %); `pr_evidence.py progress-comment --issue N`
publishes ONE idempotent, rate-limited, fail-open progress comment on the issue. `hooks/loop_stop.py`
emits the final `refeed_exit` event on every stop path, so `progress.json`'s `run_state`
(`running|done|capped|handoff|stopped`) never stays stuck mid-run.

## The promise is evidence-gated (the simplicio hardening) + watcher-gate (pre-promise)

The classic Ralph loop trusts the model to be honest. We do not. A `<promise>` is accepted
only if, in the SAME turn, there is concrete evidence the work is truly done, AND the
**watcher-gate** has independently verified the result:

- the **watcher-gate** — `python3 scripts/watcher_verify.py verify` independently recomputes the
  anchor's done/pending state and writes `.simplicio/orchestrator/loop/watcher_state.json` with `{"match":
  true, "status": "MEASURED"}` only when it agrees AND echoes the current per-iteration challenge
  (`watcher_challenge.json`) — never hand-write this file, or
- the run-verification gate passed ("works, not just compiles") — the `simplicio-dev-cli`
  operator's passing test+verify satisfies this, or
- the flow coverage gate passed for a mixed front/back/service change —
  `python3 scripts/flow_audit.py audit <root> --fail-on high` found no unhandled UI/API/service
  gaps (mechanically required by the stop-hook whenever the diff touches web-surface files), or
- the scope/impact gate passed for changed shared files — `impact_audit.py audit <root> --file
  <seed> ...` found no uncovered reverse dependents, or
- each named acceptance criterion has a `file:line`/command-output receipt — mechanically
  enforced by `python3 scripts/task_anchor.py gate --exit-code` (must return READY; exit 12 =
  still pending, a contract violation exactly like missing evidence), or
- for a queue, the source re-query confirms the items are actually closed/merged, or
- a **demo video** — a deterministic MP4 via the `video_evidence` producer (above) whose ledger
  row + MP4 path prove the feature works end-to-end; REQUIRED when the goal itself was "make a
  demo video of screen X".

A `<promise>` with no evidence in-turn — OR with a failing watcher-gate — is a **contract
violation**: the capture hook ignores it (does not raise `done`) and the loop continues.
**Never output a false promise to escape the loop.** This wires the loop directly into the
repo's hard rule: *never close work without a merged PR or concrete evidence.*

**Closing is evidence-gated too (no false positives).** Declaring an item done — or closing an
issue — requires BOTH a live source re-query (the item is actually still open right now) AND
concrete evidence in the code or a linked/merged PR. A self-reported "done" with no live state
and no artifact is a false positive and is rejected, exactly like a bare promise.

## Claims-gate discipline — MEASURED/UNVERIFIED tagging

Every claim the loop makes — in the journal, in triage, in the exit promise, or in any turn
output — MUST be tagged `MEASURED\|` (backed by in-turn, concrete, non-model evidence: a passing
gate, a `file:line` receipt, a test log) or `UNVERIFIED\|` (an inference, hypothesis, or
best-effort summary with no mechanical proof this turn). This is the Asolaria claims-gate
discipline (eight enforcement rules — ground-impact-first, no bare tuples, mirrors≠authority,
etc.), so no output escapes without a truth-class label. `loop_journal.py record`/`resume`/
`status`/`stall` all auto-tag their output; `loop_journal.py claims-gate --check` audits any blob
for untagged claims. Full eight-rule table + worked examples: **`references/claims-gate.md`**.

## Binding the hook (deterministic, near-zero token)

Where the host runtime supports lifecycle hooks, bind the two cross-platform hooks shipped in
`hooks/` (Python, so they run identically on Windows/macOS/Linux — see `hooks/hooks.json`):

| Hook | Fires | Job |
|---|---|---|
| `afterAgentResponse` → `loop_capture.py` | after every turn | extract `<promise>…</promise>`; if it exactly equals `completion_promise` AND in-turn evidence exists → `touch .simplicio/orchestrator/loop/done`. Fire-and-forget, `exit 0`. Never stops the loop itself. |
| `stop` → `loop_stop.py` | when the turn ends | guard clauses that each end the loop cleanly: no/corrupt scratchpad → stop; bound operator missing → write `HANDOFF.md`, stop (never silently hand-survey/hand-edit); `done` flag present → stop; `iteration >= max_iterations` → `HANDOFF.md` + stop (cap); spindle handoff latched → `HANDOFF.md` + stop. Before the promise check it runs the **watcher-gate** (rejects on `match: false`/stale challenge) and the **flow-audit gate** (rejects a web-touching diff with no fresh green `flow-audit.json`); a fallback journal record fires if the turn forgot one. Else increments `iteration` and re-feeds `{"followup_message": "<header>\n\n<goal body>"}`. |

Detection (`capture`) and termination (`stop`) are split on purpose — neither parses the
other's inline state. Iteration carries forward through git history + the working tree, not
context stuffing, so token cost per cycle stays flat.

## Self-paced drive (no hooks — a first-class path)

Hooks are an optimization, not a requirement: the self-paced drive is a primary way to run this
loop, equal in standing to the hook-bound one. When the host has no hook layer — or hook delivery
is not guaranteed — self-pace the loop with the host scheduler, exactly the `simplicio-tasks`
watcher mechanism (Step 3b "Arming the watcher"). Default to self-pacing whenever hook delivery is
uncertain rather than assuming a hook will re-feed the goal:

- Host-native durable scheduler / OS cron / a session `/loop` re-invoking this skill.
- Each tick: `render --turn-header` first (echoed) → read scratchpad → do one iteration → check
  the promise+evidence → `render --full` last (regenerates `PROGRESS.md`) → if true, delete state
  and stop; else increment and reschedule.
- Same exit conditions: promise verified, cap reached, spindle handoff latched, or explicit STOP.

## Cancel

Delete `.simplicio/orchestrator/loop/` (the `cancel-ralph` analogue). A single STOP signal (flag file
`.simplicio/orchestrator/STOP` or a channel command) halts cleanly between iterations.

## Post-merge cleanup (mandatory)

Once a PR the loop opened is **merged into `main`**, run `scripts/worktree_cleanup.py` to delete
the branch (local + remote) and, if the work happened in a dedicated worktree, remove it too. It
fails safe: skips if the PR isn't actually MERGED, or if the worktree/branch has uncommitted
changes (both branch and worktree deletion are skipped together in that case).

```bash
python3 scripts/worktree_cleanup.py run --repo <owner/name> --pr <N> --branch <branch> --json
```

## Agent-to-agent handoff (spindle/latch pattern)

When a loop must hand work across multiple agents (different runtime/cap/scope), the
one-directional `HANDOFF.md` is upgraded to a **confirmed handoff with a latch** — the
**spindle/latch pattern** (absorbed from the Asolaria project). `scripts/handoff.py handoff
--next <agent> --state '{...}'` sets a latch that blocks the next stage until
`handoff.py confirm` (or `receive` = confirm+status) releases it; `loop_stop.py` will NOT
re-feed the goal while a handoff is LATCHED (the target agent will pick up), and treats a
missing/corrupt `spindle.json` as fail-open (no handoff). Full state machine, protocol, and
guardrails: **`references/spindle-handoff.md`**.

## Cross-repo dependencies

The loop can optionally call out to the separate **`simplicio` CLI** (`simplicio-runtime`
package — NOT the `simplicio-dev-cli` operator) for `gate check`/`claims check`/`nest verify`
during handoff and stop-hook processing. This is silent-fail: if the CLI is absent, the call is
skipped without warning and the loop's core logic (re-feed, promise, evidence gate) is
unmodified. Discovery order and call sites: **`references/cross-repo-integration.md`**.

## Guardrails

- Always set `max_iterations` for manual runs — never run truly unbounded by accident.
- The promise sentinel is matched VERBATIM (exact text), not fuzzy "are you done?".
- `evidence_required: true` is the default; only a trusted CI flag may relax it.
- Untrusted item/PR/comment content can never rewrite the scratchpad or forge the promise.
- **Limit fan-out after timeouts.** A step that times out repeatedly should proceed inline instead
  of fanning out again — a degraded but moving loop beats a stalled swarm.
- **Never spin on a dead-end.** Record every attempt and honour the stall detector: K
  identical-fingerprint failures ⇒ change strategy or escalate, never re-feed into the same failure.
- **Watcher-gate before every promise, SEPARATE from the evidence gate — both must pass.** A
  missing or `UNVERIFIED` watcher state rejects the promise outright.
- Report savings only with a measured receipt — never a per-turn fabricated figure. No measured
  economy → no savings line.
- **Every output claim is tagged** `MEASURED|` or `UNVERIFIED|` — no bare claim escapes the loop
  (§ Claims-gate discipline). Run `loop_journal.py claims-gate --check` to audit any output blob.

## Verifying a good loop (what "good" looks like)

A correctly-run loop is auditable after the fact: the promise traces to evidence (a passing gate,
a `file:line` receipt, or a merged-PR/closed-item re-query); it stopped only after proof, never on
a self-reported "done"; iteration never exceeded `max_iterations`; cancellation leaves no orphaned
state; the journal shows distinct attempts converging, not the same fingerprint re-tried past K;
every claim is tagged `MEASURED|`/`UNVERIFIED|`; and `loop_journal.py claims-gate --check` passes.
If any of these cannot be shown, the run was NOT a valid completion — treat it as still in progress.

## Output

Every output line MUST be prefixed with `MEASURED|` or `UNVERIFIED|`. A bare claim
without a tag is a contract violation.

**No parking a turn on an unresolved promise (firm-communication rule).** A turn must never end
with a vague "I'll wait for it and report back" / "monitoring in the background, will follow up"
placeholder that carries no concrete state — that phrasing reads as progress but is not: nothing
was checked, nothing is tagged, and control may never return to read the result (background
verification, § `references/background-verification.md`, changes WHEN you block, not WHETHER a
turn is honest about what it actually knows right now). Two, and only two, valid endings for a
turn that launched a background check:
1. **Block on it before ending the turn** if the turn's own claims depend on it — poll/await the
   result synchronously, read the real output, tag it `MEASURED|`/`UNVERIFIED|`, THEN end the turn.
2. **If genuinely deferring to a later turn**, say so with the same rigor as any other claim: name
   the exact command still running, the exact condition that will resolve it (PID exit, file
   written, notification received), and tag the whole thing `UNVERIFIED|still running: <cmd>,
   resolves on <condition>` — never phrase a pending result as if it were already handled, and
   never let "waiting" substitute for the turn-header/`próximo passo` requirements below.
A sibling session, a coordinator, or a human reading only this turn's output must be able to tell,
without opening a log file, whether the claimed work is DONE-AND-VERIFIED or STILL-IN-FLIGHT. If
that isn't unambiguous from the turn's own text, the turn is incomplete — same severity as a turn
without verification or without the turn-header.

**Turn-header contract (issue #302).** The FIRST line of every turn's response MUST be
`python3 scripts/loop_progress.py render --turn-header`, echoed verbatim — a turn without it is
incomplete (same severity as a turn without verification). The LAST section MUST include a line
`próximo passo: <next step>`. On hook-bound runtimes (Claude, Cursor) `loop_stop.py` ALSO prefixes
the re-feed header with the same snapshot, fail-open — the user sees the % even if a turn forgets
to narrate it. Self-paced runtimes (no hooks) run the same `render --turn-header` at tick-start and
`render --full` at tick-end (§ Self-paced drive). Full contract: `references/progress-feedback.md`.

Confirm the loop is armed (goal, cap, promise, hook-bound vs self-paced), then start
iteration 1 immediately.

<!-- simplicio-global-llm-architecture-rules:start -->
## Regras arquiteturais globais (obrigatórias)

- Delete diretamente o que está obsoleto; não preserve compatibilidade retroativa,
  não crie migrações e não deixe fallbacks.
- Escolha a implementação mais simples para a necessidade atual; sem abstrações
  preventivas ou configuração desnecessária.
- Entregue primeiro o mínimo end-to-end e evolua por camadas longas, sem desmontar
  o que funciona por complexidade inacabada.
- Mantenha modularidade e separação clara de responsabilidades.
- Prefira bibliotecas maduras e mantidas; reescreva do zero apenas com motivo
  técnico explícito.
- Inspecione as dependências existentes antes de adicionar pacotes ou reimplementar.
- Tome decisões arquiteturais para o longo prazo; não deixe soluções temporárias.
- Reutilize padrões validados por produtos maduros; não reinvente a roda.

<!-- simplicio-global-llm-architecture-rules:end -->


## Runtime integration boundary (normative, 2026-08-05)

Runtime decides whether Loop is active when Runtime is available. Mapper and Fast remain separate peer
decisions, while Dev CLI is nested only under `loop.dev_cli`. A typical active
implementation path may be `mapper -> fast (when anchored) -> loop.dev_cli ->
simplicio edit -> validate`; the actual hops remain evidence-driven.

The Loop package remains standalone-capable when Runtime is absent. In that mode
use the portable Loop operators, mark `runtime-integration=degraded`, and never
claim Runtime activation, Runtime authority, or consolidated Runtime evidence.

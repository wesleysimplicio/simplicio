# Bound operators — survey + operate (full detail)

Moved out of `SKILL.md` § Bound operators as part of the #119 shrink (SKILL.md keeps only the
operator table, the preflight one-liner, and the BLOCK rule; this file has the full mechanics).

This loop does NOT survey the repo with the LLM, and it does NOT hand-edit files with the LLM.
Two installed CLIs are the operators; the model only DECIDES, the operators do. A normal
`pip install simplicio-loop` requests both distributions directly: `simplicio-cli` exposes
`simplicio-dev-cli`, and `simplicio-mapper` exposes the survey binary:

| Operator | CLI (binary) | Binds | Role in the loop |
|---|---|---|---|
| **simplicio-mapper** | `simplicio-mapper` | `orient` / `recall` | **Survey** — maps the repo(s) into `.simplicio/*.json` (project-map, precedent-index, symbol-index, call-graph, docs). Two-tier (v0.9+): `macro` is an instant shallow skeleton (no content reads), `scan` returns that skeleton now and runs the deep index in the background, `status` reports the deep-pass phase. v0.13+ adds `inspect` (machine-readable evidence that the artifacts actually exist — the survey's own evidence gate) and `handoff` (a compact context-pack — files, symbols, deps, `pack_hash` — that feeds the goal instead of re-reading the tree). v0.14+ adds the flow-docs engine: `ask` (low-token structured queries over the artifacts), `sync --check`/`drift --check` (docs-staleness + spec-drift gates), `flows`/`survey`/`business`/`history`/`diff` (flow inventory, onboarding report, business rules, architecture history). This survey, not an ad-hoc LLM read, is what feeds the goal each turn. |
| **simplicio-dev-cli** | `simplicio-dev-cli` | `execute` / `deterministic_edit` / `validate` / `diagnostics` | **Operate** — applies a DECIDED change through its 6-layer contract (mapper context → precedent → prompt → diff → test → verify, ≤3 retries). The CLI edits and verifies; the AI does not hand-write the diff. |

**Preflight (MANDATORY, BLOCKING).** Before iteration 1, auto-update the operator package to its
latest release (so every run uses the newest `simplicio-cli`-shipped `simplicio-mapper`/`simplicio-dev-cli`),
then confirm both runtime binaries are on
PATH:
```bash
# Always run the loop on the latest operators. FAIL-OPEN: offline / no-pip / a pin keeps the
# currently-installed build; this never blocks. Runs ONCE per loop preflight, not per turn.
python3 -m pip install -qU simplicio-cli simplicio-mapper 2>/dev/null \
  || python3 -m pip install -qU --user simplicio-cli simplicio-mapper 2>/dev/null || true
simplicio-mapper --version   # survey operator (direct simplicio-loop dependency)
simplicio-dev-cli --help     # action operator (pkg simplicio-cli; exposes `simplicio-dev-cli`)
```
The auto-update is best-effort and offline-safe — a network/pip failure leaves the working version
in place and the loop proceeds. The action binary is `simplicio-dev-cli` — NOT the bare
`simplicio`, which is reserved for the separate `simplicio-runtime` and is not what this loop
binds. `simplicio-dev-cli` has no `--version` subcommand; `--help` exiting 0 is the readiness
proof. If either runtime binary is missing or incompatible, the runner performs one bounded
`pip install -U simplicio-cli simplicio-mapper`, writes `operator-bootstrap.json`, validates
both binaries, and retries the blocked stage once. If repair fails, do NOT fall back to LLM
survey/editing; remain `BLOCKED`. This requirement is scoped to the loop drive.

**Survey step (each loop start + on any structural change).** Prefer the two-tier flow (v0.9+):
`simplicio-mapper scan . --json` returns an instant `macro` skeleton AND kicks the deep index off in
the background — the loop starts working immediately instead of blocking on a full crawl. Poll
`simplicio-mapper status . --json` (`phase`: `deep_running` → terminal) before relying on the deep
artifacts; pass `--await [--timeout <s>]` to block until terminal, or `scan --sync` (forced when
`CI=true`) for the old single-shot behavior. `simplicio-mapper index . --json` (add `--watch` for
long runs) remains the synchronous full (re)build of `.simplicio/`. Read the survey artifacts —
never re-scan the tree by hand when a fresh map exists. For a multi-repo survey, run the mapper per
repo root and aggregate the JSON.

**Survey evidence gate + context-pack (v0.13+).** Before trusting the deep artifacts, gate on
`simplicio-mapper inspect . --json [--await]` (`simplicio.map-inspection/v1`): it reports, per
artifact (project-map, precedent-index, symbol-index, call-graph, index-state, map-job,
context-cache), whether the file **exists on disk** with size + mtime, plus `warnings`. An artifact
the inspection says is missing must be treated as absent — re-run `scan`/`index`, don't guess its
content. This is the same evidence-not-claims discipline the promise gate applies, applied to the
survey itself. Then feed the goal from `simplicio-mapper handoff . --for-llm toon [--await]`
(`simplicio.map-handoff/v1`, TOON-rendered — same discipline as `task_anchor.py check --format
toon` / `loop_journal.py stall --format toon`, #92): its `context_pack` carries the relevant files
with symbols, imports, dependencies, `recent_changes` and a `pack_hash` — a pre-compressed
orientation bundle that substitutes for re-reading the tree (token economy: pack first, raw `Read`
only for the few files the pack points at). If `simplicio-mapper handoff --help` doesn't list
`--for-llm` (older install; the preflight auto-update above should already prevent this), fall back
to `handoff . --json` and record WHY, machine-readably, so the gap is visible in the journal, not
just silently absorbed: `python3 scripts/loop_journal.py record --iteration N --action "mapper
handoff" --gate pass --decision fallback-json --next-action "upgrade simplicio-mapper for
--for-llm toon"`. Honor `context_pack.llm_directives` (no-think / no-internet / minimal tools)
for the mechanical steps, and use `needs_broader_context` as the signal that the pack alone is not
enough.

**Structured queries + docs gates (v0.14+).** For triage questions the map alone doesn't answer,
query the built artifacts instead of grepping the tree:
`simplicio-mapper ask . <callers|callees|reaches|impact|flows|rules|tests-for|term> <arg> --json`
(`simplicio.ask/v1`) — e.g. `ask . impact src/api.py` before an edit (which flows/dependents does
this touch — feeds the `dependency_graph` widening), `ask . tests-for <symbol>` to pick the
affected tests to run, `ask . callers <symbol>` during review. Two mechanical verify-side gates
join the DoD pass: `simplicio-mapper sync . --check --json` (`simplicio.docs-sync/v1`) reports
generated docs now stale relative to the diff, and `simplicio-mapper drift . --check --json`
(`simplicio.spec-drift/v1`) reports spec↔code drift (orphan spec refs, unresolved placeholders,
stale docs) — surface their findings in the turn report; they BLOCK only when the task's own AC is
documentation. For an explicit docs/onboarding task, the producers are `flows` (end-to-end flow
inventory), `survey` (new-developer onboarding report), `business` (observable business rules +
glossary), and `history`/`diff` (architecture snapshots + semantic deltas).

If the installed mapper predates 0.13 (`inspect`/`handoff` absent from `--help`), the
preflight auto-update already pulls a current build; offline, fall back to `status` + reading
`.simplicio/*.json` directly — the gate is then the file-existence check you do by hand.

**Operate step (every turn that mutates code).** Once the AC and the change are DECIDED, delegate
the mutation to the operator, one decided change at a time:
```bash
simplicio-dev-cli task "<the decided, AC-scoped change>" --target <file> [--json]
```
The operator applies the diff, runs the tests, and self-corrects up to 3× — its passing
verification IS the in-turn evidence the promise gate needs (see SKILL.md § The promise is
evidence-gated). The AI never edits the file directly inside the loop; if `simplicio-dev-cli`
cannot complete a change after its retries, treat that as a genuine blocker to investigate, not a
reason to hand-edit around it.

**Where each operator fires.** The AI only DECIDES (triage, AC extraction, choosing the change,
merge/close gates); the operators do survey + apply:

| Phase | Operator | Command |
|---|---|---|
| Preflight (before iteration 1) | both | `python3 -m pip install -qU simplicio-cli` (auto-update to latest, fail-open) → `simplicio-mapper --version` · `simplicio-dev-cli --help` → BLOCK if either runtime bin is missing |
| Survey (loop start; multi-repo: per root) | mapper | `simplicio-mapper scan . --json` (instant macro + deep index in background; `--sync`/`--await` to block) → `.simplicio/*.json`. `index . --json` for a forced synchronous build. Gate: `inspect . --json` (artifacts exist on disk) → feed goal: `handoff . --for-llm toon` (context-pack, TOON-rendered; `--json` fallback + logged reason if the installed mapper predates `--for-llm`) |
| Loop contract step 2 — Triage (every turn) | mapper | `simplicio-mapper handoff . --for-llm toon` → work from the `context_pack` (symbols/deps/recent_changes); `ask . impact\|tests-for\|callers <arg> --json` for targeted questions; `macro . --json` for an instant skeleton, or `scan`/`status` + `inspect` to refresh/re-gate if the tree changed |
| Verify / DoD pass | mapper | `simplicio-mapper sync . --check --json` (stale generated docs) + `drift . --check --json` (spec↔code drift) — findings go in the turn report; BLOCK only when the AC itself is documentation |
| Loop contract step 3 — Work the goal | dev-cli | `simplicio-dev-cli task "<decided change>" --target <file> [--json]` |
| Evidence-gated `<promise>` / `simplicio-tasks` Step 4b | dev-cli | the operator's passing test+verify pass = in-turn evidence |

One turn: `preflight → survey (mapper) → triage (re-read survey) → DECIDE (AI) → operate
(simplicio-dev-cli task: apply+test+retry ≤3×) → watcher-gate (independent re-execution) → <promise> only if all gates passed`.

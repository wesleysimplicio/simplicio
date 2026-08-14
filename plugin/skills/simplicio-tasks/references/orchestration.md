# Orchestration — discover, intake, route, scale, speed (Steps 2–3d full detail)

## Step 2 — Discover + normalize work-items
**Resolve the SOURCE ADAPTER first — do not assume GitHub.** Detect which connector is available
and authed, then use it. Never claim a source works without a live connector.

| Source | Adapter (if present + authed) |
|---|---|
| GitHub Issues/PRs | `gh` CLI (native) |
| Jira / Asana / ClickUp / Linear / Monday / Notion | the host's connector for that source |
| Trello / Azure DevOps | host connector, else the `az boards` adapter (`scripts/az_boards_adapter.py`, see `azure-devops-adapter.md`) |
| agentsview sessions | `scripts/agentsview_adapter.py` (see `agentsview-adapter.md`) | session observability, recovery of stalled sessions |
| local files / CI queue | filesystem / CI API |
| vague goal / no reachable board | the LOCAL BACKLOG — `scripts/task_backlog.py` (the frozen LLM decomposition, `.simplicio/orchestrator/backlog/`; SKILL.md § Phase 0) |

If the target source has no reachable adapter, STOP and report it as a blocker (do not silently
fall back to GitHub). Each adapter exposes: list_ready (metadata-only), get_details, claim,
update_status, attach_evidence, close.

List candidates by METADATA only (titles, labels, status) — do not open every body. Normalize to
the canonical schema (title, body, labels, status, acceptance-criteria, links). Dedup by
source-id + normalized-title + problem-fingerprint AND by existing branch/PR (idempotency — never
double-implement; parallel double-implementation of the same item is a real, observed failure).
Count independent items → drives scale. Maintain a persistent `seen` set. Discovery re-runs
continuously (Step 3b).

## Step 2b — Deep item intake (MANDATORY before any implementation)
Triage is metadata-only; implementation is NOT. An agent that skips this produces generic code.

**2b-1 Read the full item (body + ALL comments).** `get_details` → title, body, labels,
assignees, milestone, acceptance_criteria, comments, linked_prs, linked_items.
- Extract explicit **acceptance criteria** (numbered, checklists, "done when…"). If none stated,
  derive + record them. An item that obviously should have ACs but has none is a BLOCKER — ask
  ONE line, don't guess. With a VAGUE goal and no source at all, decompose first (brainstorm the
  subtasks + per-item ACs + `depends_on`) and freeze the plan with `python3
  scripts/task_backlog.py init --goal "<goal>" --item-file plan.json` (SKILL.md § Phase 0). For a
  genesis repo, make one explicit `scaffold` item T1 in that input and make every later item
  depend on T1.
- Extract design decisions/constraints/rejections from comments ("don't use X", "must integrate
  with Y", reviewer requests) — these override naive title reading.
- Note linked items/PRs and check status — a blocked dependency is flagged, not ignored.

**2b-2 Orient the codebase.** Before writing a line: existing files/modules (rg/git grep),
recent commits touching them (`git log -- <files> -5`), function/type signatures in scope,
TODO/FIXME, overlapping open PRs. An implementation that duplicates existing code or ignores an
adjacent module is wrong even if it compiles. Use **signatures-only reads** (bodies elided) for
API surface — a 600-line file → ~40 lines; full-body read only when editing the body.

> **Understand Anything (optional).** When `.understand-anything/knowledge-graph.json` exists, use the knowledge graph as the primary orientation — guided tours for architecture, semantic search to find specific modules, instead of signatures-only reads.

**2b-3 Build the plan BEFORE coding:** files to change, files to read first, AC checklist, risks/
unknowns, complexity (trivial|small|medium|large|critical). Coding starts only after the plan.
Make the plan mechanically accountable with the impact audit:

```bash
python3 scripts/impact_audit.py audit <root> \
  --file <seed-you-expect-to-touch> \
  --cover <files-already-in-plan> \
  --fail-on high \
  --json > .simplicio/orchestrator/impact-audit.json
```

Treat a `high` issue as a planning failure: a caller/dependent file sits outside the declared task
surface, so the plan is incomplete. For shared/public contracts, signature changes, DTO/schema
changes, or refactors inside widely imported modules, tighten the gate to `--fail-on medium` so
uncovered local dependencies and related tests also block the plan. The point is to know the blast
radius before editing, not after the regression.

## Step 3 — Route: minimum fleet vs scaled fleet

**Hard floor: every run keeps ≥6 orchestrated agents in flight — no solo/inline path.** A single
TRIVIAL item is decomposed by ROLE, not by work-item count, so the floor holds without inventing
parallel work that doesn't exist:

| # | Role | Cardinality |
|---|---|---|
| 1 | Orient + plan (Step 2b) | 1 agent |
| 2 | Implement (Step 4) | 1 agent (2 on MEDIUM+: a fast-follow pair) |
| 3 | Review — Rubric A: security & correctness (`simplicio-review`) | 1 agent |
| 4 | Review — Rubric B: quality & maintainability (`simplicio-review`) | 1 agent |
| 5 | Review — Rubric C: does-it-reproduce / runtime (`simplicio-review`) | 1 agent |
| 6 | Independent blast-radius reviewer — re-checks Step 4a' `impact_audit.json` (and `flow_audit.json` when applicable) as a second set of eyes, not the implementer self-grading its own scope claim | 1 agent |

Roles 1–2 are sequential (plan before implementing); roles 3–6 spawn in ONE message so they run
concurrently — wall-clock down, no proportional token blow-up (`simplicio-review` Step 2 pattern).
Rubric C's heaviest sub-checks (`web_verify`, `flow_audit`) stay conditional on the diff actually
touching that surface — the rubric runs always, its expensive evidence requirements stay scoped.

- **Minimum fleet** (queue small AND every item complexity ≤ 3): the 6-role floor above runs on
  the single item. There is no solo/self-review shortcut left to fall back to — the floor IS the
  minimum, never undercut it. Finish → Step 6.
- **Scaled fleet** (large queue OR any medium+ item): fan out beyond 6. Compute the fleet, keep a
  CONTINUOUS WORKER POOL fed by a LIVE queue (not frozen waves) — a freed worker pulls the next
  item, even one that appeared seconds ago. Serialize same-file items (conflict detection).
  Quarantine items that fail K times to a dead-letter list.

**Worker report contract (every worker MUST follow).** A worker result is re-injected into the
orchestrator context verbatim and consumes context on EVERY delegation. Forbid narration; mandate the
terse MACHINE-tier schema:
```
<status>          # FIRST line, one token: done | blocked | too-big | needs-human | regressed | ambiguous
<file:line refs>  # evidence as path:line with `backticked` symbols, not prose
<counts>          # totals only ("3 files, 2 tests added, 0 failing")
<body>            # present ONLY when status is non-terminal; else omit
```
The orchestrator parses the status token deterministically and reads the body ONLY on a
non-terminal status. A done/blocked worker returning paragraphs is a contract violation — reprompt.

**Corrections memory.** When a command fails and a near-identical one succeeds within ~3 commands,
record `{wrong→right, error-class, count}` via `learn`/`recall`. Classify (unknown-flag,
command-not-found, wrong-syntax, wrong-path, missing-arg, permission-denied), keep pairs >~0.6
similarity, dedup with a count, EXCLUDE human-rejections and compile/test failures (those are the
Step 4 loop). Feed the top corrections into the shared digest so agents pre-empt them next session.

### Auto-scaling (use `autoscale` if bound; else this formula)
```
cap_cpu  = max(1, floor((cores - 2) / 2))
cap_mem  = floor(free_gb / 2)
cap_disk = (free_disk_gb < 10) ? 0 : (free_disk_gb < 25 ? 1 : 99)
fleet    = max(6, min(cap_cpu, cap_mem, cap_disk, independent_items, 16))   # 6-agent floor, 16/wave cap
waves    = ceil(queue_size / fleet)
```
If resources unknown or disk < 10 GB, the 6-role floor still runs — switch isolation to
`isolation=shared` (one checkout, sequential commits on overlapping files) instead of
worktree-per-item, so the floor is met without the disk cost of 6 separate worktrees.

**Worktree-per-item isolation (DEFAULT) + a cost opt-out.** Each item gets its OWN
`git worktree add` checkout by default, so parallel workers never touch the same tree and there is
ZERO cross-item conflict — the simplest model to reason about. Each item's branch follows the
learned `repo_conventions` profile (Step 1a' — `repo_conventions.py branch --type <t> --slug
<title>`), not a generic `agent/{id}` name, so the delivered branches match the repo's own style.

The one **opt-out** is resource pressure: a worktree is expensive for a big COMPILED project (fresh build/target dir +
disk per item). When the toolchain is heavy-compile AND items are many, fall back to conflict-AWARE
sharing: predict the file-overlap graph; items in DISJOINT files share ONE checkout, committing
sequentially on their own branches; only OVERLAPPING items serialize. Select the mode up front
(`isolation=worktree` default · `isolation=shared` for the compiled-project case) and state which.
Per item: isolated branch, its own evidence, a wall-clock timeout. Per wave: implement →
review+autofix → collect. After all waves: merge + close. Prune worktrees on teardown (Step 7).

## Step 3b — Continuous intake (see NEW work at ANY moment)
**Layer 1 — intra-run poller** (~2 min, in parallel with the pool): list via adapter
(metadata-only) → normalize → subtract `seen` → enqueue genuinely-new ready items into the LIVE
queue; the pool pulls as a slot frees. ALSO poll this run's open PRs (failed checks, new
review/requested-changes, branches behind main) → reopen the feedback loop (Step 6b). **Reset
`dry=0` whenever the poll finds anything new.** The run FINISHES only when queue empty AND no
worker busy AND `dry >= 2` consecutive empty polls (plus hard stops: time-box, scope, STOP).

**PR patrol cadence (mandatory, non-blocking).** After every **two** work-items are delivered
and their PRs are open, run the read-only patrol before starting the next delivery wave:
`python3 scripts/pr_patrol.py --repo <owner/name> --completed-items <N>`. It classifies open
PRs as conflict/rebase, review-required/requested-changes, failed checks, or clean; every
actionable result returns to Step 6b instead of being deferred. Run the same patrol with
`--final` before the run can claim completion. It is a priority signal, not a queue lock: local
work may continue while independent PR repair workers run.

**Cross-agent acceptance review.** A patrol may review PRs opened by any provider (Claude,
Codex, Cursor, Gemini, Kiro, Antigravity, Hermes/Simplicio Agent, OpenClaw, or a human). Fetch
the review packet first, inspect the diff against the explicit AC checklist and its evidence, then
publish/update exactly one marked PR comment:
`python3 scripts/pr_patrol.py review --repo <owner/name> --pr <N> --verdict accepted|changes_requested|unverified --note "<concrete evidence>" --publish`.
`accepted` is rejected unless every explicit criterion is checked and carries evidence; this is a
coordination receipt, **not** an automatic GitHub approval. Missing ACs/evidence must be commented
as `unverified`, never silently accepted. Conflict/rebase/failed-check findings return to Step 6b.

**GitHub issue signature before work.** Before any provider starts an issue, it must claim/sign
the source issue with the canonical `CLAIMED` lifecycle comment (worker/run/attempt identity and
goal) using `github_lifecycle.py publish`. Do this before editing or opening a worktree; never
take an issue already claimed by another live worker. PR reviewers keep the issue lifecycle state
intact and sign their independent AC assessment on the PR comment instead.

**agentsview (optional).** If configured (`scripts/agentsview_adapter.py` authed), poll
agentsview for stalled sessions each cycle and convert them into work-items of type 'resume
abandoned session'.

**Layer 2 — idle watcher** (nothing running): a recurring trigger re-invokes the skill; near-free
when idle, launches a run when new work exists. See standing-loop-247.md.

**Guards:** idempotency (never re-pick a `seen` item); dead-letter (K failures → no re-intake);
scoped runs (a pinned list disables re-discovery + watcher — finish exactly that set);
conflict-serialization for newly-arrived same-file items.

## Step 3c — Speed model (velocity without sacrificing quality)
1. Pipeline, not barrier (item A merges while B builds). 2. Shared compile cache (e.g. `sccache`).
3. Verify once: each agent runs a scoped incremental check; the full suite runs EXACTLY ONCE on
the merged result. 4. Front-load shared context (orient once, share the digest). 5. Tier scope,
not tier skip: the Step 3 6-role review fan-out (roles 3-6) runs on EVERY item regardless of
tier — only Rubric C's heaviest sub-checks (web/flow evidence) stay scoped to MEDIUM+ or
surface-touching diffs; a TRIVIAL item still gets the full review, just lighter individual
checks within it. 6. Pre-warm the build on clean main. 7. Time-box + quarantine stuck agents.
8. Prefetch re-discovery during the prior wave's review. Speed comes from removing redundant
work, not skipping gates.

## Step 3d — Model routing (spend reasoning only where it pays)
- **L0** Deterministic, ZERO LLM tokens: decided edits via `deterministic_edit`, repo view via
  `orient`, recall via `recall`. Any decided change goes here.
- **L1** Local/cheap mass model: triage, dedup, classify, summarize, status comments, repetitive
  generation.
- **L2** Mid coding model: standard implementation + review.
- **L3** Reasoning model: planning for LARGE/CRITICAL, architecture, ambiguity, adversarial verify
  of risky findings, security review. Sparse, high-value.
|- **L4** Paid remote (last resort): only after local cannot close the gap, with recorded escalation.

> **LMCache KV cache accelerator.** When running local models (L2-L3), `pip install lmcache` + `lmcache serve` caches KV caches across loop turns — lower TTFT on similar calls, less GPU time per iteration. Especially relevant in long loops (Step 3b poller) where the same base prompt is re-fed. Config via `LMCACHE_CONFIG` or `~/.lmcache/config.yaml`.

| Phase | Tier | | Phase | Tier |
|---|---|---|---|---|
| Discover/dedup/classify | L1 | | Implement — normal | L2 |
| Plan (SMALL/MEDIUM) | L2 | | Implement — mass/repetitive | L1 |
| Plan (LARGE/CRITICAL) | L3 | | Verify — normal | L2 |
| Implement — decided/mechanical | L0 | | Verify — risky/security | L3 adversarial |
| | | | Merge/close/status | L0–L1 |

GRANULARIZE: decompose each item so the mechanical ~80% flows to L0/L1 at near-zero cost and only
the ~20% genuine reasoning reaches L3.

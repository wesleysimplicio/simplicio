# 24/7 standing loop + arming the watcher (Step 7 full detail)

To run unattended for 24h and cover the WHOLE work universe, the skill becomes a durable,
self-governing, self-healing loop. When `simplicio-loop` is loaded, it provides the drive
(evidence-gated completion-promise + cap); this is the orchestrator-side policy. Ten axes:

### 1. Durable driver
A durable scheduler (host-native cron if bound, else OS cron / scheduled task) that survives
reboot/closed session — NOT a session-bound loop. Each ~2-min tick: load state → poll all sources
→ dispatch within capacity → persist state → sleep. If the loop dies, the scheduler restarts it
and it resumes from the journal.

### 2. Total coverage matrix ("exactly everything")
Every SOURCE × every WORK-TYPE, drained each tick:

| Sources | Work-types |
|---|---|
| GitHub issues/PRs/CI, Jira, Asana, ClickUp, Trello, Azure DevOps, local, delegations | new feature/bug, CI failure, PR review comment / requested change, PR behind main, security advisory (Dependabot/CVE), flaky test, stale PR, confirmed TODO/FIXME, failed scheduled job |

"Done forever" never happens — idle cheaply when drained, wake on anything. Forward path
(Steps 2–6) and feedback path (Step 6b) both run every tick.

### 3. Durable state (idempotent, resumable)
Persist on disk (journal, JSONL/SQLite): `seen` set, idempotency keys, in-flight claims,
dead-letter quarantine, `dry` counter, lessons. Each tick, reconcile state with reality (which PRs
merged, which items closed) before acting.

### 4. Resource governance
- Shared token/quota bucket across agents (no 429 storms); re-probe provider quota each tick.
- Re-probe CPU/RAM/disk/load each tick → degrade tiers as resources tighten.
- Disk hygiene: prune old worktrees, rotate logs, GC build artifacts + old receipts. Time-box
  every item and every tick.

### 5. Unattended safety (no human at the keyboard)
- Irreversible ops queue to an async approval channel and BLOCK. Never auto-proceed.
- **Headless rule:** if NO approver is reachable, REMOVE the destructive capability (do the safe
  part, defer the rest) — do not execute unsupervised.
- Secret-scan every push. Aggregate blast-radius cap per item AND per day. Injection hardening on
  all item/PR/comment content.

### 6. Self-healing + intelligent retry by failure class
| Failure class | Detection | Retry strategy |
|---|---|---|
| Compile error | build/typecheck emits `^error` | Fix via `diagnostics` → retry (max 3×) |
| Test failure | runner exit ≠ 0 | Parse failing test + assertion → targeted fix → retry (max 3×) |
| Merge conflict | `git merge/rebase` exit ≠ 0 | Conflict retry protocol (Step 6b) → retry (max 3×) |
| Static-analysis blocker | new clippy/Sonar blocker | Fix the finding → re-run → retry (max 2×) |
| Timeout / infra | no output > wall-clock | Kill → re-queue → backoff 2× (max 2×) |
| Missing dependency | undefined symbol from unmerged dep | Suspend until the dependency issue closes |
| Security gate | secret in diff | Remove → rotate if live → retry once; second hit → dead-letter + alert |

Circuit breakers: open after N same-class failures on the same item → dead-letter with full log.
Watchdog: no progress across ALL items in M ticks → alert + reduce WIP cap. Dead-letter items
surfaced in the evidence package + next-run intake summary.

### 7. Prioritization & WIP
Portfolio order: security/prod-broken → blockers → CI failures → high-impact/low-effort →
deadlines → bugs → features → docs. Enforce a WIP cap and backpressure.

### 8. Observability
Structured event stream (JSONL: claimed/planned/edited/gate_passed/failed/merged/blocked) +
provenance chain. A live status surface (host-provided if bound). Periodic digest: items closed,
blocked, $ spent, queue depth.

**Periodic savings audit (deterministic, zero new model calls).** On a slow cadence, scan the
run's OWN command log for commands that MATCH the output-reduction catalog but ran RAW. Split
compound commands the same way the live gate does, sum estimated leaked tokens per the catalog's
expected-%, emit: adoption rate, top offending patterns, total tokens leaked. Reuse the exact same
catalog the live gate uses so the audit never drifts.

**Snapshot-based measurement (generate once, score offline).** Split any savings/quality
measurement into an EXPENSIVE generator (runs the model once, snapshots raw outputs + metadata to
a committed file) and a CHEAP offline scorer (recomputes from the snapshot with a FIXED tokenizer,
NO model call). Regenerate only when the skill/prompt set materially changes. Prefer per-item
MEDIAN, include min–max + stdev, disclose limits. Published metrics live between begin/end markers,
mechanically rewritten from committed evidence — never hand-typed.

### 9. Self-improvement
After each item, record the trajectory + learn from the run (delegate to `simplicio-learn`); reuse
prior solved patterns (precedents) so they're applied, not regenerated. Run the Step 6 self-audit
per item. Daily meta-review: scan escapes/blocks → propose protocol tweaks, back-tested before adoption.

### 10. Coordination & clean stop
Multiple loop instances: atomic claims (tuple-space/labels/lockfile) + lease/heartbeat/TTL so a
dead worker's items are reclaimed, never stolen while live. A single `STOP` signal (flag file
`.simplicio/orchestrator/STOP` or channel command) halts cleanly between ticks.

**Exit condition: none by design** — idle when drained, wake on any new item/comment/check. Only
STOPS on the explicit stop signal, iteration cap, spindle handoff, or a safety halt.

## Arming the watcher (idle, between runs)
Cadence configurable (default ~2 min). The user chooses always-on vs session-only by the scheduler
they bind: host-native durable scheduler / OS cron for always-on, session loop for session-only.

Mechanisms (prefer the most durable):
- **Host-native durable scheduler** (if bound): a 2-minute tick that discovers + dispatches.
- **OS cron / scheduled task**: `*/2 * * * *` re-invoking this skill — survives reboots.
- **Session loop** (least durable): `/loop 2m /simplicio-tasks <goal>` — alive while the session is.
- **simplicio-loop** (if loaded): binds re-feed/iteration to a real stop-hook with an
  evidence-gated completion-promise — exits only when `<promise>` is genuinely true AND backed by a
  passing gate. Wires the watcher into the hard rule: never close work without a merged PR or
  concrete evidence.

MANDATORY before arming 24/7: persistent source auth; the irreversible-op human gate ON; the
secret-scan gate blocking any commit with a secret; a reachable STOP/cancel path.

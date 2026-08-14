---
name: simplicio-autoresearch
description: Evolutionary optimize-by-metric loop — mutate a target, evaluate against fixed criteria, KEEP if the score improves (commit) or REVERT if it doesn't (git checkout), repeat, plateau-break after N stagnated runs. Adapts Karpathy's `autoresearch` pattern (and the ECC `autoresearch-agent`) with mandatory yool guardrails (§11 caps), git-isolated branch discipline, an anti-Goodhart eval order (correctness gate FIRST, score SECOND, labeled tokenizer), a local-first mutation ladder, and a `simplicio.savings-event/v1` receipt per run. Use when the user says "optimize this by <metric>", "autoresearch loop", "evolutionary optimize", "mutate/eval/keep-revert", or asks to shrink tokens/latency/bundle size/improve pass-rate against a fixed, measurable eval. Worker: `scripts/autoresearch.py`.
---

# simplicio-autoresearch — evolutionary optimize-by-metric loop

Credit: Andrej Karpathy's `autoresearch` pattern
(https://github.com/balukosuri/Andrej-Karpathy-s-Autoresearch-As-a-Universal-Skill) and the ECC
bundle's `autoresearch-agent`, adapted into a first-class simplicio skill. The upstream loop is
**NOT installed raw** — it conflicts with this ecosystem's rules (unbounded iteration, no git
isolation discipline, single-metric hill-climbing). This skill fixes all three. The mechanical
bookkeeping (caps, git actions, journal, plateau math, receipt) is a deterministic, model-free
worker (`scripts/autoresearch.py`) — it never mutates the target itself. **You (the LLM driving
this skill) propose the mutation; the worker enforces the contract around it.**

## yool guardrails (§11 — MANDATORY, not optional)

Register this skill's runtime as an agent with a hard cap on iterations and budget BEFORE the
first mutation — an uncapped loop is a review-blocker, per spec:

```markdown
### simplicio-autoresearch

- yool_id: `agent.dev.autoresearch`
- authority: dev
- lane: background
- agent_terms:
    cpu_quota_pct: 60
    disk_quota_mb: 100
    timeout_s: 300
    max_iterations: <N>          # MANDATORY — set at `init`, never omitted
    max_token_budget: <N>        # MANDATORY — set at `init`, never omitted
```

`scripts/autoresearch.py init` **refuses to start** (exit 2) without both `--max-iterations` and
`--max-token-budget` as positive integers — the cap is enforced mechanically, not by convention.
`record` refuses (exit 12) any iteration number beyond the frozen `max_iterations`.

## When to use / when NOT to use

Fit requires: a concrete target file (or small set of files), a command that can score it, and a
correctness gate that is genuinely binary.

| Good fit (pilots) | Why |
|---|---|
| mapper — TOON encoder heuristics | eval = round-trip fixtures (correctness) + measured tokens on real artifacts (score) |
| dev-cli — prompt template | eval = the A/B bench pass-rate, fixed validation set |
| runtime — local model-ladder tuning | eval = ladder success-rate / latency on a fixed task set |

| Low fit — do NOT use | Why |
|---|---|
| sprint (planning code vs its own pytest suite) | the eval IS the test suite the code is graded against — the loop would learn to game its own gate (Goodhart) |
| an agent already in production | "cache is sacred" — mutating a live, cached agent config outside an offline branch risks correctness regressions no one is watching for |
| marketing copy with no fixed judge | a wobbling human/LLM judge with no binary criteria is not a gate, it's noise — the loop would hill-climb on judge mood, not quality |

## Contract — inputs you must have BEFORE calling `init`

- **Target**: one file (or a tight set) that the mutation touches.
- **Eval command**: prints `{"gate": "pass"|"fail", "score": <number>}` (JSON anywhere in stdout/
  stderr, or `gate: pass` / `score: 7` lines as a fallback) — see `parse_eval_output` in the
  worker. The eval **includes the repo's OWN gate** (lint + tests for the target's language/repo)
  — the loop must never commit red.
- **Binary correctness criteria FIRST** — round-trip lossless / fixtures / the target repo's test
  suite. This is the gate; it decides keep vs revert **before** the score is even consulted.
- **A labeled metric SECOND** — the score being optimized (tokens via a NAMED tokenizer, pass-
  rate, latency, bundle size). An unlabeled/unrotulado metric is not a valid score — 5 divergent
  token estimators disagree by ~30%; hill-climbing on an unlabeled number is a random walk. Pass
  `--tokenizer-id <name>` at `init` whenever the score is a token count.
- **Fixed validation set** (3-5 items), unchanged for the whole run — mutating criteria mid-run
  invalidates every prior keep/revert decision.
- **Caps**: `--max-iterations`, `--max-token-budget` (mandatory), optionally
  `--cpu-quota-pct` (default 60), `--disk-quota-mb` (default 100), `--timeout-s` (default 300),
  `--plateau-n` (default 5).

## Step 1 — init (git isolation, baseline)

```bash
python3 scripts/autoresearch.py init --target <path> --eval "<eval command>" \
    --max-iterations 20 --max-token-budget 50000 [--tokenizer-id cl100k-estimate] \
    [--branch <name>] [--direction max|min] [--margin 0.0] [--plateau-n 5]
```

Refuses to start on `main`/`master` — it resolves the target's git root, checks out (creating if
needed) an isolated `autoresearch/<slug>` branch, records the pre-mutation `HEAD`, and runs the
eval command ONCE to capture the baseline gate + score. Print the `store=` path it returns; every
later command needs `--store <that path>` (or `export SIMPLICIO_AUTORESEARCH_STORE=<that path>`).

## Step 2 — the mutate/eval/keep-revert loop (repeat until cap or promise)

For each iteration N (1..max_iterations):

1. **Mutate** — apply ONE change to the target. Prefer the **simplicio-runtime local ladder**
   (qwen 64→600) for the mutation itself; a paid remote model is stage 5 ONLY, opt-in via
   `--remote`/`--allow-remote` with recorded escalation evidence. An optimizer that burns
   frontier tokens indefinitely contradicts the point of the exercise.
2. **Record** — let the worker run the eval and decide:
   ```bash
   python3 scripts/autoresearch.py record --iteration <N> --store <store> \
       --note "<what you changed>" --mutation-summary "<one-line>"
   ```
   Gate-first, always: a `fail` gate is **always** `revert`, no matter how good the score looks
   (anti-Goodhart). Only once the gate passes does the score decide keep vs revert, by
   `--direction` (`max` default; `min` for tokens/latency/size) beyond `--margin`. `record`
   performs the matching **scoped** git action itself — `git add <target> && git commit` on keep,
   `git checkout -- <target>` on revert — never touching anything outside the target file(s).
   `hooks/action_gate.py` stays active underneath: a mutation is a file edit, never a destructive
   op.
3. **Plateau check** every iteration (cheap, no LLM):
   ```bash
   python3 scripts/autoresearch.py plateau --store <store> --exit-code
   ```
   Exit 10 = `--plateau-n` (default 5) consecutive reverts in a row. Do a **full rewrite** of the
   target from scratch (not another small nudge), then acknowledge it so the streak resets:
   ```bash
   python3 scripts/autoresearch.py record --iteration <N> --store <store> --plateau-break \
       --note "plateau-break: full rewrite"
   ```
4. **Health-check** — every 10th `record` call prints a `HEALTH-CHECK|` reminder line: pause and
   re-validate the binary criteria + validation set haven't quietly drifted before continuing.

## Step 3 — finish (squash + receipt)

```bash
python3 scripts/autoresearch.py finish --store <store> --message "<Conventional Commit subject>"
```

Squashes every kept commit since the branch's start `HEAD` into ONE commit (the whole run is a
SINGLE task for the DoD — the diff + the journal is the evidence, not N micro-tasks). Refuses
(`BLOCKED`, exit 12) if the final kept state's gate is not `pass` — a run can never "finish" on a
losing state. Writes `receipt.json` (`simplicio.savings-event/v1`):

```json
{
  "schema": "simplicio.savings-event/v1",
  "source": "autoresearch",
  "yool_id": "agent.dev.autoresearch",
  "baseline": {"gate": "pass", "score": 118.0},
  "actual": {"gate": "pass", "score": 71.0},
  "proof": {"kind": "autoresearch-eval-log", "path": ".../journal.jsonl"},
  "tokenizer": "cl100k-estimate",
  "iterations": 14, "kept": 4, "reverted": 9, "plateau_breaks": 1
}
```

`baseline`/`actual` are the values the eval command ITSELF produced, never hand-typed. `finish`
also leaves the isolated branch checked out with the squashed commit — open the PR against it
per the normal `simplicio-tasks` flow; do not merge to `main` from inside this skill.

## Other verbs

```bash
python3 scripts/autoresearch.py eval --store <store>       # run the eval now, print gate/score
python3 scripts/autoresearch.py status --store <store>     # config + plateau streak + journal tail
python3 scripts/autoresearch.py selftest                   # pure decision math, no git/network
```

## Non-negotiables

- Never run on `main`/`master` — `init` refuses; the worker mechanically enforces isolation.
- Never keep a failing gate, regardless of score — correctness before optimization, always.
- Never omit `--max-iterations`/`--max-token-budget` — a cap-less loop is blocked, not "faster".
- Never hand-type baseline/actual numbers in the receipt — they come from the eval command's own
  output, captured by the worker.
- Never squash-finish on a losing state — `finish` refuses when the winner's gate isn't `pass`.

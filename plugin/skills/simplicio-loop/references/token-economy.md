# Token-economy routing gate (full detail)

The condensed rule lives in SKILL.md Step 1c; this is the full mechanism. When `simplicio-orient`
is loaded, delegate to it — it IS this gate as a standalone skill. The cheapest token is the one
not spent: deterministic first, terminal for facts, model only where it pays.

## THINK vs NO-THINK
- NO-THINK (fast, prefer `deterministic_edit`/`orient`/`recall`): template/cache hit, known
  scaffold, single mechanical op, exact regex/AST match, a deterministic plan exists, or the
  answer is known from recall.
- THINK (planner/reviewer, record evidence): template miss, ambiguous task, multi-step plan, new
  domain, error/conflict/retry, architecture decision, output touches multiple files, security/
  release risk.

## INTERNET — default OFF
- OFF when: the task is about local code; repo/vendor/lockfile already has the API/docs; it is a
  test/docs/refactor change.
- ON only when: current external docs are required, a CVE/recent package version matters, an
  API/SDK error is undocumented locally, or the source demands current information.

## EXECUTE via terminal — NEVER simulate
Every git, gh, az, or shell command MUST run via a real terminal call. Never reason about
what a command "would return". Priority: (1) host native `shell_exec` if bound; (2) shell tool
with output clamping; (3) NEVER LLM-simulated output.

## Auto-clarity (safety overrides brevity)
Compression YIELDS to the safety gate. When a command/message is security-sensitive, irreversible
(force-push, history rewrite, prod deploy, data/schema delete, mass-file delete), or
order-dependent, FORCE full-clarity verbose output for that segment — the complete warning, the
exact command quoted verbatim, steps in explicit order — then resume terse. Brevity is never
applied to a confirmation a human must act on.

## Output-reduction catalog (drives clamp routing)
Consult BEFORE running. Each row `{pattern, recipe, exp-savings, SKIP-if}`. SKIP-if fires on
structured output (`--json`/`--jq`) or a write/confirm op. Clamp highest-savings first; NEVER
clamp a SKIP-if row; report the catalog's expected-% in the savings receipt.

| command pattern | reduce recipe | exp. savings | skip-if |
|---|---|---|---|
| test/spec runner | success-collapse to `pass: N`; on fail keep ≤20 error lines | ~90% | piped to structured consumer |
| type/compile check | error lines only; clean→`ok` | ~80% | — |
| diff / show | stat + hunks only, drop context | ~80% | piped to structured consumer |
| lint | findings only; clean→`ok` | ~80% | — |
| add / commit / push | collapse to `ok <branch/sha>` | ~59% | — |
| PR / list view | counts + titles only | ~87% | `--json`/`--jq` present |
| package / image inventory | keep ≤50 rows | ~50% | — |
| format / passthrough | run raw | 0% | always |

Content-type routing: route by detected type — JSON → keep
errors/anomalies/boundaries; code → keep signatures, collapse bodies; logs → keep failures, drop
passing noise; diff → stat+hunks. Same intent as the rows above, articulated by content type.

## Signal-tiered caps (one shared set)
`CAP_ERRORS=20`, `CAP_WARNINGS=10`, `CAP_LIST=20`, `CAP_INVENTORY=50`. Always keep ERROR lines
over surrounding context. A lowered cap is underflow-safe: falls back to the full cap rather than
emptying a non-empty result. Never flat "head N + tail N" (over-cuts errors).

## Two clamp primitives (both `unless errors present`)
- Success-collapse: exit 0 + clean pattern + no error/warning → one-line verdict.
- Dedup-with-counts: collapse runs of identical lines to `line xN`.
If ANY error/warning line exists, fall back to signal-tiered caps — a collapse can NEVER hide a failure.

## tee cache + CCR reversible retrieve (failure escape hatch)
On any NON-ZERO exit, or when a cap clips a FAILING command, write full output to
`.simplicio/orchestrator/tee/<ts>_<cmd-slug>.log` and surface only the path + kept error lines. The agent
re-reads it lazily only if needed — recovering full context WITHOUT re-running (which re-burns
tokens and may be non-deterministic). Config `.simplicio/orchestrator/orient.toml` → `tee.mode =
failures|always|never` (default `failures`).

**CCR (compress-cache-retrieve):** make the clamp REVERSIBLE, not lossy.
Every clamped blob gets a stable handle = the tee path. Surface a retrieve convention so a worker
pulls the original on demand instead of re-running:
```
retrieve <tee-path> [--lines a-b] [--grep PATTERN]
```
This turns "lossy by policy" into "reversible decision point": clamp to a signature/summary
in-context, keep the full original on disk keyed by handle, fetch by handle only when the kept
lines aren't enough. Removes the main risk of aggressive clamping (losing the one line that
mattered) at zero up-front token cost.

## Compound-command clamping (pipe/redirect-safe)
Understand `&& || ; |`: (1) split respecting quotes/escapes, clamp each segment; (2) for `|`,
clamp ONLY the left producer, leave the pipe TARGET raw; (3) never clamp a `find`/glob producer
feeding a pipe; (4) strip trailing redirects (`2>&1`,`>/dev/null`), clamp inner, re-append;
(5) unsplittable (`$(...)`, backticks, heredoc, file-target redirect) → run RAW with a tail clamp.

## Density tiers by consumer
MACHINE tier (terse, fixed-schema — the worker report contract) for worker→orchestrator reports
and internal digests; HUMAN tier (readable prose) for PR bodies, status comments, confirmations.
Skip a compression pass on already-dense content (code, config, lockfiles).

## Fail-open
Every reduction step is additive and removable. On ANY error/missing dep/unparseable payload/
unknown command, run the original command unchanged and propagate its REAL exit status. A bad
profile degrades to "slightly more tokens", never "task dead".

A raw `tsc --noEmit` costs ~2000 tokens to read; catalog-clamped
(error lines only) costs ~80.

## Terminal substitution table — use the terminal, NOT the LLM
Detect platform once: `python3 -c "import platform; print(platform.system())"` →
`Windows | Darwin | Linux`. Prefer cross-platform (`git`,`gh`,`rg`,`python3`) first.

### filesystem / system facts
| need | cross-platform | Windows | Linux/macOS |
|---|---|---|---|
| File exists? | `python3 -c "import os,sys;sys.exit(0 if os.path.exists('<p>') else 1)"` | `Test-Path <p>` | `test -f <p>` |
| Find in code | `rg "<pat>" --json` | same | same |
| Count matches | `rg -c "<pat>" <file>` | same | same |
| Grep + context | `rg -C 3 "<p>" <file>` | same | same |
| CPU cores | `python3 -c "import os;print(os.cpu_count())"` | `$env:NUMBER_OF_PROCESSORS` | `nproc` |
| Free disk GB | `python3 -c "import shutil;print(shutil.disk_usage('.').free//1024**3)"` | same | `df -BG .` |
| Free RAM MB | `python3 -c "import psutil;print(psutil.virtual_memory().available//1024**2)"` | `(Get-CimInstance Win32_OS).FreePhysicalMemory` | `free -m` |
| Today UTC | `python3 -c "from datetime import*;print(datetime.now(timezone.utc).date())"` | same | `date -u +%F` |
| Sort+dedup | `python3 -c "import sys;print('\n'.join(sorted(set(sys.stdin.read().split()))))"` | same | `sort -u` |
| Port listening? | `python3 -c "import socket;s=socket.socket();print(s.connect_ex(('127.0.0.1',<port>))==0)"` | `netstat -an \| findstr :<port>` | `ss -tlnp \| grep :<port>` |

### git (highest-value — answer from git, not from reasoning)
| intent | command (cross-platform) |
|---|---|
| Current branch | `git rev-parse --abbrev-ref HEAD` |
| Ahead of main? | `git rev-list --count main..HEAD` |
| Files changed in branch | `git diff --name-only main...HEAD` |
| Commits since base | `git log <BASE>..HEAD --oneline` |
| Last commit SHA | `git rev-parse HEAD` |
| Branch exists remotely? | `git ls-remote --heads origin <b>` |
| Show file at commit | `git show <commit>:<path>` |
| Blame line N | `git blame -L <N>,<N> <file> --porcelain` |
| Sync branch | `git fetch origin <b> && git checkout <b> && git pull --ff-only` |
| Isolated checkout | `git worktree add --detach <dir> <sha>` |

### gh (GitHub — all 5 scanned repos use this, not Azure DevOps)
| intent | command |
|---|---|
| Issue state | `gh issue view N --json state --jq ".state"` |
| Count open issues | `gh issue list --state open --json number --jq "length"` |
| List ready items (metadata) | `gh issue list --state open --json number,title,labels` |
| PR for branch | `gh pr list --head <b> --json number --jq ".[0].number"` |
| PR checks | `gh pr checks <n>` |
| PR diff | `gh pr diff <n>` |
| Comment / close | `gh issue comment N --body "…"` · `gh issue close N` |
| Workflow dispatch | `gh api repos/{owner}/{repo}/dispatches -f event_type=X` |

### node (vscode, openclaw, claude-code) / python (simplicio-agent, formerly hermes)
| intent | command |
|---|---|
| Deterministic install | `npm ci` · `pnpm install --frozen-lockfile` · `uv sync --locked` |
| Build | `npm run build` |
| Test (clamp: failures-only) | `npm test` · `pytest -q` |
| Lint (clamp: findings-only) | `eslint .` · `ruff check --fix` |
| Typecheck | `tsc --noEmit` · `mypy` |
| Dep inventory | `npm ls --depth=0` |

### docker / azure
| intent | command |
|---|---|
| Build / run | `docker build -t <img> .` · `docker run -d --name <c> <img>` |
| Exec / cleanup | `docker exec <c> sh -c "<cmd>"` · `docker rm -f <c>` |
| Compose | `docker compose -f <f> up -d` / `down` |
| Azure login / acct | `az login` · `az account show -o json` |
| Azure DevOps boards (if used) | `az boards work-item show --id N` · `az boards query --wiql "…"` · `az repos pr list` · `az pipelines runs list` |

> NOTE: the 5 scanned local repos (simplicio-agent (formerly hermes-agent), openclaw, vscode, codex, claude-code) use
> **GitHub (`gh`) + GitHub Actions exclusively** — no Azure DevOps. The `az`/`az boards` rows are
> provided for repos that DO use Azure DevOps; bind them as a `source_adapter` only when detected.

**Rule:** if the answer is a fact about the filesystem, git, processes, or system resources — the
terminal knows it exactly; the LLM approximates it expensively. Always pick the terminal.

## TOOLS / SKILLS — minimum necessary
- NO-TOOLS when the answer is derivable from context or the tool only confirms something
  irrelevant. A tool call must change a decision, an implementation, or evidence.
- NO-SKILLS by default. Rank/recall first; lazy-load only a genuinely relevant skill.

Record the chosen modes per sub-task in the receipt (one line).

## LMCache — KV-cache acceleration for local inference

LMCache accelerates inference inside the loop by caching KV (Key-Value) caches **between turns**, reducing TTFT (time-to-first-token) and eliminating redundant prefill on repeated or similar prompts.

### How it works

In a looping agent workflow, each turn triggers a fresh prefill on the accumulated context. LMCache intercepts and reuses previously computed KV caches so that only the *new* portion of the conversation needs to be prefilled:

- Caches KV state from previous turns in the loop
- Skips recomputation when the prompt prefix matches a cached entry
- Reduces TTFT significantly (up to 2–10× depending on cache hit ratio)
- Works with most local LLM inference engines (vLLM, SGLang, llama.cpp via adapter)

### Why it matters for token economy

| Dimension | Without LMCache | With LMCache |
|-----------|----------------|--------------|
| Prefill per turn | Full context re-prefilled | Only new tokens prefilled |
| TTFT | Grows linearly with conversation length | ~Constant after warmup |
| Token burn on re-prefill | Wasted on every turn | Recycled via cache hits |

### Installation

```bash
pip install lmcache
```

### Configuration

LMCache is configured via environment variables or a config file. Basic setup:

```bash
export LMCACHE_ENABLED=true
export LMCACHE_CACHE_DIR=~/.cache/lmcache
export LMCACHE_MAX_CACHE_SIZE_GB=10
```

For vLLM integration, pass `--kv-cache-dtype auto` and load the LMCache server plugin:

```bash
python -m lmcache.server &
```

### Relevance in model routing (L2–L3)

LMCache is **most impactful for local models** — typically L2 (fast local) and L3 (strong local) in the `simplicio-loop` model routing tiers:

- **L2 (fast local)**: Small local models benefit from LMCache's low overhead — TTFT drops enough to feel interactive even on long conversations.
- **L3 (strong local)**: Larger local models have the most to gain because their prefill is the most expensive — caching avoids the full forward pass on repeated context prefixes.
- **L1 (cloud)**: Cloud APIs already handle KV caching server-side; LMCache adds little value there unless you self-host the endpoint.

### Resources

- Official docs: [docs.lmcache.ai](https://docs.lmcache.ai)
- GitHub: [github.com/LMCache/LMCache](https://github.com/LMCache/LMCache)

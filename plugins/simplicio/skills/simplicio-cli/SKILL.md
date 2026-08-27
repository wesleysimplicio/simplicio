---
name: simplicio-cli
description: Use simplicio-cli for verified code changes through mapper, precedent, six-layer prompts, tests, and a verify loop. Trigger on code edits, task-to-code, diff+test, or simplicio-py requests.
---

# Skill: `simplicio-cli`

Wrap a code task in simplicio-cli's 6-layer contract instead of asking the LLM to guess. Same model, same task — only the prompt structure changes. Measured: **+51 pts average gain across 14 models** (sub-4B to frontier 2026).

> Source: this repo (`simplicio-cli`, PyPI `simplicio-cli`, MIT, v0.2.10). See `README.md` for the full bench table and methodology, `docs/benchmark-4quadrant.md` for the 4-quadrant decomposition.

---

## When to trigger

**Always** when the user asks for a code edit that fits all of these:

- One concrete target file (or small set) the user named or you can resolve from `Explore`.
- Mensurable success criteria (button gone / validation rejects empty / endpoint returns 401).
- Stack is one of the indexed stacks (`angular`, `react`, `next`, `vue`, `django`, `laravel`, `springboot`, `nestjs`, `dotnet`, `flutter`, etc. — anything with skills under `SIMPLICIO_SKILLS_DIR`) or a generic edit (`--stack generic`).

**Also trigger** on:

- Small/local model active (Ollama, Gemma sub-8B, Llama 3 sub-8B, Phi, Qwen 7B) — simplicio adds the biggest absolute gain there (+39 pts to +58 pts).
- User explicitly says: `$simplicio-py`, `/simplicio-py`, "use simplicio-py", "rode o simplicio-py", "via simplicio-cli".
- User mentions verify-loop, 6-layer prompt, precedent injection, pass-rate, skill router, content-hash cache.

**Do NOT trigger** on:

- Pure read-only ask ("what does this function do?") — answer directly.
- Architectural decision / refactor amplo cross-file — that goes to `architect` agent + ADR.
- One-off shell command, lookup, install task.
- The user is already inside `ralph-loop` and explicitly wants edits by hand — respect.

---

## Steps

### 1. Verify install + config

```bash
# is simplicio-py on PATH?
command -v simplicio-py \
  || pip install --user simplicio-cli \
  || pip install -e .            # fallback: editable install from repo root (locked venv / no PyPI)

# config check (one-shot, costs 1 LLM call)
simplicio-py smoke
```

If `smoke` fails: set the env vars and retry. Read `~/.config/simplicio/.env` or current shell env. Required:

| Provider | `SIMPLICIO_MODEL` | `SIMPLICIO_BASE_URL` | Key env var |
|---|---|---|---|
| OpenRouter | `anthropic/claude-opus-4` (or any) | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| GLM (z.ai) | `glm-4.6` | `https://api.z.ai/api/paas/v4` | `OPENAI_API_KEY` |
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com` | `OPENAI_API_KEY` |
| OpenAI | `gpt-4.1` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Ollama local | `llama3` (or any) | `http://localhost:11434/v1` | `OPENAI_API_KEY=dummy` |
| Anthropic native | `claude-opus-4-7` | *(unset)* | `ANTHROPIC_API_KEY` |

`base_url` unset + `ANTHROPIC_API_KEY` present → native Anthropic SDK. Else OpenAI-compatible client.

### 2. Index (cache warm-up)

First run on the repo (or after large changes): index once. Re-runs reuse embeddings keyed by content hash — unchanged blocks cost zero.

```bash
simplicio-py index --stack <stack>     # e.g. angular | react | django | dotnet | generic
```

Skip if `.simplicio/` already exists and the affected files were not modified since last index (`ls .simplicio/ 2>/dev/null` non-empty → cache warm).

### 3. Build the task call

Map the user's natural-language goal into the four flags:

| Flag | Meaning | Pull from |
|---|---|---|
| positional goal | one-line objective in user's words | the user's request |
| `--stack` | indexed stack name | detected from repo (look for `package.json`, `*.csproj`, `pyproject.toml`, `composer.json`, etc.) |
| `--target` | exact file path that holds the code to change | user said it, or `Explore` → grep for the affected symbol |
| `--criteria` | bullet list of mensurable success criteria | rephrase user's success into checkable bullets |
| `--constraints` | bullet list of guardrails | "don't touch X", "build still passes", "preserve public API" |

### 4. Run the task

```bash
simplicio-py task "<one-line goal>" \
  --stack <stack> \
  --target <path/to/file> \
  --criteria "- <check 1>
- <check 2>" \
  --constraints "- <guardrail 1>
- <guardrail 2>"
```

simplicio internally: precedent (from cache) → skill match → stacks the 6 layers → LLM generates diff + test + Playwright → applies → runs `SIMPLICIO_TEST_CMD` → pass = done, fail = sends error back, fixes, retries up to 3×.

### 5. Read the output

Output stream contains, in order:

1. `MAPPER` — what file was identified as the target + neighbors.
2. `PRECEDENT` — the in-repo snippet picked as the "this is how we already do it" example.
3. `SKILL` — the one mapper skill matched and injected.
4. `PROMPT` — the full 6-layer prompt sent (cache-friendly).
5. `DIFF` — the patch the LLM emitted.
6. `APPLY` — `git apply` result.
7. `TEST` — `SIMPLICIO_TEST_CMD` exit code + stderr.
8. `VERIFY` — pass/fail summary. If fail, loop up to 3× with the error appended.

> Canonical labels live in `simplicio/cli.py` — if the CLI output format changes, update this list against that file.

If `VERIFY: pass` → report to user with the diff and test artefacts. If `VERIFY: fail` after 3 retries → bubble up the last error + suggest splitting the task.

### 6. Validate locally

Whatever the project's normal validation is — run it. The simplicio test command is a fast inner loop; the full project validation is the outer truth.

| Stack | Command |
|---|---|
| Node/TS | `npm run lint && npm test` |
| Python | `ruff check . && pytest` |
| .NET | `dotnet build && dotnet test` |
| Go | `go vet ./... && go test ./...` |
| Rust | `cargo clippy && cargo test` |

If it's a UI change, also run Playwright (`npx playwright test --reporter=list,html`) with trace + screenshot + video (this repo's hard DoD rule).

---

## Patterns

- **Relevant > complete** — never inject the whole file. simplicio's precedent layer already picks the *right* snippet; don't override with `--target` pointing at a 10k-line file unless it actually is the target.
- **Criteria as testable states** — "no admin perm: button absent from DOM" (testable). Not "button should be hidden properly" (vague).
- **Constraints bound the blast radius** — list what the LLM must NOT change ("save flow", "auth middleware", "public API of `UserService`"). Without constraints, models drift.
- **Stack `generic`** is fine for non-listed stacks — skips skill router but keeps mapper + precedent + 6-layer + test + verify.
- **Cache is content-hash keyed** — `.simplicio/` directory holds embeddings. Don't `.gitignore`-ignore it casually; sharing the cache speeds team runs.
- **Cost is real** — +61% input tokens, +24% wall-clock vs. raw prompt. Justified by **+58 pts pass-rate**. Don't use simplicio for a one-line typo fix — use it where pass-rate matters.

---

## Anti-patterns

- Running `simplicio-py task` without `--target` on an ambiguous goal → mapper guesses, often wrong on big repos.
- Passing `--criteria "make it work"` → no signal for the verify loop. Pass-rate collapses.
- Using simplicio inside a Ralph loop AND wrapping each Ralph step in simplicio → double-loop, confused state. Pick one: either Ralph drives and simplicio runs the `execute` step (use `.agents/simplicio-ralph.agent.md` composition), or simplicio runs standalone.
- Indexing `node_modules` / `.venv` / `target/` — bloats cache, slows precedent. Use `.simplicioignore` (same syntax as `.gitignore`).

---

## Definition of Done

- [ ] `simplicio-py smoke` returned a clean provider config print + one successful test call.
- [ ] `simplicio-py task ...` ran with `--stack` + `--target` + `--criteria` + `--constraints` all set.
- [ ] `VERIFY: pass` in the output, OR a clear "fail after 3 retries — escalate" message.
- [ ] Diff applied (`git diff` shows the change) and project's normal validation (lint + test) is green.
- [ ] If UI change: Playwright run with trace + screenshot + video saved to `playwright-report/`.
- [ ] User gets: the diff, the test command result, and a one-line summary of what changed.

---

## Notes

- **Composition with Ralph Loop**: see `.agents/simplicio-ralph.agent.md` — Ralph drives the outer `read → plan → execute → lint → unit → e2e → fix` loop, delegates the `execute` step to `simplicio-py task` instead of editing by hand. Best for tasks where Ralph's autonomy + simplicio's per-call precision compound.
- **Bench reproduction**: `python3 bench/run_offline.py` (no API key needed for the offline scoring), or `simplicio-py bench --cases bench/cases.json --stack <s>` for real-test pass-rate.
- **4-quadrant matrix**: `python3 bench/run_4quadrant.py` decomposes prompt-effect vs. loop-effect vs. composition. Q4 (simplicio + loop) wins on pass-rate AND stays close to Q2 on cost.
- **Plug points** if extending: `prompt.py::_mapper` (real mapper), `pipeline.py::_aplicar_e_testar` (real diff/test), `skill_router.py` (your skills dir via `SIMPLICIO_SKILLS_DIR`).

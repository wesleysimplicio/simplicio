# Simplicio

A terminal-based AI coding agent and runtime.

Simplicio is the execution backbone for AI-assisted software development. It
provides deterministic editing, memory recall, quality gates, and multi-agent
orchestration — so LLMs can focus on reasoning while Simplicio handles
execution.

## Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"
```

## What It Does

| Capability | Command | Tokens |
|-----------|---------|--------|
| **Repo map** — compressed view for LLMs | `simplicio map --repo .` | Saves ~70% |
| **Memory recall** — don't re-derive known facts | `simplicio memory "query"` | Saves ~80% |
| **Mechanical edit** — deterministic file changes | `simplicio edit '{...}'` | Zero output tokens |
| **Coding loop** — iterate until tests pass | `simplicio coding-loop "task"` | Auto-repair |
| **Delivery gates** — quality check before shipping | `simplicio deliver certify` | Deterministic |
| **Multi-agent** — 600+ concurrent async agents | `simplicio run "task" --agents N` | Local-first |

## Architecture

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime (Rust)
  |                                   |
  | 1. Orient                         | simplicio map
  | 2. Recall                         | simplicio memory
  | 3. Decide                         |
  | 4. Edit  ───────────────────────> | simplicio edit (0 tokens)
  | 5. Verify <─────────────────────  | simplicio deliver certify
  | 6. Iterate                        | simplicio coding-loop
```

The LLM reasons. Simplicio executes deterministically.

## Key Features

- **Local-first inference** — built-in llama.cpp, escalates to remote only when needed
- **Graduated agent ladder** — 64 → 100 → 200 → 600 local agents before paid remote
- **Shannon novelty gate** — filters redundant agent outputs (zero LLM tokens on dedup)
- **Sharded inference pool** — per-worker channels, zero lock contention
- **Sealed receipts** — sha256 per evidence artifact, tamper-evident chain
- **5 delivery gates** — acceptance, validation, run-verify, regression, self-review
- **Action gate** — risk classification + hardline blocklist for chat-initiated mutations

## Documentation

- [Installation Guide](https://github.com/wesleysimplicio/simplicio-runtime/blob/main/docs/INSTALL.md)
- [Operational Manual](https://github.com/wesleysimplicio/simplicio-runtime/blob/main/docs/SIMPLICIO_OPERATIONAL_MANUAL.md)

## Version

Current: **v0.9.2** — 2467 tests, 159k lines of Rust, 65+ modules.

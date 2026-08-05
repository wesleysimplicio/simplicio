# Simplicio - Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), and release assets.

**Not the source code.** The Rust runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo.

## Current Version: v3.6.5

- **Release:** v3.6.5 — Windows x64 Runtime (read-only doctor effect gate)
- **Previous:** v3.6.0 — Windows x64 Runtime (loop ownership + execution metrics + install smoke)
- **Default branch:** `master`
- **Assets this release:** Windows x86_64 (refreshed). macOS/Linux binaries remain from prior multi-platform train until next full rebuild.

### Product law (v3.6.0)

1. Loop complete lives **inside Runtime** (`simplicio loop decide`)
2. mapper / dev-cli / fast **work alone** without Runtime
3. Every run emits **`simplicio.execution-report/v1`** (per-task + consolidated metrics)
4. Full LLM map: private runtime `docs/ECOSYSTEM_LLM_GUIDE.md`

## Repository Structure

```
/
├── README.md                 # Main English README
├── READMEs/                  # README translations
├── install.sh / install.ps1  # Installers
├── VERSION.md                # This file — READ ME FIRST
├── simplicio-windows-x64.exe # Windows binary
└── …
```

## Key Branches

| Branch | Purpose |
|--------|---------|
| `master` | **Canonical branch.** All distribution content lives here. |

**DO NOT push to or create `main`.** The `main` branch is NOT used for this repo.

## LLM Rules

1. **Read this file first** before any edits.
2. **Use `master` branch only.** Never push to `main`.
3. **Check `git branch`** before committing - confirm you're on `master`.
4. Keep install methods consistent across READMEs.

## Quick Links

- **GitHub:** https://github.com/wesleysimplicio/simplicio
- **Runtime source (private):** https://github.com/wesleysimplicio/simplicio-runtime
- **Official site:** https://simpleti.com.br/simplicio/

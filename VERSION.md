# Simplicio - Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), and release assets.

**Not the source code.** The Rust runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo.

## Current Version: v3.8.11

- **Release:** v3.8.11 — Runtime assets for macOS ARM64, Linux x64, and Windows x64
- **Previous:** v3.8.10 — Runtime multi-platform release
- **Default branch:** `master`
- **Assets this release:** macOS ARM64, Linux x64, and Windows x64. macOS Intel
  is not published in this release and has no supported installer asset.
- **Release readiness:** this published snapshot reports
  `source_code_distributed=false`, `login_enabled=false`, and
  `public_key_configured=false`; it is not approved for user launch. The
  installers refuse to finish until a published Runtime satisfies all three
  gates and ships signed artifacts.

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
├── simplicio                 # macOS ARM64 snapshot
├── simplicio-linux-x64       # Linux x64 snapshot
├── simplicio-windows-x64.exe # Windows x64 snapshot
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

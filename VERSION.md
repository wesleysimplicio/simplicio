# Simplicio - Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), and release assets.

**Not the source code.** The Rust runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo.

## Runtime snapshot: v3.8.16

## Current Version: v3.8.16

- **Source:** `simplicio-runtime` main at commit
  `5c178b39` (merged Runtime MCP routing, hook, release-gate, and version fixes).
- **Targets:** macOS ARM64, macOS x64, Linux x64, and Windows x64. The
  repository-root binaries and `SHA256SUMS` were regenerated from this same
  Runtime source and verified locally.
- **Release status:** signed GitHub Release `v3.8.16` is published.
  Installers and the update command resolve GitHub's `latest` release and
  require its signed manifest; the post-publish release gates have passed.
- **Default branch:** `master`
- **Release-channel gates:** signed artifacts, the configured
  `update_public_key`, and the embedded ecosystem bundle were verified for
  this user-facing release. Each installation still requires active Google
  login and entitlement validation.

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

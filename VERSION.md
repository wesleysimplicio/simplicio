# Simplicio - Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), and release assets.

**Not the source code.** The Rust runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo.

## Current Version: v3.8.13

- **Release:** v3.8.13 — Official signed release. All four canonical targets
  (`macos-arm64`, `macos-x64`, `linux-x64`, `windows-x64`) are built from
  current `simplicio-runtime` main with the canonical release Ed25519 public
  key embedded and the update manifest signed (`signed: true`,
  `security.signature_required: true`, `security.refuse_unsigned: true`).
- **Previous:** v3.8.11 — Transition snapshot (unsigned, 3 targets, readiness
  contracts still off)
- **Default branch:** `master`
- **Assets this release:** macOS ARM64, macOS x64, Linux x64, and Windows x64 —
  each Ed25519-signed against its real SHA256. Identity/login is active
  (`simplicio login google --json`, `require_active_login` in the installers),
  the readiness contract reports `source_code_distributed: true`, and
  `simplicio ecosystem verify --json` gates installation on the real embedded
  ecosystem bundle + active Google login.

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

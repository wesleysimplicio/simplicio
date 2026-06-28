# Simplicio — Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), and release assets.

**Not the source code.** The Rust runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo.

## Current Version: v1.3.6

- **Release:** v1.2.0 — Universal Adapter + 58 tests + Hermes parity
- **Default branch:** `master`
- **Last release asset:** macOS (ARM/x86_64), Linux (x86_64), Windows (x86_64)

## Repository Structure

```
/
├── README.md                 # Main English README
├── READMEs/                  # README translations (14 languages)
│   ├── README.pt-BR.md
│   ├── READM.es-ES.md
│   └── ...
├── assets/                   # Images (hero, flow diagram)
│   ├── simplicio-hero.png
│   └── simplicio-flow.svg
├── install.sh                # macOS/Linux installer
├── install.ps1               # Windows PowerShell installer
├── Formula/                  # Homebrew formula
│   └── simplicio.rb
├── npm/                      # npm wrapper packages
│   └── simplicio/
├── pypi/                     # PyPI wrapper package
│   └── simplicio/
├── .github/workflows/        # CI/CD
├── INSTALL.md                # Comprehensive install guide
├── VERSION.md                # ← This file — READ ME FIRST
└── simplicio                 # macOS binary (release asset)
```

## Key Branches

| Branch | Purpose |
|--------|---------|
| `master` | **Canonical branch.** All distribution content lives here. |
| `docs/readme-traducoes-completas` | Translation feature branch (merged). |

**⚠️ DO NOT push to or create `main`.** The `main` branch is NOT used for this repo.

## LLM Rules

1. **Read this file first** before any edits.
2. **Use `master` branch only.** Never push to `main`.
3. **Check `git branch`** before committing — confirm you're on `master`.
4. **All 15 READMEs must stay in sync** when making content changes:
   - `README.md` (English, canonical)
   - 14 translations in `READMEs/`
5. **Star History embed** uses `<picture>` with dark/light theme support via `api.star-history.com/chart`.
6. **Install methods** must be kept consistent across all READMEs: npm, pip, Homebrew, Bun, curl/sh, PowerShell.

## Quick Links

- **GitHub:** https://github.com/wesleysimplicio/simplicio
- **Runtime source (private):** https://github.com/wesleysimplicio/simplicio-runtime
- **Official site:** https://simpleti.com.br/simplicio/
- **Discord:** https://discord.gg/wM6tr7xVb

## Making Changes

1. `git checkout master && git pull`
2. Edit files
3. `git add -A && git commit -m "type(scope): description"`
4. `git push origin master`

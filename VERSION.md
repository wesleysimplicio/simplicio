# Simplicio - Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), and release assets.

**Not the source code.** The Rust runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo.

## Runtime snapshot: v3.8.24

## Current Version: v3.8.24

- **Source:** `simplicio-runtime` main at commit
  `5e87e6f8f3cd8142b1609b964bb6495dc9b9b89f` (merged Runtime v3.8.24 release metadata).
- **Targets:** macOS ARM64, macOS x64, Linux x64, and Windows x64. The
  canonical target table and release manifest define the asset, checksum,
  signature, SBOM, and provenance for each platform.
- **Release status:** GitHub Release v3.8.24 metadata is published manually, without GitHub Actions. Installers
  and the update command resolve GitHub's latest release, verify its signed
  manifest, and fail closed if an artifact signature or checksum is invalid.
- **Default branch:** master
- **Release-channel gates:** the installer enforces embedded ecosystem sources,
  the configured update key, SHA256, Ed25519 signatures, and active Google login.
  Publication alone is not a bypass for a failed verification; the release
  metadata must be regenerated when a signed artifact does not validate.

### Product law (v3.6.0)

1. Loop complete lives **inside Runtime** (`simplicio loop decide`)
2. mapper / dev-cli / fast **work alone** without Runtime
3. Every run emits **`simplicio.execution-report/v1`** (per-task + consolidated metrics)
4. Full LLM map: private runtime `docs/ECOSYSTEM_LLM_GUIDE.md`

## Repository Structure

~~~
/
├── README.md                 # Main English README
├── READMEs/                  # README translations
├── install.sh / install.ps1  # Installers
├── distribution/targets.json # Canonical platform-to-asset mapping
├── simplicio-update-manifest.json # Checksums, signatures, provenance
└── release binaries           # Published in GitHub Releases per target
~~~

The current release targets are macOS ARM64, macOS x64 (Intel), Linux x64,
and Windows x64. The installers consume the canonical mapping and do not
rewrite or download the embedded Python projects separately.

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

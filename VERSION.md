# Simplicio - Public Distribution Repository

**Read this file first. Every LLM must read this before editing.**

## Purpose

This is the **public distribution repo** for [Simplicio](https://github.com/wesleysimplicio/simplicio), a Rust-based terminal AI coding agent. It contains installers, packages, documentation (15 languages), release metadata, and the first-party Desktop source in `apps/desktop`.

The Rust Runtime source lives in the private [`simplicio-runtime`](https://github.com/wesleysimplicio/simplicio-runtime) repo. Runtime and Desktop executables are GitHub Release assets, not tracked source files.

## Runtime snapshot: v3.8.40

## Current Version: v3.8.40

- **Source:** `simplicio-runtime` main at commit
  `d2ceddade37fa965fd00cb6d9ddb9800368b0f7b` (Runtime v3.8.40).
- **Runtime targets:** macOS ARM64, macOS x64, Linux x64, and Windows x64.
  The canonical target table and release manifest define the asset, checksum,
  Ed25519 signature, SBOM, and provenance for each Runtime platform.
- **Desktop status:** Desktop remains at v3.8.39. Its
  `Simplicio-3.8.39-arm64.dmg` and `.zip` assets were published with v3.8.39,
  built from public commit
  `dd7dd0665630fcdd6c9a76d07956d840f80fc0a9`. Exact filenames, SHA-256,
  sizes, verification evidence, and signing status are recorded in
  [the release runbook](docs/RELEASE_RUNBOOK.md#published-desktop-v3839).
  Desktop is not part of the v3.8.40 release artifacts.
- **Release status:** GitHub Release v3.8.40 and `simplicio-installer 3.8.40`
  on PyPI are published manually, without GitHub Actions. Installers and the
  update command resolve the release metadata, verify the required Ed25519
  artifact signatures, and fail closed on an invalid signature or checksum.
- **Readiness limits:** the macOS ARM64 Desktop package has a valid ad-hoc
  code signature but no Apple Developer ID signature or notarization;
  Gatekeeper rejects it. Installed Ambient/Workspace/Agent action contracts
  and the remaining native-host release-train gates are not declared complete.
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
├── apps/desktop              # First-party Desktop source
├── release binaries           # Runtime assets published in GitHub Releases
└── Desktop DMG/ZIP             # Desktop assets published in GitHub Releases
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

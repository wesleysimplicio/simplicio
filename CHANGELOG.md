# Changelog

## [Unreleased]

### Changed

- Public installers now configure Codex to launch the installed Simplicio
  binary over local STDIO and merge Simplicio lifecycle/PreToolUse hooks into
  `~/.codex/hooks.json` without replacing unrelated user configuration.
- Added cross-platform Codex routing hooks for macOS/Linux and Windows, with a
  documented first-write backups.
- Windows installation now migrates legacy global hooks that invoke
  `/bin/bash` or `mcp-route.sh`, preventing stale Unix commands from failing
  after an update.

## [3.8.20] - 2026-08-22

### Fixed

- Corrected the public distribution manifest target IDs to match
  `distribution/targets.json` (`macos-arm64`, `macos-x64`, `linux-x64`, and
  `windows-x64`).
- Republished all four Runtime targets and Ed25519 sidecars from Runtime main
  commit `e698eca5`, manually and without GitHub Actions.
- Superseded the immutable v3.8.19 release after its post-release smoke exposed
  the target-ID mismatch; the prior tag remains unchanged.

### Security

- SHA-256, Ed25519, SBOM, provenance, and immutable release URLs are included
  for every target. macOS notarization and Windows Authenticode remain
  separate platform-publisher gates.

## [3.8.19] - 2026-08-22

### Changed

- Published the four canonical Runtime targets and Ed25519 sidecars manually
  from Runtime main commit `65abb2fd`, without GitHub Actions.
- Published the Runtime deterministic-only default with explicit supertool
  execution available to the user/LLM.

### Security

- SHA-256, Ed25519, SBOM, provenance, and immutable release URLs are included
  for every target. macOS notarization and Windows Authenticode remain
  separate platform-publisher gates.

## [3.8.11] - 2026-08-14

### Changed

- Synchronized the committed macOS ARM64, Linux x64, and Windows x64 binaries
  with the published Runtime v3.8.11 release.
- Updated the root checksum/manifest files and installation documentation to
  match the same release.
- Documented the mandatory Google login, Codex MCP registration, the current
  compiled-only Runtime limitation, and the current macOS Intel asset
  limitation.

### Security

- v3.8.11 artifacts verify against SHA256, but the binary reports disabled
  Google login, no distributed source bundle, and no configured public update
  key. The installers fail closed on those readiness gaps; missing checksums
  remain fail-closed as well.

## [3.6.7] - 2026-08-05

### Changed
- Published the Runtime v3.6.7 Windows x64 binary from merge SHA 9d31c6de7628e6de8f2c7ba61dc966f6613d3114.
- Documented the separate Mapper, Fast, and Loop routes; Dev CLI remains nested under Loop and direct edits use simplicio edit.


## [3.6.5] - 2026-08-05

### Fixed
- Published the Simplicio Runtime v3.6.5 Windows x64 binary with the read-only `simplicio_exec doctor` effect-gate adjustment.

## [3.6.0] - 2026-08-04

### Added
- Public Windows x64 binary from **simplicio-runtime v3.6.0**
- Loop ownership + `simplicio loop decide` / `execution-report` surfaces
- Install smoke path documented in private `packaging/windows/install.ps1`

### Changed
- Refreshed `simplicio.exe` / `simplicio-windows-x64.exe` (+ zips, SHA256, update-manifest)
- VERSION.md current version → v3.6.0

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- Mandatory pull-request quality gate with separate lint, unit, integration,
  E2E, security, benchmark, and flaky-test jobs; JUnit, coverage, package, and
  failure evidence is retained as workflow artifacts.
- Regression coverage for distribution-version drift and safe network-free npm
  installer dry runs across the supported OS and runtime matrix.

### Fixed

- Aligned public wrapper metadata with the canonical `3.5.2` update manifest
  and made release publication download only version-bound manifest artifacts,
  verify their signed SHA256 provenance, and derive checksums from that verified
  staging set.
- Expanded ignored-test enforcement to Python `skipTest`/`SkipTest` and Node
  skip options, with issue, owner, and 30-day removal metadata required.
- Made publication manual-only and immutable: tag-bound manifest provenance must
  match exactly, existing release assets cannot be replaced, and the known stale
  `v3.5.2` tag now fails closed pending separate fresh-release preparation.
- Restored a safe new-release path through distinct versioned HTTPS staging, with
  idempotent no-op success for coherent existing releases and structured PyYAML
  validation of real workflow steps, conditions, ordering, and action inputs.
- Closed the release topology to an exact job/step/action/command/environment
  allowlist, moving state, download, and metadata logic into fixed verifier
  subcommands so extra write steps and appended force/clobber commands fail.
- Restricted staging and publication to exact manifest-derived file sets, with
  stale/extra/directory/symlink rejection, allowlisted checksum generation, and
  full canonical comparison of every publish-action input.

## [1.6.1] - 2026-07-01

### Fixed

- Aligned all public install references (README, translated READMEs,
  `install.sh`, `install.ps1`, docs) with the canonical `master` branch,
  removing stale links that pointed at the wrong branch. Verified with
  `scripts/verify_distribution_consistency.py`.

## [1.6.0] - 2026-07-01

### Added

- Auto-built release from `simplicio-runtime`, including refreshed binaries
  for macOS, Linux, and Windows and an updated signed update manifest.

## [1.5.0] - 2026-06-30

### Added

- Auto-built release from `simplicio-runtime`, including refreshed binaries
  for macOS, Linux, and Windows and an updated signed update manifest.

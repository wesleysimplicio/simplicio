# Changelog

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
  and made release checksums derive from the staged artifacts.

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

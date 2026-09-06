# Desktop local acceptance — 2026-09-05

## Scope and provenance

Public repository: `wesleysimplicio/simplicio`, base `f8549765ce817b4b0d306a31560b7d0ee69972e8`.
All Desktop changes are in this repository. No Desktop project was found under Runtime's apps directory; no Runtime source was deleted.
Reference: [Orca](https://github.com/stablyai/orca) at `7bb54cc2f73c08a3df026c28766afd48b0e24471`, plus its live macOS UI.
Remaining product acceptance: [issue #375](https://github.com/wesleysimplicio/simplicio/issues/375).

## Implemented locally

- Desktop build manifests aligned with the existing Runtime 3.8.47 release; publisher now updates all five Desktop version consumers.
- Anonymous startup update check, dismissible availability notice, bounded status polling, explicit resumable failure state, duplicate-action locks and unrelated-package rejection.
- Native updater serialization, partial-file symlink guard, bundled-target requirement, newer-version and bundle identity checks, partial byte progress, relaunch journal ordering and actual running-version reconciliation.
- Home telemetry now polls supported `desktop-unified-usage`, not the unsupported `usage changefeed` command.
- No-data snapshots hide numerical totals and are labelled separately from provider subscription quotas.
- Unified export retains the exact query associated with its digest rather than recomputing a moving time window.
- Refreshed outdated IPC fixtures and added regression coverage. No provider credentials or user sessions were copied.

## Local validation

| Check | Result |
| --- | --- |
| Frontend unit tests | 376 passed |
| Playwright full suite | 115 passed; preview/mocked IPC, not installed provider proof |
| Native Rust tests | 168 passed, 3 ignored |
| Publisher contract tests | 18 passed |
| Frontend production build | Passed; existing chunk-size warning |
| Runtime staging | 3.8.47 version, SHA and Ed25519 validation passed |
| Tauri DEBUG macOS bundle | Built and opened with Runtime 3.8.47 |
| git diff --check | Passed |
| cargo fmt --check | Interrupted after remaining silent; unverified |
| Generic Simplicio validation | Python compile passed; pytest 363 passed, 3 failed, 1 skipped, 39 subtests passed |

Generic validation failures (not hidden or waived):
- `tests/test_clean_install_e2e_contract.py::test_clean_install_harness_covers_all_release_targets`
- `tests/test_plugin_release_policy.py::test_verifier_checks_published_bytes_and_runs_real_bootstrap_tests`
- `tests/unit/test_plugin_marketplace.py::test_loop_bundle_uses_canonical_reference_paths`

## Native observations

The old installed app reported Runtime 3.8.39. A separate locally built DEBUG bundle opened with the existing login and Runtime 3.8.47. Home now displays the real no-data snapshot rather than perpetually retrying an unsupported command. MCP inventory distinguishes eight registrations from zero confirmed handshakes. Tokens discovered local context ledgers, with explicit heuristic/provenance warnings, while billed usage remained unavailable. The unified report button reached the native supported contract.

This does not establish provider quota integration, completed account management, signed/notarized distribution, actual update installation/relaunch/rollback, or all platform acceptance. The app in Applications was not overwritten. No commit, push, merge, release or GitHub Actions run was performed.

## Follow-up live native audit — 2026-09-06

Unlocked macOS allowed a fresh comparison against Orca and the current debug bundle. The source build opened with the logo-only Install Now entry, completed Runtime preparation, and reached the authenticated workbench on Runtime 3.8.47. Live MCP evidence was 9 installed, 8 registered and 1 confirmed (Codex); Grok and OpenCode remained attention states rather than false confirmations. Usage, updates, permissions, diagnostics, guided setup, token/activity exports and filters were exercised. This is current debug-bundle evidence only; the stale Applications copy, signed distribution, provider OAuth and real update installation/rollback were intentionally left untouched.

# Desktop login and installation audit — 2026-08-31

Scope: public Desktop, based on `ad2fadb5a8cd73e6c2334e61ff420e9ce15d5f05`, with the bundled Runtime 3.8.39. This is a partial acceptance record, not certification of all platforms or clients.

## Corrections

- Remove the login panel border, shadow and decorative divider; retain the Google button boundary and visible keyboard focus.
- Invalidate stale account state after an ambiguous login/logout result. A read-only retry verifies the current account without repeating the account action.
- Preserve the intended guided-setup destination when the first OAuth response is unknown or its follow-up snapshot fails.
- Show absent, unchanged configuration as missing instead of already configured.
- Describe remote logout revocation as an attempt, not a guarantee.

Regression tests were run failing before these fixes, then passing. The review preserved the existing hidden-navigation policy, local project bookmarks and installation recovery locks.

## What the Desktop installs today

| Layer | Current behavior | Evidence boundary |
| --- | --- | --- |
| Runtime | Bundled by Tauri `externalBin`; installed to its managed location by native install | Verify exact sidecar digest before and after signing |
| MCP and hooks | Runtime `install --global --dry-run --json`, then `install --global --yes --json` after reviewed digest and consent | A fresh plan must confirm the reviewed targets |
| Host marketplace plugins | Additional terminal-wrapper operations, absent from the Desktop native install capability | Bundling plugin files is not installing/enabling them in a host |
| Live MCP connection | Shown separately from detection and registration | Requires a current handshake from each client |
| Models/provider subscriptions | Remain owned by the chosen host/provider | Simplicio login is not a model-provider login |

The CLI install actions were inspected read-only at the published Runtime source. No real host configurations, credentials or subscriptions were changed for this audit.

## Remaining acceptance blockers

1. **Authentication-only mode:** the exact published Runtime commit `d91aa04b39ab33c252c628fab6806bf8ea2c39a8` calls `bootstrap_apply::after_authentication` after Google. It has no supported bootstrap opt-out, including through `desktop login` or `auth login`. Isolating the login file alone does not isolate the bootstrap. See [AUTH.md](AUTH.md). A new compatible signed Runtime is required before claiming no installation effects before the Desktop consent screen.
2. **Plugin parity:** the current native installer does not install all host marketplace plugins. `simplicio plugin install` targets the Runtime's internal registry, not Codex/Claude/Gemini/Hermes host managers. The safe next implementation is Runtime-owned per-host plan/apply/verify with immutable payload digests, detected executable/version, reviewed destinations, backups and bounded per-host receipts. The Desktop and terminal wrappers should consume that same contract.
3. **Real platform acceptance:** new Google authorization, remote revocation, full clean installation and live handshakes were not performed. Windows/Linux/macOS Intel installed acceptance remains separate; local macOS ad-hoc signing is not notarization.

The public Hermes plugin additionally requires Mapper-only handshake compatibility; copying the latest plugin next to an older signed Runtime cannot establish that compatibility. The current terminal wrappers fetch marketplace content from a moving branch, so their operations cannot be silently treated as part of the Desktop's immutable reviewed plan.

## Local verification

- Vitest: 347 tests passed; TypeScript and Vite production build passed.
- Focused UI regressions: borderless login at 1280/390px, account effect recovery and setup labels passed.
- Installer contracts: 20 Python tests passed (sandbox/static contracts, not real installation).
- Complete Playwright suite: 108 tests passed (including existing reports and hidden navigation); mocked IPC is never labeled live OAuth.
- Native build and platform verification are recorded with the final delivery results.
- Bundled macOS ARM64 Runtime SHA-256: `c6dca7c384aaedb0226f6ea93a0dbe259a175f999c070e6c8ef609af519e5130`, matched to the published 3.8.39 checksum and verified with the repository Ed25519 public key/signature.

Prism/Loop skills guided survey, independent slots, regression/fix and review. The host admitted four concurrent agent slots, not 32 active workers. The installed Runtime returned incomplete context and did not activate the Loop route; bounded source reads and local agent coordination were used without claiming a Runtime Loop execution receipt. No GitHub Actions were run.

## References consulted

[Orca installation](https://www.onorca.dev/docs/install) separates first-launch detection/import and permission choices. [Buzz getting started](https://github.com/block/buzz#getting-started) distinguishes the packaged client from backend readiness. These inform the onboarding structure; neither proves Simplicio authentication or integration correctness.

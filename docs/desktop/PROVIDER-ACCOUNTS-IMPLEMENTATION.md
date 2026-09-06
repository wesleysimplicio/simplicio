# Provider account management implementation boundary

## Development

Account creation is not implemented by the current Desktop quota reader. Do not enable Add Account by relabeling a quota refresh or by running a login that overwrites the user's default agent home.

Reference inspected: Orca checkout `7bb54cc2f73c08a3df026c28766afd48b0e24471`, `src/renderer/src/components/settings/accounts-pane-codex-section.tsx`, `accounts-pane-account-actions.ts`, and `src/cli/handlers/account.ts`.

Orca distinguishes system-default authentication from managed accounts. Its CLI Codex add flow creates a temporary CODEX_HOME, runs interactive device authentication there, registers the result with the local account owner, and cleans up on completion/cancellation. Its UI can select a managed account and marks affected sessions for restart rather than silently switching running sessions. These are reference behaviors, not Simplicio capabilities.

Implement in this order:

1. Runtime-owned account store: opaque account IDs, provider and non-secret identity projection, private per-account homes, atomic registration, explicit system-default selection. Never send credential files or arbitrary home paths from the renderer.
2. Owned authentication operation: allowlisted provider CLI, isolated home, one active operation per provider, bounded lifetime/output, cancel/status operations, cleanup after every terminal outcome, and redacted errors. Do not infer authentication from exit status alone; verify provider identity after login.
3. Bind the selected account to quota reads and future agent launches. Do not mutate the user's default account or migrate active sessions without consent. Cache keys must include the account scope, not merely provider.
4. Desktop roster and add/select/reauth/remove actions use that contract. Removal requires explicit confirmation and affects only the selected managed account. Account cancellation must remain available while waiting for browser authentication.
5. Implement provider-specific adapters rather than claiming Codex behavior covers Claude, Grok, Gemini or OpenCode. Claude keychain isolation must be verified before enabling managed login on macOS.

## Validation

The public Desktop currently reads Codex quotas from the system-default app-server and Grok billing from the existing local session. Its Accounts page has no managed roster, and Add Account is disabled. Runtime source `src/account_usage_projection.rs` is a read-only quota projection, not an account creation/selection contract. No credential mutation or default-account login was executed during this review.

## Tests

Required before enabling the controls: successful and cancelled isolated login; concurrent add rejection; timeout and child cleanup; credential redaction; failed registration cleanup; restart persistence; duplicate identity behavior; explicit system-default selection; cache scope separation; removal confirmation; running-session preservation. Native manual acceptance must prove a newly authenticated account appears and its quota request uses that account, without changing the pre-existing default login.

## Item-by-item review

- Quota connectivity is already separately tested; it does not satisfy account management.
- First Simplicio Google login is a distinct Runtime authentication flow.
- Provider account management remains open under the Desktop completion work, including issue #375. This document defines the missing implementation boundary, not a completed feature.

# Desktop v1 implementation contract

`apps/desktop` is the Tauri 2 + React/TypeScript shell. It has one authority
boundary: the Tauri process invokes the signed Simplicio Runtime sidecar and
the UI renders the versioned `simplicio.desktop-snapshot/v1` response and
allowlisted, redacted token-report and integration-plan contracts.

The application has four access states:

| State | Runtime behavior | UI behavior |
| --- | --- | --- |
| `signed_out` | not started | Google login entry point |
| `inactive` | disabled | subscription and refresh actions |
| `unknown` | disabled | diagnostic refresh, never treated as unpaid |
| `active` | snapshot-backed | Today, Chats, Teams, Automations, Apps, MCP integrations, token reports and Settings |

The snapshot is bounded to 65,536 bytes, five activity rows, and 32 providers.
It is redacted at the boundary: source paths, configuration bodies, credentials,
prompts, skill bodies, and raw ledgers never reach the snapshot contract. The
separate receipt for an explicitly requested export identifies only the newly
saved report file; it does not expose the ledger's path or raw samples. Optional
Fast is not required and never injects into hooks.

All mutations are represented as governed, non-executed actions in the
snapshot and are dispatched through the bridge. The frontend never starts a
shell command, stores a token, or claims a provider handshake without a
Runtime receipt. Browser preview uses labelled demo data only; the packaged
Tauri path fails closed on an invalid or missing snapshot.

Successful active login opens Today. Account effects are serialized and
native installation stays locked until completion; there is no frontend
timeout that falsely unlocks an in-flight OAuth or configuration mutation.
Errors remain visible after entering the shell. Runtime health alone does
not certify a model inventory, provider handshake or workspace dispatcher:
unsupported actions remain disabled with a reason.

See [TOKEN-REPORTS.md](TOKEN-REPORTS.md) for the ledger query boundary and
[PROVIDERS.md](PROVIDERS.md) for review/consent, installation receipts and
the distinction between registration and a live connection. Browser E2E
tests use an explicitly mocked native IPC boundary; they do not certify a
real provider login, installation, native platform or published artifact.

Local acceptance:

```bash
npm test
npm run build
npm run test:e2e
cargo test --manifest-path src-tauri/Cargo.toml
```

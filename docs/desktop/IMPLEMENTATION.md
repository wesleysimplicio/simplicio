# Desktop v1 implementation contract

`apps/desktop` is the Tauri 2 + React/TypeScript shell. It has one authority
boundary: the Tauri process invokes the signed Simplicio Runtime sidecar and
the UI renders only the versioned `simplicio.desktop-snapshot/v1` response.

The application has four access states:

| State | Runtime behavior | UI behavior |
| --- | --- | --- |
| `signed_out` | not started | Google login entry point |
| `inactive` | disabled | subscription and refresh actions |
| `unknown` | disabled | diagnostic refresh, never treated as unpaid |
| `active` | snapshot-backed | Home, Providers, Activity, Memory, Settings |

The snapshot is bounded to 65,536 bytes, five activity rows, and 32 providers.
It is redacted at the boundary: paths, configuration bodies, credentials,
prompts, skill bodies, and raw ledgers never reach the UI contract. Optional
Fast is not required and never injects into hooks.

All mutations are represented as governed, non-executed actions in the
snapshot and are dispatched through the bridge. The frontend never starts a
shell command, stores a token, or claims a provider handshake without a
Runtime receipt. Browser preview uses labelled demo data only; the packaged
Tauri path fails closed on an invalid or missing snapshot.

Local acceptance:

```bash
npm test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
```

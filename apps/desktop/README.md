# Simplicio Desktop

This directory is the public, native Desktop shell for Simplicio. It uses
Tauri 2 with React and TypeScript. The UI owns presentation and user intent;
the Simplicio Runtime remains the authority for identity, entitlement,
provider state, memory, savings, updates and governed mutations.

The checked-in foundation is intentionally safe to preview before the Runtime
snapshot command ships. In a normal browser, the app uses clearly marked demo
data. In Tauri, it fails closed unless the Runtime returns the versioned
`simplicio.desktop-snapshot/v1` contract.

## Local preview

```bash
npm install
npm run dev
```

Use `?state=signed_out`, `?state=inactive`, `?state=unknown`, or
`?state=active` to inspect the product states in a browser preview. Add
`&view=providers`, `activity`, `memory`, or `settings` to open a specific app
surface. Demo data
is always labelled in the UI and is never used by the packaged app.

## Validation

```bash
npm test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
```

## Runtime boundary

The Tauri process invokes one fixed executable, without a shell. During local
development it resolves `simplicio` from `PATH`; an explicit
`SIMPLICIO_RUNTIME_BIN` may be provided by a controlled test or packaging
harness. The production bundle will stage a signed Runtime as a Tauri sidecar
only after the release pipeline validates its manifest, checksum, signature,
SBOM and component lock.

See [`../../docs/desktop/ADR-0001-public-tauri-shell.md`](../../docs/desktop/ADR-0001-public-tauri-shell.md)
for the ownership and security decision.

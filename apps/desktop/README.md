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

Validation is intentionally local; this repository does not depend on GitHub
Actions for the Desktop build or its Runtime contract.

```bash
npm test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
```

## Runtime boundary

The Tauri process invokes one fixed executable, without a shell. During local
development it resolves `simplicio` from `PATH`; an explicit
`SIMPLICIO_RUNTIME_BIN` may be provided by a controlled test or packaging
harness. The production bundle stages the exact signed Runtime release asset as a Tauri
sidecar after the release pipeline validates its manifest, checksum, Ed25519
signature, SBOM and provenance. The bridge prefers that bundled binary, then a
managed per-user installation, and finally the executable on `PATH`.

For a manual build, stage the verified target-specific Runtime at
`src-tauri/binaries/simplicio-<target-triple>`; for example,
`simplicio-aarch64-apple-darwin` on Apple Silicon. These executable bytes remain
ignored by Git and are never committed to the public source tree. The explicit
`Reparar integrações` action runs the Runtime's governed global installer so
MCP registrations, hooks and detected-host adapters converge together.

See [`../../docs/desktop/ADR-0001-public-tauri-shell.md`](../../docs/desktop/ADR-0001-public-tauri-shell.md)
for the ownership and security decision.

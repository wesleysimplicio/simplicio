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

The Tauri process invokes one fixed executable, without a shell. The production
bundle stages the exact signed Runtime release asset as a Tauri sidecar after
the release pipeline validates its manifest, checksum, Ed25519 signature, SBOM
and provenance. Login, logout, snapshots and host-plugin commands use only this
packaged sibling sidecar; writable per-user binaries, `PATH`,
`SIMPLICIO_RUNTIME_BIN` and UI-provided paths are never command authorities.
The managed per-user copy exists for other local clients. The Desktop records
only installations it performed in
`$HOME/.simplicio/desktop-runtime-receipt.json`, using the closed
`simplicio.desktop-runtime-receipt/v1` schema with the bundled source, strict
SemVer and SHA-256 digest. That private, atomically written receipt is used only
to decide whether a different managed binary may be upgraded or must be
preserved as newer; it never authorizes executing that binary. Exact bundled
bytes remain recoverable without a receipt. A divergent binary with a missing,
malformed or digest-mismatched receipt is preserved and the recovery flow fails
closed. Every Desktop command still runs the packaged sidecar.

The public installer receipt currently records only whether the Runtime was
installed, not its version and digest, so it cannot be imported as this
evidence. A future installer integration must add equivalent signed provenance
before the Desktop can trust it for upgrade/no-downgrade decisions.

For a manual build, stage the verified target-specific Runtime at
`src-tauri/binaries/simplicio-<target-triple>`; for example,
`simplicio-aarch64-apple-darwin` on Apple Silicon. These executable bytes remain
ignored by Git and are never committed to the public source tree. The explicit
integration review generates a plan first; host plugins are applied only after
the user consents to that exact plan digest. Runtime installation and Google
login never install host plugins.

The normal test suite includes a real executable fixture that crosses the
sidecar process boundary, installs the bytes, and reads a fresh snapshot. The
release smoke below is intentionally ignored by ordinary tests and fails closed
unless its input is an absolute path to the already signature-verified Runtime
asset for the current target:

```bash
cd apps/desktop
SIMPLICIO_DESKTOP_RELEASE_SIDECAR=/absolute/path/to/verified/simplicio \
TAURI_CONFIG='{"bundle":{"externalBin":[]}}' \
cargo test --manifest-path src-tauri/Cargo.toml --offline -j 1 packaged_release_sidecar_smoke -- --ignored
```

This smoke proves the executable-to-install-to-snapshot contract. It does not
prove a final Tauri installer bundle; release publication must still stage the
same verified asset under `src-tauri/binaries/simplicio-<target-triple>` and run
the platform packaging/manual installation checks.

See [`../../docs/desktop/ADR-0001-public-tauri-shell.md`](../../docs/desktop/ADR-0001-public-tauri-shell.md)
for the ownership and security decision.

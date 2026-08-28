# ADR-0001: Public Tauri shell with a separate Simplicio Runtime

- Status: accepted for implementation
- Date: 2026-08-28
- Owners: `wesleysimplicio/simplicio` and `wesleysimplicio/simplicio-runtime`

## Decision

The Simplicio Desktop source, product specifications, public issue tracker and
Desktop release metadata live in the public `wesleysimplicio/simplicio`
repository under `apps/desktop`.

The app uses Tauri 2 with a React/TypeScript frontend. The signed Simplicio
Runtime is bundled as a sidecar for distribution but remains a separate,
supervised process. It is not linked into the UI process and it may continue as
a per-user daemon after the window closes when the user enables that behavior.

The private Runtime repository remains authoritative for:

- identity and refresh-token storage;
- entitlement and operational access decisions;
- provider discovery, registration, handshake and repair;
- memory, Mapper, deterministic execution, cache receipts and savings;
- update verification, rollback and destructive-action gates.

The public Desktop owns:

- navigation, accessibility, localization and visual state;
- presenting login, access, Runtime health, providers and reports;
- collecting user intent and sending bounded action proposals;
- packaging metadata and public release notes.

## Why Tauri instead of Electron

Simplicio already has a native Rust Runtime. Tauri lets the Desktop reuse the
platform webview and keep the JavaScript surface focused on presentation while
the narrow Rust bridge talks to the Runtime. This reduces duplicate process and
memory overhead and gives us capability-scoped IPC. Electron remains a valid
fallback only if clean-machine tests reveal a blocking webview or accessibility
problem that cannot be solved within the release window.

## Process and data boundary

```text
React UI
  -> Tauri command with typed arguments
    -> Desktop bridge (Rust, no shell)
      -> signed Simplicio Runtime sidecar/daemon
        -> identity, entitlement, providers, mapper, memory, receipts
```

The frontend never reads provider credential files, invokes a provider CLI,
talks directly to Stripe, or starts arbitrary commands. It receives a compact,
redacted `simplicio.desktop-snapshot/v1` document and sends versioned proposals
for governed actions.

## Authentication and product access

Desktop login uses the system browser and OAuth authorization code with PKCE
and a registered deep link. Device flow remains the CLI fallback. Identity and
entitlement are separate dimensions:

- `signed_out`: no usable identity; show login;
- `inactive`: identity is valid and an inactive entitlement is confirmed;
- `active`: identity and entitlement are confirmed; enable Runtime operations;
- `unknown`: the provider could not be verified; do not call the user unpaid,
  and keep operational commands disabled while login, billing, retry, update
  and diagnostics remain available.

## Runtime snapshot contract

One bounded snapshot replaces multiple frontend probes. It includes only the
state required for the current screen and carries a schema, generation,
freshness and receipt identity. Large maps, memory bodies and provider logs stay
in the Runtime and are fetched only after an explicit user action.

This design does not use the Fast profile or inject Fast output in hooks. The
cache-hit path remains Mapper plus canonical memory plus compact receipts;
provider hooks receive stable identity metadata, never the full Map.

## Packaging and release gate

The current bootstrap download remains on its existing channel until the first
public Desktop artifact passes all gates. Cutover to the public release is
atomic and requires, per target:

1. source and lockfile build;
2. signed Runtime sidecar selected by component lock;
3. Desktop code signing/notarization or Windows signing;
4. checksum, Ed25519 signature, SBOM and provenance;
5. updater manifest and rollback test;
6. clean-machine login, inactive, unknown and active-state E2E;
7. provider detection and handshake tests with no secrets in logs.

## Consequences

The public repository can accept UI contributions without exposing private
Runtime logic. The UI cannot invent provider or subscription truth, and the
Desktop release cannot move independently of the Runtime compatibility lock.

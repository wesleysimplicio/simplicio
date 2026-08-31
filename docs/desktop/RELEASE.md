# Desktop release and updater contract

## Current manual delivery

Follow [the local release runbook](../RELEASE_RUNBOOK.md). Publication is manual,
not a GitHub Actions workflow. The Runtime's closed-world artifact manifest,
signatures, SBOM and provenance remain mandatory; Desktop installers are separate
companion assets, not additional members of that Runtime manifest. Record the
Desktop source revision, target, installer digest and bundled Runtime identity
separately. Never replace already-published bytes under an immutable version.

`Check for Updates...` currently performs a read-only check of public GitHub
release metadata and offers the release page for manual installation when a
compatible package is listed. Progress reflects received metadata bytes, not an
installer download. Metadata, a version string and an asset filename do not prove
signature verification, installation, successful startup or rollback. The UI
does not replace the app or Runtime in the background.

## Required contract before enabling automatic installation

The automatic updater is not implemented by the current metadata dialog. It must
follow a stage-before-swap transaction before it can be enabled:

1. download into an isolated staging directory;
2. verify signature, checksum, provenance, and component membership;
3. retain the current sidecar as the single rollback candidate;
4. atomically switch the active sidecar;
5. start the sidecar and restore the previous candidate if startup fails.

An automatic-updater acceptance suite must exercise both a successful fresh
start and a failed-start rollback. The Desktop UI must never present an update
as complete until the Runtime returns a healthy receipt.

## Native bundle identity

The Tauri bundle must include the exact verified Runtime release binary through
`bundle.externalBin`. Before a native build, stage it at
`apps/desktop/src-tauri/binaries/simplicio-<target-triple>` and verify that its
SHA-256 matches the public Runtime asset. The Desktop bridge resolves this
bundled sidecar before any managed per-user or `PATH` fallback. Target-specific
binary files are release staging material and remain outside Git.

Repeat this identity check **after bundling and all platform signing**, against
the sidecar inside the final app (on macOS: `Contents/MacOS/simplicio`). Tauri's
macOS bundler can re-sign `externalBin` even with an ad-hoc identity, changing
the Runtime bytes after the initial staging check. Such a package is not the
verified Runtime release and must not be published as one.

For local ad-hoc macOS packaging, restore the exact already-verified Runtime
asset inside the app and re-seal only the outer app, without recursive signing.
Then verify the app's code signature recursively and compare the sidecar SHA-256
and Ed25519 signature against the original Runtime release again. Do not rewrite
the Runtime's public signature or provenance to accept a bundler-modified binary.
Any required change to the Runtime's platform signature belongs in a new signed
Runtime release, not an invisible Desktop packaging rewrite. Ad-hoc signing is
not Developer ID signing or Apple notarization.


## Authentication-only release gate

This Desktop source requires the authentication capability in [AUTH.md](AUTH.md).
Before publication, run the exact final sidecar's `desktop status --json` on each
available native executor and require root schema `simplicio.desktop.app/v1`,
`action: status`, authentication schema `simplicio.desktop-auth-capabilities/v1`
and boolean `authentication_only: true`. Do not initiate Google to test the probe.
Runtime 3.8.39 is not compatible with this login path. A cross-compiled artifact
without native execution evidence must be reported as unexecuted, not passed.

After the probe and identity/signature verification, a separately authorized
account acceptance run must confirm `login google --authentication-only --json`
returns terminal `simplicio.auth-login/v1`, status `authenticated`, and bootstrap
`skipped/authentication_only`, without new install/bootstrap effects. This check
does not itself certify a fresh Google grant, remote revocation, package-manager
plugins or every client's live MCP connection.

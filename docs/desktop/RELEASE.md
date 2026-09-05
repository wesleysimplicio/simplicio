# Desktop release and updater contract

## Current manual delivery

Follow [the local release runbook](../RELEASE_RUNBOOK.md). Publication is manual,
not a GitHub Actions workflow. The Runtime's closed-world artifact manifest,
signatures, SBOM and provenance remain mandatory; Desktop installers are separate
companion assets, not additional members of that Runtime manifest. Record the
Desktop source revision, target, installer digest and bundled Runtime identity
separately. Never replace already-published bytes under an immutable version. This document is the normative source for the Desktop release and updater requirements; the former `distribution/desktop-release.json` duplicate specification is not consumed by the application.

`Check for Updates...` checks public GitHub release metadata and, for a
compatible Desktop package with a published SHA-256 digest, offers the bounded
download, verification and install flow. The download is anonymous, resumable,
stored in a private directory and never starts an install before size and digest
verification. A missing digest, stale manifest, wrong target, interrupted
download or failed verification fails closed and leaves the current app intact.

The updater transaction is implemented in `src-tauri::desktop_updater`:

1. re-read the official release API and bind the requested version/tag/asset;
2. resume into a private `.part` file and atomically stage the verified package;
3. retain the current macOS app bundle as one rollback candidate;
4. replace the bundle, relaunch it, and persist `awaiting_health`;
5. reconcile the running bundle version at startup, or restore the candidate.

The Desktop UI never reports completion until startup reconciliation confirms the
expected bundle version. A public GitHub digest is integrity evidence, not a
Developer ID/notarization or independent release signature; publication still
requires the signing, provenance and artifact gates below.

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

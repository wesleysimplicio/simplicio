# Desktop release and updater contract

## Current manual delivery

Follow [the local release runbook](../RELEASE_RUNBOOK.md). Publication is manual,
not a GitHub Actions workflow. The Runtime's closed-world artifact manifest,
signatures, SBOM and provenance remain mandatory; Desktop installers are separate
companion assets, not additional members of that Runtime manifest. Record the
Desktop source revision, target, installer digest and bundled Runtime identity
separately. Never replace already-published bytes under an immutable version. This document is the normative source for the Desktop release and updater requirements; the former `distribution/desktop-release.json` duplicate specification is not consumed by the application.

`Check for Updates...` checks public GitHub release metadata and, for a
compatible Desktop package with a published SHA-256 digest and matching
`<asset>.sig` sidecar, offers the bounded download, verification and install
flow. The sidecar is Ed25519 over the canonical `simplicio-release-v1:<sha256>`
payload using the pinned update-signature key. The download is anonymous,
resumable, stored in a private directory and never starts an install before
size, digest and signature verification. A missing digest or signature, stale
manifest, wrong target, interrupted download or failed verification fails closed
and leaves the current app intact.

## Public v3.8.47 companion evidence

The public Desktop channel currently contains one macOS Apple Silicon companion
asset. Its digest is kept in [`DESKTOP-SHA256SUMS`](../../DESKTOP-SHA256SUMS),
separate from the Runtime-only `SHA256SUMS` and
`simplicio-update-manifest.json`; the Runtime closed-world manifest is not
expanded with Desktop packages.

| Item | Measured evidence |
| --- | --- |
| DMG | `Simplicio-3.8.47-arm64.dmg`, 41,242,676 bytes, SHA-256 `9c8b02e8b804ddcf992c26f5d156ab0261fe498bee30237727d74abbbc38d779` |
| Bundled Runtime sidecar | `Contents/MacOS/simplicio`, 50,974,800 bytes, SHA-256 `529ab8130222b93953485d5fe7c49cddfa29767c6a7db60cdd4f5db88a1ac053` |
| Runtime authenticity | Ed25519 signature for the public `simplicio-macos-arm64` asset verified with `scripts/verify_ed25519.py`; the sidecar extracted from the DMG matches that asset byte-for-byte |
| Public release metadata | GitHub API reports the DMG as `uploaded`, with the same size and `sha256:9c8b02e8b804ddcf992c26f5d156ab0261fe498bee30237727d74abbbc38d779` |
| Desktop source revision | Not present in the v3.8.47 release metadata; no source commit is inferred |

The DMG and sidecar were downloaded again from the immutable release and the
sidecar was extracted from its APFS image before comparison. The arm64 Runtime
cannot execute on the available x86_64 verifier, so `version --json` and the
native Desktop status probe remain unexecuted here.

### Gate status for this public channel

| Gate | Status | Boundary |
| --- | --- | --- |
| Desktop package digest and Runtime sidecar identity | **verified** | Downloaded DMG hash and extracted sidecar match the public release assets |
| Desktop package Ed25519 sidecar | **blocked** | v3.8.47 publishes no `Simplicio-3.8.47-arm64.dmg.sig`; the updater must fail closed with `update_signature_unavailable` |
| Runtime closed-world manifest | **verified** | `SHA256SUMS` and `simplicio-update-manifest.json` remain Runtime-only and unchanged |
| Apple Developer ID signing and notarization | **blocked** | No Apple credentials are available; the package is ad-hoc and Gatekeeper acceptance is not claimed |
| Authentication-only native probe and Google acceptance | **unexecuted** | Requires a native macOS executor and a separately authorized account run; no Google flow was initiated |
| Windows Desktop | **blocked** | No Windows Desktop `.exe`/`.msi` installer is attached to v3.8.47; the CLI remains the Windows path |
| CI | **absent** | This repository documents and runs local gates; no GitHub Actions result is invented |

This evidence establishes a public macOS arm64 integrity channel, not a fully
notarized Apple release or a published Windows Desktop channel. Do not describe
the blocked or unexecuted gates as passed.

The updater transaction is implemented in `src-tauri::desktop_updater`:

1. re-read the official release API and bind the requested version/tag/asset and signature sidecar;
2. resume into a private `.part` file, verify SHA-256 and Ed25519, and atomically stage the verified package;
3. retain the current macOS app bundle as one rollback candidate;
4. replace the bundle, relaunch it, and persist `awaiting_health`;
5. reconcile the running bundle version at startup, or restore the candidate.

The Desktop UI never reports completion until startup reconciliation confirms the
expected bundle version. A public GitHub digest is integrity evidence; the
updater additionally requires the independent Ed25519 sidecar before staging.
This does not replace Apple Developer ID signing or notarization; publication
still requires the signing, provenance and artifact gates below. The current
public v3.8.47 Desktop package remains outside the installed updater trust gate
until its matching sidecar is published in a new immutable release.

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

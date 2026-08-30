# Desktop release and updater contract

Desktop artifacts are published only through the closed-world release
workflow. A release is eligible when the signed manifest, SHA256 digests,
SBOM, provenance records, and component lock all match the immutable staged
bytes. The workflow refuses a remote release whose tag or asset digests have
drifted.

The updater follows a stage-before-swap transaction:

1. download into an isolated staging directory;
2. verify signature, checksum, provenance, and component membership;
3. retain the current sidecar as the single rollback candidate;
4. atomically switch the active sidecar;
5. start the sidecar and restore the previous candidate if startup fails.

The release acceptance suite must exercise both a successful fresh start and
a failed-start rollback. The Desktop UI never presents an update as complete
until the Runtime returns a healthy receipt.

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

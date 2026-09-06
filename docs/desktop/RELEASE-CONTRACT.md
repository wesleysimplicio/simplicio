# Release and updater projection

`desktop.release/v1` models stable/beta channels and macOS, Windows and Linux
artifacts. An update is actionable only when the Runtime/Release service
returns a verified artifact, checksum and provenance; rollback is part of the
same descriptor.

This remains the publishing contract for a release that claims verified
provenance. The native `Check for Updates...` menu now opens the GitHub
metadata dialog, and the dialog can download/install only an exact target asset
whose GitHub release entry supplies a SHA-256 digest and matching `<asset>.sig`
sidecar. The sidecar is Ed25519 over the canonical
`simplicio-release-v1:<sha256>` payload using the pinned update-signature key.
The anonymous updater verifies size, digest and sidecar before staging; missing
or invalid signatures fail closed. Apple Developer ID signing and notarization
remain separate publication gates. See [manual delivery and the updater gate](RELEASE.md).

The Desktop never treats a version string as proof that an update is safe. In
standalone/preview mode, update and rollback remain unavailable with a reason
code.

# Release and updater projection

`desktop.release/v1` models stable/beta channels and macOS, Windows and Linux
artifacts. An update is actionable only when the Runtime/Release service
returns a verified artifact, checksum and provenance; rollback is part of the
same descriptor.

This remains the publishing contract for a release that claims verified
provenance. The native `Check for Updates...` menu now opens the GitHub
metadata dialog, and the dialog can download/install only an exact target asset
whose GitHub release entry supplies a SHA-256 digest. The updater deliberately
does not elevate that digest into `desktop.release/v1` provenance, Developer ID
signing or notarization; those publication gates remain mandatory. See
[manual delivery and the updater gate](RELEASE.md).

The Desktop never treats a version string as proof that an update is safe. In
standalone/preview mode, update and rollback remain unavailable with a reason
code.

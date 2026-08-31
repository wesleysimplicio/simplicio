# Release and updater projection

`desktop.release/v1` models stable/beta channels and macOS, Windows and Linux
artifacts. An update is actionable only when the Runtime/Release service
returns a verified artifact, checksum and provenance; rollback is part of the
same descriptor.

This is the required automatic-update contract, not a claim that it is supplied
by the current Runtime. The native `Check for Updates...` menu opens a separate
read-only GitHub metadata dialog with a manual release-page link. It never
upgrades metadata into a verified `desktop.release/v1` artifact or starts an
installation. See [manual delivery and the updater gate](RELEASE.md).

The Desktop never treats a version string as proof that an update is safe. In
standalone/preview mode, update and rollback remain unavailable with a reason
code.

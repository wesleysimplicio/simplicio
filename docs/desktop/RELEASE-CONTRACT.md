# Release and updater projection

`desktop.release/v1` models stable/beta channels and macOS, Windows and Linux
artifacts. An update is actionable only when the Runtime/Release service
returns a verified artifact, checksum and provenance; rollback is part of the
same descriptor.

The Desktop never treats a version string as proof that an update is safe. In
standalone/preview mode, update and rollback remain unavailable with a reason
code.

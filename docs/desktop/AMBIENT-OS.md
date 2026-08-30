# Ambient OS projection

The Desktop treats ambient state as a small, read-only projection. It can
signal `quiet`, `working`, `attention`, or `unavailable`, but it never starts
work, reorders priorities, or keeps a local agent loop.

The current UI consumes `ambient.state/v1` and keeps `pulse: false` so motion is
reserved for meaningful state changes. The Runtime remains authoritative for
receipts, approvals, work-item lifecycle and reconnect/replay semantics.

Until the Runtime exposes `ambient.today/v1` and `ambient.state/v1`, the Desktop
renders the installed preview with `*_projection_unavailable` reason codes.

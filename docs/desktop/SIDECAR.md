# Runtime sidecar supervision

The Desktop bridge supervises one Runtime sidecar and exposes its state as
`starting`, `healthy`, `degraded`, or `offline`. A failed start uses bounded
exponential backoff (1s, 2s, 4s, capped at 30s) and opens a circuit after
three consecutive failures. The UI must keep the Runtime disabled while the
state is not healthy and must never start a second uncontrolled process.

A successful start resets the failure counter and backoff. The supervisor is a
pure state machine, so transitions are deterministic and testable without
launching a process; the Tauri command remains the only process boundary.

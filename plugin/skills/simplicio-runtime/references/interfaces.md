# Runtime interfaces

Runtime wraps execution with policy and durable evidence. Resolve concrete MCP, native, and binary adapters from the installed Runtime version; never synthesize an adapter name.

## Gates and checkpoints

Evaluate scope, capability, authorization, resource limits, and preconditions before side effects. Persist a checkpoint before an effect that must be resumable.

## Receipts and reconciliation

Persist raw evidence before verdict. Recompute when requested and compare `reported` with `recomputed`. Use `unchanged-before`, `proven-after`, `failed`, or `ambiguous-or-diverged`. Never synthesize a receipt, silently clear a lock, or call ambiguity success.

## MCP compatibility

Normalize legacy and current MCP request/response shapes at the boundary and retain the compatibility record in evidence.

## Scheduling

Use bounded pools and backpressure. Reject or defer work that exceeds policy instead of creating unbounded concurrency.

# Loop interfaces

Loop coordinates capabilities and records causality. It is runtime-agnostic and must remain usable when Runtime is absent.

## Stage contract

Each stage receives a task ID, snapshot ID, capability ID, bounded inputs, and policy. It emits a durable event containing status, evidence, child operations, and next action.

## Slots

Prefer one issue/task per slot. Bound concurrency, isolate worktrees when mutation is possible, and preserve per-slot logs. Fan-in must report partial completion explicitly.

## Completion

Completion is an independently checkable oracle. Agent narration is evidence input, never proof. Stop on proven completion, explicit blocker, or exhausted policy.

## Runtime boundary

Call Runtime for native/MCP execution, gates, receipts, checkpoints, backpressure, or governed subagents. Otherwise execute through the Loop's portable adapters.

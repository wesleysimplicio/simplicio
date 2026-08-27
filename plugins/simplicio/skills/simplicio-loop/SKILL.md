---
name: simplicio-loop
description: Orchestrate multi-step Simplicio work with agents, slots, stages, retries, fan-out, recovery, verification, and convergence. Use for multiple issues, iterative implementation, parallel tasks, reviewer cycles, bounded retries, or workflows that must discover, act, test, correct, record, and repeat. Remain operational without Runtime.
---

# Simplicio Loop

Use Loop as the runtime-agnostic orchestration layer. It coordinates Mapper, Fast, Dev CLI, and optional Runtime capabilities without becoming the owner of repository mutations. Read `references/capabilities.yaml` and `references/interfaces.md` before selecting a stage or recovery path.

## Complete interface map

Use the generated Prism inventory for the installed Loop release. Include orchestration CLI/MCP/API surfaces, configuration, event inputs/outputs, slot and worktree effects, errors, recovery fallbacks, dependencies, concurrency cost, version, and compatibility. Mark unmeasured scheduling cost explicitly.

## Routing

- Invoke for multi-step work, multiple issues, agent slots, fan-out/fan-in, retryable tasks, review cycles, or convergence.
- Route one to three tasks through direct parallelism. For more than three tasks, use Prism;
  when quantity is omitted, use a minimum of ten tasks per logical slot with no upper logical
  limit on slots, capacity, or wave width. Physical resource and lease governors may defer work.
- Require Mapper and Dev CLI for implementation workflows; use Fast when it is available and compatible.
- Use Runtime only for capabilities requiring native execution, MCP, gates, receipts, checkpoints, backpressure, or governed subagents.
- Do not hide a failed slot, fabricate completion, or retry an ambiguous effect without reconciliation.

## Canonical flow

`discover → understand → decide → act → verify → correct → record → repeat`

Keep each stage bounded and emit an event with task ID, capability ID, inputs, outputs, evidence, and status. Stop when the completion oracle is proven, not when an agent merely reports success.

## Contract

Return `run_id`, `plan`, `slots`, `events`, `attempts`, `receipts`, `completion_verdict`, and `unresolved`. Preserve causality across retries and make parallel work reproducible.

## Resources

- `references/capabilities.yaml`: machine-readable capability map.
- `references/interfaces.md`: stages, slots, concurrency, recovery, and Runtime boundary.
- `scripts/probe-capabilities.py`: validate the capability manifest and detect duplicate IDs.

## Runtime integration boundary (normative, 2026-08-05)

Runtime decides whether this Loop route is active. The Runtime route keeps Loop
separate from Mapper and Fast, while Dev CLI is a nested Loop capability rather than
a fourth Runtime peer. When Loop is active, its implementation path may be
`mapper -> fast (when anchored) -> loop.dev_cli -> simplicio edit -> validate`;
the exact hops remain evidence-driven.

The Loop package remains usable standalone when Runtime is absent. That path is
operator-standalone and must report degraded Runtime-backed completion rather than
pretending that Runtime activation or consolidated Runtime evidence occurred.

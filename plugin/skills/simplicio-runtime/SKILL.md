---
name: simplicio-runtime
description: Govern and execute Simplicio workflows through native execution, MCP, gates, checkpoints, receipts, backpressure, pools, memory, and subagents. Use when a task needs durable evidence, controlled side effects, native acceleration, MCP compatibility, or Runtime reconciliation. Do not make Loop depend on Runtime for ordinary orchestration.
---

# Simplicio Runtime

## Worker preflight and centralized artifact policy

Every worker first reads repository `AGENTS.md`, `CLAUDE.md`, and all relevant local skills before Runtime operations. Runtime admits only the one binary/artifact set built centrally from the canonical default branch and shared read-only by workers. Workers must not rebuild binaries or regenerate canonical Mapper/Fast artifacts; worktrees isolate source edits and receipts only. Runtime receipts must include repository/revision, binary digest/version, Mapper generation, and artifact digest. Missing, stale, incompatible, or mismatched central artifacts fail closed and route to a central rebuild, never a worker-local repair or fabricated fallback.

Runtime/Tokio owns gates, effects, receipts, and reconciliation; Loop/Prism remains the Python `asyncio` scheduler and I/O layer.


Use Runtime as the governed execution layer around Loop and Dev CLI. It provides controls and evidence; it does not replace Mapper's survey or Dev CLI's mutation contract. Read `references/capabilities.yaml` and `references/interfaces.md` for exact gates and receipt rules.

## Complete interface map

Use the generated Prism inventory for the installed Runtime release. Record CLI/MCP tools, Python/Rust/native APIs, configuration, effect policies, evidence inputs/outputs, error codes, fallbacks, dependencies, measured cost, version, and MCP/OS compatibility before enabling a capability.

## Routing

- Invoke for MCP tools, native executors, gates, checkpoints, durable receipts, subagents, memory, pools, backpressure, or reconciliation.
- Require explicit capability, repository, scope, and effect policy before side effects.
- Reconcile only from durable evidence; never synthesize a receipt or delete an unknown-effect lock.
- Support old and new MCP tool shapes through the compatibility capability.
- Fall back to Loop without Runtime when governance/native execution is not required and the Loop path is available.

## Prism concurrency policy

The Runtime boundary preserves Loop's routing contract: one to three tasks use direct
parallelism; more than three tasks activate Prism. An omitted quantity uses a minimum logical
batch of ten tasks per slot. Logical slot count, slot capacity, and Prism wave width are
unbounded; Runtime must apply only measured physical worker/resource, lease, backpressure, and
effect-authority limits. Runtime receipts must record the logical route separately from the
physical admission decision.

## Required workflow

1. Validate capability, policy, inputs, and preconditions.
2. Acquire a bounded execution slot and emit a checkpoint.
3. Execute through the selected native/MCP/subagent adapter.
4. Persist receipt and evidence before reporting a verdict.
5. Recompute the result independently when reconciliation is requested.
6. Return proven, unchanged, failed, or ambiguous/diverged; preserve locks for ambiguity.

## Contract

Return `run_id`, `execution_id`, `capability_id`, `policy`, `checkpoint`, `receipt`, `evidence`, `reported`, `recomputed`, `verdict`, and `cleanup_status`.

## Resources

- `references/capabilities.yaml`: machine-readable capability map.
- `references/interfaces.md`: MCP, gates, receipts, reconciliation, pools, and fallback rules.
- `scripts/probe-capabilities.py`: validate the capability manifest and detect duplicate IDs.

## Runtime-selected operator route (normative, 2026-08-05)

When this skill is loaded with Runtime available, Runtime decides the route. The
only peer operator decisions are `mapper`, `fast`, and `loop`. Dev CLI is not
a peer Runtime route: it appears only as `loop.dev_cli` after Loop activation and
only when implementation or validation is required.

Direct file mutations default to Runtime's deterministic `simplicio edit` writer.
The component packages remain independently callable without Runtime, a Loop flow,
or a cross-component contract; missing optional context is reported degraded or
`UNVERIFIED`, never invented.

---
name: simplicio-runtime
description: Use the plugin-managed Simplicio Runtime to map repositories, recall project memory, apply deterministic edits, run every valid CLI subcommand through the governed MCP supertool, and validate evidence. Use when the user invokes Simplicio or asks for Simplicio-backed repository work. Do not authenticate, publish, register other hosts, or change account state unless the user explicitly requests it.
---

# Simplicio Runtime

Simplicio is the governed execution layer. Use its live MCP tool schemas rather than assuming arguments from documentation. The plugin's MCP bootstrap installs the pinned compatible Runtime when none is available, then launches the complete stdio server without facade mode. The Runtime owns authentication, safety gates, effects, receipts, and reconciliation; this skill does not bypass or duplicate those controls.

## Availability and scope

- Identify the target repository and read its local instructions before Runtime operations.
- Use the available `simplicio_*` MCP tools. If the user explicitly requires Simplicio and those tools are unavailable, inspect the plugin bootstrap log and report the missing Runtime or server instead of claiming Simplicio execution.
- Treat installed binary, running MCP server, live tool schemas, login, update, release, and validated command results as separate evidence lanes.
- Tool discovery is public, but protected calls can return `login_required`. Never start login inside the MCP stdio process and never paste or request passwords, device codes, access tokens, refresh tokens, or client secrets.
- Preserve unrelated dirty work and keep every effect inside the repository and task the user placed in scope.

## Repository workflow

For non-trivial repository work:

1. Call `simplicio_map` with a bounded orientation request for the actual task and repository.
2. Call `simplicio_memory` with a focused query before rediscovering project decisions.
3. Use `simplicio_read`, `simplicio_search`, and `simplicio_symbol` for compact evidence when their live schemas fit the need.
4. Before a mutation, classify it with `simplicio_gate`. Obtain explicit authorization immediately before effects that need confirmation; the user's authorization covers only the requested scope.
5. Use `simplicio_checkpoint` before a risky or broad edit when the live tool is available. Prefer `simplicio_edit` for bounded deterministic changes and `simplicio_run` for governed multi-step execution.
6. Verify with `simplicio_validate` plus the repository's relevant focused tests. Reconcile an uncertain effect before retrying it.
7. Return the outcome first, then the meaningful receipt, `run_id`, evidence, and any unresolved gap.

Use `simplicio_exec` for every valid Simplicio CLI subcommand that does not have a more specific live MCP tool. It is not an arbitrary shell. Do not fall back to raw host mutations merely because a gate asks for confirmation or a tool call times out.

## Claims and token savings

- Distinguish source inspection, installed binary, running MCP server, authentication, and validated task results; evidence in one lane does not prove the others.
- Report token savings only when a receipt supplies a baseline, actual usage, and proof kind. Qualify the public "up to 96%" figure as a controlled-workload maximum, never an unconditional result.
- Mark unavailable or ambiguous evidence plainly instead of inventing a successful result.

## Bundled Runtime system contract

The plugin also carries the first-party Runtime system contract in
`references/capabilities.yaml` and `references/interfaces.md`. Consult those
files before relying on an unfamiliar Runtime or native capability. Preserve
the following boundaries:

- Runtime governs native execution, MCP, gates, checkpoints, durable receipts,
  backpressure, pools, memory, and governed subagents; it does not replace
  Mapper's survey or Dev CLI's mutation contract.
- Loop remains operational without Runtime for ordinary orchestration. Use
  Runtime only when native execution, MCP, governance, receipts, checkpoints,
  backpressure, or governed subagents are required.
- Require explicit capability, repository, scope, and effect policy before
  side effects. Reconcile only from durable evidence; never synthesize a
  receipt or delete an unknown-effect lock.
- Keep the deterministic route: one to three tasks use direct parallelism and
  more than three tasks activate Prism. Physical resource, lease,
  backpressure, and effect-authority limits still govern admission.

---
name: simplicio-prism
description: Route broad or ambiguous work across Simplicio Mapper, Fast, Dev CLI, Loop, and Runtime. Use when a request spans components, requires choosing the correct capability, needs an end-to-end workflow, or the agent is unsure which Simplicio skill to invoke. Prism classifies and composes; it does not execute mutations itself.
---

# Simplicio Prism

## Worker preflight and centralized artifact policy

Before routing or operating, each worker reads repository `AGENTS.md`, `CLAUDE.md`, and all relevant local skills. Prism only composes a route after that preflight. One binary/artifact set is built centrally from the canonical default branch and shared read-only; workers never rebuild binaries or regenerate canonical Mapper/Fast artifacts. Worktrees isolate source edits and receipts only. Route evidence and receipts carry repository/revision, binary digest/version, Mapper generation, and artifact digest. Missing, stale, incompatible, or mismatched central artifacts fail closed and select the central rebuild path only.

The async boundary is explicit: Loop/Prism uses Python `asyncio` for scheduling, leases, and I/O; Runtime/Tokio owns gates, effects, receipts, and reconciliation. Neither async layer authorizes a worker-local rebuild or canonical artifact regeneration.


Use Prism as the top-level capability router. Read `references/capabilities.yaml` for routing rules and `references/recipes.md` for end-to-end compositions. Load a component skill only after Prism has selected it; do not duplicate component documentation here.

## Generate the complete interface map

Run the inventory generator against the actual checkout before relying on an interface:

```bash
python3 scripts/generate_capability_inventory.py /path/to/repository \
  --output /path/to/repository/capability-inventory.json
python3 scripts/generate_capability_inventory.py \
  --validate /path/to/repository/capability-inventory.json
```

The inventory covers CLI entry points and subcommands, MCP registrations, public Python and Rust APIs, configuration files, inferred inputs/outputs/effects, observed errors and fallbacks, dependency/version data, compatibility, and cost estimates. Static cost and semantic contracts remain `requires_review` until measured or supplied in `capability-overrides.json`. Use `references/capability-record.schema.json` and `references/discovery.md` to interpret confidence.

## Routing algorithm

1. Classify intent as survey, retrieve, mutate, validate, orchestrate, govern, or mixed.
2. Check repository, revision, scope, availability, preconditions, and side-effect policy.
3. Select the smallest capability set and order dependencies before dependents.
4. Require Mapper before non-trivial mutation; require Dev CLI for mutation.
5. Add Fast for compatible repeated/large retrieval.
6. Add Loop for multi-step, parallel, retryable, or convergent work.
7. Add Runtime only for MCP, native execution, gates, receipts, checkpoints, backpressure, or governed subagents.
8. Emit a routing decision with reasons, fallbacks, and expected evidence.

For task-count routing, one to three tasks use direct parallelism; more than three tasks activate
Prism. An omitted quantity defaults to a minimum logical batch of ten tasks per slot. Slot count,
slot capacity, and Prism wave width have no logical upper bound; physical resource/lease governors
may still defer execution. Always query Fast from the fresh Mapper snapshot before selecting the
route when the repository already provides that integration.

## Non-negotiable boundaries

- Prism never edits files and never fabricates a capability.
- Unknown or unavailable capabilities become explicit `unresolved` items.
- Loop remains usable without Runtime.
- A reported success is not completion until the selected verifier proves it.
- Prefer the cheapest capability that satisfies the contract.

## Contract

Return `route_id`, `intent`, `selected_capabilities`, `order`, `preconditions`, `fallbacks`, `cost_estimate`, `evidence_requirements`, and `unresolved`.

## Resources

- `references/capabilities.yaml`: cross-component registry and decision matrix.
- `references/recipes.md`: tested compositions for common workflows.
- `scripts/probe-capabilities.py`: validate the registry and detect duplicate IDs.

## Runtime precedence (normative, 2026-08-05)

Consult Runtime before composing a cross-component route. Runtime has peer routes
for Mapper, Fast, and Loop only; Dev CLI is selected only as `loop.dev_cli` after
Loop activation. Direct file edits default to `simplicio edit`. Standalone
component packages remain callable when Runtime or a flow is absent.

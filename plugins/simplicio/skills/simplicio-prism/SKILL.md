---
name: simplicio-prism
description: Route broad or ambiguous work across Simplicio Mapper, Fast, Dev CLI, Loop, and Runtime. Use when a request spans components, requires choosing the correct capability, needs an end-to-end workflow, or the agent is unsure which Simplicio skill to invoke. Prism classifies and composes; it does not execute mutations itself.
---

# Simplicio Prism

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

Task-count routing is fixed: one to three tasks use direct parallelism and more than three tasks
activate Prism. An omitted quantity means at least ten logical tasks per slot. Slot count,
capacity, and wave width have no logical upper bound; physical resource and lease governors remain
the only execution backpressure. Query Fast from the fresh Mapper snapshot before route selection
when the repository exposes that integration.

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

When Runtime is available, consult its route decision before composing capabilities.
The only peer operator routes are `mapper`, `fast`, and `loop`. Do not select
Dev CLI as a top-level Runtime capability; it is selected only under
`loop.dev_cli` after Loop activation. For direct file edits, select the Runtime
`simplicio edit` writer by default. Standalone package CLIs remain callable when
Runtime or a flow is absent, with degraded evidence reported explicitly.

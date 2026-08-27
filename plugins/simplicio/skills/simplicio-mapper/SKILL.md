---
name: simplicio-mapper
description: Survey and understand Simplicio codebases before action. Use for repository discovery, architecture mapping, symbol and dependency lookup, call-graph analysis, precedent search, snapshot creation, context selection, and any task where an agent must understand the project before editing. Do not use it as the mutation owner.
---

# Simplicio Mapper

Use Mapper as the canonical SURVEY and context-selection layer. Produce a bounded, reproducible project snapshot before any non-trivial change. Read `references/capabilities.yaml` for the complete capability catalog and `references/interfaces.md` for interface-specific details.

## Complete interface map

When documenting or invoking a concrete Mapper release, use the Prism inventory generator to record CLI, MCP, Python, Rust, configuration, I/O, effects, errors, fallbacks, dependencies, cost, version, and compatibility. Treat static inferences as review-required until validated.

## Routing

- Invoke for `mapear`, `entender`, `localizar`, `impacto`, `dependências`, `precedente`, `call graph`, `snapshot` or context selection.
- Invoke before Dev CLI mutations unless a fresh compatible snapshot is already available.
- Add Fast when the query is repeated, broad, or latency-sensitive and a compatible index exists.
- Do not edit files, invent missing symbols, or claim that a snapshot proves behavior.
- If Mapper is unavailable, use the smallest read-only native fallback and mark the result `survey-degraded`.

## Required workflow

1. Resolve repository, revision, scope, and requested intent.
2. Reuse a fresh snapshot only when repository revision and scope match.
3. Run the narrowest survey that answers the request.
4. Return evidence locations, uncertainty, and the snapshot identifier.
5. Hand the snapshot and selected context to Dev CLI, Loop, or Prism.

## Contract

Return `snapshot_id`, `repo`, `revision`, `scope`, `artifacts`, `selected_context`, `unresolved_questions`, and `verification`. Keep context minimal; never paste an entire repository when a symbol/file slice is sufficient.

## Resources

- `references/capabilities.yaml`: machine-readable capability map.
- `references/interfaces.md`: inputs, outputs, freshness, and fallbacks.
- `scripts/probe-capabilities.py`: validate the capability manifest and detect duplicate IDs.

## Runtime integration boundary (normative, 2026-08-05)

Mapper is a peer Runtime route and the project-context authority. Runtime selects it
for project-scoped requests, including edits that need repository awareness. Mapper
remains read-only: it creates bounded snapshots, provenance, and handoffs, but never
owns a source mutation.

A fresh, complete, unlocked handoff is required before another component treats the
snapshot as current. A stale, incomplete, locked, or absent artifact is a degraded
context result, not permission to invent context. Direct standalone Mapper use remains
valid without Runtime, Loop, or a cross-component contract.

---
name: simplicio-fast
description: Accelerate Simplicio retrieval with indexed search, ranking, cache, mmap, and bounded parallel reads. Use for repeated or large context lookups, low-latency symbol/file retrieval, snapshot-backed ranking, and cache-aware discovery. Do not use it as the source of truth or as a file mutation tool.
---

# Simplicio Fast

Use Fast as an acceleration layer over Mapper's canonical survey data. Prefer it when an index is compatible with the requested repository revision and scope. Read `references/capabilities.yaml` and `references/interfaces.md` before using an unfamiliar operation.

## Complete interface map

Use the generated Prism inventory for the installed Fast release. It records CLI/MCP surfaces, Python/Rust APIs, configuration, I/O, effects, errors, fallbacks, dependencies, measured or unmeasured cost, version, and compatibility. Do not promote an inferred field to a guarantee without evidence.

## Routing

- Invoke for `buscar rápido`, repeated lookup, ranking, large repositories, low latency, cache hits, index queries, or parallel read-only retrieval.
- Require a compatible Mapper snapshot or explicitly report that the result is unanchored.
- Consume the fresh Mapper handoff/provenance first; record its source revision and Fast snapshot
  generation in every route decision that uses Fast.
- Never treat a stale cache as current project truth.
- Never edit files, approve a change, or replace Dev CLI validation.
- Fall back to Mapper's direct survey when the index is missing, stale, corrupt, or incomplete.

## Required workflow

1. Check repository revision, snapshot, index schema, and freshness.
2. Normalize the query and choose the narrowest index.
3. Retrieve and rank bounded results.
4. Return evidence paths, scores, freshness, and omissions.
5. Let Mapper or Dev CLI verify semantics before action.

## Contract

Return `snapshot_id`, `index_id`, `query`, `results`, `freshness`, `ranking_basis`, `omissions`, and `fallback_used`. Keep ranking explainable and deterministic for the same inputs.

## Resources

- `references/capabilities.yaml`: machine-readable capability map.
- `references/interfaces.md`: index, cache, ranking, and fallback rules.
- `scripts/probe-capabilities.py`: validate the capability manifest and detect duplicate IDs.

## Runtime integration boundary (normative, 2026-08-05)

Fast is a conditional peer route, never an unconditional hop. Runtime enables Fast
only when a compatible fresh Mapper artifact/handoff anchors the query, or when
client output is explicitly being transformed into a Mapper/Fast artifact. Runtime
must keep Fast disabled for ordinary unanchored edits and simple reads.

Fast may operate standalone, but it never becomes project truth, never mutates source
files, and never replaces Mapper freshness/provenance checks. If its artifact is
missing, stale, corrupt, incomplete, or incompatible, fall back to direct Mapper or
the smallest read-only path and report the fallback.

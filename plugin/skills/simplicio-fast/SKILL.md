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

Runtime selects Fast only when a fresh compatible Mapper artifact/handoff exists or
when client output is explicitly being transformed into a Mapper/Fast artifact.
Fast is not the default for an unanchored edit or read, never writes source files,
and falls back to Mapper when its artifact is stale, missing, corrupt, or incomplete.

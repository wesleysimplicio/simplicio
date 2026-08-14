# Mapper interfaces

Use the repository's installed Mapper CLI/API/MCP surface discovered at runtime. Do not invent command names. The capability ID is stable; the concrete adapter may vary by version.

## Input rules

- Pin `repository`, `revision`, and `scope`.
- Treat an omitted revision as the current checkout only when the caller explicitly permits it.
- Reuse a snapshot only when revision, scope, schema, and Mapper version match.

## Output rules

Every result carries `snapshot_id`, evidence locations, freshness, and unresolved items. A missing symbol or incomplete language parser is uncertainty, not a successful empty answer.

## Handoff rules

Pass Mapper output to Fast for retrieval or to Dev CLI for mutation. Loop receives the snapshot as immutable task context. Runtime may persist the handoff but must not rewrite its meaning.

## Fallbacks

If indexing fails, perform a bounded read-only survey and mark `survey-degraded`. If revision cannot be proven, stop before mutation.

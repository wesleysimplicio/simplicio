# Fast interfaces

Fast is an acceleration layer, not canonical project truth. Bind every index and cache result to a Mapper `snapshot_id` and repository revision.

## Selection

Use indexed retrieval for repeated, broad, or latency-sensitive read-only queries. Use direct Mapper survey when the index is stale, absent, corrupt, incomplete, or semantically ambiguous.

## Result integrity

Return evidence paths, score/ranking basis, index schema, cache age, revision, and omissions. A cache hit without freshness proof is `untrusted-cache`.

## Parallelism

Bound batch concurrency and preserve query order. Do not let a fast partial batch appear complete; report per-query status.

## Side effects

Index refresh may write only index/cache state. Fast never edits source files and never substitutes Dev CLI validation.

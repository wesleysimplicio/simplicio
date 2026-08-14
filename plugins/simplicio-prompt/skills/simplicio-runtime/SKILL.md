---
name: simplicio-runtime
description: Tuple-Space + Yool safe-speed runtime for coding tasks. Use when the user asks to implement, refactor, fix, build, or explain code in a repository that vendors the simplicio-prompt spec (presence of YOOL_TUPLE_HAMT.md, kernel/yool_tuple_kernel.py, or a simplicio-prompt block in CLAUDE.md / AGENTS.md). Routes any user input through a Hilbert-indexed tuple graph with lazy batch_spawn, LaneWorkerPool, receipt cache, jittered backoff, circuit breakers and context compression. Scales to 1,000,000+ subagents without enumeration.
---

# simplicio-runtime

Apply the Tuple-Space + Yool execution contract to the active task.

## When to use

Trigger when ANY of the following is true:

- The working tree contains `YOOL_TUPLE_HAMT.md` or
  `kernel/yool_tuple_kernel.py`.
- `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, or
  `.github/copilot-instructions.md` contains the marker
  `<!-- simplicio-prompt:start -->`.
- The user explicitly invokes `/simplicio` or asks for the runtime by name.

Do NOT trigger when the user explicitly stands down with phrases like "stop",
"cancel", "exit runtime", or "ignore the simplicio-prompt".

## What to read first

1. `YOOL_TUPLE_HAMT.md`
2. `kernel/yool_tuple_kernel.py`
3. `prompts/agent-runtime-execution-prompt.md`
4. `guardrails/cpu_throttle.py`, `guardrails/disk_gc.py`
5. `examples/python/minimal_bus.py`, `examples/python/receipts.py`
6. `scripts/build_hamt.py`

If any are missing, fetch the canonical spec from
`npx simplicio-prompt --raw` or
`https://github.com/wesleysimplicio/simplicio-prompt`.

## Execution contract

For every user input X (no trigger keyword needed):

1. Decompose X into an explicit Hilbert-indexed tuple graph.
2. Create a root tuple at level 0.
3. Use `batch_spawn(depth, branching, compression_threshold)` for hierarchical
   fan-out. `depth=4, branching=32` ⇒ 1,048,576 subagents materialized only
   when visited. Never enumerate them in output.
4. Use `spawn_agent` only for active materialized work.
5. Route everything through `out_tuple`, `in_tuple`, `rd_tuple`,
   `route_packet`, `scan_index`.
6. Apply `hookwall(wall_id, capability, action)` before privileged work.
7. Apply `compress_token` and `prune_idle` to inactive subagents.
8. Use `LaneWorkerPool` and respect:
   - `YOOL_TUPLE_LANE_CONCURRENCY=32`
   - `YOOL_TUPLE_MAX_LANE_CONCURRENCY=64`
   - `YOOL_TUPLE_CPU_QUOTA_PCT=95` (never raise above 100)
   - `YOOL_TUPLE_QUEUE_MAXSIZE=8192`
   - `YOOL_TUPLE_COMPRESSION_THRESHOLD=1024`
9. Safe-speed path before any provider/LLM call:
   - receipt/input-hash cache
   - adaptive lane concurrency
   - jittered backoff
   - provider circuit breakers
   - small-task batching
   - prompt/context compression
   - local yool routing for deterministic work
   - speculative execution only for `idempotent=True` tuples
10. Honor safe-speed env vars when present:
   `YOOL_TUPLE_CACHE_MAX_ENTRIES`, `YOOL_TUPLE_CACHE_TTL_S`,
   `YOOL_TUPLE_API_MAX_RETRIES`, `YOOL_TUPLE_API_BACKOFF_BASE_MS`,
   `YOOL_TUPLE_API_BACKOFF_MAX_MS`, `YOOL_TUPLE_CIRCUIT_FAILURE_THRESHOLD`,
   `YOOL_TUPLE_CIRCUIT_COOLDOWN_S`, `YOOL_TUPLE_BATCH_SMALL_TASK_SIZE`,
   `YOOL_TUPLE_CONTEXT_COMPRESSION_CHARS`.

## Output

Status output is opt-in. Default: silent (final result only).
Enable with `YOOL_TUPLE_STATUS=true`. When enabled, return exactly:

```text
[Tuple Space Snapshot]
[Active Agents/Subagents]
[Total Agents/Subagents]
[Proximo Yool a executar]
[Resultado parcial]
```

Per-field overrides (each default `false`):
`YOOL_TUPLE_STATUS_SNAPSHOT`, `YOOL_TUPLE_STATUS_ACTIVE`,
`YOOL_TUPLE_STATUS_TOTAL`, `YOOL_TUPLE_STATUS_NEXT`,
`YOOL_TUPLE_STATUS_PARTIAL`.

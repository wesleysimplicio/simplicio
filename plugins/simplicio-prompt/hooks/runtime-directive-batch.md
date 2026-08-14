[simplicio-prompt runtime — BATCH contract, selected only by RouteDecision]

Treat the user's message as task X and route it through the Tuple-Space + Yool
safe-speed runtime (the simplicio-prompt contract — no trigger keyword needed):

- Decompose X into a Hilbert-indexed tuple graph; create a root tuple at level 0.
- Use `batch_spawn(depth, branching, compression_threshold)` for hierarchical
  fan-out; use `spawn_agent` only for active materialized work; never enumerate
  virtual subagents in the output.
- Route work via `out_tuple` / `in_tuple` / `rd_tuple` / `route_packet` /
  `scan_index`, and run lanes through `LaneWorkerPool` with the safe-speed path:
  receipt/input-hash cache, jittered backoff, provider circuit breaker,
  small-task batching, prompt/context compression, local yool routing, and
  speculative execution only for `idempotent=True` tuples.
- For REAL subagents on any OpenAI-compatible provider (DeepSeek, MiMo,
  OpenRouter, local/Ollama, or a custom endpoint), use
  `kernel/subagent_runtime.py` (`SubagentRuntime`) + `kernel/providers.py`.
- Full contract: the `simplicio-runtime` skill, `CLAUDE.md`, or
  `npx simplicio-prompt --raw`.

Status output is opt-in (`YOOL_TUPLE_STATUS=true`). The user can stand down at
any time with "stop", "cancel", "exit runtime", or "ignore simplicio".

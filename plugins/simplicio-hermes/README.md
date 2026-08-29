# Simplicio Hermes native adapter

`simplicio-hermes` ships a native Python plugin for current Hermes Agent and a
thin JavaScript middleware adapter for compatible embedders. Both call the
deterministic Runtime bridges `prepare_model_call` and `record_model_result`;
neither calls an LLM, selects a model, activates fan-out, or duplicates
Mapper/Runtime logic.

The native plugin registers `on_session_start`, `pre_llm_call`,
`post_llm_call`, and `on_session_end`. `pre_llm_call` completes before Hermes
enters its tool-calling loop and injects only the bounded Runtime context
receipt. `post_llm_call` records the matching provider result receipt. Hermes'
native `pre_llm_call` contract is context-only and fail-open, so the plugin does
not claim that a Runtime failure can block the provider call.

```bash
hermes plugins install wesleysimplicio/simplicio/plugins/simplicio-hermes --force --enable
hermes plugins doctor simplicio-hermes --ci
```

The official Simplicio installers run both commands automatically when `hermes`
is detected. Restart a running Hermes CLI or gateway after installation so its
plugin registry reloads.

The JavaScript adapter remains available through `index.mjs` for embedders that
provide the richer `llm_request`/`llm_execution` middleware contract. A clean
Hermes installation is verified through the native manifest parser and hook
registration path; `hermes mcp test simplicio` alone is not treated as plugin
proof.

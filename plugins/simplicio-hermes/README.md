# Simplicio Hermes Mapper-only adapter

The Hermes plugin uses Simplicio only for authenticated repository mapping and
provider usage receipts. Native Hermes tools, terminal, edits, tests, approvals,
model selection and execution remain owned by Hermes and each project.

The Python adapter starts its own stdio Runtime with
`SIMPLICIO_RUNTIME_MODE=mapper-only`. It verifies that initialization and the
MCP tool catalogue confirm Mapper-only before calling a tool. Global settings,
project settings, Codex and any shared HTTP Runtime remain unchanged. An older
Runtime without Mapper-only support is declined; Hermes continues natively.

## Mapping and prompt caching

`on_session_start` starts a background map warmup. `pre_llm_call` prepares the
full native Mapper artifacts using Runtime authentication. On Hermes versions
with `register_middleware`, the `llm_request` middleware checks authentication
and repository generation before every provider request and inserts the entire
verified map into the provider's existing messages, system or instructions
shape. This uses Hermes' supported middleware rather than changing its global
hook output-spill limits.

The map bytes are stable across session, turn and request IDs. They contain no
per-request timestamps or local cache-hit flags. The adapter does not silently
truncate the map or replace it with a receipt handle. Runtime's normal source
selection limits and ignores still apply. Provider/model/tools, streaming,
sampling and existing cache settings are preserved.

Older Hermes versions retain the context-only pre-hook fallback. Their own hook
output limits may spill large maps; use a Hermes version with request middleware
for complete provider delivery. The plugin never disables host safeguards to
work around an older host.

A stable prefix makes provider prompt caching possible; a local Mapper cache
hit does not prove an LLM cache hit. `post_api_request` records actual host
usage/cache counters against the matching API request. Missing counters remain
unknown. No synthetic model request or paid warmup is performed.

## Login and availability

Mapper requires login. Runtime owns the saved session and subscription-period
verification; the plugin neither copies credentials nor opens login repeatedly.
Missing login, confirmed inactive subscription, timeout, offline Runtime,
unsupported Runtime or an invalid map simply omit Simplicio context. Hermes'
native request and project tools continue. The plugin registers no native tool
gate, edit wrapper, execution middleware, Loop or Fast integration.

## Install and validate

```bash
hermes plugins install wesleysimplicio/simplicio/plugins/simplicio-hermes --force --enable
hermes plugins doctor simplicio-hermes --ci
```

Use a Runtime build that advertises Mapper-only and restart Hermes after the
plugin update. A source merge alone does not update the installed binary.

The JavaScript embedder adapter in `index.mjs` follows the same Mapper-only and
best-effort policy. Its supplied bridge must expose `runtime_mode: "mapper-only"`
from a verified Runtime handshake and implement the prepare/record methods.
Legacy `best_effort` and `enforce` constructor options migrate to Mapper-only;
they do not retain provider blocking. An explicit `maxContextBytes` budget may
omit an oversized map, but never truncate it or block native work.

Run `python3 -m pytest tests/test_hermes_native_plugin.py` at the repository root
and `npm test --prefix plugins/simplicio-hermes` for the two adapters.

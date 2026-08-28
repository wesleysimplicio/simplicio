# Simplicio Hermes native adapter

`simplicio-hermes` is a thin native middleware adapter. It calls the
deterministic Runtime bridges `prepare_model_call` and
`record_model_result`; it does not call an LLM, select a model, activate fan
out, or duplicate Mapper/Runtime logic.

The adapter registers `on_session_start`, `llm_request`, `llm_execution`,
`post_api_request`, and `api_request_error`. `llm_request` must complete before
Hermes sends the provider request. The exact provider, model, tools, streaming
flags, cache directives, and provider-specific options are copied unchanged.
Only the bounded `ContextPacket` returned by Runtime is added to `messages` or
Responses `input`.

```js
import { createHermesPlugin } from "simplicio-hermes";

const plugin = createHermesPlugin({ runtime, mode: "enforce" });
// Hermes registers plugin.hooks using its native middleware registry.
```

Use `enforce` when a request must not proceed without a preparation receipt;
use `best_effort` only when Hermes' fail-open behavior is explicitly desired.
Every status has a stable reason code, and `protected` is false until context,
provider-path, and usage receipt stages are all observed.

## Installation boundary

The package and manifest are shipped here, but the repository does not contain
a Hermes executable or a verified Hermes 0.20.x plugin-install API. Therefore
the generic host registry remains fail-closed for `hermes-agent` until a clean
profile proves installation, repair, plugin enablement, MCP availability, and
multi-step provider coverage. `hermes mcp test simplicio` alone must not turn
the protected status green.

# Desktop Bot Mode

The Desktop Bot Center is a projection client. It does not own an agent loop,
session reducer, approval gate, RBAC decision, Computer Use lease, provider
credential, or Bot registry.

## Contract boundary

The optional `botCenter` member of `simplicio.desktop-snapshot/v1` carries a
`simplicio.bot-center-snapshot/v1` projection. The projection contains only
bounded, redacted data:

- Bot roster and lifecycle/reason codes derived from Runtime receipts;
- session events with causal parent IDs, tool cards, approvals, artifacts and
  attachment handles;
- Room membership and the canonical session binding;
- Computer capability and lease state;
- measured token/cache/cost telemetry when evidence exists.

The frontend never infers `connected`, `available`, or `human_control` from
local configuration. Missing Agent API data is rendered as
`agent_api_unavailable`; missing Computer backend data is rendered as
`computer_backend_unavailable` and actions stay disabled.

## Runtime dependencies

The projection becomes live only when the Runtime exposes the Agent API and
the canonical contracts tracked by:

- `simplicio-runtime#5167` — first-party Desktop/Agent API integration;
- `#5168` — local-first Agent API and streaming events;
- `#5180` — Bot registry/roster;
- `#5181` — bot-to-bot delivery ledger;
- `#5182` — Rooms/Groups on Session Service;
- `#5183` — Computer-per-Bot lease and takeover.

Until those contracts are present, the Tauri `desktop_bot_action` command fails
closed with `agent_api_unavailable`. This is intentional: a preview must not
look like a successful Runtime execution.

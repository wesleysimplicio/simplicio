# Bot Center status

The Bot Center projection shipped in the Desktop is intentionally bounded and
fail-closed. It shows Bot identity, sessions, Rooms, causal events, approvals,
artifacts and measured telemetry when the Runtime exposes them.

The Desktop does not own the Bot registry, session reducer, approval gate,
RBAC/policy decision, Computer lease or Agent loop. `desktop_bot_action`
returns `agent_api_unavailable` until the Runtime contract is present; no
preview button mutates local state or pretends to start work.

The remaining #216 acceptance depends on Runtime contracts for roster,
bot-to-bot delivery, Rooms and Computer-per-Bot takeover.

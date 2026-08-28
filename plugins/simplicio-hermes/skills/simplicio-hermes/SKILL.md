---
name: simplicio-hermes
description: Integrate or validate the Simplicio middleware adapter for Hermes model calls and provider receipts.
---

# Simplicio Hermes

Use the native middleware adapter to prepare Hermes model calls through the Simplicio Runtime and record redacted provider receipts.

## Workflow

1. Confirm the host loads the plugin manifest and middleware entry point.
2. Preserve the caller request; add only Runtime preparation metadata.
3. Keep preparation best-effort unless the host explicitly enables enforcement.
4. Record redacted usage and cache metadata only; never store prompts, credentials, or response bodies.
5. Run `npm test` in this plugin before delivery.

The Runtime response is authoritative. Treat a missing or malformed response as degraded operation and never synthesize a successful preparation or receipt.

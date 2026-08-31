---
name: simplicio-hermes
description: Integrate or validate the Hermes Mapper-only plugin, full-map request middleware, and provider cache receipts.
---

# Simplicio Hermes

1. Verify the native plugin manifest and, for full provider delivery, Hermes request middleware registration.
2. Start the plugin-owned Runtime in Mapper-only and verify its advertised mode and tool catalogue. Keep other clients' configuration unchanged.
3. Require Runtime login for Mapper. On missing auth or unavailable Runtime, preserve the native Hermes request and tools.
4. Prepare the full native map in the pre-hook and deliver its stable content through request middleware. Preserve provider, model, tools, streaming, and existing cache options.
5. Record only matching request identifiers and real provider usage. Missing cache telemetry remains unknown; keep credentials, prompts and response bodies out of receipts.
6. Run the native Python tests and this plugin's npm tests. Verify large maps, unavailable login, Runtime failure, native tool independence and request correlation.

Read the plugin README for legacy-host limitations and installation. Treat missing
or malformed Runtime evidence as degraded operation; never synthesize a
successful map or receipt. Hermes uses Mapper-only with best-effort delivery.

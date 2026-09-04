# Simplicio Hermes Mapper-only adapter

Version 0.4.0 keeps the adapter thin: Hermes owns provider execution and
Simplicio owns authenticated Mapper context plus redacted usage receipts.

## Request identity and receipts

Hermes 0.20.4+ request, session, turn, logical-request and attempt IDs are
forwarded byte-for-byte when the host supplies them. Missing values are marked
`synthetic`; synthetic identities never prove provider-path coverage. Warmup is
tagged separately and never enters the provider-result candidate set.

Zero candidates, ambiguous candidates, duplicate hooks and duplicate provider
IDs produce bounded `simplicio.hermes-correlation-receipt/v1` diagnostics rather
than silent returns. Those receipts contain identifiers and reason codes only;
prompt, response bodies and secrets are never copied.

## Provider and measurement evidence

Final `simplicio.hermes-usage-receipt/v1` receipts keep the local Mapper cache
and provider prompt cache in separate objects. A `mapper_cache_hit` only means
that the local map artifact was reused; it never proves a provider prompt-cache
hit or token savings. Provider cache state and token buckets are recorded only
from provider/host evidence, and numeric zero remains a measured value.

The provider route includes endpoint and API mode when Hermes supplies them.
API mode may also be identified from the native request shape. Every route
field includes a source or an explicit unavailable reason, and endpoint query
strings/fragments are discarded before recording.

Normal mode continues after incomplete measurement and emits
`measurement_status=unmeasured` with reason codes. For controlled benchmarks,
set `SIMPLICIO_HERMES_MEASUREMENT_MODE=strict` (or `benchmark`). That policy
rejects results without required provider usage or stable prepare-to-response
correlation. It does not rewrite the host outcome: a completed Hermes run can
still carry a failed bridge event or a rejected measurement.

Plugin-generated IDs are labeled `synthetic`. If any required correlation ID
(`host_session_id`, `turn_id`, or `api_request_id`) is synthetic, the receipt is
unmeasured rather than presenting that ID as provider-confirmed attribution.

## Python fallback contract

The Python fallback is resolved only from an explicitly configured executable
or an installer-managed Mapper manifest. Before a map
is used, the adapter executes `version --json` and validates producer, version,
protocol, schema, capabilities, digest and an explicit minimum/maximum
compatibility range. An incompatible or unverifiable Mapper fails closed; the
hook never installs, downloads, or invokes a model.

Fallback receipts use `producer=simplicio-mapper` and `backend=python`, include
version/digest/resolution source, and never claim native provenance. The map
cache generation hashes effective project file bytes (excluding `.git` and
`.simplicio`), so changing content while preserving `git status` invalidates a
stale map.

## Install and validate

```bash
hermes plugins install wesleysimplicio/simplicio/plugins/simplicio-hermes --force --enable
hermes plugins doctor simplicio-hermes --ci
```

Run `python3 -m pytest tests/test_hermes_native_plugin.py` and
`npm test --prefix plugins/simplicio-hermes`. A source merge does not update an
already installed plugin or Runtime. Official Hermes checkout and clean-profile
tests remain required release evidence when the host checkout is available.

# Desktop provider registry

The Desktop separates host evidence from model-provider credentials. A provider
card is derived from the registry, not from a host name or a successful config
file write.

## Canonical states

| State | Required evidence | Meaning |
| --- | --- | --- |
| `connected` | installed + registered + current live handshake | The Simplicio server identity and protocol were observed within the TTL. |
| `registered` | installed + registration read back | The config is present, but no current handshake was proven. |
| `detected` | installed host only | The host/CLI exists, but registration is not proven. |
| `needs_attention` | stale handshake/freshness or drift/incompatibility | Repair or verification is required. |
| `not_installed` | host/CLI absent | Installation instructions are the only safe action. |

`redactedProviderScan` is the dry-run/diagnostic surface. It is bounded by the
Runtime snapshot limit and contains evidence fields and action IDs only; it
never includes config files, credentials, prompts, or provider payloads.

Registration writes must remain atomic, create a recoverable backup, and read
back the resulting document before reporting `registered`. Connect, verify,
repair, and instruction actions must be idempotent. The registry intentionally
does not mark `hermes-agent` as supported until its clean-profile installer and
provider-path E2E contract is available.

## Reviewed installation from Desktop

The **Integrações MCP** navigation entry exposes a read-only review first.
`desktop_plan_integrations` runs `install --global --dry-run --json`, returns
only bounded target labels/change states, and hashes the underlying proposed
configuration without disclosing config bodies or paths to the webview.

After explicit consent, `desktop_repair_providers` serializes installation,
requires active access, regenerates the plan and rejects a changed digest.
It then runs `install --global --yes --json`: omitting `--yes` only produces
a plan, even on exit zero. Success requires `simplicio.install-apply/v1`,
`status: applied`, successful/skipped actions and a completed rollback
manifest. A failure may leave partial changes; the UI asks for diagnostics
and a fresh review rather than claiming that nothing happened.

This flow copies the bundled Runtime to its managed location and delegates
MCP/hook writes and backups to Runtime. It does not change PATH, launch a
global service or install every host's marketplace plugin. Those remain
explicit host-specific steps. A successful install is not a live MCP
handshake; reopen the client session to verify connection separately.

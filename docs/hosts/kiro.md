# Kiro integration

Kiro is detected by the exact `kiro-cli` executable. The default user-scoped
configuration is `~/.kiro/settings/mcp.json`; the workspace equivalent is
`.kiro/settings/mcp.json` when `--scope workspace` is selected.

The adapter writes only the managed `simplicio` MCP entry, preserves unrelated
settings, makes a backup before atomic replacement, and verifies the result.
Repeated installation is idempotent. The Runtime, not the installer, owns
the live MCP handshake.

Use `--dry-run` for a no-write preview and
`SIMPLICIO_SKIP_KIRO=1` to opt out.

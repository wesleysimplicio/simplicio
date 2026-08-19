# Connecting an MCP Client to Simplicio

Simplicio exposes a local [Model Context Protocol](https://modelcontextprotocol.io/) server. The Runtime owns authentication, entitlement checks, safety gates, and the embedded Python ecosystem; an MCP client only discovers and invokes the structured tools.

## Prerequisite: Google login

Product commands and MCP require an active Simplicio session, including during the public beta:

```bash
simplicio login google
simplicio auth status --json
```

Continue only when the status reports `active: true`. Never copy a password, device code, bearer token, refresh token, or client secret into an MCP config.

## Codex: local STDIO MCP and hooks

The official installer configures Codex to launch the installed binary directly:

```toml
[mcp_servers.simplicio]
command = "/path/to/simplicio"
args = ["serve", "--mcp", "--stdio"]
```

The installer also merges Simplicio `SessionStart`, `UserPromptSubmit`,
`SubagentStart`, and `PreToolUse` hooks into `~/.codex/hooks.json`, preserving
unrelated user hooks. Restart Codex and review the result in **Settings →
Hooks**. The Runtime still validates Google login and entitlement on every
local MCP session; never paste tokens into either config file.

To verify the registration:

```bash
codex mcp list
```

Set `SIMPLICIO_MCP_ROUTE=0` for a temporary hook escape hatch. Rerunning the
installer repairs the integration idempotently and leaves `.simplicio.bak`
copies of the original Codex files.

## Other clients: local STDIO

Add this server entry to any MCP-compatible client that supports STDIO:

```json
{
  "mcpServers": {
    "simplicio": {
      "command": "simplicio",
      "args": ["serve", "--mcp", "--stdio"]
    }
  }
}
```

Common locations:

| Client | File |
|---|---|
| Claude Code | `~/.claude/settings.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `.vscode/mcp.json` |
| Cline | `~/.config/cline/mcp_settings.json` |
| Continue | `~/.continue/config.json` |

Reload the client after editing its configuration. STDIO does not require a manually copied bearer token, but the local Runtime still requires the Google login above.

## Tools

The server advertises ten tools through `tools/list`:

| Tool | Purpose |
|---|---|
| `simplicio_map` | Compact structural repository map |
| `simplicio_memory` | Indexed project-memory recall |
| `simplicio_edit` | Structured deterministic file edits |
| `simplicio_gate` | Mission/effect safety gate |
| `simplicio_validate` | Contract-oriented validation |
| `simplicio_run` | Governed task execution |
| `simplicio_symbol` | Symbol/declaration navigation |
| `simplicio_search` | Structural or semantic search |
| `simplicio_read` | Compact file reads |
| `simplicio_exec` | Supervised external commands |

Always discover the live schemas at startup instead of hard-coding arguments:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | simplicio serve --mcp --stdio
```

A successful response contains the tool definitions. A `login required` error means the account session is not active; authenticate instead of bypassing the gate.

## Automatic setup

The official installers perform the binary checksum and embedded-bundle checks,
require active login, and configure Codex's local STDIO MCP plus Simplicio
hooks:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

For the full installation, update, benchmark, and troubleshooting guide, see [`README.md`](README.md).

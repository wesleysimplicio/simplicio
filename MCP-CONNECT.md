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

Codex integration is opt-in. The base installer leaves Codex unchanged. Enable
the versioned, reversible integration explicitly:

~~~bash
SIMPLICIO_INSTALL_CODEX=1 sh install.sh
~~~

When enabled, Codex launches the installed binary directly:

~~~toml
[mcp_servers.simplicio]
command = "/path/to/simplicio"
args = ["serve", "--mcp", "--stdio"]
~~~

STDIO is local and avoids a local HTTP daemon, but the Runtime still validates
Google login and entitlement on every MCP session. Existing user hooks remain
preserved; review enabled Simplicio hooks in Settings → Hooks and run codex mcp
list. Never paste tokens into either config file.

To verify the registration:

```bash
codex mcp list
```

The hook route is mandatory and has no environment-variable escape hatch.
Native reads, edits, shell commands, and directory exploration are denied; use
the Simplicio MCP tools. Rerunning the installer repairs the integration
idempotently. To repair the managed integration, rerun with
`SIMPLICIO_INSTALL_CODEX=1`. The integration helper keeps user data separate
and leaves `.simplicio.bak` copies of the original Codex files.

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

The official installers verify the binary checksum, Ed25519 signature, and
embedded-bundle contract, then require active login. Codex MCP registration and
routing hooks are opt-in; enable them explicitly with SIMPLICIO_INSTALL_CODEX=1.
Other MCP clients can use the local STDIO entry above without copying tokens.

A quick installer bootstrap is:
~~~bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
~~~

For the full installation, update, benchmark, and troubleshooting guide, see [`README.md`](README.md).

# Connecting an MCP Client to Simplicio

Simplicio exposes a local [Model Context Protocol](https://modelcontextprotocol.io/) server. The Runtime owns authentication, entitlement checks, safety gates, and the embedded Python ecosystem; an MCP client only discovers and invokes the structured tools.

## Prerequisite: Google login

Product commands and MCP require an active Simplicio session, including during the public beta:

```bash
simplicio auth login
simplicio auth status --json
```

Continue only when the status reports `active: true`. Never copy a password, device code, bearer token, refresh token, or client secret into an MCP config.

## Codex: local STDIO MCP and hooks

The installer automatically invokes the installed Runtime's host registrar.
There is no Codex opt-in flag and no separately downloaded hook. The Runtime
detects supported clients, records the absolute managed-binary path, preserves
existing user configuration, and installs native hooks only where a verified
native hook API is available.

Registration runs before login reporting, so a fresh installation is configured
even when the user has not authenticated yet. Protected MCP operations still
validate Google login and entitlement when they are used. Restart every open
client after installation so it reloads the MCP and hook files.

MCP clients launch `command` directly, so do not use `~` and do not expect
shell expansion.

#### Windows

~~~toml
[mcp_servers.simplicio]
command = "C:/Users/YourName/.simplicio/bin/simplicio.exe"
args = ["serve", "--mcp", "--stdio"]

[mcp_servers.simplicio.env]
SIMPLICIO_MCP_URL = "http://127.0.0.1:8787/mcp"
~~~

Use forward slashes in Windows TOML paths.

#### macOS

~~~toml
[mcp_servers.simplicio]
command = "/Users/your-name/.simplicio/bin/simplicio"
args = ["serve", "--mcp", "--stdio"]

[mcp_servers.simplicio.env]
SIMPLICIO_MCP_URL = "http://127.0.0.1:8787/mcp"
~~~

#### Linux

~~~toml
[mcp_servers.simplicio]
command = "/home/your-name/.simplicio/bin/simplicio"
args = ["serve", "--mcp", "--stdio"]

[mcp_servers.simplicio.env]
SIMPLICIO_MCP_URL = "http://127.0.0.1:8787/mcp"
~~~

STDIO is the primary local transport. The Runtime's JSON registration report
lists every client it detected and whether the MCP configuration or native hook
was written. A failed write makes installation fail rather than silently
continuing.

To inspect or repair the detected integrations:

~~~bash
simplicio mcp register --binary "$(command -v simplicio)" --json
~~~

Restart Codex and other open clients after registration. Never paste tokens into
client configuration files.

## Other clients: local STDIO

Add this server entry to any MCP-compatible client that supports STDIO:

```json
{
  "mcpServers": {
    "simplicio": {
      "command": "/absolute/path/to/.simplicio/bin/simplicio",
      "args": ["serve", "--mcp", "--stdio"]
    }
  }
}
```

Common locations:

| Client | File |
|---|---|
| Claude Code | `~/.claude.json` (user/local) or project `.mcp.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `.vscode/mcp.json` |
| Cline | `~/.config/cline/mcp_settings.json` |
| Continue | `~/.continue/config.json` |

Replace the placeholder with the installed binary's absolute path. Claude Code plugin-provided servers follow the plugin lifecycle; do not copy them into project configuration unless the host requires it. Reload the client after editing its configuration. STDIO does not require a manually copied bearer token, but the local Runtime still requires the Google login above.

## Tools

The public CLI/MCP vocabulary is `simplicio map`, `simplicio context`,
`simplicio memory`, `simplicio edit`, and `simplicio run`. Mapper observes,
Fast projects or retrieves, Dev CLI edits, Runtime governs, and Loop
converges. Claude and Hermes Mapper-only sessions advertise map/context
(and memory when the host profile allows it) and never advertise
`edit`/`run`/`loop`/`exec`. Full-mode hosts keep the broader Runtime surface.
Deprecated aliases (`mapper`, `index`, `code-graph`, `mapper-memory`) must
not appear as a second MCP tool. A Runtime below the unified-surface
minimum must not advertise the new names.

`tools/list` is the live authority. A current full-mode Runtime may advertise:

| Tool | Purpose |
|---|---|
| `simplicio_map` | Compact structural repository map (`simplicio map`) |
| `simplicio_context` | Bounded task context (`simplicio context`) |
| `simplicio_memory` | Indexed project-memory recall (`simplicio memory`) |
| `simplicio_edit` | Structured deterministic file edits (`simplicio edit`) |
| `simplicio_run` | Governed task execution (`simplicio run`) |
| `simplicio_gate` | Mission/effect safety gate |
| `simplicio_validate` | Contract-oriented validation |
| `simplicio_symbol` | Symbol/declaration navigation |
| `simplicio_search` | Structural or semantic search |
| `simplicio_read` | Compact file reads |
| `simplicio_exec` | Supervised external commands |

Always discover the live schemas at startup instead of hard-coding arguments:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | ~/.simplicio/bin/simplicio serve --mcp --stdio
```

A successful response contains the tool definitions. A `login required` error means the account session is not active; authenticate instead of bypassing the gate.

## Automatic setup

The official PyPI bootstrap verifies the binary checksum, Ed25519 signature,
and release-manifest contract, then requires active login. Codex MCP registration
and routing hooks are registered by the installer for supported hosts;
review the JSON receipt and any requested consent before relying on the integration.
Other MCP clients can use the local STDIO entry above without copying tokens.

A quick PyPI bootstrap is:
~~~bash
python3 -m pip install --upgrade simplicio-installer
simplicio install
~~~

For the full installation, update, benchmark, and troubleshooting guide, see [`README.md`](README.md).

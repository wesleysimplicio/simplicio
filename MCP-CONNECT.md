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

Codex integration is opt-in. The base installer leaves Codex unchanged. Enable
the versioned, reversible integration explicitly:

~~~bash
SIMPLICIO_INSTALL_CODEX=1 SIMPLICIO_CODEX_HOOK_REF=v3.8.35 sh install.sh
~~~

When enabled, the installer writes the absolute managed-binary path
automatically. If you inspect or repair `config.toml` manually, copy the block
for your operating system. MCP clients launch `command` directly, so do not
use `~` and do not expect shell expansion.

#### Windows

Use forward slashes in TOML. Windows accepts them, and they avoid invalid TOML
escapes such as `\U` in `C:\Users\...`.

~~~toml
[mcp_servers.simplicio]
command = "C:/Users/YourName/.simplicio/bin/simplicio.exe"
args = ["serve", "--mcp", "--stdio"]

[mcp_servers.simplicio.env]
SIMPLICIO_MCP_URL = "http://127.0.0.1:8787/mcp"
~~~

If you are testing a downloaded asset before installation, the same rule is
`C:/Users/YourName/Downloads/simplicio-windows-x64.exe`. Never paste
a raw-backslash Windows path into a double-quoted TOML command; use forward
slashes as shown above.

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

STDIO is the primary local transport and launches the managed binary directly.
`SIMPLICIO_MCP_URL` keeps the loopback HTTP endpoint discoverable for HTTP-only
or manual clients, but Codex should not use the URL as its primary registration.
The Runtime still validates Google login and entitlement on every MCP session.
Existing user hooks remain preserved; review enabled Simplicio hooks in Settings
→ Hooks and run codex mcp list. Never paste tokens into either config file.

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
  | ~/.simplicio/bin/simplicio serve --mcp --stdio
```

A successful response contains the tool definitions. A `login required` error means the account session is not active; authenticate instead of bypassing the gate.

## Automatic setup

The official PyPI bootstrap verifies the binary checksum, Ed25519 signature,
and release-manifest contract, then requires active login. Codex MCP registration
and routing hooks are opt-in; enable them explicitly after `simplicio install`.
Other MCP clients can use the local STDIO entry above without copying tokens.

A quick PyPI bootstrap is:
~~~bash
python3 -m pip install --upgrade simplicio-installer
simplicio install
~~~

For the full installation, update, benchmark, and troubleshooting guide, see [`README.md`](README.md).

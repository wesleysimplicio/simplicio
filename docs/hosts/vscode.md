# Visual Studio Code integration

Visual Studio Code is detected by the exact `code` or `code-insiders`
executable. The adapter supports the three documented scopes:

- user: `~/.vscode/mcp.json`
- workspace: `.vscode/mcp.json` in the workspace
- remote: `.vscode/mcp.json` in the selected remote workspace

The requested scope is explicit and never silently falls back to another one.
Registration preserves unrelated settings, uses an atomic replacement with a
backup, and verifies the managed MCP entry after writing. Runtime owns the
live handshake and remote-session evidence.

Preview with `--dry-run`; opt out with `SIMPLICIO_SKIP_VSCODE=1`.

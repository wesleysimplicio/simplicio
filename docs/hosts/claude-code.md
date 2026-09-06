# Claude Code integration

Claude Code is detected only by the exact `claude` executable. Simplicio does
not launch the host during discovery and never treats a similarly named binary
as Claude Code.

The installer writes one managed `simplicio` MCP entry to the user-scoped
`~/.claude/settings.json` file (or `~/.claude/.mcp.json` when that is the first
documented path available). Existing keys are preserved, writes are atomic,
and a `.simplicio.bak` copy is kept before a replacement. Re-running the
installer is a no-op after the entry is already correct.

The installer-scoped MCP entry sets `SIMPLICIO_RUNTIME_MODE=mapper-only`. This
keeps direct host registration aligned with the native Claude plugin: Mapper
discovery and read-only context are available, while edit, run, loop, and
execution surfaces are not advertised. Claude still owns its native editing
and terminal tools; a registration receipt is not a live handshake.

Live MCP registration and handshake evidence remain Runtime-owned. A dry run
reports the planned path without creating or changing files; set
`SIMPLICIO_SKIP_CLAUDE_CODE=1` to opt out.

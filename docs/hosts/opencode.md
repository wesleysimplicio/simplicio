# OpenCode integration

OpenCode is detected only by the exact `opencode` executable. Its user-scoped
MCP document is `~/.config/opencode/opencode.json`; workspace registration is
not inferred because it is not part of the verified contract in this matrix.

The installer preserves unrelated JSON, writes the managed `simplicio` entry
atomically, verifies the round trip, and keeps a recovery backup. Runtime
handshake evidence is reported separately from this config-level proof.

Use `--dry-run` to preview the change or `SIMPLICIO_SKIP_OPENCODE=1` to opt
out. No provider credentials or prompt content are written by the adapter.

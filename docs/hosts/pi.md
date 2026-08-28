# Pi and oh-my-pi integrations

Pi and oh-my-pi are separate hosts with separate exact probes:

- Pi: `pi`, user MCP file `~/.pi/agent/mcp.json`
- oh-my-pi: `omp`, user MCP file `~/.omp/mcp.json`

Neither name is treated as an alias for the other. The installer preserves
unrelated entries, writes each managed entry atomically, verifies the JSON
round trip, and is idempotent. Runtime owns live handshakes and any host-side
plugin semantics.

Use `--dry-run` or the corresponding `SIMPLICIO_SKIP_PI=1` and
`SIMPLICIO_SKIP_OH_MY_PI=1` opt-outs before changing either host.

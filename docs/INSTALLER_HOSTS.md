# Installer host registration

The public shell, PowerShell and PyPI installers delegate MCP configuration to
the downloaded Runtime. The expanded adapters ship in the signed
[Runtime v3.8.50 release](https://github.com/wesleysimplicio/simplicio/releases/tag/v3.8.50)
and are available through the public shell, PowerShell and PyPI installers.
Devin and Codebuff retain the manual integration requirements documented below.

## Additional user configuration paths

| Host | Default path | Upstream contract |
|---|---|---|
| Command Code | `~/.commandcode/mcp.json` | [Documentation](https://commandcode.ai/docs/settings) |
| Grok CLI (Superagent) | `~/.grok/settings.json` | [Documentation](https://github.com/superagent-ai/grok-cli) |
| MiMo Code | `~/.config/mimocode/mimocode.json` | [Documentation](https://github.com/XiaomiMiMo/MiMo-Code) |
| Amp | `~/.config/amp/settings.json` | [Documentation](https://ampcode.com/docs/customize/mcp) |
| OpenClaude | `~/.openclaude.json` | [Documentation](https://github.com/Gitlawb/openclaude) |
| oh-my-pi | `~/.omp/agent/mcp.json` | [Documentation](https://github.com/can1357/oh-my-pi) |
| Goose | `~/.config/goose/config.yaml` | [Documentation](https://block.github.io/goose/docs/guides/config-files/) |
| Auggie | `~/.augment/settings.json` | [Documentation](https://docs.augmentcode.com/cli/integrations) |
| Autohand Code | `~/.autohand/config.json` | [Documentation](https://github.com/autohandai/code-cli/blob/main/docs/config-reference.md) |
| Charm / Crush | `~/.config/crush/crush.json` | [Documentation](https://github.com/charmbracelet/crush) |
| Continue IDE | `~/.continue/mcpServers/simplicio.yaml` | [Documentation](https://docs.continue.dev/customize/mcp-tools) |
| Droid | `~/.factory/mcp.json` | [Documentation](https://docs.factory.ai/harness/connectors) |
| Kilo Code CLI | `~/.config/kilo/kilo.json` | [Documentation](https://kilo.ai/docs/automate/mcp/using-in-cli) |
| Kimi | `~/.kimi/mcp.json` | [Documentation](https://moonshotai.github.io/kimi-cli/en/customization/mcp.html) |
| Mistral Vibe | `~/.vibe/config.toml` | [Documentation](https://docs.mistral.ai/vibe/code/cli/mcp-servers) |
| Qwen Code | `~/.qwen/settings.json` | [Documentation](https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/) |
| Rovo Dev CLI | `~/.rovodev/mcp.json` | [Documentation](https://support.atlassian.com/rovo/docs/connect-to-an-mcp-server-in-rovo-dev-cli/) |
| Pi | `~/.pi/agent/extensions/simplicio.ts` | [Documentation](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md) |
| Codex | `~/.codex/config.toml` | [Documentation](https://developers.openai.com/codex/mcp/) |

Goose on Windows uses `%APPDATA%/Block/goose/config/config.yaml`.
The native planner uses the detected initialized configuration directory.
It never launches a host during planning. Registration uses the existing
transactional writer and returns per-file receipts.

## Verification

1. Install or initialize the client and run the Simplicio installer.
2. Inspect `simplicio mcp register --dry-run --binary <absolute-path> --json`.
3. Apply with `simplicio mcp register --binary <absolute-path> --json`.
4. Restart/reload the host. In Pi use `/reload`.
5. Confirm the client lists Simplicio tools, then make one read-only
   `simplicio_map` call in a test repository.

The PyPI receipt accepts Runtime `writes` entries with `done` or idempotent
`skipped` status, without confusing dry-run plans with completed registration.
Invalid files, JSONC and explicit custom config paths are preserved and reported.
A user's explicit disabled state stays disabled; registration does not override
the host's permission or trust prompts.

## Clients without a user MCP registry

- **Devin:** use [Devin MCP settings](https://docs.devin.ai/work-with-devin/mcp)
  in the environment where Devin executes. Install Simplicio there and configure
  a stdio server whose command is that environment's absolute binary path with
  arguments `serve --mcp --stdio`. Local desktop paths do not refer to Devin's
  cloud filesystem; organization authorization remains Devin-owned.
- **Codebuff:** use its [custom tools SDK](https://www.codebuff.com/docs/advanced/sdk)
  in a project integration. A global `~/.codebuff/mcp.json` contract was not
  verified. The installer reports this requirement rather than claiming success.

## Maintainer validation

Runtime adapter fixtures cover JSON/YAML/TOML parsing, Windows command paths,
unrelated server preservation, idempotence and malformed/custom configuration.
The Pi extension tests exercise MCP initialization, tool discovery, calls,
shutdown, failure handling and concurrent stdio responses.
These tests do not establish live acceptance by every third-party client.

# Simplicio public plugin marketplaces

This repository publishes installable Codex and Claude Code marketplaces for
the Simplicio ecosystem.

## Install in Codex

```bash
codex plugin marketplace add wesleysimplicio/simplicio --ref master
codex plugin add simplicio@simplicio-codex
```

Start a new Codex task after installation. The plugin's MCP bootstrap then
reuses a compatible Simplicio Runtime or installs the pinned, verified Runtime
release and starts its complete stdio MCP surface. `simplicio_exec` exposes
every valid CLI subcommand, while the Runtime publishes its dedicated tools
dynamically. Authentication remains explicit; installation never logs in on
the user's behalf.

The Codex package, including its official Simplicio logo, lives at
[`plugins/simplicio`](plugins/simplicio).

## Install in Claude Code

In Claude Code:

```text
/plugin marketplace add wesleysimplicio/simplicio
/plugin install simplicio-loop@simplicio
/plugin install simplicio-prompt@simplicio
/plugin install simplicio-sprint@simplicio
```

Install the Runtime MCP separately for Claude Code and restart the host:

```bash
simplicio install --global --dry-run --json
simplicio install --global --yes --json
```

The Runtime entrypoint is `simplicio serve --mcp --stdio`.

## Published components

| Plugin | Owns | Source |
|---|---|---|
| `simplicio` (Codex) | Verified Runtime bootstrap, complete live MCP surface, all CLI commands through `simplicio_exec`, setup and Runtime skills | This repository |
| `simplicio-loop` | Loop, tasks alias, orient, review, compress, learn, autoresearch, Prism, Mapper, Fast, Dev CLI, Runtime skills and safety hooks | [`simplicio-loop`](https://github.com/wesleysimplicio/simplicio-loop) |
| `simplicio-prompt` | Tuple-Space/Yool prompt contract, fan-out commands, and opt-in prompt adapter | [`simplicio-prompt`](https://github.com/wesleysimplicio/simplicio-prompt) |
| `simplicio-sprint` | Sprint intake, mapping, evidence collection, and draft-PR delivery | [`simplicio-sprint`](https://github.com/wesleysimplicio/simplicio-sprint) |

The Loop plugin is the default integration. Prompt and Sprint remain separate
installable plugins so their hooks and commands do not create duplicate runtime
activation or hidden provider calls.

## Verification

```bash
simplicio plugin list --json
simplicio-plugins --json
simplicio self-test --json
simplicio contracts smoke --json
```

The plugin bundles are MIT-licensed within their plugin directories. The root
Runtime distribution and its release artifacts retain their repository license.

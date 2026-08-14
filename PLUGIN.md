# Simplicio public plugin marketplace

This repository publishes the installable Claude Code marketplace for the
Simplicio ecosystem. The compiled `simplicio` Runtime remains a separate
platform-specific binary and provides the MCP server; the marketplace carries
the host-side skills and adapters.

## Install

In Claude Code:

```text
/plugin marketplace add wesleysimplicio/simplicio
/plugin install simplicio-loop@simplicio
/plugin install simplicio-prompt@simplicio
/plugin install simplicio-sprint@simplicio
```

Install the Runtime MCP separately and restart the host:

```bash
simplicio install --global --dry-run --json
simplicio install --global --yes --json
```

The Runtime entrypoint is `simplicio serve --mcp --stdio`.

## Published components

| Plugin | Owns | Source |
|---|---|---|
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

The bundle is local and MIT-licensed within its plugin directories. The root
Runtime distribution and its release artifacts retain their repository license.

# Simplicio public plugins and host integrations

This repository publishes one Simplicio package through native Codex and Claude
Code marketplaces, the portable Agent Plugins v1 contract, and a Gemini CLI
extension. Hosts without a verified plugin API use the Runtime-owned MCP/config
integration instead of an invented plugin format.

The official `install.sh` and `install.ps1` detect installed hosts and install
every compatible published package automatically. Claude Code, GitHub Copilot
CLI, and Qwen Code receive all five marketplace plugins; Codex and Gemini
receive their native package; Cursor and Kiro receive the portable Agent Plugin;
and Hermes receives and enables the native `simplicio-hermes` plugin.

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

## Install as an Agent Plugin

The portable package at `plugins/simplicio` contains the Agent Plugins v1
`plugin.json`, `mcp.json`, and shared `skills/`. Cursor, GitHub Copilot,
Kiro, and Qwen Code can consume this format according to their own install UI or
CLI.

For a local checkout, select or install:

```text
./plugins/simplicio
```

## Install in Gemini CLI

Install the repository checkout's package directory:

```bash
gemini extensions install ./plugins/simplicio
```

The native `gemini-extension.json` starts the same verified bootstrap and
Gemini discovers the bundled skills.

## Install in Claude Code

In Claude Code:

```text
/plugin marketplace add wesleysimplicio/simplicio
/plugin install simplicio@simplicio
```

The main `simplicio` package bootstraps the verified Runtime automatically and
installs mandatory Mapper-only Claude hooks. The hooks keep the project map in
`.simplicio/hook-context/`, reuse it while the project generation is unchanged,
and refresh it after a visible project change. They call the Runtime map
operation first and use the installed `simplicio-mapper` Python project as a
Mapper-only fallback if Runtime mapping fails. Fast and other context
accelerators are not lifecycle dependencies. To provision the fallback ahead
of time, use `python -m pip install --upgrade simplicio-mapper` or point the
hook at a checkout with `SIMPLICIO_MAPPER_ROOT`.

The separate `simplicio-loop`, `simplicio-prompt`, `simplicio-sprint`, and
`simplicio-hermes` packages remain available for explicit workflows and their
respective hosts. Install `simplicio-loop` only when the Loop orchestration
surface is intentionally needed.

## Published components

| Plugin | Owns | Source |
|---|---|---|
| `simplicio` (Codex, Claude, Agent Plugins v1, Gemini) | Verified Runtime bootstrap, complete live MCP surface, shared skills, and Runtime-managed pre-hooks | This repository |
| `simplicio-loop` | Loop, tasks alias, orient, review, compress, learn, autoresearch, Prism, Mapper, Fast, Dev CLI, Runtime skills and safety hooks | [`simplicio-loop`](https://github.com/wesleysimplicio/simplicio-loop) |
| `simplicio-prompt` | Tuple-Space/Yool prompt contract, fan-out commands, and opt-in prompt adapter | [`simplicio-prompt`](https://github.com/wesleysimplicio/simplicio-prompt) |
| `simplicio-sprint` | Sprint intake, mapping, evidence collection, and draft-PR delivery | [`simplicio-sprint`](https://github.com/wesleysimplicio/simplicio-sprint) |
| `simplicio-hermes` | Native `pre_llm_call` context preparation and post-call Runtime receipts for Hermes Agent | This repository |

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

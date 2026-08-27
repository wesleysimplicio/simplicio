# Simplicio for Codex

![Simplicio Runtime](./assets/simplicio-hero.png)

This Codex plugin bootstraps a release-contract-valid Simplicio Runtime, exposes
its complete live MCP surface, and teaches Codex the governed Simplicio
workflow.

## Automatic Runtime bootstrap

Codex plugins do not have an install-time script event. The bundled MCP server
therefore performs an idempotent bootstrap when the first new Codex task loads
the enabled plugin:

1. Reuse a valid Simplicio Runtime v3.8.35 or newer when one is already present.
2. Otherwise download the official installer from an immutable repository
   commit and verify the installer SHA-256 before execution.
3. Install the pinned Runtime release through its fail-closed SHA-256 and
   Ed25519 release checks.
4. Start `simplicio serve --mcp --stdio --no-facade-mode` with stdout reserved
   exclusively for MCP JSON-RPC.

The managed binary is installed at `~/.simplicio/bin/simplicio`. Existing valid
installs at `~/.local/bin/simplicio` are reused. Concurrent starts share an
installation lock, and diagnostics go to
`~/.simplicio/logs/codex-plugin-bootstrap.log`.

Runtime v3.8.35 supports macOS arm64/x64, Linux x64, and Windows x64. The plugin
launcher requires Node.js 18 or newer to be available to Codex MCP processes.
The official Unix installer additionally requires Python 3 and either curl or
wget. The current package is live-tested on macOS arm64; the other targets use
the same official installers but still require platform-matrix verification.

## Authentication

Installation never starts an account flow or consumes MCP stdin. Tool schemas
can load before login, while protected calls fail closed until the user
explicitly authenticates:

```bash
$HOME/.simplicio/bin/simplicio login google --json
$HOME/.simplicio/bin/simplicio auth status --json
```

## Commands and tools

The plugin does not hard-code a stale command list. Runtime v3.8.35 currently
advertises 44 MCP tools, and later compatible releases supply their schemas
dynamically. `simplicio_exec` is the governed supertool for every valid
Simplicio CLI subcommand; individual CLI commands are not duplicated as 44+
separate plugin definitions.

Included skills:

- `simplicio-runtime`: map, recall, edit, execute, and validate through live MCP
  schemas, with the Runtime capability and interface contracts bundled locally.
- `simplicio-setup`: verify bootstrap, authentication, repair, and explicit
  global host registration.
- `simplicio-mapper`: survey repositories and produce bounded, revision-aware
  context before implementation.
- `simplicio-fast`: accelerate indexed, cache-aware, read-only retrieval while
  preserving Mapper provenance and freshness checks.
- `simplicio-dev-cli`: perform deterministic edits, tests, diagnostics, and
  evidence-backed validation through the Dev CLI contract.
- `simplicio-loop`: orchestrate multi-step work with bounded stages, retries,
  fan-out, recovery, and convergence.
- `simplicio-prism`: route mixed work across Mapper, Fast, Dev CLI, Loop, and
  Runtime using the bundled capability inventory and recipes.
- `rtk-cli` and `simplicio-cli`: optional local tooling for compact shell output
  and the Simplicio six-layer task-to-code verification workflow.

The five component skills include their upstream `references/`, `agents/`,
`assets/`, and Prism helper files so Codex can use the same system contracts
without importing Runtime source code. The plugin intentionally bundles only
Simplicio first-party system skills, not the Runtime's unrelated external skill
catalog.

Source and official artwork:
<https://github.com/wesleysimplicio/simplicio> and the Simplicio Runtime source
repository.

The host-side plugin material is MIT-licensed. The separately distributed
Simplicio Runtime and release artifacts retain their repository license.

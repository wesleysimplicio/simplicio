---
name: simplicio-setup
description: Verify, repair, authenticate, update, or explicitly register the Simplicio Runtime installed by the Codex plugin. Use when the user asks to install Simplicio, enable all Simplicio commands, fix plugin startup, check authentication, or register Simplicio with other hosts. Login and broad host registration require explicit user intent.
---

# Simplicio Setup

The plugin has no click-time script lifecycle. Its bundled MCP bootstrap runs on
the first new Codex task after the plugin is enabled or reinstalled. It reuses a
valid Runtime v3.8.35 or newer, or runs the pinned official installer and then
starts the complete stdio MCP server.

## Verify the setup

1. Call `simplicio_runtime_health` and report the server version, connection,
   dynamic tool count, and readiness separately.
2. Use `simplicio_exec` with `version --json` to verify the executable contract.
3. If the server did not start, inspect only
   `~/.simplicio/logs/codex-plugin-bootstrap.log` and the managed binary paths
   `~/.simplicio/bin/simplicio` and `~/.local/bin/simplicio`.
4. Do not claim installation from a manifest, cache entry, or tool schema alone.

## Authentication boundary

Installation and `tools/list` do not prove login. Protected calls fail closed
with `login_required` until the user explicitly authenticates. When the user
asks to log in, launch the Runtime's normal Google login command in a terminal,
not through MCP stdio, and then verify `auth status --json`. Never request or
display tokens, passwords, device codes, or client secrets.

## All commands

Use specific `simplicio_*` tools where available. Use `simplicio_exec` for any
other valid Simplicio subcommand. The Runtime advertises live schemas, so never
freeze the current tool count or copy CLI argument schemas into this skill.

## Updates and other hosts

- A valid installed Runtime starts offline; do not update it on every session.
- Treat an update as an explicit workflow and validate the new binary before
  claiming success.
- Broad `install --global --yes` or `mcp register` operations can edit multiple
  client configurations. Run their dry-run form first and apply only when the
  user explicitly requests that wider scope.

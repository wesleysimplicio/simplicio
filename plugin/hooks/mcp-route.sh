#!/usr/bin/env bash
# The Runtime owns the canonical mandatory policy. Fail closed if it is absent.
set -uo pipefail
route="${HOME:-}/.simplicio/hooks/mcp-route.sh"
if [ -z "$route" ] || [ ! -f "$route" ]; then
  printf '%s\n' 'Simplicio Runtime hook is not installed; install the Simplicio Runtime before using this plugin.' >&2
  exit 2
fi
# Claude's Loop hook is a Mapper-only host adapter. Scope the mode to this
# child process so the Runtime cannot route the hook through other modules.
export SIMPLICIO_RUNTIME_MODE="mapper-only"
exec bash "$route"

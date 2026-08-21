#!/usr/bin/env bash
# The Runtime owns the canonical mandatory policy. Fail closed if it is absent.
set -uo pipefail
route="${HOME:-}/.simplicio/hooks/mcp-route.sh"
if [ -z "$route" ] || [ ! -f "$route" ]; then
  printf '%s\n' 'Simplicio Runtime hook is not installed; install the Simplicio Runtime before using this plugin.' >&2
  exit 2
fi
exec bash "$route"

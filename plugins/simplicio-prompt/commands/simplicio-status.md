---
description: Toggle the simplicio-prompt opt-in status output ([Tuple Space Snapshot] / [Active] / [Total] / [Next Yool] / [Partial Result]).
argument-hint: "[on|off|field:on|field:off]"
allowed-tools: Bash
---

Toggle the simplicio-prompt status output for the current shell.

- `/simplicio-status on` → set `YOOL_TUPLE_STATUS=true`
- `/simplicio-status off` → unset `YOOL_TUPLE_STATUS`
- `/simplicio-status snapshot:on` → set `YOOL_TUPLE_STATUS_SNAPSHOT=true`
- Per-field vars: `snapshot`, `active`, `total`, `next`, `partial`.

Apply `$ARGUMENTS` to the active shell environment and print the resulting
state. If unset, the runtime is silent and returns only the final result.

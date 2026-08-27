# Dev CLI interfaces

The agent supplies intent and a bounded plan. Dev CLI owns source mutations, validation, diagnostics, and evidence. Resolve the installed command/API/MCP adapter at runtime; never invent flags.

## Mutation guard

Require repository, key/path, scope, snapshot, and pre-effect validation. Keep a lock or equivalent causal marker for every mutation. Empty or malformed input must not create a false lock.

## Verification

Record diff, command output, exit status, tests, and evidence file. A reported success without durable evidence is not proven.

## Unknown effects

Use `unchanged-before`, `proven-after`, `failed`, or `ambiguous-or-diverged`. Preserve the lock on ambiguity and delegate governed reconciliation to Runtime when available.

## Retry

Retry only the declared transient class and within the capability's limit. Do not repeat a mutation when effect status is unknown.

## Runtime selection rule

Dev CLI is a standalone package capability, but not a peer Runtime route. Runtime
exposes it only as `loop.dev_cli` after Loop activation. Direct Runtime file writes
use `simplicio edit` unless the active Loop operation delegates through Dev CLI.

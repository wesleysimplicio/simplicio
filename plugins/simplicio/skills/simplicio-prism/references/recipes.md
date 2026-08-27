# Prism recipes

Use the smallest recipe that satisfies the request. Resolve concrete adapters from the capability registry before execution.

## Understand a codebase

`mapper.project-survey → mapper.snapshot-create → mapper.context-select`

Add `fast.index-open → fast.search → fast.rank` for repeated or broad retrieval.

## Implement and verify a change

`mapper.snapshot-create → mapper.context-select → dev-cli.preflight → dev-cli.edit → dev-cli.tests → dev-cli.evidence`

Use `dev-cli.reconcile` or Runtime reconciliation when effect status is ambiguous.

## Multiple issues or agents

`mapper.project-survey → loop.plan → loop.slot-dispatch → loop.stage`

Add `loop.fanout`, `loop.retry`, `loop.review`, and `loop.complete` according to the plan. Keep one issue/task per slot by default.

## Governed or native execution

`prism.classify → runtime.gate → runtime.checkpoint → runtime.native-execute|runtime.mcp-invoke → runtime.receipt → runtime.reconcile`

Use Runtime only when the policy, evidence, MCP, native, pool, or subagent requirement justifies it.

## Unavailable component

Return the selected capability as `unavailable`, choose the declared fallback, and preserve the unresolved item. Never silently substitute a semantically different operation.

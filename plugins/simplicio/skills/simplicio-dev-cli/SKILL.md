---
name: simplicio-dev-cli
description: Perform deterministic Simplicio code changes and validation through the Dev CLI. Use for file edits, patches, implementation, formatting, tests, diagnostics, pre-effect validation, retries, evidence files, and safe mutation workflows. The agent decides intent; Dev CLI owns the mutation and verification.
---

# Simplicio Dev CLI

Use Dev CLI as the EXECUTE, EDIT, VALIDATE, and DIAGNOSTICS owner. Survey with Mapper first, then pass a bounded plan and evidence to the CLI. Read `references/capabilities.yaml` and `references/interfaces.md` for exact contracts and failure handling.

## Complete interface map

Generate or refresh the Prism inventory for the installed Dev CLI before using a new command. Require the map to cover CLI commands/subcommands, MCP tools, Python/Rust APIs, configuration, I/O, effects, errors, fallbacks, dependencies, cost, version, and compatibility.

## Routing

- Invoke for `editar`, `implementar`, `corrigir`, `refatorar`, `formatar`, `testar`, `validar`, `diagnosticar`, patching, or applying a plan.
- Require a repository/key/path scope and pre-effect validation before mutating.
- Do not manually write the intended diff when the Dev CLI operation exists.
- Do not claim success from a reported receipt without durable evidence and post-effect validation.
- On unknown effect, preserve the lock and escalate to Runtime reconciliation when configured.

## Required workflow

1. Accept Mapper snapshot, intent, scope, and constraints.
2. Validate repository, path, key, and preconditions before effect.
3. Execute one bounded mutation or validation capability.
4. Collect stdout, stderr, exit status, diff, tests, and evidence file.
5. Retry only according to the capability contract; never oscillate blindly.
6. Return a durable result for Loop or Runtime to reconcile.

## Contract

Return `operation_id`, `snapshot_id`, `pre_effect`, `effect`, `post_effect`, `diff`, `tests`, `evidence_file`, `verdict`, and `retry_history`. Verdicts must distinguish proven, unchanged, failed, and ambiguous/diverged.

## Resources

- `references/capabilities.yaml`: machine-readable capability map.
- `references/interfaces.md`: mutation, validation, diagnostics, lock, retry, and evidence rules.
- `scripts/probe-capabilities.py`: validate the capability manifest and detect duplicate IDs.

## Runtime integration boundary (normative, 2026-08-05)

The Dev CLI package remains independently executable for compatibility and focused
local work, but Runtime must not select it as a peer route. Inside Runtime, Dev CLI
is exposed only as the nested `operator_route.loop.dev_cli` capability after the
Loop route is active and the Loop task requires implementation, validation, tests,
or diagnostics.

The default Runtime writer for a decided file edit is `simplicio edit`. Dev CLI may
prepare or validate the Loop operation and delegate the mechanical write to that
Runtime writer. No standalone Dev CLI invocation should be represented as a Loop
activation or as a Runtime-backed completion.

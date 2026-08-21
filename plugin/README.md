# simplicio-loop — public Claude Code plugin

This directory is the public marketplace bundle for `simplicio-loop`. It carries
the canonical host-side skills and wired safety hooks; the compiled
`simplicio` Runtime remains a separate platform-specific binary and MCP server.
The bundle currently publishes the 12 `simplicio-*` skill surfaces from the
Loop release, including Runtime, Mapper, Fast, Dev CLI, and Prism adapters.

The bundle intentionally excludes the Loop repository's heavy pip-only assets
(capture proxy, dashboard, and development-only tooling).

```
plugin/
├── .claude-plugin/plugin.json   # the plugin manifest (skills + hooks)
├── skills/                      # canonical Loop/Runtime/operator skills
└── hooks/                       # only the hooks wired by hooks.claude.json (+ orient_clamp)
```

## Install

```
/plugin marketplace add wesleysimplicio/simplicio
/plugin install simplicio-loop@simplicio
```

The marketplace catalog at the public repository root
([`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)) points
its `source` at this `plugin/` subdirectory, so the install carries only this
bundle.

## Quick start

After install, **start every run with `/simplicio-loop`** — that is the entry
command for the orchestrator. It reads your queue of work (open issues, a
milestone, CI failures, kanban cards) and drives it end-to-end. The satellite
skills are called automatically by the orchestrator, or on their own when you
only need one piece.

```
/simplicio-loop              # start: drain the whole queue end-to-end
/simplicio-loop #123 #124    # scope the run to specific issues
```

### Flow and gains

Each step buys a concrete gain in **quality**, **token economy**, or **delivery security**:

| Step | What happens | Main gain |
|---|---|---|
| **Orient** (`simplicio-orient`) | map the repo; clamp heavy read-only command output before it reaches context | **tokens** — read a compressed map instead of bulk-reading files |
| **Recall** (`simplicio-learn`) | pull prior decisions/lessons from memory | **tokens + quality** — reuse instead of re-deriving |
| **Implement** (`simplicio-loop`) | hardened Ralph loop: re-feed the same goal each turn; deterministic edits | **quality** — converges on its own edits; **tokens** — local-first, mechanical edits |
| **Verify** | actually run the build/tests, not just compile | **delivery** — proof it works, not just that it builds |
| **Review** (`simplicio-review`) | parallel adversarial subagents refute the change before merge | **quality + delivery** — catches bugs/regressions pre-merge |
| **Gate** (`action_gate`) | fail-closed: block force-push, secret-leaking commits, irreversible ops | **delivery security** — a dangerous/unverifiable action is denied, not trusted |
| **Merge and close** | merge and close the work item — only after the gates pass | **delivery** — nothing lands unguarded |
| **Exit** (`loop_stop`) | exit only on a typed completion-promise backed by evidence | **delivery** — never a false "done" |
| **Compress** (`simplicio-compress`) | terse output levels; never touches code/paths | **tokens** — cut output tokens with no loss of meaning |
| **Learn** (`simplicio-learn`) | write the run's lessons back to memory | **quality + tokens** — next run is smarter and cheaper |

## Wired hooks

| Event | Hooks |
|---|---|
| `Stop` | `loop_stop.py` (re-feed / evidence-gated exit) |
| `PreToolUse` (all tools) | `mcp-route.sh` (mandatory Runtime route) · `action_gate.py` (fail-closed safety gate) · `orient_rewrite.py` (opt-in output clamp) |

The Runtime route is mandatory inside the host session: native reads, edits, shell commands, and
directory exploration are denied, while Simplicio MCP tools are allowed. It also warms a bounded
`map → fast` context packet in the background on lifecycle events. Install the Runtime first so
`~/.simplicio/hooks/mcp-route.sh` exists; there is no environment-variable escape hatch. All hooks
run locally and make zero network calls.

## Maintainers

The canonical implementation remains in
<https://github.com/wesleysimplicio/simplicio-loop>. When that release changes,
refresh this public bundle from the pinned source release and rerun the bundle
contract tests before opening a distribution PR.

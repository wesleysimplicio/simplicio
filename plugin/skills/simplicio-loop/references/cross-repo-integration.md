# Cross-repo dependencies (`simplicio` CLI, optional) — full detail

Moved out of `SKILL.md` § Cross-repo dependencies as part of the #119 shrink.

The simplicio-loop can optionally call out to the **simplicio CLI** (`simplicio`) when
it is available on PATH. This is an optional, silent integration — the loop never blocks
or changes behaviour when the CLI is absent.

### What the loop calls

| CLI command | Where | When | Effect |
|---|---|---|---|
| `simplicio gate check <reported> <watcher>` | `scripts/handoff.py` | On handoff to the next agent | Best-effort gate verification before transferring state |
| `simplicio claims check` | `hooks/loop_stop.py` | Every stop-hook invocation during an active loop | Verifies claim tags (`MEASURED|`/`UNVERIFIED|`) on the turn output |
| `simplicio nest verify` | `hooks/loop_stop.py` | Every stop-hook invocation during an active loop | Verifies the dependency-tree structure |

All three calls are **silent-fail**: if the CLI is not installed, the call is skipped
without warning or error. The loop's core logic — re-feed, promise, evidence gate —
is unmodified.

### Discovery order

The `_discover_simplicio_cli()` helper probes these candidates in order and uses the
first that responds:

```
simplicio gate          # primary binary
simplicio-py gate       # alternative build
python3 -m simplicio.cli gate  # module invocation
```

Each probe is a `--help` subprocess with a 5-second timeout; any failure moves to the
next candidate.

### Optional dependency

`simplicio-dev-cli` (from `pip install simplicio-cli`) is the **operate** operator of the loop
(see `SKILL.md` § Bound operators / `references/bound-operators.md`). The bare `simplicio` binary
probed here is the separate `simplicio-runtime` package, which provides gate/nest/claims
subcommands independently of the operator CLI. Neither is required for the loop to function; the
loop's contract hard-requires only `simplicio-mapper` (survey) and `simplicio-dev-cli`
(action operator) for its core preflight.

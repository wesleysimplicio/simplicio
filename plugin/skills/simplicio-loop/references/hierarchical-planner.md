# HRM-style hierarchical planner (two-level reasoning loop) — full detail

Moved out of `SKILL.md` § HRM-style hierarchical planner as part of the #119 shrink.

Inspired by the **Hierarchical Reasoning Model** (arXiv:2506.21734, JesseBrown1980/HRM),
the loop now operates at TWO levels instead of one:

| Level | Speed | Runs | Job |
|-------|-------|------|-----|
| **High-level planner** (`scripts/hierarchical_planner.py`) | Slow (every N turns or on stall) | `plan` subcommand called by `loop_stop.py` before each re-feed | Re-assess abstract strategy; MAY write a new **phase** (`.simplicio/orchestrator/loop/phase.json`) that changes direction |
| **Low-level executor** (the loop itself) | Fast (every turn) | The normal Ralph re-feed within the current phase | Execute one AC-scoped change, verify, record to journal — never change the phase |

**Phase states** (ordered escalation):

| Phase | When | Strategy | Tactical guard |
|-------|------|----------|----------------|
| `explore` | First stall, or fresh complex bug | Survey codebase, read logs — DO NOT mutate | No edits — only read/grep/log analysis |
| `debug` | After explore, or known bug | Add instrumentation, narrow failure, prove root cause | Do not fix yet — isolate first |
| `harden` | Working code that needs safety | Add tests, edge cases, error handling | Do not add features — only safety nets |
| `refactor` | Code quality debt | Restructure without changing behavior | Zero behavior change — tests pass before AND after |
| `implement` | Default / fresh goal | Write new code against frozen ACs | One AC at a time, verify each |
| `escalate` | Deep stall (>K identical failures) | STOP mutations — gather context for human handoff | Zero mutations — only HANDOFF.md |

The planner is **deterministic and model-free** — same rules apply regardless of
LLM provider. State lives in `.simplicio/orchestrator/loop/phase.json`. The loop runs in
flat mode if the planner script is missing.

**Usage:**
```bash
# Before deciding the next action each turn, read the current phase
python3 scripts/hierarchical_planner.py status
# → MEASURED|phase: debug — started at iter 3, strategy: "Add instrumentation..."

# Force replan manually (normally automatic)
python3 scripts/hierarchical_planner.py plan

# Reset to flat mode
python3 scripts/hierarchical_planner.py clear
```

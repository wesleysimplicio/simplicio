# Agent-to-agent handoff (spindle/latch pattern) — full detail

Moved out of `SKILL.md` § Agent-to-agent handoff as part of the #119 shrink (SKILL.md keeps only a
short pointer; this file has the full terminology, state machine, protocol, and guardrails).

When a loop must hand work across multiple agents — each with a different runtime, iteration cap,
or scope — the existing one-directional `HANDOFF.md` (agent A writes, walks away) is upgraded to
a **confirmed handoff** with a latch. This is the **spindle/latch pattern**, absorbed from
the Asolaria project (Jesse's agent-to-agent handoff protocol).

### Terminology

| Term | Meaning |
|------|---------|
| **Spindle** | A pipeline of agents: A → B → C → ... each doing one phase and passing the state forward. |
| **Latch** | A boolean flag (`spindle.json: latch: true`) that blocks the next stage until the receiving agent confirms receipt. The latch ensures delivery — the handoff is NOT final until the next agent ACKs. |
| **Handoff** | `handoff(next_agent, state)` — pass the accumulated state and set the latch. |
| **Confirm** | `handoff confirm` — the receiving agent ACKs; the latch is released. |

### State machine

```
IDLE ──handoff──→ LATCHED ──confirm──→ ACTIVE ──handoff──→ LATCHED ──...
                    ↑                      │
                    └─────── clear ────────┘
```

- **IDLE**: no active handoff. A fresh loop start.
- **LATCHED**: a handoff was made but NOT yet confirmed by the next agent. The spindle is stalled.
- **ACTIVE**: the handoff was confirmed; the current agent is processing.

### Protocol

The canonical flow for a multi-agent pipeline:

```bash
# ── Agent A does its phase, then passes to Agent B ──
python3 scripts/handoff.py handoff --next "agent-b" \
    --state '{"done_phases": ["phase1"], "artifacts": {"build": "./dist"}, "meta": {"issue": 42}}' \
    --note "Phase 1 complete. Build is in ./dist. Tests pass."

# Agent A can now stop cleanly. The latch holds until Agent B confirms.
# The loop_stop.py hook will NOT re-feed the goal when a latched handoff exists.

# ── Agent B arrives (new session, possibly different runtime) ──

# 1. Check what's pending
python3 scripts/handoff.py status
# → State: LATCHED (handoff pending confirmation)
#   Next agent: agent-b
#   Transferred state: { ... }

# 2. Confirm receipt (releases the latch)
python3 scripts/handoff.py confirm
# → ✓ Handoff confirmed. You are now the active agent.

# Or in one step:
python3 scripts/handoff.py receive
# → confirm + status in one command

# 3. Use the transferred state to resume
#    (reads from spindle.json or the --state passed earlier)

# 4. Process phase 2...

# 5. Hand off to the next agent
python3 scripts/handoff.py handoff --next "agent-c" \
    --state '{"done_phases": ["phase1", "phase2"], ...}'
```

### Integration with the loop stop hook

When the `loop_stop.py` hook detects an active (latched or confirmed) spindle handoff, it
changes its behaviour:

| Stop condition | With spindle handoff | Behaviour |
|---------------|---------------------|-----------|
| `max_iterations` cap | Latched handoff exists | **Do NOT re-feed.** The handoff target will pick up. Write HANDOFF.md + stop cleanly. |
| Manual STOP | Latched handoff exists | **Do NOT re-feed.** Same as above. |
| Normal re-feed | Active (confirmed) handoff | Re-feed normally — the current agent is still processing. |
| Normal re-feed | Latched handoff | **Do NOT re-feed.** The latch means the handoff target hasn't confirmed yet — wait for them. |

A spindle handoff **overrides** the normal re-feed logic: if the state file shows a latched
handoff, the stop hook does NOT increment the iteration counter or re-feed the goal, because
the next agent will handle it from here.

### Guardrails specific to spindle handoffs

- The latch is fail-open: if `spindle.json` is unreadable, treat it as if no handoff exists
  (never trap the loop on a corrupt file).
- The `handoff.py` script is fail-open on all I/O — a write error never blocks the stop.
- `handoff confirm` is idempotent: confirming an already-released latch is a no-op (exit 0).
- Handoff events are logged to `.simplicio/orchestrator/loop/handoffs/events.jsonl` (append-only) for
  auditability — each handoff, confirm, and clear is timestamped.

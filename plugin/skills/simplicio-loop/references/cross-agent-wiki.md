# Cross-agent persistent wiki (`.simplicio/orchestrator/wiki/`) — full detail

Moved out of `SKILL.md` § Cross-agent persistent wiki as part of the #119 shrink.

Evolved from the one-shot `HANDOFF.md` pattern (inspired by JesseBrown1980/ai-memory).
Every turn's key decisions, findings, and dead-ends are captured into a persistent
markdown wiki at `.simplicio/orchestrator/wiki/` — a per-project, cross-agent, zero-friction
knowledge base that survives across agent vendors (Simplicio Agent → Claude Code → Codex).

A fresh agent arriving in the repo reads the wiki and sees "where we left off"
without needing the prior conversation transcript.

**Structure:**
```
.simplicio/orchestrator/wiki/
  SUMMARY.md          — regenerated each turn; full index of all entries
  journal/            — per-turn captures (YYYY-MM-DD_HH-MM-SS.md)
  decisions/          — accepted ACs, rejected approaches, settled facts
  artifacts/          — links to evidence files, PRs, run IDs
```

**Commands:**
```bash
python3 scripts/cross_agent_wiki.py capture    # capture this turn's state
python3 scripts/cross_agent_wiki.py summary    # regenerate SUMMARY.md
python3 scripts/cross_agent_wiki.py handoff    # write HANDOFF.md for next agent
python3 scripts/cross_agent_wiki.py status     # show wiki stats
```

**How it works per turn:**
1. After each iteration, `cross_agent_wiki.py capture` saves the turn: goal, phase,
   journal stats, recent git log, working tree diff, last action + gate + fingerprint.
2. `cross_agent_wiki.py summary` regenerates the index, showing all entries with
   pass/fail counts, unique fingerprints, and distinct actions tried.
3. On handoff (cap/STOP/spindle), `cross_agent_wiki.py handoff` writes a structured
   markdown with frozen goal, AC status, last 3 distinct actions (anti-oscillation),
   and explicit resume instructions for the next agent.

The wiki is plain markdown — `grep`-able by any agent, editable by any editor,
backup-able with `rsync`. No vector DB, no `write_note` ceremony.

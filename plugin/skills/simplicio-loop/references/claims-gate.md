# Claims-gate discipline — MEASURED/UNVERIFIED tagging (full detail)

Moved out of `SKILL.md` § Claims-gate discipline as part of the #119 shrink (SKILL.md keeps only
the two-tag table and the rule that every output line must be tagged; this file has the full
eight-rule contract and worked examples).

Every claim the loop makes — in the journal, in triage, in the exit promise, or in any
turn output — MUST be tagged with its evidence class. This is the Asolaria claims-gate
discipline, absorbed into simplicio-loop so no output escapes without a truth-class label.

**Two tags, no exceptions:**

| Tag | Meaning | When to use |
|-----|---------|-------------|
| `MEASURED\|` | The claim is backed by in-turn, concrete, non-model evidence | A passing gate, a `file:line` receipt, a `diff --stat`, a test log, a live API response, or any artifact the loop itself did NOT hallucinate |
| `UNVERIFIED\|` | The claim is an inference, a plan, a hypothesis, or a best-effort summary the model makes without mechanical proof | Triage notes, hypotheses in the journal, proposed next actions, stall analysis, or any claim the loop cannot prove this turn |

**Every `loop_journal.py` output is tagged.** The `record` command tags passing gates
`MEASURED\|` and failing/blocked ones `UNVERIFIED\|`. `resume` and `status` prefix every
summary line. The stall verdict is `MEASURED\|` when it reports concrete fingerprint matches,
`UNVERIFIED\|` when it recommends a next action.

**The eight rules** (from Asolaria's claims-gate contract) enforce this mechanically:

| # | Rule | Meaning |
|---|------|---------|
| 1 | **ground impact before severity** | Tag the impact (what actually broke/failed) first; the severity label follows only if measurable. |
| 2 | **no flat tuples** | Never output a bare `(MEASURED\|..., UNVERIFIED\|...)` tuple without a sentence explaining each. |
| 3 | **mirrors != authority** | A mirror/duplicate of a source is UNVERIFIED unless the loop independently checks the source. |
| 4 | **cylinders ≠ levels** | A numeric or categorical tag (iteration N, severity X) is not a claims-gate tag — always add `MEASURED\|` or `UNVERIFIED\|` explicitly. |
| 5 | **owning gate, not transcript** | The loop owns its claims-gate tags — it does NOT copy tags from transcript or tool output; it RE-tags every claim with its own assessment. |
| 6 | **missing ≠ clean-zero** | Absence of evidence is not evidence of absence — tag unresolved signals as `UNVERIFIED\|`, never skip the tag because nothing failed. |
| 7 | **real lane** | Tag every claim in the output lane the user sees (scratchpad, journal, triage, promise), not just internal debug lines. |
| 8 | **source ≠ live** | A source reference (e.g., a linked file on disk) is UNVERIFIED until the loop re-reads it this turn; a cached source is never `MEASURED\|`. |

**How to apply each turn:**

```
# triage output — hypothesis, not proof
UNVERIFIED| root cause is likely a race in the connection pool

# journal record on a passing gate
MEASURED| py_test --gate pass --fingerprint - (all 47 tests green)

# journal record on a failing gate
UNVERIFIED| integration/gate fail -- fingerprint a3b2c1 -- retry with longer timeout

# stall verdict
MEASURED| STALLED -- 3 identical fingerprints, dead-end actions: ["retry fetch"]

# exit promise
MEASURED| <promise>All acceptance criteria met</promise> -- verified by test run, flow audit, and task anchor gate

# watcher-gate (pre-promise verification)
MEASURED| watcher_state.json match:true -- agent PID result == watcher PID recomputed truth
UNVERIFIED| watcher_state.json missing or match:false -- watcher disagrees, promise rejected
```

**The eight-rule checklist is appended to every loop initialization and every triage step**
(see `SKILL.md` § The loop contract, step 2): review every output claim against rules 1–8 before
proceeding. The `loop_journal.py claims-gate --check` helper audits any output blob for
untagged claims.

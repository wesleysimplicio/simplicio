# Run-journal + stall detector (the loop's working memory) — full detail

Moved out of `SKILL.md` § Run-journal + stall detector as part of the #119 shrink (SKILL.md keeps
only the three commands and the one-paragraph summary; this file has the full mechanics).

A re-feed loop with no memory of its own attempts has two failure modes the classic Ralph loop
cannot see: it **re-derives the same triage every turn** (wasted tokens) and it **oscillates** —
tries X, fails, tries X again — until the cap burns. The journal + stall detector close both. Both
are deterministic and model-free (`scripts/loop_journal.py`), so a resume is reproducible from disk.

**1. The run-journal — `.simplicio/orchestrator/loop/journal.jsonl` (append-only attempt memory).** One
record per turn: `{iteration, action, hypothesis, gate: pass|fail|blocked, fingerprint, ts}` with
optional lineage fields such as `execution_state`, `stage_id`, `source_artifact`, `chunk_id`,
`validator`, `decision`, `retry_count`, `blocked_reason`, and `next_action`. On a failing gate the
gate output is reduced to a **stable fingerprint** — line numbers, file paths, hex/uuids,
timestamps and durations are normalized away, so the SAME bug hashes the SAME across turns even
when the incidental text differs. This is the loop's memory of WHAT WAS TRIED; the scratchpad only
holds the goal.

**2. The stall detector — `loop_journal.py stall`.** Reads the journal and returns
`PROGRESS | STALLED`. STALLED = the last **K** consecutive attempts all failed with the **same
fingerprint** (default K=3). A different fingerprint each turn = the loop is moving (PROGRESS); the
same one K times = it is spinning. On STALLED it names the **dead-end actions** (already tried under
this fingerprint) and recommends `switch-strategy` (K) or `escalate` (>K) — and `--exit-code` exits
10 for hook/`if:` gating.

**How the loop uses it each turn:**
```bash
# triage (step 2) — START here so you never retry a known dead-end
python3 scripts/loop_journal.py resume
#   → distinct actions tried + their outcomes + "AVOID (dead-ends): …" + live fingerprint
# … decide + operate + verify (step 3) …
python3 scripts/loop_journal.py record --iteration N --action "<change>" \
    --hypothesis "<why>" --gate pass|fail --gate-output <test.log> \
    --execution-state planned --stage-id validate --validator pytest --decision retry
# re-feed gate (step 4) — before re-feeding the same goal
python3 scripts/loop_journal.py stall --k 3 --exit-code
#   PROGRESS → re-feed normally
#   STALLED  → do NOT re-feed the same goal into the same failure:
#              switch strategy (change the approach, not just retry), or
#              escalate to the human_gate with the fingerprint + dead-ends, or
#              (headless, no approver) stop with a blocked status — never burn the cap spinning
```

This upgrades invariant 3 (Deterministic continuation): the next iteration re-feeds the goal **and
the attempt memory** — and a STALLED loop changes course instead of repeating itself. It also makes
resume real: a fresh process reads the journal and continues without re-deriving prior turns.

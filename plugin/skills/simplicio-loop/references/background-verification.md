# Background verification — run tests non-blocking, keep working (full detail)

Referenced from `SKILL.md` § The loop contract, step 3 ("Work the goal"), alongside
`triage-verify-detail.md`. This file covers HOW the verification commands themselves are launched,
not WHAT they verify.

**The problem.** A test suite, `claims_audit.py`, or a full `scripts/check.py` run commonly takes
30s-5min. A turn that launches the run and then sits idle waiting for it to finish burns that whole
window doing nothing — the next backlog item, the next file read, the next PR draft could all have
happened during that wait.

**The convention.** Launch the verification command in the BACKGROUND and keep doing the next
useful thing (decompose the next backlog item, draft the next commit message, survey the next
issue, read the next file) while it runs. Only block on the result at the point you actually need
it — right before you commit/push/open a PR/mark an AC done. This does not weaken the evidence gate
(§ The promise is evidence-gated) — the same command, the same exit code, the same output is
required before a promise/AC/merge; only WHEN you wait for it changes.

**What this looks like in practice:**
1. Launch the test/selftest/claims_audit run non-blocking (host-native background execution, or
   `cmd &` / a job-control equivalent in a plain shell).
2. Immediately continue with other in-scope work — do not idle-poll the run every few seconds.
3. When notified the run finished (or when you reach a point that genuinely depends on its result,
   e.g. about to commit), read its full output and treat it exactly as the loop contract already
   requires: a concrete, in-turn, MEASURED verification. A run you never actually read back is not
   evidence — background execution changes *when* you wait, not *whether* you check the result.
4. If two or more independent checks are both needed before the same commit (e.g. the new unit
   tests AND `claims_audit.py`), launch them in parallel rather than sequentially chaining them.

**What this is NOT:**
- Not a license to skip reading the output, or to assume a background run "probably passed."
- Not a license to end a turn on "I'll wait for it and report back" with no concrete state — see
  `SKILL.md` § Output, "No parking a turn on an unresolved promise": either block and read the
  real result before ending the turn, or end it with an explicit `UNVERIFIED|still running: <cmd>,
  resolves on <condition>` tag. A turn's own text must make DONE-AND-VERIFIED vs STILL-IN-FLIGHT
  unambiguous without anyone having to go open a log file.
- Not a change to `evidence_required`, the watcher-gate, or any AC-verification rule — every gate in
  `references/triage-verify-detail.md` and the DoD table in `SKILL.md` still applies unchanged.
- Not parallel *mutation* of the same files — this is about overlapping a slow, read-only
  verification with the NEXT unit of work, not two agents editing concurrently (see
  `references/bound-operators.md` and, for multi-agent collision avoidance specifically, the
  coordinator decision core in `scripts/coordinator.py`, #467/#468).

**Why it matters at this repo's current scale.** With multiple concurrent loop sessions/worktrees
active against the same GitHub repo (observed directly: issues #466-#469 each had a live claim from
a sibling session), idling on a single test run is strictly worse than in a single-agent repo — the
same wall-clock window could have been spent avoiding a duplicate-work collision (checking
`coordinator.py decide` for the next issue, reading a sibling session's latest comment) instead of
watching a progress bar.

# Multi-Agent Coordination Convention

When the `simplicio-loop` drains a queue of issues and **every open issue returns
`DEFER_ACTIVE_CLAIM`** (already claimed by another session/agent), the idle session
MUST NOT idle. Instead it switches to **PR review mode**:

1. Query open PRs (`gh pr list --state open`).
2. For each PR, resolve the referenced issue and its frozen acceptance criteria.
3. Run the mechanical verifier `scripts/pr_dod_review.py`:
   - `python3 scripts/pr_dod_review.py check --pr-body @pr.txt --issue-body @issue.txt`
   - It emits a verdict on the **7 DoD dimensions** (implementation, unit tests,
     integration tests, system tests, regression tests, perf benchmark, min coverage)
     and lists any **unresolved `- [ ]` acceptance criteria** from the issue.
4. Post the verdict as a PR comment so the claiming agent sees exactly what remains:
   - `python3 scripts/pr_dod_review.py --post --pr-url <url> --pr-body @pr.txt --issue-body @issue.txt`

This turns "nothing to claim" into "help the claimed work converge" — no session
wastes a tick. The verifier is mechanical (stdlib only); it never approves a merge,
it only surfaces gaps.

Convention owner: WI-485. Referenced from `SKILL.md` triage (Step 2).

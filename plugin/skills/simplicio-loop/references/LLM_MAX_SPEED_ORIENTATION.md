# Simplicio max-speed orientation

This is the canonical bundled orientation for the Simplicio Loop. It is
self-contained so an installed bundle does not depend on an absent sibling
document.

- Runtime first when available: consult simplicio loop decide --json and honor
  .simplicio/runtime/loop-decision.json. When Runtime is absent, continue
  through standalone Loop operators and report Runtime integration as degraded;
  never claim Runtime authority.
- Economy-parallel: run simplicio-loop economy apply --json and
  preflight --strict before autonomous work.
- Hot path: Mapper scan or handoff, then Fast understand/plan/apply when up,
  then dev-cli or structured edit with strict validation and no hand-edit.
- Work only on the current task and acceptance criteria. Make the smallest safe
  change and preserve dirty work, lease, and ownership.
- For 1–3 tasks work directly; for more tasks use Prism with a minimum batch of
  10. Serialize writes and let the physical governor admit only verified
  capacity.
- Use GitHub or gh only when the task requires an issue, pull request, or
  release; GitHub is the source of truth for the drain.
- Do not use generic web research, subagents, or a local LLM by default. Keep
  the execution concise and evidence-backed.
- Do not edit with stale context, active locks, absent artifacts, or unverified
  capacity.
- Run focused tests and report the round's evidence with MEASURED or UNVERIFIED
  tags. Never invent metrics.
- End each run with DONE, NEXT(one step), or BLOCKED(code). Act before
  narrating.
- Treat failure or ambiguity as a real blocker; do not repeat the same blind
  attempt.

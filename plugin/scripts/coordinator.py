#!/usr/bin/env python3
"""simplicio-loop — coordinator decision core (phase-1 slice of #467/#468).

#467 (Continuous Evolution) and #468 (Adaptive Architecture) both ask for a "coordinator"
that always decides by looking at the WHOLE board — every open issue, every claim, every merged
PR — instead of an agent grabbing whatever it's told and duplicating work another session already
did. That live collision is not hypothetical: while building this, a sibling session (branch
`claude/simplicio-loop-skill-issues-0c53a9`) built `scripts/findings.py` as a from-scratch
duplicate of this repo's already-merged `scripts/finding_collector.py` (#466 PR #475), because
neither side had a shared, mechanical view of "who's doing what, and is it already done".

This module is that shared view's decision core — model-free, deterministic, unit-testable without
network. It does NOT decide "propose new stages"/"speculative duplicate agents" (the rest of
#467/#468/#469's scope) — it decides the one thing every one of those visions depends on first:
for a given issue, given its claim comments and the PRs that reference it, what should THIS session
do next: OWN it, DEFER to an active claim, RECLAIM a stale one, or flag a DUPLICATE_RISK because two
sessions claimed it near-simultaneously.

Verbs:
    decide    Read a snapshot (--snapshot-file JSON, or stdin) of {issue, comments, prs} and print
              one decision per issue: MEASURED| tagged action + reason. `comments` items are
              {"body", "created_at", "author"}; `prs` items are {"number", "state", "body",
              "head_ref_name", "merged_at"}. Actions:
                OWN                  no active claim, no merged PR referencing the issue yet
                CONTINUE_OWN         the most recent claim's branch is --self-branch
                DEFER_ACTIVE_CLAIM   another branch claimed it recently (< --stale-hours old)
                RECLAIM_STALE        another branch claimed it but the claim is stale and nothing
                                     merged since
                VERIFY_PARTIAL       a PR referencing the issue already merged, but the issue is
                                     still open — partial delivery, verify before claiming more
              Every issue additionally gets a `duplicate_risk` flag: true when 2+ distinct branches
              posted a claim for the SAME issue within --collision-window-hours of each other with
              no merge in between (the exact `finding_collector.py` vs `findings.py` scenario).
    survey    Best-effort, network-touching helper: shells out to `gh issue list`/`gh issue view`/
              `gh pr list` for --repo and writes a snapshot JSON `decide` can consume. Fail-open: if
              `gh` is missing/unauthenticated, prints an UNVERIFIED stub and exits 0 (the decision
              core itself never depends on network availability, only `survey` does).
    selftest  Prove the decide() logic deterministically against fixture snapshots — no network.

Usage:
    python3 scripts/coordinator.py survey --repo wesleysimplicio/simplicio-loop \\
        --issues 466,467,468,469 > .simplicio/orchestrator/coordinator/snapshot.json
    python3 scripts/coordinator.py decide --snapshot-file .simplicio/orchestrator/coordinator/snapshot.json \\
        --self-branch claude/simplicio-loop-skill-issues-4cff87
    python3 scripts/coordinator.py selftest
"""
import json
import os
import re
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

CLAIM_RE = re.compile(
    r"Claimed.{0,40}?branch[^`]*`([^`]+)`", re.I | re.S)
DEFAULT_STALE_HOURS = 6.0
DEFAULT_COLLISION_WINDOW_HOURS = 2.0


def log(msg):
    print(msg, flush=True)


def _parse_ts(value):
    """Parse an ISO-8601 timestamp (GitHub's format, or a bare float epoch for fixtures)."""
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return 0.0
    text = str(value).strip()
    if re.match(r"^-?\d+(\.\d+)?$", text):
        return float(text)
    text = text.replace("Z", "+00:00")
    try:
        import datetime
        return datetime.datetime.fromisoformat(text).timestamp()
    except Exception:
        return 0.0


def _field(d, *names):
    """Accept both snake_case (fixtures/tests) and gh's camelCase JSON field names."""
    for name in names:
        if name in d and d[name] is not None:
            return d[name]
    return None


def extract_claims(comments):
    """Return [(branch, ts), ...] sorted oldest-first, one per comment that matches CLAIM_RE."""
    claims = []
    for c in comments or []:
        body = c.get("body") or ""
        m = CLAIM_RE.search(body)
        if m:
            claims.append((m.group(1).strip(), _parse_ts(_field(c, "created_at", "createdAt"))))
    claims.sort(key=lambda x: x[1])
    return claims


def has_merged_pr_referencing(issue_number, prs, after_ts=0.0):
    """True if any PR in `prs` is MERGED, its body references #issue_number, and (optionally)
    it merged after `after_ts` — used to tell 'delivered since the claim' from 'delivered before'."""
    needle = f"#{issue_number}"
    for pr in prs or []:
        if pr.get("state") != "MERGED":
            continue
        body = pr.get("body") or ""
        title = pr.get("title") or ""
        if needle in body or needle in title:
            merged_ts = _parse_ts(_field(pr, "merged_at", "mergedAt"))
            if merged_ts >= after_ts:
                return True
    return False


def decide_for_issue(issue_number, comments, prs, self_branch,
                      stale_hours=DEFAULT_STALE_HOURS,
                      collision_window_hours=DEFAULT_COLLISION_WINDOW_HOURS,
                      now=None):
    now = now if now is not None else time.time()
    claims = extract_claims(comments)
    any_merged_pr = has_merged_pr_referencing(issue_number, prs)

    duplicate_risk = False
    if len(claims) >= 2:
        window = collision_window_hours * 3600
        distinct_branches_in_window = set()
        # a rolling check: any two DISTINCT-branch claims within the window, with nothing merged
        # for this issue strictly between them, counts as a collision.
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                b_i, t_i = claims[i]
                b_j, t_j = claims[j]
                if b_i == b_j:
                    continue
                if abs(t_j - t_i) <= window and not has_merged_pr_referencing(
                        issue_number, prs, after_ts=t_i):
                    duplicate_risk = True
                    distinct_branches_in_window.add(b_i)
                    distinct_branches_in_window.add(b_j)

    if not claims:
        if any_merged_pr:
            action = "VERIFY_PARTIAL"
            reason = "a PR referencing this issue already merged, but the issue is still open"
        else:
            action = "OWN"
            reason = "no active claim and no merged PR references this issue yet"
    else:
        last_branch, last_ts = claims[-1]
        age_hours = (now - last_ts) / 3600.0
        if last_branch == self_branch:
            action = "CONTINUE_OWN"
            reason = "the most recent claim is this session's own"
        elif any_merged_pr:
            # Something already landed on this issue (whether before or after the latest claim) —
            # verify what's actually done before deferring blindly or reclaiming as if untouched.
            action = "VERIFY_PARTIAL"
            reason = "a PR referencing this issue already merged, but the issue is still open"
        elif age_hours < stale_hours:
            action = "DEFER_ACTIVE_CLAIM"
            reason = f"branch '{last_branch}' claimed this {age_hours:.1f}h ago (< {stale_hours}h stale threshold)"
        else:
            action = "RECLAIM_STALE"
            reason = f"branch '{last_branch}' claimed this {age_hours:.1f}h ago and nothing merged since"

    return {
        "issue": issue_number,
        "action": action,
        "reason": reason,
        "duplicate_risk": duplicate_risk,
        "claims": [{"branch": b, "ts": t} for b, t in claims],
        "has_merged_pr": any_merged_pr,
    }


def cmd_decide(opts):
    snapshot_file = opts.get("snapshot-file")
    if snapshot_file:
        raw = open(snapshot_file, encoding="utf-8").read()
    else:
        raw = sys.stdin.read()
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"UNVERIFIED|coordinator decide: invalid snapshot JSON: {exc}")
        sys.exit(2)
    self_branch = opts.get("self-branch", "")
    stale_hours = float(opts.get("stale-hours", DEFAULT_STALE_HOURS))
    collision_window_hours = float(opts.get("collision-window-hours", DEFAULT_COLLISION_WINDOW_HOURS))
    prs = snapshot.get("prs") or []
    issues = snapshot.get("issues") or []
    decisions = []
    for issue in issues:
        number = issue.get("number")
        comments = issue.get("comments") or []
        decisions.append(decide_for_issue(number, comments, prs, self_branch,
                                          stale_hours=stale_hours,
                                          collision_window_hours=collision_window_hours))
    for d in decisions:
        tag = "MEASURED|" if d["claims"] or d["has_merged_pr"] else "UNVERIFIED|"
        print(tag + json.dumps(d, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_survey(opts):
    repo = opts.get("repo")
    issue_numbers_raw = opts.get("issues", "")
    if not repo or not issue_numbers_raw:
        print("UNVERIFIED|coordinator survey: --repo and --issues are required")
        return 2
    try:
        issue_numbers = [int(x.strip()) for x in issue_numbers_raw.split(",") if x.strip()]
    except ValueError:
        print("UNVERIFIED|coordinator survey: --issues must be a comma-separated list of integers")
        return 2

    def gh(*args):
        try:
            out = subprocess.run(["gh"] + list(args), capture_output=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=30, cwd=REPO)
            if out.returncode != 0:
                return None
            return out.stdout
        except Exception:
            return None

    pr_raw = gh("pr", "list", "--repo", repo, "--state", "all", "--limit", "100",
                "--json", "number,title,state,headRefName,body,mergedAt")
    if pr_raw is None:
        print(json.dumps({"schema": "simplicio.coordinator-snapshot/v1", "status": "UNVERIFIED",
                          "reason_code": "gh_unavailable", "issues": [], "prs": []},
                         ensure_ascii=False))
        return 0
    prs = json.loads(pr_raw)

    issues = []
    for number in issue_numbers:
        issue_raw = gh("issue", "view", str(number), "--repo", repo,
                       "--json", "number,title,state,comments")
        if issue_raw is None:
            continue
        issues.append(json.loads(issue_raw))

    snapshot = {"schema": "simplicio.coordinator-snapshot/v1", "status": "MEASURED",
                "issues": issues, "prs": prs}
    print(json.dumps(snapshot, ensure_ascii=False))
    return 0


def cmd_selftest(_opts):
    checks = []

    def chk(name, got, want):
        checks.append((name, got == want, got, want))

    now = 1_800_000_000.0
    hour = 3600.0

    # OWN: no claims, no merged PR
    d = decide_for_issue(100, [], [], "branch-a", now=now)
    chk("own_when_no_claims", d["action"], "OWN")
    chk("own_no_duplicate_risk", d["duplicate_risk"], False)

    # CONTINUE_OWN: latest claim is self
    comments = [{"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-a`.",
                "created_at": now - hour}]
    d = decide_for_issue(101, comments, [], "branch-a", now=now)
    chk("continue_own_when_self_claimed", d["action"], "CONTINUE_OWN")

    # DEFER_ACTIVE_CLAIM: recent claim from someone else
    comments = [{"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-b`.",
                "created_at": now - hour}]
    d = decide_for_issue(102, comments, [], "branch-a", now=now, stale_hours=6.0)
    chk("defer_when_recent_foreign_claim", d["action"], "DEFER_ACTIVE_CLAIM")

    # RECLAIM_STALE: old claim from someone else, nothing merged since
    comments = [{"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-b`.",
                "created_at": now - 10 * hour}]
    d = decide_for_issue(103, comments, [], "branch-a", now=now, stale_hours=6.0)
    chk("reclaim_when_stale_foreign_claim", d["action"], "RECLAIM_STALE")

    # VERIFY_PARTIAL: a merged PR references the issue, issue still open (the #466 case)
    comments = [{"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-b`.",
                "created_at": now - 10 * hour}]
    prs = [{"number": 475, "state": "MERGED", "body": "feat(#104): phase-1 slice",
           "title": "feat(#104)", "merged_at": now - 5 * hour}]
    d = decide_for_issue(104, comments, prs, "branch-a", now=now, stale_hours=6.0)
    chk("verify_partial_when_pr_merged_but_issue_open", d["action"], "VERIFY_PARTIAL")
    chk("verify_partial_has_merged_pr_true", d["has_merged_pr"], True)

    # duplicate_risk: two distinct branches claim within the collision window, nothing merged between
    comments = [
        {"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-a`.",
         "created_at": now - 2 * hour},
        {"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-b`.",
         "created_at": now - 1.5 * hour},
    ]
    d = decide_for_issue(105, comments, [], "branch-a", now=now, collision_window_hours=2.0)
    chk("duplicate_risk_flagged_for_near_simultaneous_claims", d["duplicate_risk"], True)

    # no duplicate_risk when the two claims are outside the collision window
    comments = [
        {"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-a`.",
         "created_at": now - 20 * hour},
        {"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `branch-b`.",
         "created_at": now - 1 * hour},
    ]
    d = decide_for_issue(106, comments, [], "branch-a", now=now, collision_window_hours=2.0)
    chk("no_duplicate_risk_outside_window", d["duplicate_risk"], False)

    # exact real-world case: #466 — merged PR from self branch + active foreign claim after it
    comments = [
        {"body": "some earlier unrelated comment", "created_at": now - 8 * hour},
        {"body": "🔒 **Claimed** — working via `/simplicio-loop` on branch `sibling-branch`.",
         "created_at": now - 1 * hour},
    ]
    prs = [{"number": 475, "state": "MERGED", "body": "feat(#107): phase-1 slice (T1)",
           "title": "feat(#107)", "merged_at": now - 3 * hour}]
    d = decide_for_issue(107, comments, prs, "self-branch", now=now, stale_hours=6.0)
    chk("real_world_466_case_is_verify_partial", d["action"], "VERIFY_PARTIAL")

    ok = True
    for name, passed, got, want in checks:
        tag = "PASS" if passed else "FAIL"
        print(f"  [{tag}] {name} (got={got!r} want={want!r})")
        ok = ok and passed

    n = len(checks)
    passed_n = sum(1 for _, p, _, _ in checks if p)
    if ok:
        print(f"MEASURED|coordinator selftest: {passed_n}/{n} checks passed")
        return 0
    print(f"UNVERIFIED|coordinator selftest: {passed_n}/{n} checks passed (FAILURES ABOVE)")
    return 1


def _parse(args):
    opts = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[key] = args[i + 1]
                i += 2
            else:
                opts[key] = True
                i += 1
        else:
            i += 1
    return opts


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        sys.exit(2)
    if argv[0] == "--describe-cli":
        print(json.dumps({
            "verbs": ["decide", "survey", "selftest"],
            "flags": ["--snapshot-file", "--self-branch", "--stale-hours",
                      "--collision-window-hours", "--repo", "--issues"],
        }))
        sys.exit(0)
    sub, opts = argv[0], _parse(argv[1:])
    handler = {"decide": cmd_decide, "survey": cmd_survey, "selftest": cmd_selftest}.get(sub)
    if handler is None:
        print("unknown command '%s'. choices: decide survey selftest" % sub)
        sys.exit(2)
    sys.exit(handler(opts) or 0)


if __name__ == "__main__":
    main()

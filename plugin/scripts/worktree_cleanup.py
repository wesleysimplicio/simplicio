#!/usr/bin/env python3
"""simplicio-loop — post-merge worktree/branch cleanup (#484).

The loop opens a PR from a dedicated branch (often a dedicated `git worktree`). Once that PR is
MERGED into `main`, nothing else deletes the branch or the worktree — they pile up silently. This
worker is the mandatory post-merge step: once a PR the loop opened is confirmed MERGED, delete its
branch (local + remote) and, if the work happened in a dedicated worktree, remove that worktree too
— but ONLY when it's safe: the PR must actually be MERGED, and the worktree/branch must have no
uncommitted changes. Never delete on ambiguous or unmerged state.

Deterministic and testable by construction: the "should we delete?" decision
(`decide_cleanup`) is a PURE function with no I/O, so it is exhaustively unit-testable; the
`gh`/`git` calls are each isolated in their own tiny function so tests can fake them without a
real network or repo.

Verbs:
  run        Check PR state, decide, and (unless --dry-run) delete the branch and/or worktree.
             --repo owner/name --pr N --branch NAME [--dry-run] [--json].
  selftest   Prove the porcelain parser + decision matrix + dry-run wiring deterministically —
             no real network/git calls, everything faked via function parameters.

Usage:
    python3 scripts/worktree_cleanup.py run --repo wesleysimplicio/simplicio-loop --pr 484 \\
        --branch simplicio/loop-worktree-cleanup --json
    python3 scripts/worktree_cleanup.py run --repo owner/name --pr 12 --branch fix-x --dry-run
    python3 scripts/worktree_cleanup.py selftest
"""
import json
import os
import subprocess
import sys

try:  # Windows consoles default to cp1252 and choke on non-ASCII — force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.environ.get("SIMPLICIO_REPO") or os.path.dirname(HERE))
CLEANUP_RECEIPT_SCHEMA = "simplicio.worktree-cleanup-receipt/v1"


def log(msg):
    print("  " + msg)


def _emit_progress(step, status, **kw):
    """Fail-open progress-feedback hook (#299/#300 pattern) — never raises, never blocks cleanup."""
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import loop_progress
        loop_progress.emit_event(step, status=status, source="worktree_cleanup.py", **kw)
    except Exception:
        pass


# ----- isolated I/O calls (each a tiny function so tests can fake them) --------------------------

def _gh_pr_view_raw(repo, pr_number):
    """Shell out to `gh pr view` and return the raw JSON dict. Isolated so `check_pr_merged`'s
    decision logic can be unit-tested against a fake instead of a real `gh`/network call."""
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--repo", repo,
         "--json", "state,mergedAt,headRefName"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("gh pr view failed (%d): %s" % (proc.returncode, proc.stderr.strip()))
    return json.loads(proc.stdout)


def _git_worktree_list_porcelain(cwd=None):
    """Shell out to `git worktree list --porcelain`. Isolated so `find_worktree_for_branch`'s
    parser can be unit-tested against fixture text instead of a real repo."""
    proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=cwd or REPO, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("git worktree list failed (%d): %s" % (proc.returncode, proc.stderr.strip()))
    return proc.stdout


def _git_status_porcelain(worktree_path):
    """Shell out to `git status --porcelain` in a given worktree path."""
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_path, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("git status failed (%d): %s" % (proc.returncode, proc.stderr.strip()))
    return proc.stdout


def _git_worktree_remove(worktree_path, cwd=None):
    proc = subprocess.run(
        ["git", "worktree", "remove", "--force", worktree_path],
        cwd=cwd or REPO, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("git worktree remove failed (%d): %s" % (proc.returncode, proc.stderr.strip()))
    return proc.stdout


def _git_branch_delete_local(branch_name, cwd=None):
    proc = subprocess.run(
        ["git", "branch", "-D", branch_name],
        cwd=cwd or REPO, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("git branch -D failed (%d): %s" % (proc.returncode, proc.stderr.strip()))
    return proc.stdout


def _git_branch_delete_remote(branch_name, cwd=None):
    proc = subprocess.run(
        ["git", "push", "origin", "--delete", branch_name],
        cwd=cwd or REPO, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError("git push --delete failed (%d): %s" % (proc.returncode, proc.stderr.strip()))
    return proc.stdout


# ----- pure / near-pure helpers (selftest exercises these directly, no I/O) ----------------------

def check_pr_merged(repo, pr_number, fetch=_gh_pr_view_raw):
    """Return {"merged": bool, "head_ref": str} for a PR. `fetch` is injectable so this stays
    unit-testable with a fake instead of a real `gh` call."""
    data = fetch(repo, pr_number) or {}
    state = str(data.get("state") or "").upper()
    merged_at = data.get("mergedAt") or None
    merged = state == "MERGED" and bool(merged_at)
    return {"merged": merged, "head_ref": str(data.get("headRefName") or "")}


def find_worktree_for_branch(porcelain_text, branch_name):
    """Parse `git worktree list --porcelain` TEXT and return the worktree path whose checked-out
    branch matches `branch_name`, or None. Pure — no I/O, so unit-testable on fixture text."""
    if not porcelain_text or not branch_name:
        return None
    target_full = "refs/heads/%s" % branch_name
    current_path = None
    for line in porcelain_text.splitlines():
        line = line.rstrip("\n")
        if line.startswith("worktree "):
            current_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            branch_ref = line[len("branch "):].strip()
            if current_path and (branch_ref == target_full or branch_ref == branch_name):
                return current_path
        elif not line.strip():
            current_path = None
    return None


def has_uncommitted_changes(worktree_path, status_fn=_git_status_porcelain):
    """True if `git status --porcelain` in `worktree_path` reports any pending change.

    `status_fn` is injectable (defaults to the real `git status --porcelain` subprocess call) so
    this stays unit-testable against a fake without a real filesystem/repo."""
    if not worktree_path:
        return False
    out = status_fn(worktree_path)
    return bool(out.strip())


def _cleanup_receipt(safety=None, decision="skip", reason=""):
    """Return the stable, secret-free receipt required for every cleanup decision."""
    safety = dict(safety or {})
    return {
        "schema": CLEANUP_RECEIPT_SCHEMA,
        "worktree_id": str(safety.get("worktree_id") or ""),
        "terminal_handle": str(safety.get("terminal_handle") or ""),
        "lease_owner": str(safety.get("lease_owner") or ""),
        "cleanup_decision": str(decision or "skip"),
        "reason": str(reason or ""),
    }


def _cleanup_safety(safety=None):
    """Normalize activity evidence without treating missing fields as safe."""
    raw = dict(safety or {})
    return {
        **raw,
        "lease_active": bool(raw.get("lease_active")),
        "agent_active": bool(raw.get("agent_active")),
        "terminal_active": bool(raw.get("terminal_active")),
        "terminal_exited": bool(raw.get("terminal_exited")),
        "receipt_explicit": bool(raw.get("receipt_explicit")),
        "commit_receipt": bool(raw.get("commit_receipt")),
        "pr_receipt": bool(raw.get("pr_receipt")),
        "no_changes_confirmed": bool(raw.get("no_changes_confirmed")),
    }


def decide_cleanup(pr_merged, head_ref, worktree_path, has_uncommitted, safety=None):
    """PURE decision function — no I/O. Given the facts gathered above, decide what cleanup (if
    any) is safe. Branch and worktree deletion are independent: a missing worktree does not block
    branch deletion, but a DIRTY worktree blocks BOTH (report clearly, don't half-clean)."""
    safety = _cleanup_safety(safety)
    if not pr_merged:
        return {"action": "skip", "reason": "pr_not_merged"}
    if worktree_path and has_uncommitted:
        return {
            "action": "skip", "reason": "uncommitted_changes", "path": worktree_path,
            "detail": "worktree at %s has uncommitted changes — skipping branch AND "
                      "worktree deletion" % worktree_path,
        }
    if safety.get("safety_error"):
        return {"action": "skip", "reason": "safety_evidence_unavailable",
                "detail": str(safety["safety_error"])[:240]}
    if safety["lease_active"] or safety["agent_active"] or safety["terminal_active"]:
        return {"action": "skip", "reason": "active_worktree",
                "detail": "lease, agent, or terminal is still active"}
    if not safety["receipt_explicit"]:
        return {"action": "skip", "reason": "missing_cleanup_receipt",
                "detail": "cleanup requires explicit terminal/commit/PR/no-change evidence"}
    if not safety["terminal_exited"]:
        return {"action": "skip", "reason": "terminal_exit_unconfirmed"}
    if not (safety["commit_receipt"] or safety["pr_receipt"] or safety["no_changes_confirmed"]):
        return {"action": "skip", "reason": "completion_receipt_unconfirmed"}
    if not worktree_path:
        return {
            "action": "cleanup", "head_ref": head_ref, "worktree_path": None,
            "delete_worktree": False, "delete_branch": True,
            "reason": "no_worktree_branch_only",
        }
    return {
        "action": "cleanup", "head_ref": head_ref, "worktree_path": worktree_path,
        "delete_worktree": True, "delete_branch": True,
    }


# ----- orchestration -------------------------------------------------------------------------

def _remote_matches(repo_root, repo):
    """Return whether a local checkout's origin is the requested GitHub repo."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    remote = proc.stdout.strip().lower().rstrip("/").removesuffix(".git")
    expected = str(repo).strip().lower().strip("/")
    return remote.endswith("github.com/" + expected) or remote.endswith("github.com:" + expected)


def _resolve_repo_root(repo, explicit=None):
    """Find the exact local checkout for a remote repo, failing closed when ambiguous."""
    requested = explicit or os.environ.get("SIMPLICIO_REPO")
    if requested:
        root = os.path.abspath(str(requested))
        return root if _remote_matches(root, repo) else None

    target_name = str(repo).rsplit("/", 1)[-1]
    cursor = os.path.abspath(REPO)
    seen = set()
    while cursor not in seen:
        seen.add(cursor)
        candidate = os.path.join(cursor, target_name)
        if os.path.isdir(candidate) and _remote_matches(candidate, repo):
            return candidate
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    return os.path.abspath(REPO) if _remote_matches(REPO, repo) else None


def cleanup(
    repo, pr_number, branch_name,
    dry_run=False,
    fetch=_gh_pr_view_raw,
    worktree_list_fn=_git_worktree_list_porcelain,
    status_fn=_git_status_porcelain,
    remove_worktree_fn=_git_worktree_remove,
    delete_local_branch_fn=_git_branch_delete_local,
    delete_remote_branch_fn=_git_branch_delete_remote,
    safety_fn=None,
    safety=None,
    repo_root=None,
):
    """Wire evidence checks to the verified checkout for the requested remote repo."""
    try:
        pr_state = check_pr_merged(repo, pr_number, fetch=fetch)
        porcelain = (worktree_list_fn(cwd=repo_root) if repo_root
                     else worktree_list_fn())
    except Exception as exc:
        normalized_safety = _cleanup_safety(safety)
        reason = "cleanup_evidence_unavailable"
        decision = {"action": "skip", "reason": reason,
                    "detail": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
        return {"repo": repo, "pr": pr_number, "branch": branch_name, "dry_run": bool(dry_run),
                "decision": decision, "actions_taken": [],
                "receipt": _cleanup_receipt(normalized_safety, "skip", reason)}
    worktree_path = find_worktree_for_branch(porcelain, branch_name)
    try:
        dirty = has_uncommitted_changes(worktree_path, status_fn=status_fn) if worktree_path else False
    except Exception as exc:
        normalized_safety = _cleanup_safety(safety)
        reason = "git_status_unavailable"
        decision = {"action": "skip", "reason": reason,
                    "detail": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
        return {"repo": repo, "pr": pr_number, "branch": branch_name, "dry_run": bool(dry_run),
                "decision": decision, "actions_taken": [],
                "receipt": _cleanup_receipt(normalized_safety, "skip", reason)}
    if safety_fn is not None:
        try:
            safety = safety_fn(worktree_path, branch_name) or {}
        except Exception as exc:
            safety = {"safety_error": "%s: %s" % (type(exc).__name__, exc)}
    normalized_safety = _cleanup_safety(safety)
    decision = decide_cleanup(pr_state["merged"], pr_state["head_ref"] or branch_name,
                              worktree_path, dirty, safety=normalized_safety)
    result = {"repo": repo, "pr": pr_number, "branch": branch_name, "dry_run": bool(dry_run),
              "decision": decision, "actions_taken": [],
              "receipt": _cleanup_receipt(normalized_safety, decision.get("action"),
                                           decision.get("reason"))}
    if decision["action"] != "cleanup":
        return result
    if dry_run:
        would = []
        if decision.get("delete_worktree"):
            would.append("remove worktree %s" % decision["worktree_path"])
        if decision.get("delete_branch"):
            would.append("delete local branch %s" % branch_name)
            would.append("delete remote branch %s" % branch_name)
        result["would_do"] = would
        return result
    if decision.get("delete_worktree"):
        if repo_root:
            remove_worktree_fn(decision["worktree_path"], cwd=repo_root)
        else:
            remove_worktree_fn(decision["worktree_path"])
        result["actions_taken"].append("removed_worktree")
    if decision.get("delete_branch"):
        if repo_root:
            delete_local_branch_fn(branch_name, cwd=repo_root)
        else:
            delete_local_branch_fn(branch_name)
        result["actions_taken"].append("deleted_local_branch")
        try:
            if repo_root:
                delete_remote_branch_fn(branch_name, cwd=repo_root)
            else:
                delete_remote_branch_fn(branch_name)
            result["actions_taken"].append("deleted_remote_branch")
        except Exception as exc:  # remote branch may already be gone (e.g. GitHub auto-delete)
            result["remote_delete_note"] = str(exc)
    return result


# ----- CLI -----------------------------------------------------------------------------------

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


def cmd_run(opts):
    repo = opts.get("repo")
    pr = opts.get("pr")
    branch = opts.get("branch")
    if not repo or not pr or not branch:
        print("run requires --repo owner/name --pr N --branch NAME")
        sys.exit(2)
    dry_run = bool(opts.get("dry-run"))
    repo_root = _resolve_repo_root(repo, opts.get("repo-root"))
    if not repo_root:
        result = {"repo": repo, "pr": pr, "branch": branch, "dry_run": dry_run,
                  "decision": {"action": "skip", "reason": "repo_root_unresolved",
                               "detail": "pass --repo-root or configure SIMPLICIO_REPO for the requested remote"},
                  "actions_taken": [],
                  "receipt": _cleanup_receipt({}, "skip", "repo_root_unresolved")}
        if opts.get("json"):
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("skip")
            log(result["decision"]["detail"])
        return
    safety = None
    if opts.get("safety-json"):
        try:
            with open(str(opts["safety-json"]), encoding="utf-8") as fh:
                safety = json.load(fh)
            if not isinstance(safety, dict):
                raise ValueError("safety receipt must be an object")
        except (OSError, ValueError, TypeError) as exc:
            receipt = _cleanup_receipt({}, "skip", "invalid_safety_receipt")
            print(json.dumps({"decision": {"action": "skip", "reason": "invalid_safety_receipt"},
                              "receipt": receipt, "error": str(exc)}, ensure_ascii=False))
            sys.exit(1)
    try:
        pr_number = int(pr)
    except (TypeError, ValueError):
        print("--pr must be an integer")
        sys.exit(2)
    try:
        result = cleanup(repo, pr_number, branch, dry_run=dry_run, safety=safety, repo_root=repo_root)
    except Exception as exc:
        print("error: %s" % exc)
        _emit_progress("cleanup", "blocked", outcome="blocked", detail=str(exc))
        sys.exit(1)
    as_json = opts.get("json")
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        decision = result["decision"]
        print(decision["action"])
        if decision["action"] == "skip":
            log("skipped: %s" % decision.get("reason"))
            if decision.get("detail"):
                log(decision["detail"])
        elif dry_run:
            for line in result.get("would_do", []):
                log("would " + line)
        else:
            log("done: %s" % ", ".join(result.get("actions_taken") or ["nothing"]))
            if result.get("remote_delete_note"):
                log("note: remote branch delete: %s" % result["remote_delete_note"])
    _emit_progress("cleanup", "pass" if result["decision"]["action"] == "cleanup" else "skip",
                   outcome=result["decision"]["action"], detail=result["decision"].get("reason", ""))
    sys.exit(0)


def cmd_selftest(_opts):
    checks = []
    safe_safety = {
        "worktree_id": "selftest-wt", "terminal_handle": "selftest-term",
        "lease_owner": "selftest", "receipt_explicit": True,
        "terminal_exited": True, "no_changes_confirmed": True,
    }

    def chk(name, got, want):
        ok = got == want
        checks.append(ok)
        print("  [%s] %-32s got=%r want=%r" % ("ok" if ok else "XX", name, got, want))

    # ---- find_worktree_for_branch: fixture porcelain text, 2-3 worktrees ----
    porcelain = (
        "worktree /repo\n"
        "HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.claude/worktrees/feature-x\n"
        "HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "branch refs/heads/feature-x\n"
        "\n"
        "worktree /repo/.claude/worktrees/detached-one\n"
        "HEAD cccccccccccccccccccccccccccccccccccccccc\n"
        "detached\n"
    )
    chk("find.match", find_worktree_for_branch(porcelain, "feature-x"),
        "/repo/.claude/worktrees/feature-x")
    chk("find.no_match", find_worktree_for_branch(porcelain, "no-such-branch"), None)
    chk("find.detached_no_branch_line", find_worktree_for_branch(porcelain, "detached-one"), None)
    chk("find.empty_text", find_worktree_for_branch("", "feature-x"), None)

    # ---- decide_cleanup: all 4 outcomes ----
    chk("decide.not_merged",
        decide_cleanup(False, "feature-x", "/repo/wt", False),
        {"action": "skip", "reason": "pr_not_merged"})

    dirty = decide_cleanup(True, "feature-x", "/repo/wt", True)
    chk("decide.uncommitted.action", dirty["action"], "skip")
    chk("decide.uncommitted.reason", dirty["reason"], "uncommitted_changes")
    chk("decide.uncommitted.path", dirty["path"], "/repo/wt")

    no_wt = decide_cleanup(True, "feature-x", None, False, safety=safe_safety)
    chk("decide.no_worktree.action", no_wt["action"], "cleanup")
    chk("decide.no_worktree.delete_worktree", no_wt["delete_worktree"], False)
    chk("decide.no_worktree.delete_branch", no_wt["delete_branch"], True)

    full = decide_cleanup(True, "feature-x", "/repo/wt", False, safety=safe_safety)
    chk("decide.cleanup.action", full["action"], "cleanup")
    chk("decide.cleanup.delete_worktree", full["delete_worktree"], True)
    chk("decide.cleanup.delete_branch", full["delete_branch"], True)

    # ---- check_pr_merged with a fake fetch (no real gh/network call) ----
    def fake_fetch_merged(repo, pr_number):
        return {"state": "MERGED", "mergedAt": "2026-07-17T00:00:00Z", "headRefName": "feature-x"}

    def fake_fetch_open(repo, pr_number):
        return {"state": "OPEN", "mergedAt": None, "headRefName": "feature-x"}

    chk("check_pr_merged.merged", check_pr_merged("o/r", 1, fetch=fake_fetch_merged),
        {"merged": True, "head_ref": "feature-x"})
    chk("check_pr_merged.open", check_pr_merged("o/r", 1, fetch=fake_fetch_open),
        {"merged": False, "head_ref": "feature-x"})

    # ---- cleanup() orchestration: dry-run never calls delete; real run calls it once ----
    calls = {"remove_worktree": 0, "delete_local": 0, "delete_remote": 0}

    def fake_remove_worktree(path):
        calls["remove_worktree"] += 1

    def fake_delete_local(branch):
        calls["delete_local"] += 1

    def fake_delete_remote(branch):
        calls["delete_remote"] += 1

    def fake_worktree_list():
        return porcelain

    def fake_status_clean(path):
        return ""

    result_dry = cleanup(
        "o/r", 1, "feature-x", dry_run=True,
        fetch=fake_fetch_merged, worktree_list_fn=fake_worktree_list,
        status_fn=fake_status_clean, remove_worktree_fn=fake_remove_worktree,
        delete_local_branch_fn=fake_delete_local, delete_remote_branch_fn=fake_delete_remote,
        safety=safe_safety,
    )
    chk("cleanup.dry_run.action", result_dry["decision"]["action"], "cleanup")
    chk("cleanup.dry_run.no_delete_calls",
        (calls["remove_worktree"], calls["delete_local"], calls["delete_remote"]), (0, 0, 0))
    chk("cleanup.dry_run.would_do_present", len(result_dry.get("would_do", [])) > 0, True)

    result_real = cleanup(
        "o/r", 1, "feature-x", dry_run=False,
        fetch=fake_fetch_merged, worktree_list_fn=fake_worktree_list,
        status_fn=fake_status_clean, remove_worktree_fn=fake_remove_worktree,
        delete_local_branch_fn=fake_delete_local, delete_remote_branch_fn=fake_delete_remote,
        safety=safe_safety,
    )
    chk("cleanup.real_run.action", result_real["decision"]["action"], "cleanup")
    chk("cleanup.real_run.remove_worktree_called_once", calls["remove_worktree"], 1)
    chk("cleanup.real_run.delete_local_called_once", calls["delete_local"], 1)
    chk("cleanup.real_run.delete_remote_called_once", calls["delete_remote"], 1)

    # not-merged path never touches delete fns
    calls2 = {"remove_worktree": 0, "delete_local": 0, "delete_remote": 0}
    result_skip = cleanup(
        "o/r", 1, "feature-x", dry_run=False,
        fetch=fake_fetch_open, worktree_list_fn=fake_worktree_list,
        status_fn=fake_status_clean,
        remove_worktree_fn=lambda p: calls2.__setitem__("remove_worktree", calls2["remove_worktree"] + 1),
        delete_local_branch_fn=lambda b: calls2.__setitem__("delete_local", calls2["delete_local"] + 1),
        delete_remote_branch_fn=lambda b: calls2.__setitem__("delete_remote", calls2["delete_remote"] + 1),
        safety=safe_safety,
    )
    chk("cleanup.skip_not_merged.action", result_skip["decision"]["action"], "skip")
    chk("cleanup.skip_not_merged.no_calls",
        (calls2["remove_worktree"], calls2["delete_local"], calls2["delete_remote"]), (0, 0, 0))

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    sys.exit(0 if ok else 1)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        sys.exit(2)
    if argv[0] == "--describe-cli":
        print(json.dumps({
            "verbs": ["run", "selftest"],
             "flags": ["--repo", "--pr", "--branch", "--dry-run", "--safety-json", "--json", "--help"],
        }))
        sys.exit(0)
    sub, opts = argv[0], _parse(argv[1:])
    {"run": cmd_run, "selftest": cmd_selftest}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: run selftest" % sub), sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

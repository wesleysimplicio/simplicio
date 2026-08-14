#!/usr/bin/env python3
"""simplicio-loop — watcher verification producer.

Generates a watcher receipt bound to the current challenge and run artifacts.
Without challenge + anchor criteria + structured evidence, the watcher fails closed.

Anchor-derived challenges:
  - `issue` writes a deterministic challenge derived from the current anchor.
  - `verify` validates that binding when the challenge uses the anchor-derived schema.
  - A derived challenge alone NEVER approves criteria; without an independent
    watcher receipt the final state stays UNVERIFIED.
"""
import json
import os
import subprocess
import hashlib
import sys
import tempfile
import time
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
CHALLENGE = os.path.join(LOOP_DIR, "watcher_challenge.json")
ANCHOR = os.path.join(LOOP_DIR, "anchor.json")
WATCHER_STATE = os.path.join(LOOP_DIR, "watcher_state.json")
ANCHOR_CHALLENGE_SCHEMA = "simplicio.anchor-challenge/v1"

if REPO not in sys.path:
    sys.path.insert(0, REPO)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from simplicio_loop.evidence import execute_receipt_checks, watcher_truth_from_receipt  # noqa: E402
from simplicio_loop.quality_matrix import (  # noqa: E402
    independent_reverify_quality_matrix,
    receipt_path as quality_matrix_receipt_path,
)


def _emit_progress(status, outcome=None, detail=""):
    """Fail-open progress-feedback hook (#300) — never raises. Called ONLY after the watcher
    receipt is already written to disk (invariant 2: progress is a projection of the gate, never
    a substitute for it — it must never fire before watcher_state.json exists)."""
    try:
        import loop_progress
        loop_progress.emit_event("watcher", status=status, outcome=outcome, detail=detail,
                                 source="watcher_verify.py")
    except Exception:
        pass


def _set_repo(repo):
    global REPO, LOOP_DIR, CHALLENGE, ANCHOR, WATCHER_STATE
    REPO = repo
    LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
    CHALLENGE = os.path.join(LOOP_DIR, "watcher_challenge.json")
    ANCHOR = os.path.join(LOOP_DIR, "anchor.json")
    WATCHER_STATE = os.path.join(LOOP_DIR, "watcher_state.json")


def _set_loop_dir(loop_dir):
    """Bind the producer to a persisted run-local control directory."""
    global LOOP_DIR, CHALLENGE, ANCHOR, WATCHER_STATE
    LOOP_DIR = loop_dir
    CHALLENGE = os.path.join(LOOP_DIR, "watcher_challenge.json")
    ANCHOR = os.path.join(LOOP_DIR, "anchor.json")
    WATCHER_STATE = os.path.join(LOOP_DIR, "watcher_state.json")


def _resolve_wi_worktree(wi):
    """#561: resolve the Orca worktree for a given WI id (e.g. WI-3307 ->
    .simplicio/orchestrator/worktrees/wi-3307). Returns None when no such worktree exists
    (caller must fail closed to UNVERIFIED rather than silently using REPO)."""
    if not wi:
        return None
    candidate = Path(REPO) / ".simplicio/orchestrator" / "worktrees" / wi.lower()
    if candidate.is_dir():
        return str(candidate)
    return None

_run_dir = os.environ.get("SIMPLICIO_RUN_DIR", "").strip()
_repo_override = os.environ.get("SIMPLICIO_LOOP_REPO", "").strip()
if _repo_override:
    _set_repo(_repo_override)
# NOTE: SIMPLICIO_RUN_DIR selects the run-local artifact directory and must NOT
# redefine REPO/LOOP_DIR — the run dir is resolved by _find_run_dir(wi=...) below.
# The legacy parents[2] heuristic broke backlog/items/<wi>/run layouts (double
# .simplicio/orchestrator path). REPO stays the script-resolved default unless SIMPLICIO_LOOP_REPO is set.
_loop_override = os.environ.get("SIMPLICIO_LOOP_DIR", "").strip()
if _loop_override:
    _set_loop_dir(_loop_override)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _stable_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _find_run_dir(wi=None):
    run_dir = os.environ.get("SIMPLICIO_RUN_DIR", "").strip()
    if run_dir:
        return Path(run_dir)
    orch = Path(REPO) / ".simplicio/orchestrator"
    runs_root = orch / "runs"  # new convention: .simplicio/orchestrator/runs/wi-XXXX
    legacy_root = orch          # legacy convention: .simplicio/orchestrator/run-WIXXXX

    def _has_independent(p):
        return p.is_dir() and (p / "independent-watcher-receipt.json").is_file()

    # Normalize the WI number (accept "wi-569", "WI-569", "569").
    wi_num = ""
    if wi:
        digits = "".join(ch for ch in str(wi) if ch.isdigit())
        wi_num = digits

    if wi and wi_num:
        # 1) New convention: runs/wi-<n> (directory uses lowercase wi-<n>).
        new_dir = runs_root / ("wi-%s" % wi_num)
        if _has_independent(new_dir):
            return new_dir
        # 2) Legacy convention: run-WI<n> (uppercase, no dash).
        legacy_dir = legacy_root / ("run-WI%s" % wi_num)
        if _has_independent(legacy_dir):
            return legacy_dir

    # Fallback: scan both new (runs/*) and legacy (run-*) trees for ANY
    # dir holding an independent receipt. Prefer one whose name embeds the
    # requested WI number when --wi was given; otherwise take the first found.
    candidates = []
    if runs_root.is_dir():
        for entry in sorted(runs_root.glob("wi-*")):
            if _has_independent(entry):
                candidates.append(entry)
    if legacy_root.is_dir():
        for entry in sorted(legacy_root.glob("run-*")):
            if _has_independent(entry):
                candidates.append(entry)
    if not candidates:
        return None
    if wi and wi_num:
        for c in candidates:
            if wi_num in c.name:
                return c
    return candidates[0]

def _load_run_artifacts(run_dir):
    if not run_dir:
        return None, None
    evidence = _read_json(run_dir / "evidence-receipt.json")
    independent = _read_json(run_dir / "independent-watcher-receipt.json")
    return evidence, independent


def _git_meta(worktree=None):
    def _run(*args):
        try:
            done = subprocess.run(["git", *args], cwd=worktree or REPO,
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
            return (done.stdout or "").strip() if done.returncode == 0 else ""
        except Exception:
            return ""
    # Include NEW (untracked) files in the diff fingerprint. The default
    # `git diff HEAD` ignores untracked paths, so a run that only *creates*
    # files would always hash to the empty-string sha and never match a
    # receipt that recorded the real change. We stage everything
    # temporarily (`git add -A`), read `git diff --cached HEAD` (which
    # DOES include newly-added paths), then restore the original index
    # with `git reset` (mixed) so the working tree is untouched.
    diff = ""
    staged = False
    try:
        st = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                            cwd=worktree or REPO, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=15)
        if st.returncode == 0 and any(line[:2] in ("??", " A", "M ", "M ") or line.startswith("??")
                               for line in st.stdout.splitlines()):
            subprocess.run(["git", "add", "-A"], cwd=worktree or REPO,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
            staged = True
        diff = _run("diff", "--no-ext-diff", "--cached", "HEAD")
    finally:
        if staged:
            subprocess.run(["git", "reset", "-q"], cwd=worktree or REPO,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
    return {
        "commit_sha": _run("rev-parse", "HEAD"),
        "diff_hash": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "diff_present": bool(diff.strip()),
    }


def _anchor_criteria(anchor):
    criteria = (anchor or {}).get("criteria") or []
    return [item for item in criteria if isinstance(item, dict) and item.get("id")]


def _anchor_snapshot(anchor):
    items = []
    for item in _anchor_criteria(anchor):
        items.append({
            "id": str(item.get("id") or ""),
            "status": str(item.get("status") or "pending"),
        })
    items.sort(key=lambda entry: entry["id"])
    return {
        "goal_fp": str((anchor or {}).get("goal_fp") or ""),
        "criteria": items,
    }


def _derive_anchor_challenge(anchor, iteration=0):
    snapshot = _anchor_snapshot(anchor)
    material = {
        "goal_fp": snapshot["goal_fp"],
        "criteria": snapshot["criteria"],
        "iteration": int(iteration or 0),
        "schema": ANCHOR_CHALLENGE_SCHEMA,
    }
    criteria_json = _stable_json(snapshot["criteria"])
    snapshot_json = _stable_json(snapshot)
    material_json = _stable_json(material)
    return {
        "schema": ANCHOR_CHALLENGE_SCHEMA,
        "mode": "anchor-derived",
        "challenge": hashlib.sha256(material_json.encode("utf-8")).hexdigest(),
        "goal_fp": snapshot["goal_fp"],
        "iteration": int(iteration or 0),
        "anchor_sha256": hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest(),
        "criteria_fp": hashlib.sha256(criteria_json.encode("utf-8")).hexdigest(),
        "challenge_material": material,
        "challenge_derivation": (
            "SHA-256 over schema + iteration + anchor.goal_fp + sorted criterion ids/statuses. "
            "This binds the challenge to the frozen anchor only; it does not approve criteria "
            "without an independent watcher receipt."
        ),
    }


def _is_anchor_derived_challenge(challenge):
    return isinstance(challenge, dict) and str(challenge.get("schema") or "") == ANCHOR_CHALLENGE_SCHEMA


def _validate_anchor_derived_challenge(anchor, challenge):
    expected = _derive_anchor_challenge(anchor or {}, challenge.get("iteration", 0))
    reasons = []
    if not challenge.get("written_at"):
        reasons.append("challenge has no issuance timestamp")
    for field in ("challenge", "goal_fp", "anchor_sha256", "criteria_fp"):
        if str(challenge.get(field) or "") != str(expected.get(field) or ""):
            reasons.append("anchor-derived challenge %s does not match current anchor" % field)
    if challenge.get("challenge_material") != expected.get("challenge_material"):
        reasons.append("anchor-derived challenge material does not match current anchor")
    return expected, reasons


def _evidence_index(evidence):
    idx = {}
    for item in evidence.get("criteria") or []:
        if isinstance(item, dict) and item.get("id"):
            idx[item["id"]] = item
    return idx


def _criterion_results(anchor, evidence, executed):
    anchor_items = _anchor_criteria(anchor)
    evidence_items = _evidence_index(evidence or {})
    executed_by_id = {item.get("id"): item for item in (executed.get("results") or []) if item.get("id")}
    results = []
    for item in anchor_items:
        reported_done = item.get("status") == "done"
        ev = evidence_items.get(item["id"])
        ev_state = (ev or {}).get("verification_state", "unverified")
        recomputed = ev_state == "verified"
        proof_refs = list((ev or {}).get("proof_refs") or [])
        check = executed_by_id.get(item["id"])
        if check:
            proof_refs.append(check.get("proof_ref", ""))
            recomputed = recomputed and (check.get("status") == "MEASURED")
        # A status flag alone is not evidence.  Every verified AC must carry
        # at least one non-empty, producer-supplied proof reference; otherwise
        # a hand-written ``verification_state`` could satisfy completion.
        proof_refs = [str(ref).strip() for ref in proof_refs if str(ref).strip()]
        recomputed = recomputed and bool(proof_refs)
        results.append({
            "id": item["id"],
            "reported_result": "done" if reported_done else item.get("status", "pending"),
            "recomputed_result": "verified" if recomputed else ev_state,
            "evidence_ids": [ref for ref in proof_refs if ref],
            "match": reported_done and recomputed,
        })
    return results


def _wi_files_from_receipt(independent):
    """#612-followup: extract file paths cited in an independent watcher receipt's
    evidence_ids / verification_method so the commit-diff check can be scoped to the
    WI's own files. A receipt generated in an isolated worktree at an older commit must
    still validate when the main repo HEAD has advanced *only in unrelated files*.
    Returns a list of repo-relative paths that actually exist in the repo (a bare
    basename like ``runner.py`` without a path separator is ignored unless it resolves
    to a real file, so hand-written prose refs don't pollute the diff scope)."""
    import re
    files = set()
    if not isinstance(independent, dict):
        return []
    candidates = []
    for item in independent.get("criteria_results") or []:
        for ref in (item.get("evidence_ids") or []):
            ref = str(ref)
            for m in re.findall(r"([A-Za-z0-9_./-]+\.py)(?::\d+)?", ref):
                candidates.append(m)
    method = str(independent.get("method") or "")
    for m in re.findall(r"([A-Za-z0-9_./-]+\.py)", method):
        candidates.append(m)
    for f in candidates:
        # Only keep paths that exist in the repo, or contain a separator (real
        # repo-relative path). A bare basename is rejected unless it resolves.
        if "/" in f or "\\" in f:
            files.add(f)
        elif os.path.exists(os.path.join(REPO, f)):
            files.add(f)
    return sorted(files)


def _wi_diff_empty_between(expected_commit, head_commit, wi_files):
    """Return True when the WI's own files are unchanged between expected_commit and
    head_commit (i.e. the older receipt is still valid despite HEAD advancing)."""
    if not expected_commit or not head_commit or expected_commit == head_commit:
        return False
    if not wi_files:
        return False
    try:
        done = subprocess.run(
            ["git", "diff", "--name-only", expected_commit, head_commit, "--", *wi_files],
            cwd=REPO, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15,
        )
        return done.returncode == 0 and not done.stdout.strip()
    except Exception:
        return False


def _independent_criterion_results(anchor, independent):
    anchor_items = _anchor_criteria(anchor)
    independent_items = {
        item.get("id"): item
        for item in (independent or {}).get("criteria_results") or []
        if isinstance(item, dict) and item.get("id")
    }
    results = []
    for item in anchor_items:
        reported_done = item.get("status") == "done"
        measured = independent_items.get(item["id"]) or {}
        recomputed = measured.get("status") == "MEASURED" and bool(measured.get("match"))
        evidence_ids = [str(ref).strip() for ref in (measured.get("evidence_ids") or []) if str(ref).strip()]
        recomputed = recomputed and bool(evidence_ids)
        results.append({
            "id": item["id"],
            "reported_result": "done" if reported_done else item.get("status", "pending"),
            "recomputed_result": "verified" if recomputed else measured.get("recomputed_result", "pending"),
            "evidence_ids": evidence_ids,
            "match": reported_done and recomputed,
        })
    return results


def cmd_issue():
    anchor = _read_json(ANCHOR)
    anchor_items = _anchor_criteria(anchor)
    if not anchor or not anchor_items:
        print("UNVERIFIED|watcher_verify: cannot issue challenge without anchor criteria")
        return 1
    anchor_ids = [item["id"] for item in anchor_items]
    if len(anchor_ids) != len(set(anchor_ids)):
        print("UNVERIFIED|watcher_verify: cannot issue challenge with duplicate acceptance-criterion ids")
        return 1
    current = _read_json(CHALLENGE) or {}
    payload = _derive_anchor_challenge(anchor, current.get("iteration", 0))
    payload["written_at"] = _now()
    os.makedirs(LOOP_DIR, exist_ok=True)
    tmp = CHALLENGE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CHALLENGE)
    print("MEASURED|watcher challenge issued: %s (anchor-derived deterministic binding)" % payload["challenge"])
    return 0


def _quality_gate_reverify(run_dir):
    """#283: independently re-derive the quality-matrix verdict for this run, instead of just
    trusting the receipt's own self-reported ``status``. Returns None when there is no
    quality-matrix.json for this run at all (nothing to re-verify -- callers must not treat that
    as a pass; the oracle's own quality-matrix gate already fails closed on a missing receipt)."""
    if not run_dir:
        return None
    if not quality_matrix_receipt_path(str(run_dir)).exists():
        return None
    try:
        rerun = os.environ.get("SIMPLICIO_WATCHER_QUALITY_RERUN", "1").strip() != "0"
        return independent_reverify_quality_matrix(str(run_dir), repo=REPO, rerun=rerun)
    except Exception as exc:  # pragma: no cover - defensive, fail-closed below
        return {"ready": False, "reason_code": "quality_gate_reverify_error", "reason": str(exc),
                "self_reported": {}, "lane_checks": []}


def cmd_verify(wi=None, worktree=None):
    wt = None
    if wi or worktree:
        wt = worktree or _resolve_wi_worktree(wi)
    challenge = _read_json(CHALLENGE)
    if not challenge:
        print("UNVERIFIED|watcher_verify: no challenge on disk yet — nothing to answer")
        return 1

    anchor = _read_json(ANCHOR)
    anchor_items = _anchor_criteria(anchor)
    run_dir = _find_run_dir(wi=wi)
    evidence, independent = _load_run_artifacts(run_dir)
    quality_reverify = _quality_gate_reverify(run_dir)

    reasons = []
    if quality_reverify is not None and not quality_reverify.get("ready"):
        reasons.append("quality-matrix independent re-verification failed: %s" % quality_reverify.get("reason", ""))
    if not anchor or not anchor_items:
        reasons.append("anchor missing or has no criteria")
    anchor_ids = [item["id"] for item in anchor_items]
    if len(anchor_ids) != len(set(anchor_ids)):
        reasons.append("anchor contains duplicate acceptance-criterion ids")
    anchor_bound = _is_anchor_derived_challenge(challenge)
    if anchor_bound:
        _, challenge_reasons = _validate_anchor_derived_challenge(anchor or {}, challenge)
        reasons.extend(challenge_reasons)
    else:
        challenge_goal = str(challenge.get("goal_fp") or "")
        anchor_goal = str((anchor or {}).get("goal_fp") or "")
        if challenge_goal and anchor_goal and challenge_goal != anchor_goal:
            reasons.append("challenge goal fingerprint does not match anchor")
        if not challenge.get("written_at"):
            reasons.append("challenge has no issuance timestamp")
    if not evidence and not independent:
        reasons.append("independent watcher receipt missing" if anchor_bound else "evidence receipt missing")
    elif evidence and not (evidence.get("operator") or {}).get("coverage_ok", True):
        uncovered = ", ".join((evidence.get("operator") or {}).get("uncovered_paths") or [])
        reasons.append("uncovered diff outside operator receipt: %s" % uncovered)

    using_independent = bool(independent) and (anchor_bound or not evidence)
    if using_independent:
        independent_challenge = str((independent or {}).get("challenge") or "")
        if independent_challenge and independent_challenge != str(challenge.get("challenge") or ""):
            reasons.append("independent watcher challenge does not match current challenge")
        if not str((independent or {}).get("task_contract_hash") or "").strip():
            reasons.append("independent watcher task-contract hash missing")
        executed = {"all_passed": bool(independent and independent.get("match")), "results": []}
        truth = {
            "ready": bool(independent and independent.get("match") and independent.get("status") == "MEASURED"),
            "reported": "independent watcher recomputed all criteria"
            if independent and independent.get("match")
            else "independent watcher did not verify all criteria",
            "status": "MEASURED" if independent and independent.get("match") else "UNVERIFIED",
        }
        criteria_results = _independent_criterion_results(anchor or {}, independent or {})
    else:
        if anchor_bound and not independent:
            reasons.append("independent watcher receipt missing for anchor-derived challenge")
        executed = execute_receipt_checks(evidence or {})
        truth = watcher_truth_from_receipt(evidence or {})
        criteria_results = _criterion_results(anchor or {}, evidence or {}, executed)

    if not criteria_results:
        reasons.append("no criteria results could be recomputed")

    run_meta = (evidence or {}).get("run") or {}
    if using_independent:
        run_meta = {
            "task_contract_hash": (independent or {}).get("task_contract_hash", ""),
            "plan_hash": (independent or {}).get("plan_hash", "") or (independent or {}).get("verify_plan_hash", ""),
            "commit_sha": (independent or {}).get("commit_sha", ""),
            "diff_hash": (independent or {}).get("diff_hash", ""),
        }
    git_meta = _git_meta(worktree=wt)
    expected_commit = run_meta.get("commit_sha", "")
    expected_diff = run_meta.get("diff_hash", "")
    # #612-followup: tolerate HEAD advancement when the WI's own files are unchanged
    # between the receipt's commit and the current HEAD. This prevents a false-negative
    # watcher verdict when the repo evolved only in unrelated orchestration files.
    wi_files = _wi_files_from_receipt(independent) if using_independent else _wi_files_from_receipt(evidence)
    commit_advance_ok = (
        bool(wi_files)
        and _wi_diff_empty_between(expected_commit, git_meta["commit_sha"], wi_files)
    )
    if expected_commit and git_meta["commit_sha"] and expected_commit != git_meta["commit_sha"]:
        if not commit_advance_ok:
            reasons.append("run commit differs from watcher worktree")
    if expected_diff and expected_diff != git_meta["diff_hash"]:
        if not commit_advance_ok:
            reasons.append("run diff differs from watcher worktree")
    all_criteria_match = bool(criteria_results) and all(item["match"] for item in criteria_results)
    ready = not reasons and truth["ready"] and executed["all_passed"] and all_criteria_match
    reported = truth["reported"]
    if reasons:
        reported = "; ".join(reasons)
    elif evidence and evidence.get("checks"):
        reported = "%s; watcher checks=%d/%d passed" % (
            reported,
            sum(1 for r in executed["results"] if r["status"] == "MEASURED"),
            len(executed["results"]),
        )

    receipt = {
        "schema": "simplicio.watcher-receipt/v1",
        "match": ready,
        "status": "MEASURED" if ready else "UNVERIFIED",
        "checked_at": _now(),
        "challenge": challenge.get("challenge", ""),
        "goal_fp": challenge.get("goal_fp", ""),
        "iteration": challenge.get("iteration", 0),
        "reported": reported,
        "recomputed_truth": ready,
        "run_id": (evidence or independent or {}).get("run_id", ""),
        "task_contract_hash": run_meta.get("task_contract_hash", ""),
        "plan_hash": run_meta.get("plan_hash", ""),
        "commit_sha": run_meta.get("commit_sha", "") or git_meta["commit_sha"],
        "diff_hash": run_meta.get("diff_hash", ""),
        "tool_versions": {
            "watcher": "watcher_verify.py",
            "python": sys.version.split()[0],
        },
        "criteria_results": criteria_results,
        "check_results": executed["results"],
        # #283: independent re-derivation of the quality-matrix verdict (not a re-parse of its
        # self-reported status) -- matches the issue's requested watcher promise-gate shape:
        # {"quality_gate": "VERIFIED", "match": true, "status": "MEASURED"}. `None` means this run
        # has no quality-matrix.json at all (nothing for the watcher to independently confirm);
        # that case is still fail-closed further up the stack via the oracle's own quality gate.
        "quality_gate": (
            "VERIFIED" if (quality_reverify and quality_reverify.get("ready"))
            else ("BLOCKED" if quality_reverify is not None else "NOT_PRESENT")
        ),
        "quality_gate_detail": quality_reverify,
        "producer": {
            "pid": os.getpid(),
            "repo": REPO,
            "run_dir": str(run_dir) if run_dir else "",
        },
    }
    os.makedirs(LOOP_DIR, exist_ok=True)
    tmp = WATCHER_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    os.replace(tmp, WATCHER_STATE)
    tag = "MEASURED|" if ready else "UNVERIFIED|"
    print("%swatcher receipt written: match=%s (%s)" % (tag, ready, receipt["reported"]))
    _emit_progress("end", outcome=("pass" if ready else "fail"),
                  detail=receipt["reported"][:400])
    return 0


def cmd_selftest():
    origin = REPO
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _set_repo(tmp)
            os.makedirs(LOOP_DIR, exist_ok=True)

            rc = cmd_verify()
            assert rc == 1
            assert not os.path.exists(WATCHER_STATE)

            with open(CHALLENGE, "w", encoding="utf-8") as f:
                json.dump({"challenge": "abc123", "goal_fp": "fp1", "iteration": 2,
                           "written_at": "2026-07-10T00:00:00Z"}, f)

            rc = cmd_verify()
            assert rc == 0
            state = _read_json(WATCHER_STATE)
            assert state["match"] is False
            assert state["status"] == "UNVERIFIED"

            with open(ANCHOR, "w", encoding="utf-8") as f:
                json.dump({"goal_fp": "fp1", "criteria": [
                    {"id": "AC1", "status": "done"},
                    {"id": "AC2", "status": "done"},
                ]}, f)
            run_dir = os.path.join(tmp, ".simplicio/orchestrator", "runs", "demo")
            os.makedirs(run_dir, exist_ok=True)
            with open(os.path.join(run_dir, "evidence-receipt.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "schema": "simplicio.evidence-receipt/v1",
                    "run_id": "demo",
                    "status": "VERIFIED",
                    "run": {"task_contract_hash": "hash1", "plan_hash": "hash2", "commit_sha": "", "diff_hash": ""},
                    "criteria": [
                        {"id": "AC1", "verification_state": "verified", "proof_refs": ["proof-1"]},
                        {"id": "AC2", "verification_state": "verified", "proof_refs": ["proof-2"]},
                    ],
                    "summary": {"criteria_total": 2, "criteria_verified": 2, "scenario_total": 2,
                                "scenario_verified": 2, "rule_total": 1, "rule_verified": 1},
                    "checks": [],
                }, f)
            os.environ["SIMPLICIO_RUN_DIR"] = run_dir
            rc = cmd_verify()
            assert rc == 0
            state = _read_json(WATCHER_STATE)
            assert state["match"] is True
            assert len(state["criteria_results"]) == 2
            os.environ.pop("SIMPLICIO_RUN_DIR", None)

            print("watcher_verify selftest: PASS")
    finally:
        _set_repo(origin)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="watcher verification producer")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("issue")
    pv = sub.add_parser("verify")
    pv.add_argument("--wi", default=None, help="Work item id (e.g. WI-3307) to isolate worktree/run")
    pv.add_argument("--issue", default=None, help="GitHub issue number (resolves to WI via mapping)")
    pv.add_argument("--worktree", default=None, help="Explicit worktree path to isolate")
    sub.add_parser("selftest")
    args = parser.parse_args()
    if not args.cmd:
        print("Usage: python3 scripts/watcher_verify.py issue|verify|selftest")
        sys.exit(2)
    if args.cmd == "issue":
        sys.exit(cmd_issue())
    elif args.cmd == "verify":
        wi = args.wi
        if not wi and args.issue:
            wi = _wi_for_issue(args.issue)
        sys.exit(cmd_verify(wi=wi, worktree=args.worktree))
    elif args.cmd == "selftest":
        cmd_selftest()
    else:
        print("UNVERIFIED|unknown command: %s" % args.cmd)
        sys.exit(2)


def _wi_for_issue(issue):
    """#561: map a GitHub issue number to its canonical WI id via the tasks dir."""
    try:
        tasks_root = Path(REPO) / ".simplicio/orchestrator" / "tasks"
        if tasks_root.is_dir():
            for entry in sorted(tasks_root.glob("WI-*.md")):
                text = entry.read_text(encoding="utf-8", errors="ignore")
                if ("#%s" % str(issue)) in text:
                    return entry.stem
    except Exception:
        pass
    return None

if __name__ == "__main__":
    main()

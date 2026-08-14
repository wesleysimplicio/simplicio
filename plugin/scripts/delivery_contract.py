#!/usr/bin/env python3
"""simplicio-loop — delivery contract worker (issue #526 Etapa 4).

Client delivery restrictions said in natural language ("don't open a PR", "don't commit tests",
"no comments in the code") stop being prose the agent might forget mid-run and become a **frozen
contract** living next to the task anchor (`task_anchor.py set --delivery delivery.json`), with
mechanical gates that consume it instead of re-deriving it from memory every turn:

  * `open_pr: false`      -> `pr_evidence.py build` runs in `--local-report` mode (writes the
                             evidence body to a local file, never calls the PR API).
  * `allow_new_files_in_repo: false` -> a per-contract file-appearance baseline
                             (`capture_baseline`/`check_new_files`) the stop-hook consumes to BLOCK
                             the turn the moment an unauthorized new file shows up in `git status`.
  * `allow_comments_in_code: false`  -> a deterministic, comment-syntax-aware diff linter
                             (`find_added_comment_lines`) that fails when the diff adds a comment
                             line, covering at least C#/TS/JS (`//`, `/* */`) and Python (`#`, new
                             docstrings).
  * `commit_message_convention` -> a template-derived regex checked against the actual commit
                             subject (`commit_message_matches`).

Schema: `references/delivery-contract.md` (mirrored under
`.claude/skills/simplicio-loop/references/`). Strict and fail-CLOSED on an unknown field — a typo'd
or extra key in delivery.json is a hard error, never a silent no-op. Freezing follows the SAME
semantics `task_anchor.py`'s goal re-anchor already established: a changed contract is refused
unless `--force` — a silent contract swap mid-run is exactly the drift class this exists to catch.

State:
  `.simplicio/orchestrator/loop/delivery_baseline.json` — the new-file baseline captured once, at freeze
      time (`capture_baseline`). Every path listed there is "pre-existing" and never re-flagged;
      everything else that later shows up as untracked/staged-new is a violation. NOT rewound on
      an ordinary turn — only re-captured by an explicit re-freeze (`--force`), matching the
      contract's "no new files, period" semantics for its whole lifetime.
  `.simplicio/orchestrator/loop/delivery_report.md` — the default `--local-report` output path used by
      `pr_evidence.py` when `open_pr: false`.

Verbs:
  validate            Validate a candidate delivery.json against the schema. Exit 2 on error.
  capture-baseline     Snapshot the CURRENT new/untracked files as the contract's baseline.
  check-new-files      Compare the working tree against the baseline; exit 1 on violation.
  lint-comments        Scan `git diff` (`--cached` by default, or `--working-tree`) for added
                       comment lines; exit 1 on violation.
  check-commit-message Check a commit subject against a `commit_message_convention` template.
  report               Render the "### Delivery contract compliance" markdown block.

Usage:
    python3 scripts/delivery_contract.py validate --file delivery.json
    python3 scripts/delivery_contract.py capture-baseline
    python3 scripts/delivery_contract.py check-new-files
    python3 scripts/delivery_contract.py lint-comments --working-tree
    python3 scripts/delivery_contract.py check-commit-message \\
        --message "#526 - feat: add delivery contract" --convention "#<issue> - <type>: <desc>"
    python3 scripts/delivery_contract.py report --anchor .simplicio/orchestrator/loop/anchor.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

try:  # Windows consoles default to cp1252 and choke on non-ASCII — force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCHEMA = "simplicio.delivery-contract/v1"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOOP_DIR = os.path.join(REPO, ".simplicio/orchestrator", "loop")
DEFAULT_ANCHOR = os.environ.get("SIMPLICIO_ANCHOR_FILE") or os.path.join(LOOP_DIR, "anchor.json")
# Env overrides mirror task_anchor.py's SIMPLICIO_ANCHOR_FILE -- lets a subprocess-driven test
# (or an alternate install layout) redirect state without ever touching this repo's own
# .simplicio/orchestrator/loop/ (same isolation discipline as test_intake_progress.py's SIMPLICIO_*_FILE).
DEFAULT_BASELINE = (os.environ.get("SIMPLICIO_DELIVERY_BASELINE_FILE")
                     or os.path.join(LOOP_DIR, "delivery_baseline.json"))
DEFAULT_LOCAL_REPORT = (os.environ.get("SIMPLICIO_DELIVERY_REPORT_FILE")
                         or os.path.join(LOOP_DIR, "delivery_report.md"))

# ----- schema ---------------------------------------------------------------------------------

# The 5 mandatory fields from the issue's example payload. Unknown fields are a hard error (never
# silently dropped); every one of these must be present with the right type.
REQUIRED_FIELDS: dict = {
    "open_pr": bool,
    "push_branch": bool,
    "allow_new_files_in_repo": bool,
    "allow_comments_in_code": bool,
    "commit_message_convention": str,
}


def validate(data: Any) -> list:
    """Return a list of schema errors for a candidate delivery contract. [] means valid.

    Strict: an unknown key is refused (not silently ignored), every required field must be
    present with the declared type, and `commit_message_convention` must be a non-blank string.
    """
    errors = []
    if not isinstance(data, Mapping):
        return ["delivery contract must be a JSON object, got %r" % type(data).__name__]
    unknown = sorted(set(data.keys()) - set(REQUIRED_FIELDS) - {"schema"})
    if unknown:
        errors.append("unknown field(s) in delivery contract: %s" % ", ".join(unknown))
    for field, typ in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append("missing required field: %s" % field)
            continue
        value = data[field]
        if typ is bool and not isinstance(value, bool):
            errors.append("field %r must be a boolean, got %r" % (field, value))
        elif typ is str and (not isinstance(value, str) or not value.strip()):
            errors.append("field %r must be a non-empty string, got %r" % (field, value))
    return errors


def load_contract_file(path) -> dict:
    """Read+parse a delivery.json candidate. Raises ValueError on any I/O/parse failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise ValueError("cannot read delivery contract %s: %s" % (path, exc)) from exc


def freeze(existing, new_contract: Mapping, force: bool = False):
    """Pure: -> (frozen_dict, error_or_None).

    Refuses to silently replace an ALREADY-frozen, DIFFERENT contract unless `force=True` — the
    same semantics `task_anchor.py`'s goal re-anchor already uses for a changed goal.
    """
    normalized = {k: new_contract[k] for k in REQUIRED_FIELDS}
    if existing and dict(existing) != normalized and not force:
        return None, ("a delivery contract is already frozen and differs from the new one — "
                       "re-freeze with --force only if the client's restrictions genuinely "
                       "changed (same semantics as a goal re-anchor)")
    return normalized, None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ----- git plumbing (self-contained — no cross-import from diff_escalation.py) -----------------

def _git(root, args: Sequence) -> str:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("git unavailable: %s" % exc) from exc
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "git failed").strip())
    return completed.stdout


# Never source, and would otherwise make THIS worker's own state write (the baseline file
# itself, mid-capture) or the loop's/runtime's own state look like a "new file" the client's
# contract forbids -- the exact self-inflicted false-positive class `hooks/loop_stop.py`'s
# `_changed_files()` already guards against for its own diff heuristic.
_IGNORED_PREFIXES = (".simplicio/orchestrator/", ".simplicio/")


def _new_file_paths(status_text: str) -> list:
    """Untracked ('??') or newly-staged-added ('A' in the first two columns) paths from
    `git status --porcelain=v1`, excluding the loop's/runtime's own state directories."""
    out = []
    for line in status_text.splitlines():
        if len(line) < 3:
            continue
        status, path = line[:2], line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        path = path.strip('"')
        if not path:
            continue
        norm = path.replace("\\", "/")
        if norm.startswith(_IGNORED_PREFIXES) or "__pycache__" in norm:
            continue
        if status == "??" or "A" in status:
            out.append(path)
    return sorted(set(out))


def current_new_files(root=".") -> list:
    """New (untracked/staged-added) paths in the working tree right now.

    [] on any git error — fail-open at the MEASUREMENT layer; callers (the guard functions) decide
    what an empty/unreadable measurement means for their own gate.
    """
    try:
        status = _git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    except RuntimeError:
        return []
    return _new_file_paths(status)


# ----- new-file baseline / guard (allow_new_files_in_repo: false) ------------------------------

def capture_baseline(root=".", path=None) -> dict:
    """Snapshot the CURRENT new-file set as the contract's baseline.

    Every path captured here is treated as pre-existing/authorized for the LIFETIME of this
    delivery contract and never re-flagged. Call once, right when `allow_new_files_in_repo: false`
    is frozen (`task_anchor.py set --delivery`); re-capture only alongside an explicit `--force`
    re-freeze.
    """
    path = path or DEFAULT_BASELINE
    payload = {"schema": SCHEMA, "new_files": current_new_files(root), "captured_at": _now()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return payload


def read_baseline(path=None) -> dict:
    path = path or DEFAULT_BASELINE
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def check_new_files(root=".", baseline_path=None) -> dict:
    """Compare the CURRENT new-file set against the frozen baseline.

    `ok=True` when every currently-new file was already in the baseline (nothing genuinely new
    appeared since the contract was frozen). An ABSENT baseline is treated as an empty one — i.e.
    every currently-untracked/staged-new file is a violation — so a guard that runs before
    `capture_baseline` ever ran fails closed rather than silently passing.
    """
    baseline = set(read_baseline(baseline_path).get("new_files") or [])
    current = current_new_files(root)
    violations = sorted(f for f in current if f not in baseline)
    return {"ok": not violations, "violations": violations, "current": current,
            "baseline": sorted(baseline)}


def new_file_guard(anchor, root=".", baseline_path=None):
    """Return a violation reason string, or None when there is nothing to block.

    `anchor` is the loaded task_anchor.json dict (or None/{}). No `delivery` key, or
    `allow_new_files_in_repo` true/absent -> None (nothing to enforce).
    """
    delivery = (anchor or {}).get("delivery") if isinstance(anchor, Mapping) else None
    if not isinstance(delivery, Mapping) or delivery.get("allow_new_files_in_repo", True):
        return None
    result = check_new_files(root, baseline_path)
    if result["ok"]:
        return None
    return ("delivery contract violation — allow_new_files_in_repo=false but %d unauthorized new "
            "file(s) appeared: %s" % (len(result["violations"]), ", ".join(result["violations"])))


# ----- comment linter (allow_comments_in_code: false) -------------------------------------------

# Deterministic, per-extension comment syntax. Covers at least C#, TS/JS, and Python per the AC;
# `//`/`/* */` families share one rule shape, Python gets its own (`#` + new docstrings).
_LANG_RULES = {
    ".cs": {"line": ("//",), "block": ("/*", "*/")},
    ".ts": {"line": ("//",), "block": ("/*", "*/")},
    ".tsx": {"line": ("//",), "block": ("/*", "*/")},
    ".js": {"line": ("//",), "block": ("/*", "*/")},
    ".jsx": {"line": ("//",), "block": ("/*", "*/")},
    ".mjs": {"line": ("//",), "block": ("/*", "*/")},
    ".cjs": {"line": ("//",), "block": ("/*", "*/")},
    ".py": {"line": ("#",), "block": None, "docstring": True},
}

_DOCSTRING_RE = re.compile(r'^(?:[rRuUbB]{1,2})?("""|\'\'\')')
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_NEW_FILE_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")


def _rules_for_path(path):
    if not path:
        return None
    ext = os.path.splitext(path)[1].lower()
    return _LANG_RULES.get(ext)


def _is_comment_line(rules: Mapping, stripped: str) -> bool:
    if not stripped:
        return False
    for tok in rules.get("line") or ():
        if stripped.startswith(tok):
            return True
    block = rules.get("block")
    if block:
        open_tok, close_tok = block
        if stripped.startswith(open_tok) or close_tok in stripped:
            return True
        if stripped.startswith("*") and not stripped.startswith("*/"):
            return True  # continuation line inside an existing /* ... */ block
    if rules.get("docstring") and _DOCSTRING_RE.match(stripped):
        return True
    return False


def find_added_comment_lines(diff_text: str) -> list:
    """Scan a unified diff (`git diff` output) for ADDED lines that are comments, per the target
    file's language. Returns [] when clean, else a list of {"file","line","text"} dicts."""
    violations = []
    current_file = None
    rules = None
    new_lineno = None
    for raw in (diff_text or "").splitlines():
        if raw.startswith("+++ "):
            m = _NEW_FILE_RE.match(raw)
            current_file = m.group(1).strip() if m else None
            if current_file == "/dev/null":
                current_file = None
            rules = _rules_for_path(current_file)
            continue
        if raw.startswith("@@"):
            m = _HUNK_RE.match(raw)
            new_lineno = int(m.group(1)) if m else None
            continue
        if raw.startswith("+"):
            text = raw[1:]
            if rules and new_lineno is not None and _is_comment_line(rules, text.strip()):
                violations.append({"file": current_file, "line": new_lineno, "text": text.strip()})
            if new_lineno is not None:
                new_lineno += 1
            continue
        if raw.startswith("-"):
            continue  # a removed line does not advance the NEW file's line counter
        if raw.startswith("\\"):
            continue  # "\ No newline at end of file"
        if new_lineno is not None:
            new_lineno += 1  # context line present on both sides
    return violations


def lint_working_diff(root=".", cached: bool = True) -> dict:
    """Run `find_added_comment_lines` over the real `git diff` of `root`.

    `cached=True` (default) scans the STAGED diff (pre-commit use); `cached=False` scans the
    working-tree diff (pre-stage / stop-hook use).
    """
    args = ["diff", "--cached"] if cached else ["diff"]
    try:
        diff_text = _git(root, args)
    except RuntimeError as exc:
        return {"ok": False, "violations": [], "error": str(exc)}
    violations = find_added_comment_lines(diff_text)
    return {"ok": not violations, "violations": violations, "error": None}


def comment_guard(anchor, root=".", cached: bool = True):
    """Return a violation reason string, or None. Fail-open on a git measurement error — never
    trap a commit over a git-plumbing failure; the contract still gates on a READABLE diff."""
    delivery = (anchor or {}).get("delivery") if isinstance(anchor, Mapping) else None
    if not isinstance(delivery, Mapping) or delivery.get("allow_comments_in_code", True):
        return None
    result = lint_working_diff(root, cached=cached)
    if result.get("error"):
        return None
    if result["ok"]:
        return None
    detail = "; ".join("%s:%d: %s" % (v["file"], v["line"], v["text"][:80])
                        for v in result["violations"])
    return ("delivery contract violation — allow_comments_in_code=false but the diff adds %d "
            "comment line(s): %s" % (len(result["violations"]), detail))


# ----- commit message convention -----------------------------------------------------------------

def commit_message_matches(message: str, convention: str) -> bool:
    """Check a commit message SUBJECT (first line) against a convention template such as
    `#<issue> - <type>: <desc>`. `<issue>` -> digits, `<type>` -> a bare word, `<desc>` -> any
    non-empty remainder. A blank convention matches anything (nothing declared -> nothing to
    enforce)."""
    if not convention or not convention.strip():
        return True
    pattern = re.escape(convention)
    pattern = pattern.replace(re.escape("<issue>"), r"\d+")
    pattern = pattern.replace(re.escape("<type>"), r"[A-Za-z][\w-]*")
    pattern = pattern.replace(re.escape("<desc>"), r".+")
    subject = (message or "").splitlines()[0] if message else ""
    return re.match("^" + pattern + "$", subject) is not None


# ----- final-report compliance block -------------------------------------------------------------

def render_compliance_report(anchor, root=".", baseline_path=None, last_commit_message: str = ""
                              ) -> str:
    """Render the "### Delivery contract compliance" markdown block: the contract + the
    mechanically-computed compliance of EACH clause, tagged MEASURED (issue #526 Etapa 4, last
    bullet: "O relatório final lista o contrato e o cumprimento de cada cláusula, com tag
    MEASURED.")."""
    delivery = (anchor or {}).get("delivery") if isinstance(anchor, Mapping) else None
    lines = ["### Delivery contract compliance"]
    if not isinstance(delivery, Mapping):
        lines.append("- _(no delivery contract frozen for this item)_")
        return "\n".join(lines)
    lines.append("")

    open_pr = bool(delivery.get("open_pr"))
    if open_pr:
        lines.append("- [MEASURED] open_pr: true — normal PR flow")
    else:
        lines.append("- [MEASURED] open_pr: false — compliant (pr_evidence.py runs in "
                      "--local-report mode; no PR API call)")

    lines.append("- [MEASURED] push_branch: %s — declared clause (not independently observed by "
                  "this worker)" % json.dumps(bool(delivery.get("push_branch"))))

    if delivery.get("allow_new_files_in_repo", True):
        lines.append("- [MEASURED] allow_new_files_in_repo: true — no restriction")
    else:
        chk = check_new_files(root, baseline_path)
        status = ("compliant" if chk["ok"] else
                   "VIOLATION — unauthorized new file(s): %s" % ", ".join(chk["violations"]))
        lines.append("- [MEASURED] allow_new_files_in_repo: false — %s" % status)

    if delivery.get("allow_comments_in_code", True):
        lines.append("- [MEASURED] allow_comments_in_code: true — no restriction")
    else:
        chk = lint_working_diff(root, cached=False)
        if chk.get("error"):
            lines.append("- [MEASURED] allow_comments_in_code: false — UNVERIFIED (%s)"
                          % chk["error"])
        else:
            status = ("compliant" if chk["ok"] else
                       "VIOLATION — %d added comment line(s)" % len(chk["violations"]))
            lines.append("- [MEASURED] allow_comments_in_code: false — %s" % status)

    convention = delivery.get("commit_message_convention") or ""
    if last_commit_message:
        ok = commit_message_matches(last_commit_message, convention)
        subj = last_commit_message.splitlines()[0] if last_commit_message else ""
        status = "compliant" if ok else "VIOLATION — %r does not match %r" % (subj, convention)
        lines.append("- [MEASURED] commit_message_convention: %r — %s" % (convention, status))
    else:
        lines.append("- [MEASURED] commit_message_convention: %r — declared (no commit checked "
                      "yet)" % convention)
    return "\n".join(lines)


# ----- CLI -----------------------------------------------------------------------------------

def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_validate(args) -> int:
    try:
        data = load_contract_file(args.file)
    except ValueError as exc:
        print("blocked")
        print("  %s" % exc)
        return 2
    errors = validate(data)
    if errors:
        print("blocked")
        for e in errors:
            print("  %s" % e)
        return 2
    print("valid")
    return 0


def cmd_capture_baseline(args) -> int:
    payload = capture_baseline(args.root, args.baseline)
    _print(payload)
    return 0


def cmd_check_new_files(args) -> int:
    result = check_new_files(args.root, args.baseline)
    _print(result)
    return 0 if result["ok"] else 1


def cmd_lint_comments(args) -> int:
    result = lint_working_diff(args.root, cached=not args.working_tree)
    _print(result)
    return 0 if result["ok"] else 1


def cmd_check_commit_message(args) -> int:
    ok = commit_message_matches(args.message, args.convention)
    print("ok" if ok else "blocked")
    return 0 if ok else 1


def cmd_report(args) -> int:
    anchor = {}
    try:
        with open(args.anchor, encoding="utf-8") as f:
            anchor = json.load(f)
    except Exception:
        anchor = {}
    print(render_compliance_report(anchor, args.root, args.baseline, args.last_commit_message))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("capture-baseline")
    p.add_argument("--root", default=".")
    p.add_argument("--baseline", default=DEFAULT_BASELINE)
    p.set_defaults(func=cmd_capture_baseline)

    p = sub.add_parser("check-new-files")
    p.add_argument("--root", default=".")
    p.add_argument("--baseline", default=DEFAULT_BASELINE)
    p.set_defaults(func=cmd_check_new_files)

    p = sub.add_parser("lint-comments")
    p.add_argument("--root", default=".")
    p.add_argument("--working-tree", action="store_true",
                   help="scan the working-tree diff instead of the staged (--cached) diff")
    p.set_defaults(func=cmd_lint_comments)

    p = sub.add_parser("check-commit-message")
    p.add_argument("--message", required=True)
    p.add_argument("--convention", required=True)
    p.set_defaults(func=cmd_check_commit_message)

    p = sub.add_parser("report")
    p.add_argument("--root", default=".")
    p.add_argument("--anchor", default=DEFAULT_ANCHOR)
    p.add_argument("--baseline", default=DEFAULT_BASELINE)
    p.add_argument("--last-commit-message", default="")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

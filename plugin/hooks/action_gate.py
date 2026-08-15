#!/usr/bin/env python3
"""simplicio-loop — action_gate: a FAIL-CLOSED safety gate run BEFORE a mutation, not as prose.

The skills DESCRIBE a safety contract (secret-scan every diff, human-gate irreversible ops). This
ENFORCES it mechanically, so an autonomous agent that commits/pushes/merges on its own cannot skip
it. It is the executable form of `simplicio-tasks` Step 5 + the `action_gate`/`security` extension
points.

Fail-closed where it counts: a matched irreversible op, or a secret found in the diff about to be
committed/pushed, is **BLOCKED** — and if a push/commit's diff cannot be scanned, that push is
blocked too (a security check that can't run is not a pass). Benign commands pass untouched, so the
gate never bricks normal work; only the dangerous/unverifiable paths are denied.

Runs four ways:
  • Claude PreToolUse (Bash matcher) — reads `{tool_name, tool_input:{command}}` on stdin; a block
    exits 2 (Claude blocks the tool call and feeds `reason` back to the model).
  • git pre-push hook — `action_gate.py pre-push` secret-scans the REAL push range (HEAD vs.
    upstream, not the staged diff — see `_push_diff`) AND requires a green
    `scripts/check.py --core-gate` (#291: the local, mandatory-and-impossible-to-bypass
    equivalent of CI now that GitHub Actions was removed in #311). `--full` runs the complete
    gate instead of the fast core one.
  • git pre-commit hook — `action_gate.py check --staged` secret-scans the staged diff.
  • CLI / tests — `check --command "<cmd>"`, `scan-diff --diff FILE`, `selftest`.

Exit codes: 0 = allow · 2 = BLOCK (deny). Never exits 0 on a detected secret, irreversible op, or
(pre-push only) a failing local gate.

Usage:
    action_gate.py check --command "git push --force origin main"     # -> block (exit 2)
    action_gate.py check --staged                                     # secret-scan staged diff
    action_gate.py pre-push                                           # wire as .git/hooks/pre-push
    action_gate.py pre-push --full                                    # full gate, not --core-gate
    action_gate.py scan-diff --diff changes.patch
    action_gate.py selftest
    echo '{"tool_input":{"command":"git push -f"}}' | action_gate.py    # PreToolUse mode
"""
import json
import os
import re
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _project_relevant():
    """Project-relevance gate for the PreToolUse path ONLY.

    The plugin's Bash gate must not impose itself on every repo on the machine — it acts
    only inside an active simplicio-loop project. Relevant when the opt-in env var
    SIMPLICIO_LOOP (or SIMPLICIO_ORCHESTRATOR) is set, or when a `.simplicio/orchestrator/` marker
    dir (the orchestrator's state dir, created when the loop runs) exists in the current
    working directory or an ancestor. Outside such a project the PreToolUse hook no-ops.
    The explicit CLI / git-hook entry points (check / scan-diff / selftest) are NOT gated —
    they are invoked deliberately and always run.
    """
    if os.environ.get("SIMPLICIO_LOOP") or os.environ.get("SIMPLICIO_ORCHESTRATOR"):
        return True
    home = os.path.realpath(os.path.expanduser("~"))
    d = os.path.realpath(os.getcwd())
    for _ in range(40):  # depth backstop so an off-home tree can't climb forever
        parent = os.path.dirname(d)
        # Never treat the home dir or a drive/filesystem root as a project marker location:
        # a stray ~/.simplicio/orchestrator, or a marker at a drive root, must not widen the scope.
        if d == home or parent == d:
            return False
        if os.path.isdir(os.path.join(d, ".simplicio/orchestrator")):
            return True
        d = parent
    return False


# Irreversible / history-rewriting / destructive ops → BLOCK and route to a human (Step 5).
# High-precision patterns: each is genuinely hard to undo; benign commands never match.
IRREVERSIBLE = [
    (re.compile(r"\bgit\s+push\b.*(--force\b|--force-with-lease\b|(?<!-)\B-f\b)"),
     "force-push (history overwrite) — route to a human; prefer an additive rebase"),
    (re.compile(r"\bgit\s+push\b.*(--mirror|--delete\b|\s:\S)"),
     "remote branch/ref deletion or mirror-push — irreversible on the remote"),
    (re.compile(r"\bgit\s+(filter-branch|filter-repo)\b"),
     "history rewrite across the repo — irreversible for everyone"),
    (re.compile(r"\brm\s+-rf?\s+(/|~|\.|\*|\$HOME)(\s|$)"),
     "recursive delete of a root/home/cwd/glob — mass-file deletion"),
    (re.compile(r"\b(DROP\s+(DATABASE|TABLE|SCHEMA)|TRUNCATE\s+TABLE)\b", re.I),
     "destructive schema/data DDL"),
    (re.compile(r"\bterraform\s+destroy\b|\bkubectl\s+delete\s+(namespace|ns|pv|deployment)\b", re.I),
     "infrastructure teardown / prod resource deletion"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),
     "fork bomb"),
]

# Secret signatures (high-precision; the generic key/secret rule needs a long value to fire).
SECRETS = [
    (re.compile(r"-----BEGIN\s+(RSA|EC|OPENSSH|DSA|PGP)?\s*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OpenAI-style secret key"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*"
                r"['\"][A-Za-z0-9/+_\-]{16,}['\"]"), "hardcoded credential"),
]
# Lines that are obviously placeholders / examples are not secrets.
PLACEHOLDER = re.compile(r"(?i)(your[_-]?|example|placeholder|xxxx|<.*>|changeme|dummy|fake|redacted|\.\.\.)")
# An explicit, auditable allowlist marker for known-fake fixtures (the detect-secrets convention):
# a line carrying it is exempt. Grep-able, so an exemption is always visible in review.
ALLOWLIST = re.compile(r"(?i)(pragma:\s*allowlist secret|allowlist[- ]secret|noqa:\s*secret)")


def _run(argv, **kw):
    try:
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=kw.pop("cwd", REPO), **kw)
    except FileNotFoundError:
        return None


def classify_command(cmd):
    """Return (None) if benign, or (reason) if it's an irreversible op to BLOCK."""
    if not cmd:
        return None
    for rx, reason in IRREVERSIBLE:
        if rx.search(cmd):
            return reason
    return None


def scan_secret_text(text):
    """Return a list of (label, lineno) secret hits in a diff/patch/text. Placeholder-aware."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        # only scan added lines in a diff (start with '+'), or all lines in raw text
        probe = line[1:] if line[:1] == "+" else (line if not line.startswith(("-", "@@", "diff ")) else None)
        if probe is None:
            continue
        if ALLOWLIST.search(probe):
            continue  # explicitly allowlisted fixture — exempt (auditable, grep-able)
        for rx, label in SECRETS:
            if rx.search(probe) and not PLACEHOLDER.search(probe):
                hits.append((label, n))
                break
    return hits


def _effective_command_cwd(cmd):
    """Resolve an explicit leading cd or git -C target for PreToolUse scans."""
    base = os.getcwd()
    candidate = None
    leading = re.match(
        r"""^\s*(?:cd|Set-Location)\s+(?:"([^"]+)"|'([^']+)'|([^&;\n]+))\s*(?:&&|;)""",
        cmd or "",
    )
    if leading:
        candidate = next((value for value in leading.groups() if value), "").strip()
    else:
        git_c = re.search(r"""\bgit\s+-C\s+(?:"([^"]+)"|'([^']+)'|(\S+))""", cmd or "")
        if git_c:
            candidate = next((value for value in git_c.groups() if value), "").strip()
    if not candidate:
        return os.path.abspath(base)
    candidate = os.path.expandvars(os.path.expanduser(candidate))
    if not os.path.isabs(candidate):
        candidate = os.path.join(base, candidate)
    return os.path.normpath(os.path.abspath(candidate))


def _staged_diff(cwd=None):
    r = _run(["git", "diff", "--cached", "--unified=0"], cwd=cwd or os.getcwd())
    return (r.stdout if r and r.returncode == 0 else None)


def _push_diff(cwd=None):
    """Return the commits actually leaving the selected repository on git push."""
    cwd = cwd or os.getcwd()
    r = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=cwd)
    upstream = r.stdout.strip() if r and r.returncode == 0 and r.stdout.strip() else None
    if upstream:
        d = _run(["git", "diff", "%s...HEAD" % upstream, "--unified=0"], cwd=cwd)
        if d and d.returncode == 0:
            return d.stdout
    d = _run(["git", "diff", "HEAD~1..HEAD", "--unified=0"], cwd=cwd)
    if d and d.returncode == 0:
        return d.stdout
    d = _run(["git", "diff", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", "HEAD", "--unified=0"],
             cwd=cwd)
    return (d.stdout if d and d.returncode == 0 else None)


def _delivery_contract(cwd):
    """Load the optional frozen delivery contract for the effective repository."""
    local_anchor = os.path.join(cwd, ".simplicio/orchestrator", "loop", "anchor.json")
    anchor_path = local_anchor if os.path.exists(local_anchor) else (
        os.environ.get("SIMPLICIO_ANCHOR_FILE") or local_anchor
    )
    try:
        with open(anchor_path, encoding="utf-8") as handle:
            anchor = json.load(handle)
        contract = anchor.get("delivery")
        if not contract:
            return None, None
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        from simplicio_loop.delivery_contract import normalize_contract
        return normalize_contract(contract), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return None, "invalid frozen delivery contract: %s" % exc


def _diff_new_paths(cwd, push):
    """Return added paths from the same range that will be secret-scanned."""
    if push:
        upstream = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=cwd)
        ref = upstream.stdout.strip() if upstream and upstream.returncode == 0 else ""
        ranges = (["%s...HEAD" % ref] if ref else ["HEAD~1..HEAD", "4b825dc642cb6eb9a060e54bf8d69288fbee4904", "HEAD"])
        for item in ranges:
            args = ["git", "diff", item, "--name-status"] if "..." in item or ".." in item else ["git", "diff", item, "HEAD", "--name-status"]
            result = _run(args, cwd=cwd)
            if result and result.returncode == 0:
                return [line.split("\t", 1)[-1] for line in result.stdout.splitlines()
                        if line and line[0] in {"A", "C"} and "\t" in line]
        return []
    result = _run(["git", "diff", "--cached", "--name-status"], cwd=cwd)
    if not result or result.returncode != 0:
        return []
    return [line.split("\t", 1)[-1] for line in result.stdout.splitlines()
            if line and line[0] in {"A", "C"} and "\t" in line]


def _delivery_guard(cwd, diff, push):
    contract, error = _delivery_contract(cwd)
    if error:
        return error
    if contract is None:
        return None
    new_paths = _diff_new_paths(cwd, push)
    if not contract["allow_new_files_in_repo"] and new_paths:
        return "delivery contract forbids new files (cwd=%s): %s" % (cwd, ", ".join(sorted(new_paths)))
    if not contract["allow_comments_in_code"]:
        code_paths = {
            line[6:].strip()
            for line in diff.splitlines()
            if line.startswith("+++ b/")
        }
        code_suffixes = (".cs", ".js", ".jsx", ".ts", ".tsx", ".py")
        if not any(path.lower().endswith(code_suffixes) for path in code_paths):
            return None
        comments = []
        for line in diff.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            added = line[1:].lstrip()
            if added.startswith(("#", "//", "/*", "*", '"""')):
                comments.append(added[:80])
        if comments:
            return "delivery contract forbids new code comments (cwd=%s; lines=%d)" % (cwd, len(comments))
    return None


def _is_commit_or_push(cmd):
    return bool(re.search(r"\bgit\s+(commit|push)\b", cmd or ""))


def _is_push(cmd):
    return bool(re.search(r"\bgit\s+.*\bpush\b", cmd or ""))




def _verdict(allow, reason=""):
    return {"action": "allow" if allow else "block", "reason": reason}


def _runtime_gate_escalation(cmd):
    """Best-effort consult of the `simplicio` runtime's own risk classifier for an
    ADDITIONAL block signal — never a replacement for the checks above.

    Purely additive: this can only turn an otherwise-allowed command into a block, never
    the reverse. The hardcoded IRREVERSIBLE/secret checks remain the fail-closed floor
    regardless of this function's outcome. Any failure — binary absent, timeout,
    non-JSON output, unexpected shape — returns None (no additional signal), so a broken
    or missing runtime NEVER weakens or breaks the existing gate.

    Only escalates on `decision == "block"` (the runtime's hardline/denylist floor —
    catastrophic ops like pipe-to-shell or mkfs that this file's own IRREVERSIBLE list
    doesn't cover). A "confirm" decision is deliberately NOT treated as a block signal:
    under `--gate ask`/`auto` the runtime returns "confirm" for essentially every ordinary
    mutation (a plain `git push`, `rm -f`, `npm install`, ...) — a PreToolUse hook has no
    way to actually pause for human confirmation (only allow/block), so escalating on
    "confirm" would silently turn this into "block nearly all real work", not a genuine
    extra safety signal. Verified against the live binary before shipping this — see
    tests/test_action_gate.py for the exact commands checked.
    """
    if not cmd:
        return None
    binary = shutil.which("simplicio")
    if not binary:
        return None
    try:
        # cwd=os.getcwd(), not REPO: the gate must classify against the project the
        # command is about to run in (same reasoning as _staged_diff() above).
        result = _run(
            [binary, "gate", "classify", "--action", cmd, "--gate", "ask", "--json"],
            cwd=os.getcwd(),
            timeout=5,
        )
    except Exception:
        return None
    if result is None:
        return None
    try:
        payload = json.loads(result.stdout)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("decision") == "block":
        reason = payload.get("reason") or "simplicio runtime gate classified this as %s risk" % (
            payload.get("risk_class") or "elevated"
        )
        return reason
    return None


def gate_command(cmd, staged=False):
    """The core decision. Secret scans use the command's effective repository."""
    reason = classify_command(cmd)
    if reason:
        return _verdict(False, "irreversible op: " + reason)
    if staged or _is_commit_or_push(cmd):
        cwd = _effective_command_cwd(cmd)
        push = _is_push(cmd)
        diff = _push_diff(cwd) if push else _staged_diff(cwd)
        if diff is None:
            target = "push" if push else "staged"
            return _verdict(
                False,
                "cannot read %s diff to secret-scan (cwd=%s) - fail-closed" % (target, cwd),            )
        hits = scan_secret_text(diff)
        if hits:
            labels = ", ".join(sorted({h[0] for h in hits}))
            target = "push" if push else "staged"
            return _verdict(
                False,
                "secret in %s diff (%s; cwd=%s) - remove it before mutation" % (target, labels, cwd),            )
        delivery_reason = _delivery_guard(cwd, diff, push)
        if delivery_reason:
            return _verdict(False, delivery_reason)
    runtime_reason = _runtime_gate_escalation(cmd)
    if runtime_reason:
        return _verdict(False, "simplicio runtime gate: " + runtime_reason)
    return _verdict(True)


    # 3) additional signal from the simplicio runtime's own risk classifier, when installed
    #    (best-effort, additive-only — see _runtime_gate_escalation).
    runtime_reason = _runtime_gate_escalation(cmd)
    if runtime_reason:
        return _verdict(False, "simplicio runtime gate: " + runtime_reason)
    return _verdict(True)


# ---------------------------------------------------------------------------------------------
def _hbp_append_gate_blocked(reason, cmd=""):
    """Record a gate BLOCK into the runtime's HBP tamper-evident hash chain (#128) — fail-open,
    `simplicio`-only, mirrors `hooks/loop_stop.py`'s `_call_simplicio_hbp_append*` family. A
    blocked mutation is exactly the kind of decision that should be provable later (a later
    `simplicio hbp verify` can show this exact command/reason was recorded in order), not just
    printed to stderr and forgotten. Absent binary or any failure: silent no-op, never blocks
    the gate's own allow/block decision (that decision already happened before this is called).
    """
    binary = shutil.which("simplicio")
    if not binary:
        return
    try:
        import hashlib
        # minimal payload contract shared by the #128 topics: fingerprint + attempt id.
        fp = hashlib.sha1((reason or "").encode("utf-8", "replace")).hexdigest()[:12]
        attempt = None
        try:  # attempt id = live loop iteration from the scratchpad frontmatter, when armed
            with open(os.path.join(".simplicio/orchestrator", "loop", "scratchpad.md"),
                      encoding="utf-8") as f:
                m = re.search(r"^iteration:\s*(\d+)", f.read(), re.M)
            attempt = int(m.group(1)) if m else None
        except Exception:
            attempt = None
        payload = json.dumps({"fingerprint": fp, "attempt": attempt,
                              "reason": (reason or "")[:200], "command": (cmd or "")[:200]})
        subprocess.run(
            [binary, "hbp", "append",
             "--topic", "loop-gate-blocked",
             "--payload", payload,
             "--provenance", "simplicio-loop",
             "--json"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass


def _emit_and_exit(verdict, pretooluse=False, cmd=""):
    if verdict["action"] == "block":
        _hbp_append_gate_blocked(verdict.get("reason", ""), cmd)
        if pretooluse:
            # Claude PreToolUse: exit 2 blocks the call; reason on stderr is fed back to the model.
            sys.stderr.write("action_gate BLOCK — " + verdict["reason"] + "\n")
            sys.exit(2)
        print("block")
        print("  " + verdict["reason"])
        sys.exit(2)
    if not pretooluse:
        print("allow")
    sys.exit(0)


def cmd_check(opts):
    cmd = opts.get("command", "")
    _emit_and_exit(gate_command(cmd, staged=bool(opts.get("staged"))), cmd=cmd)


def cmd_pre_push(opts):
    """git pre-push: secret-scan the real push range AND require a green local gate (#291).

    This is the "obrigatório e impossível de contornar" (mandatory, impossible to bypass) local
    equivalent for a repo whose CI substrate (GitHub Actions) was removed in #311: with no
    Actions-enforced branch protection left, the git pre-push hook is the only mechanical choke
    point that runs on every push from every clone. Two checks, either one fail-closed:

      1. secret-scan of `_push_diff()` (the actual commits about to be pushed, not the staged
         diff — see `_push_diff` for why `--staged` was the wrong range for this hook);
      2. `python3 scripts/check.py --core-gate` (audit + mirror-parity + loop-contract +
         clean-env + token-budget + repo-budget + the core/mandatory test set, skipping only the
         satellite-only tests `--core-gate` already excludes — see `scripts/check.py`'s
         docstring and `docs/SCRIPTS_INVENTORY.md`). A repo without `scripts/check.py` (this
         hook copied into a project that doesn't ship it) skips step 2 rather than blocking a
         push it cannot verify against a script that doesn't exist.

    `--full` runs the complete gate (no `--core-gate`) instead, for a deliberate slower/thorough
    push (e.g. right before a release). Exit 2 on ANY failure — never partial-pass.
    """
    diff = _push_diff()
    if diff is None:
        print("block")
        print("  cannot read the push diff to secret-scan (fail-closed). Ensure this is a git "
              "repo with at least one commit.")
        _hbp_append_gate_blocked("cannot read push diff — fail-closed", "pre-push")
        sys.exit(2)
    hits = scan_secret_text(diff)
    if hits:
        labels = ", ".join(sorted({h[0] for h in hits}))
        print("block")
        print("  secret in pushed commits (%s) — remove it (or rewrite history) before pushing"
              % labels)
        _hbp_append_gate_blocked("secret in push diff (%s)" % labels, "pre-push")
        sys.exit(2)
    check_py = os.path.join(REPO, "scripts", "check.py")
    if os.path.exists(check_py):
        gate_args = [sys.executable, check_py] + ([] if opts.get("full") else ["--core-gate"])
        r = subprocess.run(gate_args, cwd=REPO)
        if r.returncode != 0:
            gate_name = "scripts/check.py" if opts.get("full") else "scripts/check.py --core-gate"
            print("block")
            print("  local gate failed (%s) — fix before pushing. Re-run it directly to see "
                  "the failures; there is no bypass flag by design (#291)." % gate_name)
            _hbp_append_gate_blocked("local gate failed (%s)" % gate_name, "pre-push")
            sys.exit(2)
    print("allow")
    sys.exit(0)


def cmd_scan_diff(opts):
    src = opts.get("diff")
    text = ""
    if src and src != "-":
        try:
            with open(src, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            print("block\n  cannot read diff file (fail-closed)")
            sys.exit(2)
    else:
        text = sys.stdin.read()
    hits = scan_secret_text(text)
    if hits:
        for label, n in hits:
            print("  secret: %s (line %d)" % (label, n))
        print("block")
        _hbp_append_gate_blocked("secret in diff (%s)" % ", ".join(sorted({h[0] for h in hits})),
                                  "scan-diff %s" % (src or "-"))
        sys.exit(2)
    print("allow")
    sys.exit(0)


def _hand_edit_forbidden():
    """Strict operator-only mode: host Write/Edit tools must not mutate the tree."""
    val = (os.environ.get("SIMPLICIO_LOOP_STRICT") or os.environ.get("SIMPLICIO_LOOP_FORBID_HAND_EDIT") or "").strip().lower()
    if val in {"1", "true", "yes", "on", "strict", "full-stack", "required"}:
        return True
    mode = (os.environ.get("SIMPLICIO_LOOP_MODE") or "").strip().lower()
    return mode in {"strict", "full-stack"}


def _runtime_binary_present():
    """Runtime is optional for the loop; probe only (no subprocess)."""
    try:
        return shutil.which("simplicio") is not None
    except Exception:
        return False


def _mcp_force_enabled():
    """MCP-first tool use when flag set AND Runtime binary is present.

    ``simplicio-runtime`` is **not** mandatory for simplicio-loop (core =
    mapper + dev-cli; Fast when operational). ``SIMPLICIO_REQUIRE_MCP`` only
    forces MCP tools when Runtime is available — never bricks a standalone loop.
    """
    val = (
        os.environ.get("SIMPLICIO_REQUIRE_MCP")
        or os.environ.get("SIMPLICIO_MCP_FORCE")
        or ""
    ).strip().lower()
    if val not in {"1", "true", "yes", "on", "required", "force"}:
        return False
    return _runtime_binary_present()


_HAND_EDIT_TOOLS = frozenset({
    "write", "edit", "strreplace", "search_replace", "applypatch", "apply_patch",
    "create_file", "delete_file", "notebookedit", "editnotebook",
})

# Host tools that dump repo context without Runtime MCP economy layer.
_MCP_BYPASS_READ_TOOLS = frozenset({
    "read", "read_file", "grep", "glob", "search_code", "list_dir", "listdir",
})

# Bash that floods context instead of simplicio_map / simplicio_search / simplicio_read.
_CONTEXT_FLOOD_RE = re.compile(
    r"(?i)(^|[;&|]\s*)(cat|type|Get-Content|rg\s|findstr\s|find\s+.+\s+-name)"
    r".+\.(py|ts|tsx|js|jsx|rs|go|java|md)\b"
)


def from_pretooluse():
    """Claude PreToolUse mode: gate Bash and, under strict mode, block hand-edit tools."""
    try:
        relevant = _project_relevant()
    except Exception:
        relevant = True  # safety gate: can't prove irrelevant → still run the gate (fail-closed)
    if not relevant:
        sys.exit(0)  # outside a simplicio-loop project → no-op (project-relevance gate)
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)  # not our JSON → don't interfere with non-Bash tools
    tool_name = str(data.get("tool_name") or data.get("name") or "").strip().lower()
    # Normalize names like "Write", "Edit", "mcp__...__Write"
    tool_tail = tool_name.rsplit("__", 1)[-1].rsplit(".", 1)[-1]
    # Allow MCP tools always (simplicio__*, mcp__simplicio__*)
    if "simplicio" in tool_name and ("mcp" in tool_name or tool_name.startswith("simplicio")):
        sys.exit(0)
    if _hand_edit_forbidden() and (tool_name in _HAND_EDIT_TOOLS or tool_tail in _HAND_EDIT_TOOLS):
        reason = (
            "SIMPLICIO_LOOP_STRICT forbids host hand-edit tools (%s); "
            "use simplicio-dev-cli / simplicio-py task / simplicio_edit (MCP) for mutations"
            % (tool_name or tool_tail or "edit")
        )
        _emit_and_exit(_verdict(False, reason), pretooluse=True, cmd=tool_name)
        return
    if _mcp_force_enabled() and (tool_name in _MCP_BYPASS_READ_TOOLS or tool_tail in _MCP_BYPASS_READ_TOOLS):
        reason = (
            "SIMPLICIO_REQUIRE_MCP (Runtime present) forbids host bulk-read tool %s; "
            "use simplicio_map / simplicio_search / simplicio_memory / simplicio_read (MCP). "
            "Without Runtime, host tools remain allowed (Runtime is optional for loop)."
            % (tool_name or tool_tail or "read")
        )
        _emit_and_exit(_verdict(False, reason), pretooluse=True, cmd=tool_name)
        return
    cmd = (data.get("tool_input", {}) or {}).get("command", "")
    if not cmd:
        sys.exit(0)
    if _mcp_force_enabled() and _CONTEXT_FLOOD_RE.search(cmd):
        if not re.search(r"(?i)\bsimplicio\b", cmd):
            reason = (
                "SIMPLICIO_REQUIRE_MCP (Runtime present) blocks context-flood shell (%s…); "
                "use simplicio_map / simplicio_search / simplicio_read MCP tools"
                % (cmd.strip()[:80],)
            )
            _emit_and_exit(_verdict(False, reason), pretooluse=True, cmd=cmd)
            return
    _emit_and_exit(gate_command(cmd), pretooluse=True, cmd=cmd)


def cmd_selftest(_opts):
    # Deterministic + hermetic: exercise the PURE functions only (classify_command /
    # scan_secret_text). The git-dependent path (staged-diff scan, fail-closed) is covered
    # hermetically in tests/test_action_gate.py with temp repos.
    checks = []

    def chk(name, got, want):
        ok = got == want
        checks.append(ok)
        print("  [%s] %-34s got=%s want=%s" % ("ok" if ok else "XX", name, got, want))

    def act(cmd):  # block if classified irreversible, else allow
        return "block" if classify_command(cmd) else "allow"

    # irreversible-op classification
    chk("force-push.block", act("git push --force origin main"), "block")
    chk("force-lease.block", act("git push --force-with-lease"), "block")
    chk("filter-branch.block", act("git filter-branch --tree-filter x HEAD"), "block")
    chk("rmrf-root.block", act("rm -rf /"), "block")
    chk("drop-db.block", act("psql -c 'DROP DATABASE prod'"), "block")
    chk("tf-destroy.block", act("terraform destroy -auto-approve"), "block")
    # benign commands are NOT classified as irreversible
    chk("status.allow", act("git status"), "allow")
    chk("normal-push.allow", act("git push -u origin feature"), "allow")
    chk("rm-file.allow", act("rm -f build/tmp.o"), "allow")
    chk("ls.allow", act("ls -la && grep -rn foo src/"), "allow")
    # secret-scan (text mode, placeholder-aware). Fixtures built so this source file stays clean.
    fake_aws = "AKIA" + "QRSTUVWX01234567"          # matches AKIA[0-9A-Z]{16}, no placeholder word
    chk("secret.detected", len(scan_secret_text('+k = "%s"' % fake_aws)) >= 1, True)
    chk("placeholder.ignored", scan_secret_text('+api_key = "your-api-key-here"'), [])
    chk("ghp.detected", len(scan_secret_text("+token=ghp_" + "z" * 36)) >= 1, True)
    chk("removed-line.ignored", scan_secret_text('-secret = "%s"' % fake_aws), [])
    # the allowlist pragma exempts an otherwise-matching line (auditable fixture exemption)
    chk("allowlist.exempts", scan_secret_text('+k = "%s"  # noqa: secret' % fake_aws), [])

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    sys.exit(0 if ok else 1)


def _parse(args):
    opts, i = {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            k = a[2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                opts[k] = args[i + 1]; i += 2
            else:
                opts[k] = True; i += 1
        else:
            i += 1
    return opts


SUBCOMMANDS = ("check", "scan-diff", "selftest", "pre-push")


def main():
    argv = sys.argv[1:]
    # No subcommand + piped JSON → Claude PreToolUse mode.
    if not argv or (argv and argv[0] not in SUBCOMMANDS and not sys.stdin.isatty()):
        from_pretooluse()
        return
    sub, opts = argv[0], _parse(argv[1:])
    {"check": cmd_check, "scan-diff": cmd_scan_diff, "selftest": cmd_selftest,
     "pre-push": cmd_pre_push}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: %s" % (sub, " ".join(SUBCOMMANDS))),
                         sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

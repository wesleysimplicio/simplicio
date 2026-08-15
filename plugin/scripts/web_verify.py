#!/usr/bin/env python3
"""simplicio-tasks — web_verify worker (front-end proof via Playwright).

The runnable form of the `web_verify` extension point documented in
`.claude/skills/simplicio-tasks/references/web-evidence.md`. Drives a real headless browser to
PROVE a front-end change renders, and captures a **screenshot + trace** as evidence. Evidence is
ALWAYS a file path + a boolean verdict — never DOM, pixels, or page HTML (token economy).

Three verbs:

  detect   Cheap FE-diff gate (terminal, no browser). Lists changed front-end files vs a base
           ref. Exit 0 + "skip" when none changed; exit 0 + "fe-changed" when the gate should
           fire. Pass --exit-code to instead exit 10 when FE changed (for CI `if:` gating).
  run      Drive headless Chromium to a URL, assert --expect text is present, write a
           screenshot + trace + console scan under the evidence dir, append a ledger row, and
           print the one-line MACHINE-tier verdict. Two runnable backends via --runner:
             npx     (default) `npx playwright test` — Fallback A in web-evidence.md
             pytest  `pytest` + playwright-python — Fallback B (Python repos)
           playwright-mcp is the richer path when a worker has the MCP server registered.
  verify   detect, then run only if the diff is front-end; otherwise record a SKIP ledger note.
           This is the gate the quality loop (Step 4b) calls.

CI artifact upload (the second half of issue #10):
  - GitHub Actions:  .github/workflows/web-verify.yml uploads `.simplicio/orchestrator/tee/web` via
    actions/upload-artifact (gated on a front-end path filter; manual run via workflow_dispatch).
  - locally / ad-hoc: `run --upload --pr <N>` runs `gh release upload` + `gh pr comment` with the
    artifact URLs (links, never bytes). See web-evidence.md "Attach to the PR".

Usage:
    python3 scripts/web_verify.py detect [--base origin/main] [--exit-code]
    python3 scripts/web_verify.py run --url http://localhost:3000/login \\
        --expect "Sign in" [--runner npx|pytest] [--out DIR] [--issue 10] [--upload --pr N]
    python3 scripts/web_verify.py verify --url URL --expect TEXT [--base REF] [--issue N]
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:  # Windows consoles default to cp1252 and choke on non-ASCII — force UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(REPO, ".simplicio/orchestrator", "tee", "web")
# same matcher as web-evidence.md "When it fires"
FE_RE = re.compile(r"\.(tsx|jsx|vue|svelte|css|scss|html)$|^(components|pages|app|public|src/ui)/", re.I)

if HERE not in sys.path:
    sys.path.insert(0, HERE)


def log(msg):
    print("  " + msg)


def _emit_progress(status, outcome=None, detail=""):
    """Fail-open progress-feedback hook (#301) — never raises, never blocks web_verify."""
    try:
        import loop_progress
        loop_progress.emit_event("evidence", status=status, outcome=outcome, detail=detail,
                                 source="web_verify.py")
    except Exception:
        pass


def _exe(name):
    """Resolve an executable on PATH (finds npx.cmd/git.cmd on Windows); fall back to the name."""
    return shutil.which(name) or name


def _run(argv, **kw):
    """Run a command WITHOUT a shell. Returns the CompletedProcess, or None if the exe is absent."""
    try:
        return subprocess.run([_exe(argv[0])] + argv[1:], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", **kw)
    except FileNotFoundError:
        return None


def fe_changed_files(base):
    """Front-end files changed vs `base` (terminal, not LLM). [] means SKIP the gate."""
    r = _run(["git", "-C", REPO, "diff", "--name-only", "%s...HEAD" % base])
    if r is None:
        log("! git not found on PATH")
        return []
    if r.returncode != 0:
        # base ref not found (shallow clone / detached) — fall back to last commit
        r = _run(["git", "-C", REPO, "diff", "--name-only", "HEAD~1...HEAD"])
    files = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    return [f for f in files if FE_RE.search(f)]


def cmd_detect(opts):
    base = opts.get("base", "origin/main")
    fe = fe_changed_files(base)
    if fe:
        print("fe-changed: %d file(s)" % len(fe))
        for f in fe[:20]:
            log(f)
        if opts.get("exit-code"):
            sys.exit(10)
    else:
        print("skip: no front-end files changed vs %s" % base)


# self-contained @playwright/test spec — no project config needed (Fallback A, npx)
NPX_SPEC = r"""
const {{ test, expect }} = require('@playwright/test');
test('web_verify', async ({{ page }}) => {{
  const errors = [];
  page.on('console', m => {{ if (m.type() === 'error') errors.push(m.text()); }});
  await page.goto({url!r}, {{ waitUntil: 'load', timeout: 30000 }});
  {expect_line}
  await page.screenshot({{ path: {shot!r}, fullPage: true }});
  require('fs').writeFileSync({errlog!r}, JSON.stringify(errors, null, 2));
  expect(errors, 'console errors: ' + JSON.stringify(errors)).toHaveLength(0);
}});
"""

# self-contained playwright-python test (Fallback B, pytest) — traces programmatically
PY_SPEC = r"""
import json
from playwright.sync_api import sync_playwright
def test_web_verify():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        ctx.tracing.start(screenshots=True, snapshots=True)
        page = ctx.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.goto({url!r}, wait_until='load', timeout=30000)
        {expect_line}
        page.screenshot(path={shot!r}, full_page=True)
        ctx.tracing.stop(path={trace_zip!r})
        browser.close()
    with open({errlog!r}, 'w') as f:
        json.dump(errors, f)
    assert not errors, 'console errors: %s' % errors
"""


def _append_ledger(out, line):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "ledger.txt"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _blocked(out, msg):
    _append_ledger(out, "web_verify: BLOCKED — " + msg)
    print("blocked")
    log(msg)
    _emit_progress("blocked", outcome="blocked", detail=msg[:400])
    sys.exit(3)


def cmd_run(opts):
    if "url" not in opts:
        print("run requires --url")
        sys.exit(2)
    url = opts["url"]
    _emit_progress("begin", detail="web_verify: %s" % url)
    expect = opts.get("expect", "")
    issue = str(opts.get("issue", "x"))
    out = opts.get("out", DEFAULT_OUT)
    runner = opts.get("runner", "npx")
    os.makedirs(out, exist_ok=True)
    shot = os.path.join(out, "%s-web.png" % issue)
    trace_dir = os.path.join(out, "trace-%s" % issue)
    trace_zip = os.path.join(out, "%s-trace.zip" % issue)
    errlog = os.path.join(out, "%s-console.json" % issue)

    if runner == "pytest":
        expect_line = ("page.get_by_text(%r).first.wait_for(timeout=15000)" % expect) if expect else "pass"
        spec = PY_SPEC.format(url=url, expect_line=expect_line, shot=shot,
                              trace_zip=trace_zip, errlog=errlog)
        spec_path = os.path.join(tempfile.gettempdir(), "test_web_verify.py")
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec)
        cmd = ["pytest", spec_path, "-q"]
        trace_ref = trace_zip
    else:  # npx (default)
        expect_line = ("await expect(page.getByText(%r, {exact: false}).first())"
                       ".toBeVisible({timeout: 15000});" % expect) if expect else ""
        spec = NPX_SPEC.format(url=url, expect_line=expect_line, shot=shot, errlog=errlog)
        spec_path = os.path.join(tempfile.gettempdir(), "web_verify_spec.spec.js")
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec)
        cmd = ["npx", "--yes", "playwright", "test", spec_path,
               "--trace", "on", "--output", trace_dir, "--reporter", "line"]
        trace_ref = trace_dir

    log("running (%s): %s" % (runner, " ".join(cmd)))
    r = _run(cmd, cwd=REPO)
    if r is None:
        _blocked(out, "%s not found on PATH — install the toolchain "
                      "(npx: Node.js; pytest: `pip install pytest-playwright && playwright install`)"
                      % cmd[0])
    stderr = (r.stderr or "").lower()
    if r.returncode != 0 and ("playwright" in stderr and ("not found" in stderr or "no module" in stderr)):
        _blocked(out, "Playwright not installed — run "
                      "`npx playwright install --with-deps chromium` (or `playwright install`)")
    ok = r.returncode == 0
    verdict = "web_verify: %s — %s (expect=%r, runner=%s) shot=%s trace=%s" % (
        "PASS" if ok else "FAIL", url, expect, runner, shot, trace_ref)
    _append_ledger(out, verdict)
    print("done" if ok else "fail")
    log(verdict)
    _emit_progress("end", outcome=("pass" if ok else "fail"),
                  detail="%s, screenshots em %s" % (verdict, out))
    if opts.get("upload") and opts.get("pr"):
        _upload(out, str(opts["pr"]), shot, trace_ref)
    sys.exit(0 if ok else 1)


def _upload(out, pr, shot, trace_ref):
    """Attach evidence to the PR as LINKS (web-evidence.md). Best-effort; logs the gh calls."""
    tag = "evidence-pr%s" % pr
    rel = _run(["gh", "release", "create", tag, "--notes", "web_verify evidence", shot], cwd=REPO)
    if rel is None:
        log("! gh not found — skipping upload (artifacts remain at %s)" % out)
        return
    if rel.returncode != 0:  # release may already exist — upload into it
        _run(["gh", "release", "upload", tag, shot, "--clobber"], cwd=REPO)
    body = ("web_verify ✅  screenshot + trace attached to release `%s` "
            "(open trace in trace.playwright.dev)" % tag)
    _run(["gh", "pr", "comment", pr, "--body", body], cwd=REPO)
    log("uploaded evidence -> release %s, commented on PR #%s" % (tag, pr))


def cmd_verify(opts):
    base = opts.get("base", "origin/main")
    out = opts.get("out", DEFAULT_OUT)
    fe = fe_changed_files(base)
    if not fe:
        _append_ledger(out, "web_verify: SKIP — no front-end files changed vs %s" % base)
        print("skip")
        log("no front-end diff — gate skipped (PASS by exemption)")
        return
    log("front-end diff detected (%d files) — running web_verify" % len(fe))
    cmd_run(opts)


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
    sub, opts = argv[0], _parse(argv[1:])
    {"detect": cmd_detect, "run": cmd_run, "verify": cmd_verify}.get(
        sub, lambda _o: (print("unknown command '%s'. choices: detect run verify" % sub),
                         sys.exit(2)))(opts)


if __name__ == "__main__":
    main()

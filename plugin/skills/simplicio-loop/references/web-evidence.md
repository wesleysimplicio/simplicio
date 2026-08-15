# Web evidence — `web_verify` via Playwright (front-end proof)

Concrete implementation of the `web_verify` extension point: drive a real browser to PROVE a
front-end change works, and capture a **screenshot + trace** as evidence. The north star from
Step 4b ("works, not just compiles") applied to UI: a front-end change that was never rendered is
PARTIAL, not done.

Credit: Microsoft Playwright (`playwright`, `playwright-mcp`, `playwright-python`). The agent-facing
path is **playwright-mcp** (structured accessibility snapshots, not pixels).

## When it fires (cheap gate — terminal, not LLM)
Run the front-end detector via the terminal:
```
git diff --name-only <base>...HEAD | rg -i "\.(tsx|jsx|vue|svelte|css|scss|html)$|^(components|pages|app|public|src/ui)/"
```
No front-end files changed → SKIP the whole gate. Front-end files changed → run `web_verify` as a
conditional sub-gate of `validate`/`smoke`.

## How to drive the browser
**Preferred — playwright-mcp** (the worker has the MCP server registered):
```json
{ "mcpServers": { "playwright": { "command": "npx",
  "args": ["@playwright/mcp@latest", "--headless", "--output-dir", ".simplicio/orchestrator/tee/web", "--save-trace"] } } }
```
Per acceptance check: `browser_navigate(url)` → act (`browser_click` / `browser_fill_form` /
`browser_type`) → `browser_snapshot` (assert text present — compact a11y tree, no vision needed) →
`browser_take_screenshot({filename:"<issue>-<step>.png", fullPage:true})` →
`browser_console_messages` + `browser_network_requests` for an error scan. Trace auto-written by
`--save-trace`.

**Fallback A — `npx playwright` (no MCP):**
```bash
npx playwright install --with-deps chromium
PWTEST_OUTPUT_DIR=.simplicio/orchestrator/tee/web npx playwright test --trace on --output .simplicio/orchestrator/tee/web
```

**Fallback B — playwright-python / pytest (Python repos, e.g. the Simplicio Agent repo, formerly hermes-agent):**
```bash
pip install playwright pytest-playwright && playwright install chromium
pytest --tracing retain-on-failure --output .simplicio/orchestrator/tee/web
```
or programmatic: `context.tracing.start(screenshots=True, snapshots=True)` … `page.screenshot(
path=".simplicio/orchestrator/tee/web/shot.png")` … `context.tracing.stop(path=".simplicio/orchestrator/tee/web/trace.zip")`.

## Capture into the evidence ledger
All artifacts write to `.simplicio/orchestrator/tee/web/` (screenshots `*.png`, `trace.zip`, optional
`console.log`/`network.json`). Append a ledger row recording **paths + a one-line verdict**:
```
web_verify: PASS — /login renders, 0 console errors; shot=.simplicio/orchestrator/tee/web/login.png trace=…/trace.zip
```
The ledger stores the path, never the bytes.

## Attach to the PR (link, don't paste)
```bash
# CI: prefer actions/upload-artifact; locally a release/gist works
gh release upload "evidence-<pr>" .simplicio/orchestrator/tee/web/login.png .simplicio/orchestrator/tee/web/trace.zip
gh pr comment <pr> --body "web_verify ✅  screenshot: <url>  trace: <url> (open in trace.playwright.dev)"
```

## Token economy (critical)
- NEVER paste DOM, screenshot bytes, or full page HTML into context. Evidence = **file path/URL +
  boolean verdict**.
- Prefer `browser_snapshot` (compact a11y text) over vision to assert state; the screenshot is for
  the human reviewer, not the model.
- Clamp `browser_console_messages` / `browser_network_requests` through the orient catalog (tee to
  file; feed back only count + first N error lines — same rtk-style clamp as build/test output).
- Run `--headless --isolated`, one browser context per check.

## Enforcement (simplicio-review rubric line)
At MEDIUM+, `simplicio-review` adds: "if the diff is front-end, REQUIRE a `web_verify` ledger entry
with screenshot+trace paths and 0 console errors, else FAIL." `web_verify` is the producer;
`simplicio-review` is the enforcer; `pr`/`evidence` attaches.

## Runnable worker (`scripts/web_verify.py`)
The prose above is the contract; `scripts/web_verify.py` is the runnable form. Two backends via
`--runner`: `npx` (default, Fallback A) and `pytest` (Fallback B, playwright-python);
playwright-mcp stays the richer path when a worker has the MCP server:
```bash
python3 scripts/web_verify.py detect --base origin/main [--exit-code]   # cheap FE-diff gate
python3 scripts/web_verify.py run    --url URL --expect "Sign in" --issue 10 [--runner npx|pytest] [--upload --pr N]
python3 scripts/web_verify.py verify --url URL --expect TEXT --base origin/main --issue 10
```
`verify` = detect + (run only if the diff is front-end, else a SKIP ledger note). It writes the
screenshot, trace, and console scan under `.simplicio/orchestrator/tee/web/`, appends the ledger row, and
prints the MACHINE-tier verdict (`done|fail|skip|blocked`); a missing toolchain yields BLOCKED,
never a fake pass. **CI artifact upload:** `.github/workflows/web-verify.yml` runs the worker on
front-end PRs and uploads `.simplicio/orchestrator/tee/web` via `actions/upload-artifact@v4`; locally pass
`--upload --pr <N>` to `gh release upload` the artifacts and `gh pr comment` the links.

## Scope (v1 — don't over-engineer)
Build: FE-diff detector · `web_verify` worker (playwright-mcp preferred, npx/pytest fallback) ·
ledger row schema · the review rubric line. Skip: vision/coordinate caps, video, visual-diff
baselines, multi-browser matrix. Single headless Chromium + screenshot + trace is sufficient proof.

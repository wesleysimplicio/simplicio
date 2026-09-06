# Desktop master task list — 2026-09-05

## Scope

Authoritative implementation repository: `wesleysimplicio/simplicio`, under
`apps/desktop`. Runtime remains in `wesleysimplicio/simplicio-runtime`.
Product reference: Orca macOS behavior and `stablyai/orca` source. Visual
references also include `/Users/wesleysimplicio/Desktop/prints_sistemas`.

## Implemented and locally verified

- [x] Full Simplicio application icon with the logo filling the asset; no added
  frame, inset card or decorative border.
- [x] First-run idle surface contains only the logo and **Install Now**.
- [x] Idle login surface contains only the logo and the Google action.
- [x] Google action uses the official four-color Google mark.
- [x] Login returns through the Desktop callback flow without the Desktop
  handling account credentials.
- [x] The first-run action installs and validates the packaged Runtime before
  login.
- [x] After installation, Desktop invokes Runtime-owned preparation for memory
  migrations, seeds, local service readiness and detected MCP client
  registration, and accepts only a bounded redacted receipt.
- [x] Live MCP initialization records are reconciled with process liveness, so
  active Codex sessions count as confirmed instead of treating registry files
  as handshakes.
- [x] Codex and Grok quota surfaces distinguish observed data, unavailable data
  and refresh-required states.
- [x] Native system-permission queries refresh while the permission screen is
  open and preserve the distinction between not requested, denied and granted.
- [x] Update availability, progress, recovery and relaunch state are surfaced
  without silently treating a source version as an installed update.
- [x] Usage totals do not render unavailable provider data as zero.
- [x] Selected (or sole) local project context savings are loaded from the Runtime-owned report and surfaced in Home and the status bar with net-savings guardrails, event count, evidence kind and confidence. Provider token usage remains unreported until real provider events exist.
- [x] Entry and setup surfaces use a restrained white/futuristic layout with progressive disclosure instead of explanatory walls of text.
- [x] Preparation progress names packaged dependencies, Python detection, memory/seeds/migrations and detected clients without claiming unavailable metrics.
- [x] Runtime exposes an idempotent 15-minute `session-service close-idle` transition; Desktop polls it once per minute after activation and keeps provider input/output/reasoning/cache refresh explicitly pending instead of inventing zeros. Running queued requests are excluded, and prompt enqueue/claim/completion refresh the session activity clock.
- [x] Idle-close receipts are persisted in Runtime SQLite with a deterministic finalization id, bounded payload and replay of the original evidence; transcript, tool, effect and attachment writes refresh the session activity clock without reviving duplicate records.
- [x] Runtime runs bounded, read-only provider refresh adapters for Claude Code, Codex CLI and OpenCode, plus generic JSON/JSONL probes constrained to known local roots for Grok, VS Code, Antigravity, Pi, Kiro, Cursor, Windsurf, Cline, Gemini, Hermes and Orca. Generic probes preserve unknown metrics and redacted provenance; providers with no local source remain unavailable and `other` stays explicitly unbound.
- [x] Provider refresh reports `unavailable` when all bound sources are absent, while preserving `pending_provider_refresh` for discovered or failed sources; no-source state is never presented as completed usage.

## Still requiring end-to-end acceptance

- [ ] Install a signed/notarized current artifact over the stale Applications
  copy and verify its macOS identity preserves Accessibility, Screen Recording,
  Camera and Microphone grants.
- [ ] Exercise the exact first-run **Install Now** effect on a clean macOS user
  and verify the Runtime preparation receipt against actual host writes.
- [ ] Verify Google OAuth from signed application launch through callback,
  persisted session, logout and relaunch.
- [ ] Verify update download, signature validation, relaunch and rollback with a
  real published update artifact.
- [ ] Confirm token input, output, reasoning and cache fields against real
  completed sessions for every supported host rather than inferred local data.
- [ ] Verify the 15-minute logical close against real provider sessions and
  complete the provider adapters/refresh receipt for Claude, Codex, OpenCode,
  Grok, VS Code, Antigravity, Pi, Kiro and other supported clients. The
  Runtime/Desktop lifecycle contract is implemented and tracked in
  `wesleysimplicio/simplicio#376`.
- [x] Completed screen-by-screen and button-by-button acceptance on the newest
  debug macOS build against the open Orca reference: accounts, usage history,
  updates, permissions, diagnostics, filters, exports and guided setup. The
  signed/notarized installed-copy identity check remains tracked in
  `wesleysimplicio/simplicio#375`.
- [x] Re-ran the frontend suite (63 files, 406 tests), full Playwright suite
  (117 passed) and a debug Tauri macOS build; the ad-hoc bundle was removed
  after visual review to reclaim disk. Repository-wide Python validation still
  has three unrelated pre-existing plugin/release failures.
- [ ] Publish, install or replace the Applications bundle only after explicit
  release authorization.

## Conversation request index

- **Orca parity and source reference:** compared the public Orca clone/source and
  recorded Usage, update/skills, accounts, telemetry, permissions and
  diagnostics; the newest debug macOS build was inspected live while Orca was
  open, with signed installed-copy identity still pending.
- **Repository scope:** all Desktop work is scoped to `/Users/wesleysimplicio/Projetos/ai/simplicio`; Runtime remains a separate backend repository. No second executable Desktop UI was found in `simplicio-runtime`; its `desktop/` directory is retained as backend-contract documentation only.
- **Full-bleed brand icon:** replaced the framed asset with a full-bleed Simplicio logo and propagated it to web/native icon assets.
- **Usage, MCPs and providers:** added liveness-backed MCP reconciliation plus observed/unavailable states for Codex, Grok and provider usage; bounded generic JSON/JSONL probes now cover the remaining named hosts without inventing metrics; real installed-app/provider acceptance remains open.
- **Token-savings reports:** project-scoped `savings report` now feeds Home and the status bar; gross/net context savings remain separate from provider token/cost telemetry, and missing provider events stay blocked rather than zero.
- **Permissions and updates:** added native permission refresh and honest update/recovery surfaces; signed/notarized artifact checks remain open.
- **Logout and 15-minute close:** logout is wired; Runtime logical close and Desktop polling are implemented, while real provider refresh/collection remains an acceptance item in `simplicio#376`.
- **Google login:** replaced the generic mark with the four-color Google mark and kept credentials in the browser callback flow; signed OAuth persistence still needs acceptance.
- **Runtime-first onboarding:** Install Now now installs/validates the packaged Runtime, then runs bounded Python/dependencies, memory, seeds, migrations and detected-client preparation before login.
- **Minimal clean UI:** idle entry/login expose only logo plus primary action; progress/error screens retain only actionable state and no explanatory wall of text.
- **Disk recovery:** removed only regenerable Desktop build outputs and
  dependency artifacts, preserved projects, profiles, memories and active
  runtimes, and measured 8.1 GiB available (68% capacity) after the final
  validation; filesystem cache can fluctuate.
- **Future repository rename:** no remote or package rename to `simpletibr/simplicio` was made; that remains a later release task.

## Evidence from this worktree

- Frontend suite: 63 files, 406 tests passed.
- Focused first-run/preparation/session-idle suite: 2 files, 14 tests passed.
- Native preparation tests: 6 passed; native MCP connection tests: 4 passed.
- Runtime Agent Plane focused idle-session tests: close-idle, pending prompt and activity-clock cases — 3 passed.
- Full Playwright suite: 117 passed with mocked IPC and preview/browser coverage.
- Debug macOS application: rebuilt after the context-savings patch for 3.8.47
  with one cargo job and stripped dev debuginfo; the local artifact was removed
  after visual review to recover disk space. This remains an ad-hoc build, not a
  signed release.
- Packaged icon extracted from the built application: 1024 × 1024, visually
  full-bleed; the borderless login regression now checks the shared asset and
  rendered image behavior.
- Native UI inspection of the newest debug build completed with macOS unlocked;
  the selected project displayed Runtime-proven context savings in Home and the
  status bar (`economia consultada`, event count, mixed/low-confidence evidence).
  Source/installed/release evidence remains separated and the ad-hoc bundle was
  removed after review.
- Provider token-usage ledger remained empty in this environment, so input,
  output, reasoning, cache and cost are still truthfully blocked rather than
  shown as zero.

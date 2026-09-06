## Pre-login bootstrap contract finding

The actual bundled Runtime 3.8.47 rejected `bootstrap plan --repo <isolated-home> --json` after the isolated user logged out: `login required`. Therefore the canonical bootstrap cannot simply be moved before Google login in Desktop. Source `bootstrap_transaction.rs` owns memory migrations/seeds; `bootstrap_profiles.rs` and `bootstrap_apply.rs` coordinate authenticated profiles. Follow-up inspection corrected the initial conclusion that a new pre-auth command was required: the public installer's existing `mcp register` route invokes `bootstrap_home_neural()` (migrations and seeds) and remains available before login. The packaged 3.8.47 `mcp register --dry-run --json` returned `simplicio.mcp-register-plan/v1` successfully in the signed-out isolated HOME. Evidence: `.simplicio/spill/1788659782-env-744c050315d2.log`. Do not relax the general bootstrap/product authorization gate. Integrate this existing route with explicit scope review and bounded receipts; dry-run does not prove apply, dependency readiness or database initialization.

## Expanded pre-login preparation requirement

The user now requires preparation before login to cover Python detection, dependency installation, memory setup, seeds and migrations, with actual step status visible, rather than the current core-binary-only installation. At the time of this capture, this remained unimplemented. The current source now provides the Runtime-backed redacted receipt and state gate described in Current preparation implementation follow-up below; clean-user native acceptance is still required.

The current public `install.sh` verifies and installs the signed Runtime, registers MCP/native hooks, reconciles the public hook overlay, and reports separate host-plugin consent. Python is used by verification helpers. It does not contain named seed/migration steps; inspect Runtime bootstrap entry points to establish their actual contracts before exposing them as performed by Desktop. Keep the current repository origin `wesleysimplicio/simplicio`; the requested future `simpletibr/simplicio` migration is not authorized for immediate execution.

The login button source now uses a four-color SVG instead of the generic letter G, with the site's rectangular outline/320px style. Four focused entry-screen tests pass. This visual change is not yet in a rebuilt native bundle.

## Native session persistence and logout

After both prior Desktop processes had exited, reopened only the isolated review HOME as process 47433. It reached the authenticated workspace without reinstalling Runtime or requesting another Google login. Used the Account screen's Sair da conta action; it returned to the welcome/entry screen. The installed Runtime SHA-256 remained `529ab8130222b93953485d5fe7c49cddfa29767c6a7db60cdd4f5db88a1ac053`. No logout was invoked against the normal user HOME.

Evidence: `.simplicio/spill/1788659438-orca-482aa7b62af6.log` (authenticated after restart), `.simplicio/spill/1788659465-orca-8d23819af4c0.log` (logout action), `.simplicio/spill/1788659491-orca-96dc34675dcd.log` (signed-out entry). This proves the local UI/account transition and installation preservation; remote revocation was not independently queried.

## Native Google login acceptance

The user completed Google authorization in the browser for the isolated review HOME. Review process 43039 transitioned from the waiting login screen into the authenticated application. The Account screen then showed the expected identity and an active annual entitlement; the expiration date remained explicitly unavailable. No identity email or device code is reproduced here.

The isolated inventory remained at zero detected registrations, as expected for the temporary home. This must not be reported as loss of integrations in the user's main installation. The new authentication serialization source change was unit-tested but is not part of this earlier review executable.

Evidence: `.simplicio/spill/1788659254-orca-d799d523e582.log` (authenticated application) and `.simplicio/spill/1788659289-orca-87fd66068007.log` (account state; contains private identity, do not publish raw).

Current complete local unit suites: 382 frontend tests passed across 60 files; 179 native library tests passed and 4 were explicitly ignored. The complete browser suite subsequently passed 117 tests in 2.6 minutes (`apps/desktop/.simplicio/spill/1788659361-env-c12a92f06517.log`). Browser IPC fixtures remain distinct from the native Google login evidence above.

## Native first-install acceptance

Launched the review bundle with an empty environment and a newly created HOME. The first `/tmp` spelling was rejected by the existing symlink-ancestor policy (macOS `/tmp` links to `/private/tmp`). Reopened with canonical `/private/tmp/simplicio-native-onboarding.XsNxd2`, used Consultar estado to reconcile the failed attempt, then explicitly pressed Tentar novamente.

The native install completed and transitioned to the welcome screen; Começar opened Entre no Simplicio with Continuar com Google. The managed binary exists only in the temporary home, mode 0700, and SHA-256 matches the packaged sidecar: `529ab8130222b93953485d5fe7c49cddfa29767c6a7db60cdd4f5db88a1ac053`. The install journal was located under that temporary home's Library/Application Support, confirming isolation from the user's normal app data. No OAuth request was initiated; authenticated login completion remains unverified.

Evidence: `.simplicio/spill/1788658805-orca-452022159c1d.log` (rejected path), `.simplicio/spill/1788658847-orca-84555b60a894.log` (reconciliation), `.simplicio/spill/1788658896-orca-66379de3cb64.log` (welcome after installation), `.simplicio/spill/1788658911-orca-70635390bb70.log` (login screen). This is local debug first-install evidence, not signed distribution or cross-platform acceptance.

## Isolated native bundle acceptance

Packaged the already-built executable with a separate `CARGO_TARGET_DIR=apps/desktop/src-tauri/target/native-review`, without replacing the existing debug bundle. Launched review process 23788 while preserving process 92939; all review interactions targeted the explicit PID.

- Startup reached the authenticated workspace with Runtime 3.8.47, without another login or install.
- The quota popover returned Codex 28 percent and Grok's refresh-required state. It displayed source/reset windows, not fixture values.
- Accounts > Consultar conexão Codex completed with quota confirmation, explicitly without claiming account identity. Add-account controls remain unavailable and are not accepted as complete.
- General > Verificar atualizações do Desktop reached the native updater and returned local-version-newer: published Desktop 3.8.39 versus local 3.8.47. No installer was downloaded and no downgrade was offered.
- Evidence: `.simplicio/spill/1788658556-orca-36a1be31d0a9.log`, `.simplicio/spill/1788658583-orca-f01db1a85471.log`, `.simplicio/spill/1788658611-orca-8d1e125ac028.log`.
- This does not prove fresh login, clean first-install, successful Grok billing, a granted permission, or update installation/rollback. No permission was changed in the review copy.

## Latest local verification

- Re-read both live applications: Simplicio process 92939 reports Codex 28 percent and accessibility not granted; Orca still shows its two outdated skills. No permission toggle or account change was performed.
- Onboarding now uses indeterminate progress while the native install receipt is pending. The copy-verification description matches the packaged-sidecar authority contract rather than claiming execution of the writable managed copy. Six entry-flow browser tests passed, with mocked IPC; native first-install acceptance remains outstanding.
- The complete debug executable compiled with `CARGO_INCREMENTAL=0 npx tauri build --debug --no-bundle`. The first attempt failed with disk exhaustion; after confirming no cargo/rustc processes remained, only this Desktop's regenerable `target/debug/incremental` cache was removed. The retry passed with 12 dead-code warnings. Receipt: `apps/desktop/.simplicio/spill/1788658472-env-289490e74077.log`.
- This is executable-build evidence, not installed-app acceptance. The running `.app` bundle was not replaced, preserving its identity for the pending permission check.

## Development

Follow-up to the user's screenshots: implemented native OS permission observations and Codex subscription quotas in the public Desktop, rather than another Runtime-ledger placeholder.

- Provider quota popover and footer indicator read Codex account/rateLimits/read through an owned app-server process. Initialize/initialized handshake, 15-second deadline, 256 KiB output ceiling, owned-child cleanup, 30-second cache, and explicit unavailable states. No thread/turn or credential import.
- macOS permission observations run in the Desktop process using AVCaptureDevice, CGPreflightScreenCaptureAccess and AXIsProcessTrusted, not the sidecar's permissions.
- Allowlisted settings actions open the specific macOS privacy pane. Microphone/camera can request permission only from an explicit button when not determined; Info.plist usage descriptions are included. No capture starts.
- Native request serialization, bounded callback wait, and no inferred success after cancellation or timeout.

## Validation

Live DEBUG Desktop (not a signed release) showed Codex 22 percent weekly usage, reset date and separate server quota groups. These values came from Codex app-server, not fixtures or copied Orca screenshots.
Live permission reads distinguished not-determined microphone/camera and not-granted screen/accessibility. The review action reached the actual Accessibility privacy pane in System Settings. No permission switch was operated by the agent.

The microphone/camera prompt implementation is compiled and covered by mocked UI response tests; a real grant/deny round trip is not yet claimed.

## Tests

- 378 frontend unit tests passed before the final media-request extension.
- Full Playwright suite: 116 passed for quota/read-only permission integration.
- Final focused permission/reference UI tests: 8 passed, including simulated camera denial.
- Native permission allowlist tests: 2 passed.
- Native quota projection/RPC lifecycle tests: 3 passed; deterministic test verifies no turn starts.
- Frontend build and git diff --check passed.
- Native DEBUG build including media-request commands succeeded; the bundled Info.plist includes both camera and microphone usage descriptions.

## Grok follow-up

Compared the running Orca again: Codex 22 percent, Grok Run to refresh, and two outdated skills. Implemented the Grok CLI billing reader from the reference contract, using the existing reqwest and chrono dependency families. The native reader accepts only xAI issuer sessions, uses a fixed HTTPS billing origin with redirects disabled, caps responses at 256 KiB, and never sends credentials to the renderer or starts a chat. Expired credentials require delegated refresh in Grok; missing usage remains unknown.

The explicit local native observation returned `refresh_in_grok`, consistent with the currently open Orca. This exercised the expired-session path, not a successful network billing response. Four focused Rust tests passed; the opt-in native observation passed separately. The updated browser interaction test passed with both provider fixtures and detailed/compact modes. TypeScript checking and whitespace checks passed. These changes have not replaced the running debug bundle while permission identity verification is pending.

## Guided installation contract follow-up

Read-only `host-plugins plan --all` produced identical plans from the managed and bundled Runtime 3.8.47. The real matrix contains Kilo and OpenCode, but both Desktop parsers still required Cursor and Kiro. Corrected the closed host set and the setup labels, with the captured non-sensitive plan as a shared native/frontend regression fixture. No installation was applied. The plan reports plugin version 0.2.11 and blocked Codex/OpenCode states; it is not proof that an installed plugin is outdated or that an update should be applied.

## Consolidated validation after follow-ups

- Frontend unit suite: 379 passed in 59 files.
- Native library suite: 178 passed, 4 explicitly ignored; the Grok local observation was executed separately.
- Frontend production build passed with a bundle-size warning.
- Shared permission observation now serves both Permissions and Computer Use. The focused interaction test verifies the externally changed accessibility state on both routes. Computer Use remains excluded by the existing navigation policy; its direct route is retained.
- The reopened, unchanged debug application reports Codex 24 percent and accessibility not granted for that executable. This does not override the user's grant to another same-named bundle.
- Desktop PNG/ICNS/ICO and web icon were regenerated with a larger, edge-cleaned brand mark, without an added frame. The running bundle has not been replaced.

## Account connection follow-up

The full browser suite passed all 116 tests after updating the host-plan fixture and retaining the high-resolution public icon. Added Grok to AI Provider Accounts and explicit read-only connection checks for Codex/Grok using the same bounded quota reader. Successful quota access is not presented as managed account identity. After this change, 73 focused unit tests and 8 focused browser tests passed; TypeScript checking passed. Actual account creation/login management remains incomplete.

## Item-by-item review

Still open: fresh-session Grok billing response and installed-app presentation, actual skill-version freshness/update nudge, provider account management, real permission prompt completion, signed installation and updater restart/rollback acceptance. The Runtime connection inventory is not a provider account login signal. Earlier generic Python validation failures have not been reclassified as fixed.

## Pre-login memory bootstrap: isolated packaged-binary evidence

The packaged 3.8.47 Runtime completed `mcp register --codex-only --json` while signed out in the isolated onboarding HOME. The test explicitly set `SIMPLICIO_SERVICE_AUTO_START=0` and restricted PATH to system directories. This is a scoped bootstrap test, not proof that the full Desktop onboarding or all host integrations are ready.

- Result: `simplicio.mcp-register-result/v1`, status passed, dry_run false.
- Service: disabled_by_config. Hermes: disabled. Codex CLI: not-installed.
- Only the isolated Codex configuration was written. The default user HOME was not used.
- Memory: 16 migration IDs, 815 memory items, 557 skills, quick_check ok.
- Independent SQLite inspection of the closed, checkpointed database (no WAL file present) confirmed quick_check ok and counts 16/815/557 using an immutable read. A normal readonly open initially failed because WAL reader setup required an unavailable write; this was not treated as corruption.
- Evidence: `.simplicio/spill/1788660096-env-e0e31df59832.log`. Do not publish personal paths from raw receipts.
- This demonstrates that Python is not required to execute the packaged native memory migration/seed stage; it does not establish readiness of Python-dependent optional integrations.
- The new native preparation preview and strict frontend parser remain previews only. No preparation apply command, persistent preparation readiness gate, or complete visual preparation flow is implemented yet.


## Google button native review after rebuild

- Full frontend suite: 392 tests passed across 61 files.
- Debug native build and separate review app bundle completed successfully; 12 unused-code warnings remain.
- Opened the rebuilt review bundle with isolated HOME, owned PID 69960. Navigated Welcome > Começar and visually inspected the native login screen: four-color Google mark, outlined rectangular button, and intact login/accessibility label.
- Evidence: `.simplicio/spill/1788660250-orca-44644c121cd0.log`; its screenshot was inspected. This turn did not initiate a new Google authentication.
- A different Simplicio instance (PID 48060) was already present. It was observed read-only and left untouched; it was not mistaken for the isolated acceptance process.
- The owned isolated review process was terminated after inspection. The user's installed/main application was not replaced.


## Subtle visual refresh: first entry pass

The user requested a cleaner, subtly futuristic Desktop with less explanatory copy. Applied a restrained Avenir Next typography stack, compact login hierarchy, a thin green accent, cleaner welcome copy, and progressive disclosure for privacy/access explanations. Google button branding remains unchanged. Error and waiting states remain explicit.

Rebuilt and inspected the separate native review bundle, isolated PID 74607: Welcome and Login rendered correctly at 1280x820. Screenshot evidence: `.simplicio/spill/1788660449-orca-fd7ec6f7b65d.log`. Privacy summary was present and closed in the native accessibility tree; clicking it was refused due to lost window focus, so native expansion is not claimed. The rendering regression covers its details/summary semantics.

Checks: full frontend suite 392 passed before adding the new disclosure test; the focused access suite subsequently passed all 5 tests. Native debug build succeeded with 12 existing unused-code warnings. Diff check passed after removing a trailing blank line. Owned review process terminated; other user instances left untouched.

Scope was the first entry pass, not a completed redesign of every Desktop screen. At that time, full environment preparation was not connected to onboarding; the current source now connects the bounded preparation receipt to Install Now. An attempted multi-file preparation-panel edit was rejected atomically before application; no panel files or bridge changes from that attempt were applied.


## Minimal entry and disk recovery

User-authorized cache cleanup removed npm cache and Chrome HTTP/code cache only; profiles, cookies, credentials, sessions and projects were preserved. Free space increased from approximately 120 MiB to 1.5 GiB, then 1.4 GiB during rebuilding. Earlier agent-owned staging executable and native build intermediates were also removed and later regenerated.

Setup welcome now contains the logo and Install Now. The native login contains only the logo and Google action when idle; pending and error states remain visible. All 393 unit tests passed. The reference setup Playwright test passed after adding assertions for one button, visible logo and no introductory headings, paragraphs, header or footer, followed by consent-controlled application checks. This uses mocked IPC and does not prove full pre-login installation.

Rebuilt the separate native-review app bundle and inspected isolated PID 99014. Native login accessibility and screenshot show exactly the Simplicio image and Continuar com Google. Evidence: .simplicio/spill/1788661092-orca-6ec5f790e33c.log. The isolated process was terminated after inspection. The main installed app has not been replaced.

Grok native CLI audit: mcp list reports Simplicio configured at ~/.local/bin/simplicio. That executable reports Runtime 3.8.46; the Desktop bundle contains 3.8.47. The governed grok mcp doctor simplicio --json attempt failed during initialize, with a child-process-group permission warning. This is scoped to the diagnostic execution context, not proof of failure in every interactive Grok session. Evidence: .simplicio/spill/1788661072-grok-f597c3378f93.log. No configuration was changed. Runtime snapshot reporting Grok unregistered conflicts with Grok's own configuration listing and still needs correction.

## Current preparation implementation follow-up

The earlier preview-only note above is superseded by the current source implementation: Desktop now invokes the managed Runtime's bounded `mcp register --binary <managed-path> --json` preparation after Install Now, before Google login. The native command projects only the redacted `simplicio.desktop-preparation-result/v1` contract and atomically persists a readiness receipt; the renderer fails closed when that receipt is absent or malformed. Runtime remains the authority for memory migrations, seeds, local service readiness and detected client registration. Browser tests cover the state machine and receipt parser; native preparation tests cover six receipt/projection cases. This still requires clean-user native acceptance against actual host writes and signed distribution.

Latest local verification: frontend unit suite 398 passed across 62 files, full Playwright suite 117 passed, native preparation tests 6 passed and native MCP connection tests 4 passed. The rebuilt frontend passed TypeScript/Vite production build; the existing chunk-size warning remains. A constrained native debug build also passed with one cargo job and stripped dev debuginfo; its executable was copied to `/tmp/Simplicio-latest.app`. The cargo target was cleaned afterward to recover disk space; no user project, profile or running app was removed.

## Live native audit after unlock — 2026-09-06

The Mac was unlocked and the newest public-repository debug bundle was built and opened at /Users/wesleysimplicio/Projetos/ai/simplicio/apps/desktop/src-tauri/target/debug/bundle/macos/Simplicio.app. The entry surface showed only the full-bleed Simplicio mark and **Install Now**; preparation then completed through the packaged Runtime and opened Runtime 3.8.47. The ad-hoc bundle was closed and removed after review.

With the authenticated snapshot loaded, the live UI reported 9 installed clients, 8 MCP registrations and 1 confirmed handshake. The Orca reference was open during the comparison: its Usage popover showed Codex weekly quota and Grok refresh-required behavior. Simplicio's Usage footer/popover matched the observed Codex quota, Codex account query confirmed quota without importing identity, and Grok returned an explicit expired-session message. MCP filters (all/installed/available/attention), provider detail expansion, refresh, guided-plan review, and receipt reconciliation were exercised without applying a new host-plugin plan.

The native audit also exercised account settings, general/update lookup (local 3.8.47 newer than installed 3.8.39; no downgrade), compact/comfortable appearance, token report period/projection/JSON/CSV exports, Activity filters/receipt export, permissions query/Finder reveal/System Settings review, Runtime refresh and redacted diagnostic export, quick-command copy, and setup details. No permission grant or user credential was changed. Export confirmations reached Downloads. Real signed OAuth/update/rollback and provider billing/session receipts remain release acceptance items; the installed Applications copy was not overwritten.

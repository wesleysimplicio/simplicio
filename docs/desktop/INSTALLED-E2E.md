# Installed Desktop E2E

The installed E2E route verifies the canonical user path:

`Welcome → Browser login → Runtime access gate → Guided setup → Workbench`

The main workbench checks project bookmarks, Activity, Agents/IDEs, MCP
integrations, token reports and categorized Settings. The legacy Today, Chats,
Teams, Automations and Apps projections remain tested for honest disabled states
but are not advertised as working primary destinations. Tests also cover
responsive widths, account transitions and downloads.
Native acceptance must run against the built Desktop/sidecar and a
Runtime fixture; a missing browser or missing Runtime is an environment failure,
not permission to turn the tests into a mock.

The preview and mocked-IPC tests in `apps/desktop/e2e` are separate UI contract
checks, not installed acceptance. Real acceptance also launches the freshly
built native executable against the verified Runtime and an isolated synthetic
ledger, verifies navigation and the read-only integration plan, and records
what was not exercised (fresh OAuth, live host handshakes, config writes and
other native platforms). Token export acceptance must click both JSON and CSV
in the native WebView, inspect the actual saved files and verify that navigation
still works afterward. A Chromium download test is not evidence that a macOS
WebView download works. Preserve pre-existing files in Downloads and clean up
only the synthetic exports owned by that test. Do not label a preview-only route
as installed E2E.

Guided setup acceptance checks welcome/back navigation, read-only plan creation,
explicit consent, duplicate-click protection, progress driven by operation
responses, partial-install failure and final-verification failure. Do not write
real host configuration merely to test its visual states. An active account
already signed in before launch opens the workbench; guided setup is also
reachable from Settings. Fresh successful login offers setup without running it
automatically. Inactive and unknown access must never enter installation.

Local-project acceptance validates an actual folder, opens it through the fixed
native handler, scopes the token query to that directory and removes only the
bookmark. Native diagnostic/activity exports must return an actual saved path
and preserve existing Downloads files, just like the token exports.

## #375 acceptance evidence path

The installed run writes one redacted report per native executor under the
ignored local path `reports/desktop-installed/<platform>-<run>.json`. Validate
that report with:

```bash
python3 scripts/verify_desktop_installed_acceptance.py \
  --evidence reports/desktop-installed/macos-arm64-<run>.json --json
```

The report schema is `simplicio.desktop-installed-acceptance/v1`. It must name
the installed app and bundled Runtime digest, use an isolated clean HOME, and
mark each of these checks as `verified` before the report can be `READY`:

`bundle_identity`, `runtime_snapshot`, `provider_quotas_contract`,
`provider_quotas_current`, `signed_update_download`, `signed_update_install`,
`signed_update_relaunch`, `signed_update_health`, `signed_update_rollback`,
`logout_relogin`, and `permissions`.

`provider_quotas_contract` records only the v2 schema, fixed source/scope,
redaction and status/window counts. `provider_quotas_current` separately
requires at least one fresh provider id; an honest unavailable session is not
converted into a current reading. The report contains no paths, credentials,
raw provider payloads or account identity.

The updater checks are separate lifecycle gates: a verified download is not an
installed update, a relaunch is not health confirmation, and a failed health
check must retain rollback evidence. A missing Desktop `.sig`, unavailable
native executor, unavailable Apple signing/notarization, or incompatible Rust
toolchain is recorded with `blocked`/`unexecuted` plus a reason code and keeps
the report blocked. Preview/Playwright evidence is rejected by the verifier.

For the current Linux workspace, do not create a synthetic macOS report. The
published v3.8.47 DMG has no matching `.sig`, Linux has no native signed
macOS-install evidence, and native Rust evidence is conditional on a
Tauri-compatible `rustc` (the earlier PR run was blocked by rustc 1.85.0);
these remain explicit blockers in the PR and release notes when applicable.

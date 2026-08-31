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

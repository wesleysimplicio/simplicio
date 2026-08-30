# Installed Desktop E2E

The installed E2E route verifies the canonical user path:

`Today → Chats → Teams → Automations → Apps`

It also checks the legacy contextual surfaces (Activity, Providers, Memory and
Settings), responsive widths, account transitions, downloads and honest disabled
states. Native acceptance must run against the built Desktop/sidecar and a
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

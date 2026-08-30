# Installed Desktop E2E

The installed E2E route verifies the canonical user path:

`Today → Chats → Teams → Automations → Apps`

It also checks the legacy contextual surfaces (Activity, Providers, Memory and
Settings), responsive widths, account transitions, downloads and honest disabled
states. The browser suite must run against the built Desktop/sidecar and a
Runtime fixture; a missing browser or missing Runtime is an environment failure,
not permission to turn the tests into a mock.

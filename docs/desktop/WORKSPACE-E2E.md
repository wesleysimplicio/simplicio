# Workspace conformance E2E

The installed suite covers the canonical route `Today → Chats → Teams →
Automations → Apps`, then checks disabled `+ New`/Search and unavailable
capability/session states. The existing contextual suites cover account access,
Providers, Activity, Memory, Settings, downloads, Bot Center and responsive
widths.

The suite must run against the packaged Desktop and a real installed Runtime
fixture. Missing Chrome, packaged artifacts or Runtime contracts are setup
failures; production mocks are not an acceptable substitute.

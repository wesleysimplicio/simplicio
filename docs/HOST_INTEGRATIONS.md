# Host integration registry

The public installer distributes one verified Simplicio Runtime. It does not
copy credentials, download arbitrary editor plugins, or maintain a second MCP
writer for every host. After the binary is staged and its release contract is
verified, the installer invokes:

```text
simplicio mcp register --binary <absolute-path> --json
```

The Runtime owns the transactional host edits and native hook decisions. The
launcher records the redacted result in
`<binary-directory>/simplicio-host-integrations.json`.

## Detection policy

Detection is non-invasive. It checks an exact executable name or a documented
application path and never starts a host session. A configuration file by
itself is not enough to mark a host as installed because stale files are common.
Unknown products have no automatic executable probe until their official
contract is verified; they are reported as `unsupported` instead of producing
a false positive.

The current Runtime-delegated entries are Claude Code, Cursor, OpenCode, VS
Code, Kiro, Pi, and oh-my-pi. Orca is reported through the documented portable
CLI path. DeepSeek Harness, Antigravity, Command Code, and the remaining
compatibility-matrix entries remain explicit `unsupported`/`unverified` until
their canonical upstream contract is confirmed.

Claude Code is detected only through the exact `claude` executable. Its
supported configuration locations are `~/.claude/settings.json` and
`~/.claude/.mcp.json`; the public installer does not copy Codex-only hooks into
those files. Verification is the Runtime registration receipt produced by
`simplicio mcp register --binary <absolute-path> --json`, and the Runtime is
responsible for the atomic merge and rollback of the host configuration.

Cursor is detected only through the exact `cursor` executable. The registry
declares both user (`~/.cursor/mcp.json`) and workspace (`.cursor/mcp.json`)
scopes, with user scope as the default. The Runtime receives the selected
scope and must preserve every unrelated provider, rule, extension, and MCP
entry when reconciling the managed server.

DeepSeek Harness is intentionally fail-closed. No executable name or
verification command is registered until the official harness plugin/MCP
contract is confirmed. It therefore appears as `unsupported`/`unverified`
instead of treating a similarly named binary or arbitrary configuration file
as proof of compatibility.

OpenCode uses the exact `opencode` executable probe and its documented user or
workspace configuration locations (`~/.config/opencode/opencode.json` and
`opencode.json`). Registration and verification remain delegated to the
Runtime; the installer does not parse or rewrite OpenCode configuration.

Visual Studio Code is probed through the exact `code` or `code-insiders`
executable. Its registry entry declares user (`~/.vscode/mcp.json`), workspace
(`.vscode/mcp.json`), and remote scopes, with user scope as the default. The
Runtime owns the JSON merge and returns the verification receipt.

## Opt-out and scope

Skip every host with a comma-separated list or one host with an environment
variable:

```text
SIMPLICIO_SKIP_HOSTS=cursor,kiro
SIMPLICIO_SKIP_CURSOR=1
```

These controls affect detection/registration reporting only; they never remove
existing user configuration. Re-running the installer is safe and delegates
idempotent reconciliation to the Runtime.

## Receipt shape

The receipt uses `simplicio.host-integration/v1` and contains the Runtime
registration status, one row for every matrix entry, exact detected evidence,
the capability (`runtime-mcp`, `portable-cli`, or `unsupported`), a
minimum-version field, a verification command (when known), and the primary
documentation URL. It contains no tokens or provider credentials and is
written atomically with mode `0600`.

The receipt is evidence of what the installer observed; a host is marked
`registered` only when the Runtime JSON result names it as registered. File
presence alone is never promoted to a successful integration.

# Desktop authentication contract

The Google button invokes the native `desktop_login` IPC command. Before any
account effect, the Desktop runs `desktop status --json` on a Runtime candidate
and requires `simplicio.desktop.app/v1`, action `status`, and
`authentication: {schema: "simplicio.desktop-auth-capabilities/v1", authentication_only: true}`.
Only that same candidate may then run `login google --authentication-only --json`.

This is a Runtime-owned device authorization flow: it opens the system browser
and polls for authorization, with PKCE/state at the Runtime/service boundary.
It is not embedded Google login. Tokens never enter a URL or React state.
`src/auth.ts` contains a separately tested callback utility, but is not wired
into this production exchange.

## Capability and effect boundary

Only an unstarted read-only capability probe permits another Runtime candidate.
A legacy/malformed response stops before login; a started probe failure, login
failure or ambiguous result never retries another binary. Capability and final
receipt parsing are bounded to 64 KiB and do not reflect raw output to the UI.
The last non-empty JSONL event must be `simplicio.auth-login/v1`, status
`authenticated`, with bootstrap `skipped` and reason `authentication_only`.
The fresh authoritative snapshot still determines account access.

Runtime 3.8.39 does not support this contract and is refused before Google login.
A new release must bundle the verified compatible Runtime and recheck its
identity and capability after packaging; a source merge alone is insufficient.
In the compatible Runtime, the authentication-only flag skips bootstrap for both
new and existing sessions. Normal CLI login retains its Full/Mapper behavior.
No provider failure or fake inactive entitlement is used to suppress bootstrap.

## Account states and recovery

1. Startup requests the Runtime's versioned Desktop snapshot. Canonical
   `signed_out` presents the welcome/Google screens.
2. Explicit login starts one account action; native capture bounds it to three
   minutes. React does not independently time out or repeat the operation.
3. Only a fresh `active` snapshot opens guided setup. If the initial result is
   `unknown`, successful read-only **Tentar novamente** verification resumes
   setup without another OAuth attempt.
4. A login/logout error can happen after its effect but during the next snapshot.
   The UI therefore invalidates stale account state and uses the `unknown` gate.
   Refresh does not repeat login, logout or installation.
5. `inactive` and `unknown` never grant access; provider/network errors are not
   interpreted as an inactive subscription.

Logout remains available in account settings and the recovery gate. It invokes
`logout --json`, then queries a fresh snapshot. The Runtime removes local login
and attempts remote revocation; `remote_revoke: unverified` is not confirmed
server revocation. Project files and saved project shortcuts are preserved.

Installation remains a separate reviewed-plan and explicit-consent action.
Authentication-only does not install a CLI, MCP registration, hook or plugin.

## Verification boundaries

Native protocol tests use injected subprocess responses, while Playwright tests
use mocked Tauri IPC. They prove argument selection, no unsafe fallback, account
state recovery and consent boundaries; they are not a fresh Google grant,
remote revocation, global installation or live client handshake.

`SIMPLICIO_AUTH_FILE` isolates a QA login file, not every Runtime/bootstrap path.
Do not treat that variable or `SIMPLICIO_HOME` alone as a host-isolation sandbox.

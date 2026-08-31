# Desktop authentication contract

The Google button invokes the native `desktop_login` IPC command, which runs
`simplicio login google --json`. In the currently bundled Runtime this is a
Runtime-owned device authorization flow: it opens the system browser and polls
for the authorization result, using PKCE/state at the Runtime/service boundary.
It is not an embedded Google login or a React deep-link callback flow.

The Desktop never receives access or refresh tokens in a URL or React state.
`src/auth.ts` contains a separately tested PKCE/callback utility, but it is not
wired into the production login path and is not evidence that the Desktop itself
performs the callback exchange.

## Account states and recovery

1. Startup requests the Runtime's versioned Desktop snapshot. A canonical
   `signed_out` state presents the welcome/Google entry screens.
2. Explicit login starts one account action. The native process is bounded to
   three minutes; React does not time it out independently or retry it.
3. Only a fresh authoritative `active` snapshot opens guided installation.
   If the first result is `unknown`, a later successful **Tentar novamente**
   verification resumes that installation screen without another OAuth attempt.
4. An error from login or logout may occur after the account action completed,
   during its following snapshot query. The UI therefore switches to the
   `unknown` gate rather than reusing a stale signed-out/active snapshot.
   Refresh is read-only; it does not repeat login, logout or installation.
5. `inactive` and `unknown` never grant access. A provider/network failure is
   not interpreted as an inactive subscription.

Logout is available in account settings and the access-recovery gate. It invokes
`logout --json`, then requests a new snapshot. The Runtime removes its local
login file and **attempts** remote revocation; its `remote_revoke` result can be
`unverified`, so local logout must not be described as confirmed server-side
revocation. Project files and saved project shortcuts are not deleted.

## Native compatibility and consent boundary

The bundled Runtime source at release commit
`d91aa04b39ab33c252c628fab6806bf8ea2c39a8` calls
`bootstrap_apply::after_authentication` after a successful login. That path
defaults to the recommended CLI profile and can install the CLI and persist
bootstrap state before the Desktop's separate integration-plan consent screen.
It does not honor `SIMPLICIO_DESKTOP_BRIDGE` as a bootstrap opt-out.

Consequently, mocked Desktop tests proving that the UI never calls
`desktop_repair_providers` without consent do **not** prove that this Runtime
login has no bootstrap effects. A Runtime-supported authentication-only mode
and a verified compatible bundle are required before making that stronger
claim. Do not fake an inactive entitlement to suppress bootstrap.

`SIMPLICIO_AUTH_FILE` isolates the Runtime login file for QA, but
`SIMPLICIO_HOME` does not isolate all bootstrap paths in this Runtime release.
Do not conduct a supposedly isolated live login with only those settings.

## Verification boundaries

The account-effect Playwright tests exercise real UI transitions with mocked
Tauri IPC, including OAuth/snapshot failure, later verification, and logout
recovery. They are not a fresh Google grant, live remote revocation or global
installation test. Native signed-out projection is checked independently with
an absent isolated login file; no real user session is revoked by that check.

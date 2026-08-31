# Workbench / entry / guided setup QA — 2026-08-30

Status: implementation and local build verified; native installation acceptance
is **incomplete**. This is a human-readable work log, not a release receipt.
The initial observations below are historical; the 2026-08-31 follow-up records
the subsequent fixes and their separate validation evidence.

Source: `fix/desktop-orca-workbench`, based on public `master`
`9d65cddb3f5a1c0de77dbef04fd9803136bfd598`. The changes were not published or
merged as part of this verification.

## Implemented

- White workbench with project bookmarks, searchable sidebar, real navigation
  history, categorized settings and canonical Runtime/client status.
- Existing-folder validation/opening through fixed native commands; removing a
  project deletes only its local bookmark. Project token queries use its path.
- Two-screen welcome/login sequence; authentication and entitlement remain
  Runtime-owned. Unknown entitlement never becomes inactive or active locally.
- Guided setup: verify Runtime/access, review a read-only plan, confirm the
  reviewed digest, apply, then verify a fresh snapshot. No simulated timers or
  download progress. Failure does not trigger an automatic retry.
- Native diagnostic/activity exports to Downloads with allowlisted fields and
  exclusive file creation; existing files are preserved.

The supplied private screenshot references were organized outside Git. The Orca
source links consulted for interaction patterns are recorded in `DESIGN.md`.

## Completed checks

From `apps/desktop`:

```text
npm run build
  PASS — TypeScript application/config and Vite production build
npm test -- --reporter=dot
  PASS — 84 tests / 36 files
SIMPLICIO_DESKTOP_TEST_PORT=1438 npm run test:e2e -- --workers=1
  PASS — 21 tests
```

The E2E suite includes preview navigation/layout, two-step entry, conservative
access gates, reviewed installation and error states, operation locks, project
bookmarks, filtered token queries and native-export IPC contracts. Native calls
in these browser tests are mocked, not live installation evidence.

From `apps/desktop/src-tauri`, using the existing shared Cargo target directory
and `CARGO_BUILD_JOBS=2`:

```text
cargo test --release --offline --locked
  PASS — 25 tests; 1 ignored
```

Repository checks:

```text
python3 -m pytest -q tests/test_public_contract.py tests/test_repository_policy.py
  PASS — 5 tests
python3 scripts/repository_policy.py
  PASS — tracked source tree
git diff --check
  PASS
```

Visual inspection covered the white workbench, Google sign-in card, guided
setup welcome and in-progress checklist. Responsive browser checks covered
390px, 768px and 1280px widths. System dark mode did not change the white canvas.

## Native macOS QA build

A separate `Simplicio Workbench QA.app` was built manually with identifier
`br.com.simpleti.simplicio.workbenchqa`; it did not replace the production app.
The app is under the existing Cargo cache's `release/bundle/macos` directory.

The bundled Runtime's SHA-256 before and after app packaging/sealing was:

```text
c6dca7c384aaedb0226f6ea93a0dbe259a175f999c070e6c8ef609af519e5130
```

`codesign --verify --deep --strict` passed for the QA app. Its signature is
ad-hoc, **not** Developer ID signing or Apple notarization. No release assets,
installer packages or GitHub Actions were published or dispatched.

The native app opened and rendered the real Runtime-backed guided setup.
During interactive use, the application reached the configuration step but
reported that installation was not confirmed (2 of 4 stages complete). The
UI correctly retained failure instead of presenting successful installation.
Subsequent native screens showed client inventory and the truthful unavailable
ledger state. These observations do not certify every native control.

## Unresolved / do not treat as passed

- The exact cause of the native configuration failure has not been reproduced
  in a deterministic, isolated test. Do not repeat global installation while
  its effects are uncertain.
- After that observation, command execution through the Simplicio MCP failed
  or timed out. `simplicio_exec` and `simplicio_validate` reported
  `timed out awaiting tools/call after 300s`; a read-only test command also timed
  out. In-process file reads and health metadata remained responsive. This is
  not proof of a causal relationship with the installer failure.
- Native shell fallback was refused by the existing PreToolUse hook. The hook
  was not disabled or bypassed.
- The Orca computer-use executable was absent at the existing CLI symlink
  target. The alternate Computer Use interface could read the QA window, but
  automated click validation was not completed.
- Native configuration errors currently collapse the child-process details to
  a generic message. A follow-up should preserve a bounded, non-secret exit
  code/reason before retesting, without exposing raw process output.
- Fresh OAuth, complete host configuration writes, current MCP handshakes,
  native token-file exports, Windows and Linux packages remain unverified for
  this workbench change.

## Follow-up — 2026-08-31

The authenticated Simplicio MCP command lane was restored and used for local
tests. Earlier command timeouts above are not the current authentication state.

Additional implementation:

- The product and native menu use **Simplicio**. **Check for Updates...** opens a
  bounded, read-only check for a compatible Desktop installer in official public
  GitHub releases. Runtime-only releases do not become Desktop update offers.
  Opening the fixed releases page has a separate timeout and ignores late
  responses; it neither installs nor verifies a downloaded installer.
- Initial/refresh snapshot reads share one in-flight request and report a
  30-second timeout. The pending native operation is not killed or duplicated;
  late responses cannot overwrite the timed-out result. Login, logout and
  installation are deliberately outside this read-only deadline.
- Unknown/inactive access states offer account recovery through logout. Project
  navigation history preserves the selected project and token-report scope.
- Installation failures expose only bounded, allowlisted reasons/exit codes,
  never raw process output. Once a Runtime process starts, output-collection
  failure cannot trigger a fallback that repeats its effects.
- Guided setup separates a confirmed apply from a fresh target verification.
  Reviewed targets that existed or needed changes must remain unambiguous, exist, and have no pending
  changes in the new plan before the UI declares completion. A client handshake
  is still a separate fact. Static preview plans cannot fabricate completion.
- Diagnostic exports copy only the known boolean redaction flags, never extra
  nested metadata. Adding and opening a project use the same post-resolution
  path validation, including rejection of UNC/device targets and control text.

Fresh local checks on the follow-up source:

```text
npm run build
  PASS — TypeScript application/config and Vite production build
npm test
  PASS — 153 tests / 39 files
SIMPLICIO_DESKTOP_TEST_PORT=1438 npm run test:e2e -- --workers=1
  PASS — 43 tests (browser preview and mocked native IPC)
cargo test --release --offline --locked
  PASS — 41 tests; 1 ignored
simplicio_validate (compileall and complete Python suite)
  PASS — 260 tests; 39 subtests
bash tests/test_codex_hooks.sh
  PASS — 12 checks
```

The snapshot-deadline regression was observed failing before the implementation
and passing afterward. A separate read-only review found no concrete defect in
the shared snapshot-request lifecycle. These checks are source/test evidence,
not proof of a fresh OAuth flow, completed global installation, native menu
interaction or current client handshakes.

The original native configuration failure still requires isolated native
acceptance with the new redacted reason. No Windows/Linux installer, notarized
macOS installer, new release or release-asset replacement is established by this
work log. Delivery remains manual; no GitHub Actions are required.
Native child-output collection still has no execution deadline or streaming
byte limit; the 30-second UI read deadline does not cancel that process or
release an installation lock. This pre-existing limitation is not marked fixed.

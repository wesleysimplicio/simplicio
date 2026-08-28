# Desktop product states and screens

## State machine

```text
launch
  -> signed_out -> system-browser login -> checking
  -> checking -> active -> bootstrap -> home
  -> checking -> inactive -> locked home + subscribe
  -> checking -> unknown -> locked home + retry/diagnostics
```

Closing or reopening the app must not change access truth. A valid identity may
remain signed in while the product is locked. Only the Runtime can move the app
from `checking` to an entitlement outcome.

## Screen inventory

1. **Welcome / login** — one primary Google action, security explanation and no
   credential entry inside the app.
2. **Preparing Simplicio** — component-lock progress, signed artifact checks,
   provider discovery and rollback-safe errors.
3. **Access required** — confirmed inactive state, pricing/billing action and a
   recheck action; Runtime execution remains disabled.
4. **Access unavailable** — unknown state with retry and diagnostics; never
   rendered as non-payment.
5. **Home** — verified savings, cache hit, deterministic runs, Runtime health,
   provider summary and recent receipts.
6. **Providers** — detected-first cards, explicit status semantics, account-safe
   details and governed repair actions.
7. **Activity / reports** — searchable receipts and exportable savings evidence.
8. **Memory / skills** — bounded metadata and freshness, with content shown only
   after explicit access.
9. **Settings / diagnostics / updates** — account, language, launch behavior,
   signed update, support bundle and uninstall.

## Visual direction

The Desktop uses a compact native-app treatment rather than a marketing
dashboard: a pale butter canvas, warm ivory surfaces, soft borders, restrained
shadows, friendly rounded controls and small provider icons. Green is reserved
for confirmed state and primary actions; amber signals recoverable attention.
Copy stays short enough to scan like a desktop utility, not a web landing page.

Provider clarity is inspired by Orca's detected-first onboarding, while the
warm, low-noise density takes cues from OpenCode's light desktop surfaces:
installed or connected hosts appear first, status is visible on every row, and
users get one specific next action. Simplicio does not copy either product's
branding, worktree IDE, terminal or permission controls.

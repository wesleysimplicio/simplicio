# Desktop design system and accessibility baseline

The Desktop uses a small, light-native visual system: white canvas, sidebar and
surfaces, near-black text, soft green for healthy/action states, and amber only
for attention. CSS custom properties in `src/styles.css` are the source of
truth for spacing, radius, focus, motion, and target-size tokens. The final
light-workbench color and layout overrides live in `src/workbench.css`.

The native window also starts with a white background and the light theme, so
startup, login and workspace surfaces remain consistent when the operating
system prefers dark mode. Neutral secondary surfaces use a light gray; color
accents communicate status and actions rather than tinting the application
background. Browser theme tests do not certify an installed platform package.

The initial locale is `pt-BR`. `src/i18n.ts` contains UI copy keys only;
Runtime strings and provider IDs remain data and are never used as translation
keys.

The baseline includes visible keyboard focus, `aria-current` navigation,
pressed filter controls, labeled regions, 44px primary controls, responsive
collapsible sidebar navigation, a reduced-motion media query, and a forced-colors
fallback. Screens keep loading, empty, offline, recoverable-error, and
updating states short and actionable. Review screenshots at narrow and wide
window sizes before shipping a visual change.

Motion uses named durations: instant 80–120ms, fast 140–180ms, standard
180–240ms, deliberate 260–360ms, and ambient 2.4–4s. Motion never delays an
action, and reduced-motion removes decorative movement while preserving state
changes and focus visibility.

## Workbench and onboarding

The workbench follows the supplied Orca references: project shortcuts and search
on the left, a restrained native toolbar, a central welcome surface, categorized
settings, searchable client rows and a compact evidence-based status bar. It
keeps Simplicio branding and white surfaces; native window controls are provided
by the OS, not painted as inert buttons. Only implemented destinations appear in
primary navigation. Agent API previews remain explicitly unavailable when the
Runtime has not exposed the required capability.

Local projects are bookmarks, not agent worktrees. Native code validates and
canonicalizes existing directories; opening a bookmark revalidates the path.
Removal only removes the bookmark. Density, sidebar path visibility and the last
project are local preferences, never authentication or execution authority.
The native folder picker fills a canonical path for review; choosing a directory
does not add the bookmark automatically. A complete path can still be entered
manually, and confirmation revalidates it. Canceling the picker preserves the
typed path and returns focus without reporting an error. Browser preview cannot
open or validate local directories.

Below 760px, expanded navigation overlays the workspace instead of squeezing it.
Its search, scrollable destinations and fixed controls remain available; Escape,
outside dismissal, keyboard focus containment and focus restoration are explicit.
Settings destinations use `src/reference_screens.ts`, with grouped navigation and
search across labels and descriptions. The status bar separates detected
registrations from current, confirmed MCP handshakes; lack of a confirmed
handshake is not proof of disconnection.

Entry uses the supplied Claude references for a focused two-screen sequence:
welcome, then a sign-in card. Only the supported browser-based Google login is
offered. Password and email-code forms are not invented. Unknown entitlement
remains unknown; neither login nor onboarding can authorize access locally.

The guided installer follows the supplied Hermes references with real stages:
Runtime/access check, read-only plan, confirmed installation, and final state
verification. Progress advances only after each operation returns, with no
simulated download percentage or duration. Applying requires explicit consent to
the current digest. The progress header and action footer stay visible while
destinations and details scroll; reviewing destinations never checks consent.
Failed operations show their stage and preserve uncertainty about partial
changes. Only a changed plan or a process confirmed not started permits a new
review and consent. Uncertain outcomes block reapplication in the current
session; a confirmed receipt followed by failed verification offers a read-only
diagnostic refresh, not reinstallation. Navigating away and back does not remove
that guard, and restarting is not evidence of reconciliation. Navigation is
locked during an operation that the backend cannot safely cancel. Completion
confirms configuration, not a live MCP handshake in every client. Marketplace
plugins and host permissions are not represented as automatically installed.

Reference screenshots stay outside the public repository. Browser preview and
mocked-IPC screenshots demonstrate layout and UI contracts, not native install,
OAuth, subscription, or platform acceptance.

The public Orca source was also consulted for behavioral reference:
[Landing](https://github.com/stablyai/orca/blob/main/src/renderer/src/components/Landing.tsx),
[AgentCatalogRow](https://github.com/stablyai/orca/blob/main/src/renderer/src/components/settings/AgentCatalogRow.tsx),
[TitlebarLeftControls](https://github.com/stablyai/orca/blob/main/src/renderer/src/app-shell/TitlebarLeftControls.tsx)
and [setup failure feedback](https://github.com/stablyai/orca/blob/main/src/renderer/src/components/settings/AgentSkillSetupFailureNotice.tsx).
These confirm the centered entry actions, expandable client rows, real
navigation history and actionable setup errors. Simplicio retains its own
implementation, assets and Runtime authority; no Orca source or assets were
vendored into this change.

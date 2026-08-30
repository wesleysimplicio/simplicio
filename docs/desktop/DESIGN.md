# Desktop design system and accessibility baseline

The Desktop uses a small, light-native visual system: butter canvas, ivory
surfaces, near-black text, soft green for healthy/action states, and amber only
for attention. CSS custom properties in `src/styles.css` are the source of
truth for color, spacing, radius, focus, motion, and target-size tokens.

The initial locale is `pt-BR`. `src/i18n.ts` contains UI copy keys only;
Runtime strings and provider IDs remain data and are never used as translation
keys.

The baseline includes visible keyboard focus, `aria-current` navigation,
pressed filter controls, labeled regions, 44px primary controls, responsive
sidebar-to-bottom navigation, a reduced-motion media query, and a forced-colors
fallback. Screens keep loading, empty, offline, recoverable-error, and
updating states short and actionable. Review screenshots at narrow and wide
window sizes before shipping a visual change.

Motion uses named durations: instant 80–120ms, fast 140–180ms, standard
180–240ms, deliberate 260–360ms, and ambient 2.4–4s. Motion never delays an
action, and reduced-motion removes decorative movement while preserving state
changes and focus visibility.

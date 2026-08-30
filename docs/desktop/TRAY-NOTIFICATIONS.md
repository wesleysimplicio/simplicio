# Tray and native notifications

`desktop.tray/v1` is a contextual projection. It appears for attention or
active work, links back to the canonical Activity/Live item and does not keep
the Runtime or an agent alive when the app is idle.

Notification text contains bounded summaries and reason codes, never prompts,
credentials or raw effect payloads. Native permission and deep-link failures
remain recoverable/unavailable states.

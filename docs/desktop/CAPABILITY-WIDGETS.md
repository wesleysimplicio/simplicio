# Capability Apps and Today widgets

`capability.widgets/v1` keeps optional Today widgets separate from the default
clean surface. A user may pin at most three read-only widgets; the default is
empty. Widget configuration is a Runtime operation and never changes
priorities, starts work or creates a second dashboard authority.

Apps remain the canonical entry point for capability detail. Each widget links
back to the same projection (Today, Activity, Token Reports, Live or Library).

# Automation Studio

`automation.studio/v1` represents suggestions, drafts and active routines
without moving execution authority into the Desktop. Suggestions carry the
receipt that motivated them and start in `review_required`.

Accepting a suggestion must create a Runtime action descriptor. The current
surface therefore keeps Accept, Dismiss and Save draft disabled for preview or
unverified sources. Trigger filters, quiet hours, budgets, cancellation and
emergency stop belong to the Runtime policy boundary.

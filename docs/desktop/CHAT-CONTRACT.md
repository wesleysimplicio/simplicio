# Chat session contract

`chat.session/v1` is a Desktop projection of the Runtime Session Service. It
keeps the canonical session ID, revision, causal event IDs and bounded event
list together. Tool results, approvals, artifacts and attachment handles are
rendered as event kinds; prompt bodies, credentials and attachment bodies are
always redacted.

The composer and session controls are enabled only when the projection source
is `runtime` and the Agent API is authoritative. Preview data is useful for
layout and accessibility checks, but cannot send, steer, cancel or interrupt a
real session.

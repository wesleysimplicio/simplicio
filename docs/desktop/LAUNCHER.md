# `+ New` launcher

`desktop.launcher/v1` gives the global `+ New` menu stable capability IDs for
Start Chat, Create Team, Assign Work, Open App and Create Automation. Forms and
LLM tools use the same action descriptor; the launcher is not a second command
engine.

The shell keeps the menu disabled until a Runtime probe verifies the actions.
An unavailable launcher is visible with remediation rather than a clickable
placeholder or a fake success toast.

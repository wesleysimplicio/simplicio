# OrcaDev / Orca ADE integration

Orca uses the exact `orca` executable and a portable CLI verification plan:
`orca status --json`. Simplicio does not rewrite Orca configuration, install
skills, mutate worktrees, or read credentials for this host.

The plan is evidence-only and can be surfaced to the Runtime/UI for an
explicit verification step. A detected Orca binary is therefore reported as
detected with `manual_host_verification`, while live host semantics remain
outside the installer.

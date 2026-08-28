# Bootstrap profiles

The public download surface offers exactly two channels:

1. `recommended-desktop` — the recommended signed Desktop shell. Desktop
   includes the CLI and bootstraps the Runtime, state, skills, managed
   integrations, updater, rollback metadata, uninstall ledger, and savings
   receipts after login.
2. `recommended-cli` — a per-user CLI bootstrap for terminals and headless
   environments. It uses the same Runtime transaction, component lock, state
   profile, and receipts, but excludes the Desktop shell.

The machine-readable contract is
[`distribution/bootstrap-profiles.json`](../distribution/bootstrap-profiles.json).
The Runtime and Desktop repositories own the implementation of the transaction;
this repository owns the stable public profile IDs and download choices.

## Happy path

```text
Desktop download → open → login → bootstrap apply → ready
CLI bootstrap    → login → bootstrap apply → ready
```

The application must not add a mode wizard, technical preflight, embedded
terminal, or second consent step to this path. Every channel derives from the
same signed release/component lock and must verify before execution.

Installers prefer per-user locations, stage before switching, preserve healthy
state on failure, and keep managed integration edits reversible. They never
copy provider credentials or bypass operating-system security prompts.

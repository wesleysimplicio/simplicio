# Simplicio repository instructions

This repository owns public distribution, installers, host-plugin packages and the Tauri Desktop source in apps/desktop. The Runtime implementation is maintained in simplicio-runtime; inspect its verified public contracts when changing this boundary.

Work on the current MacBook and preserve unrelated changes. Record the repository revision and changed paths before editing. Use current source, installed-binary results and published artifacts as separate evidence.

**Working order**

1. Obtain bounded repository context and recall relevant decisions through the Simplicio MCP.
2. Select an existing standard workflow when it matches the task. Supply prepared operations, exact paths, preconditions and local checks for deterministic execution. A prose issue alone is not an executable patch.
3. Apply the bounded plan through the governed edit/command surfaces. Stop on stale preconditions; reconcile an applied edit before repeating a failed check.
4. Run the smallest local validation that covers the changed behavior. Keep exit codes and test totals. Report unexecuted checks explicitly.
5. Review the diff item by item and report implementation, validation and remaining uncertainty.

Use one coordinator; delegate independent work when the user authorizes it. Internal deterministic execution does not prove zero caller-model tokens or zero model use by arbitrary child commands.

**Current product direction**

Desktop is the intended default installation route: install the required local environment before the first login, then support persistent login, logout and app updates. Keep the current menus. Track incomplete behavior in issues; do not describe an unimplemented flow as delivered.

For Desktop changes, read apps/desktop/README.md and the relevant contract under docs/desktop/. Verify UI to bridge to native command to Runtime receipt before claiming integration. A projection with tests is not evidence of a connected feature.

For hook, Mapper-cache or host-plugin changes, read docs/AGENT_HOST_CONTRACT.md. For packaging, read docs/RELEASE_RUNBOOK.md; publication is a separate authorized action. Keep host-specific manifests and loader-required files.

For local development commands, use CONTRIBUTING.md and docs/testing-strategy.md. This repository has no GitHub Actions workflows; validate locally and do not recreate them.

**Hygiene**

Keep one authoritative definition and use short pointers for host-specific instruction files. Delete only named obsolete files after checking hashes, actual loaders, references and replacement ownership. Keep historical release evidence distinguishable from current operating instructions.

Issue bodies use Development, Validation, Tests and Item-by-item review. Record deterministic steps and evidence in those four sections.

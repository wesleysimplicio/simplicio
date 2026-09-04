# Contributing

This repository owns public Simplicio distribution: release artifacts, installers, package-manager wrappers, host-plugin packages, manifests, documentation, and the Tauri Desktop source under apps/desktop. The Runtime implementation remains in the separate simplicio-runtime repository.

## Before editing

Read AGENTS.md and the relevant host or Desktop contract before planning changes. Preserve unrelated work, keep the current master branch policy, and distinguish source edits, built artifacts, installed behavior, and published release evidence.

For hook or Mapper changes, preserve the Mapper-only gate, do not add network or installation work to hooks, and update the focused Claude and Hermes tests. For Desktop changes, verify the UI, bridge, native command, packaged sidecar, and Runtime receipt boundary.

## Local validation

Install development dependencies in an isolated environment, then run the Python distribution checks:

    pip install -r requirements-dev.txt
    python -m pytest tests/unit -v --cov=scripts --cov-report=term-missing --cov-fail-under=85
    python3 scripts/verify_distribution_consistency.py

The Python suite is deterministic and should use throwaway pytest tmp_path fixtures. The 85 percent threshold applies to the measured scripts surface; critical release-integrity code has a 90 percent target when its focused coverage is available.

The Desktop package declares these local commands in apps/desktop/package.json:

    cd apps/desktop
    npm test
    npm run build
    npm run test:e2e

For native checks, run the Rust library tests from apps/desktop:

    cargo test --manifest-path src-tauri/Cargo.toml

Native package and installed-journey checks require the available target platform and staged, verified sidecar bytes. Report unavailable platforms, signing, notarization, or host integrations as unverified.

## Making changes

Keep pull requests scoped and include the changed paths, commands, exit codes, evidence type, and remaining uncertainty. Do not mix release version or binary changes with unrelated tooling work. Add a regression test for behavior changes and keep manifests, loaders, and package versions synchronized.

The canonical integration branch is master. Open a pull request against master and use its review and merge result as delivery evidence; a local source change is not a published release.

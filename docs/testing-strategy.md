# Testing strategy

This repository contains public distribution tooling, host-plugin packages, documentation, and the Tauri Desktop source. The Runtime remains a separate implementation boundary. Tests must identify whether they cover source, a fixture, a built package, an installed app, or a real host.

## Test surfaces

Python distribution and release tooling is covered by tests/unit and the repository contract tests. Host-plugin changes use the focused Claude and Hermes suites. Desktop frontend changes use the scripts declared in apps/desktop/package.json: Vitest through npm test, TypeScript/Vite validation through npm run build, and Playwright through npm run test:e2e. Native Desktop changes use cargo test with the apps/desktop/src-tauri/Cargo.toml manifest.

## Local commands

    pip install -r requirements-dev.txt
    python -m pytest tests/unit -v --cov=scripts --cov-report=term-missing --cov-fail-under=85
    python3 scripts/verify_distribution_consistency.py

    cd apps/desktop
    npm test
    npm run build
    npm run test:e2e
    cargo test --manifest-path src-tauri/Cargo.toml

Run only the commands relevant to the changed surface when developing, then run the complete applicable contract set before delivery. Keep network, clock, filesystem, and provider behavior isolated in tests. Hooks must remain network-free and must not install packages.

## Evidence rules

A passing unit or frontend test does not prove a signed release, native launch, installed host configuration, login, update, or provider telemetry. Record those as separate evidence classes. Demo or preview data must stay labelled and cannot be promoted to live Runtime evidence. A skipped check requires a concrete reason and an explicit unverified scope.

## Coverage and regressions

Maintain at least 85 percent coverage for the measured Python tooling and aim for 90 percent on critical release-integrity code. Do not claim project-wide coverage until Node, installer, Desktop, and native surfaces are included in the same measured run. Every behavior fix should include a regression that fails before the fix.

## Repository policy

Run scripts/repository_policy.py locally before delivery. It checks the tracked tree for generated state, secrets, personal paths, dependency trees, build products, and compiled executables. Keep historical release documents separate from current operating instructions. This repository has no checked-in GitHub Actions workflow; local command results and their exact evidence are the active quality record.

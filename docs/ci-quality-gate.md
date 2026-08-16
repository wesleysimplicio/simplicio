# CI Quality Gate

Implements issue #10. This document is the policy the workflow in
`.github/workflows/quality-gate.yml` enforces mechanically.

## Why this exists

Before this change the only quality signal in this repo was
`scripts/verify_distribution_consistency.py`, run manually with no CI
wiring and no required checks — so release-version drift (see the
regression test below) shipped silently. This gate turns "someone should
run the checks" into "the merge is blocked until the checks pass."

## What this repo actually is

This repository ships **prebuilt release artifacts** (`simplicio*`
binaries, npm/PyPI wrapper packages, install scripts, docs) — it
is not the application's source tree. There is no compiled application
code here to unit-test, benchmark, or run E2E against. The gate is scoped
to what actually lives in this repo: the Python release-integrity tooling
under `scripts/`, the packaging/version metadata, and the install scripts.
The 85%/90% coverage targets from the issue apply to that tooling.

## Pipeline stages (`.github/workflows/quality-gate.yml`)

| Job | Purpose | Blocking? |
| --- | --- | --- |
| `lint` | `ruff check` over `scripts/` and `tests/` | Yes |
| `unit` | `pytest` + coverage (matrix: ubuntu/windows/macos × Python 3.11/3.12) | Yes |
| `integration` | Runs the real `scripts/verify_distribution_consistency.py` audit end-to-end against the checked-out repo | Yes |
| `security` | `bandit` (static analysis), `pip-audit` (known-vuln scan of the gate's own tooling), `gitleaks` (secret scan) | Yes |
| `benchmark` | Runtime of the audit script vs. a committed baseline, configurable regression threshold | Yes |
| `quality-gate` | Fans in all of the above into one required status check | N/A (aggregator) |

**Matrix rationale:** the install scripts (`install.sh`, `install.ps1`) and
wrapper packages target Linux/macOS/Windows, so the unit job's OS matrix
mirrors that support surface. Python 3.11/3.12 cover the versions the
`scripts/` tooling is written against.

**Expected total pipeline time:** ~3-6 minutes wall-clock (jobs run in
parallel; the slowest leg is the 6-way `unit` matrix, each leg typically
well under 2 minutes). Budget: **fail the pipeline design, not the PR
author, if total time exceeds 15 minutes** — that's a signal the gate
needs re-scoping (e.g. splitting a job or trimming a redundant matrix
leg), not a reason to skip checks.

## Coverage policy

- `unit` enforces `--cov-fail-under=85` on `scripts/` (issue's global
  minimum). The one script under test currently measures ~90% branch
  coverage, satisfying the "90% in critical areas" bar issue #10 asks for
  release-integrity tooling to meet, since a silent version-drift bug is
  exactly the kind of critical-path failure this gate exists to catch.
- New scripts added under `scripts/` must ship with tests in `tests/` in
  the same PR, or the coverage gate will fail on its own.

## Regression-test policy ("every fixed bug gets a regression test")

`tests/test_verify_distribution_consistency.py::test_version_txt_matches_update_manifest_regression`
pins the fix in this PR: `version.txt` (3.0.2) and
`simplicio-update-manifest.json` (3.5.2) had drifted apart, and the
audit script's own ERROR-level check for that was never wired into CI, so
nobody saw it fail. Going forward:

1. Any bug fix that changes behavior must add or update a test in
   `tests/` that fails on the old (buggy) code and passes on the fix.
2. The PR description must name the regression test it added.
3. Reviewers should block a PR that fixes a reported bug without one,
   per the acceptance criteria in issue #10.

## Flaky-test policy

- `unit` uses `pytest-rerunfailures` (`--reruns 2 --reruns-delay 1`): a
  test that fails and then passes on retry does **not** fail the build,
  but every attempt (including retries) is recorded in the uploaded
  JUnit XML artifact (`reports-unit-*`).
- A test that needs a rerun to pass more than occasionally is flaky, not
  robust. Anyone who notices a test rerunning repeatedly in the uploaded
  artifacts should open an issue and quarantine or fix it — reruns are a
  safety net for CI noise, not a substitute for a deterministic test.

## Benchmark policy

`scripts/bench_verify_distribution_consistency.py` measures the audit
script's median runtime over 25 in-process runs and compares it against
`.github/quality-gate/benchmark-baseline.json`. The allowed regression is
configurable via the `BENCH_REGRESSION_THRESHOLD_PCT` environment
variable (default `150`, i.e. up to 2.5x baseline, plus a 5ms noise
floor) — deliberately generous today because the audited script's real
runtime is sub-millisecond and dominated by CI-runner jitter, not
algorithmic work. When perf-sensitive code lands in this repo, point the
same `--update-baseline` / threshold pattern at it and tighten the
threshold.

To refresh the baseline after an intentional, reviewed performance
change:

```sh
python scripts/bench_verify_distribution_consistency.py --update-baseline
```

## Exception policy ("no skipping tests without a registered justification")

- Do not add `pytest.mark.skip`, `# noqa`, `# nosec`, or disable a CI job
  without a comment **in the same diff** that names: (a) which check is
  bypassed, (b) why, (c) the follow-up issue/PR that will remove the
  exception. An unexplained skip is a review blocker.
- Any exception that spans more than one PR must be tracked in an open
  GitHub issue linked from the code comment, so it shows up in the
  backlog instead of being silently permanent.

## Branch protection (manual step — requires repo admin)

This PR ships the workflow and its required-check aggregator
(`quality-gate`), but does **not** change the repository's branch
protection settings — that's a GitHub security setting a bot/PR should
not flip on its own. A repo admin should, once this workflow has run at
least once on `master`:

1. Go to **Settings → Branches → Branch protection rules** for `master`.
2. Require status checks to pass before merging, and select
   **`quality-gate (required)`** (and, optionally, the individual
   `lint`/`unit`/`integration`/`security`/`benchmark` jobs for
   finer-grained PR annotations).
3. Enable "Require branches to be up to date before merging."

Until that's done, the acceptance criterion "Branch principal exige
checks verdes" is implemented in code but not yet enforced by GitHub
itself.

## Out of scope for this PR (follow-ups)

This repo has no compiled application source, so some of issue #10's
language doesn't map 1:1 yet. Tracked as follow-up work, not silently
dropped:

- **True E2E tests**: there's no running application/service in this
  repo to drive end-to-end. `integration` currently covers the one
  meaningful cross-file check that exists (the consistency audit). If/when
  install-script E2E smoke tests (actually running `install.sh` /
  `install.ps1` in disposable containers/VMs) are wanted, that's a
  distinct, heavier job worth its own PR.
- **Wrapper/version auto-fix**: the public source metadata is now aligned with
  the published v3.8.11 manifest. Publishing the corresponding npm/PyPI
  packages remains a separate registry operation and must not be inferred from
  a source-repository commit alone.
- **Branch protection activation**: see above — requires admin action
  outside this PR.

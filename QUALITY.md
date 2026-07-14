# CI quality gate

Issue #10 is enforced by `.github/workflows/quality.yml`. Every pull request and push to
`master` runs independent lint, unit, integration, end-to-end, security, benchmark, and flaky-test
jobs. The `quality-gate` aggregate job fails unless every mandatory job succeeds; configure branch
protection to require that exact check name.

## Required evidence

| Job | Contract | Expected duration |
| --- | --- | ---: |
| `lint` | Python/Node/PowerShell/shell syntax plus ignored-test policy | 2 minutes |
| `unit` | Python and Node unit tests, JUnit, global coverage >=85%, critical functions >=90% | 4 minutes |
| `integration` | Strict distribution audit and package builds on Linux, macOS, Windows; Python 3.11/3.13 | 8 minutes |
| `e2e` | Real npm CLI entrypoints in network-free dry-run mode; Node 20/22/24 on all three OSes | 6 minutes |
| `security` | High-confidence secret scan plus dynamic code/shell detection | 4 minutes |
| `benchmark` | Installer payload and audit-time budgets against `benchmarks/baseline.json` | 2 minutes |
| `flaky` | Three clean repetitions of Python and Node unit suites | 5 minutes |

Matrix jobs run concurrently. The expected wall-clock target is 15 minutes. A run above 20 minutes
for three consecutive successful PRs requires a tracking issue and a baseline review.

JUnit, coverage, benchmark, security, package-build, and flaky-attempt reports are uploaded with
`if: always()` and retained for 14 days, including on failure.

## Coverage and regression policy

- Global line/branch coverage over testable first-party Python quality code must stay at or above
  85%. `scripts/verify_distribution_consistency.py`, the critical release-integrity surface, must
  stay at or above 90%.
- Node installer lines must stay at or above 85% and functions at or above 90%.
- Every bug fix must add a test that fails before the fix. The version-source and expired-beta
  regressions that triggered issue #10 are frozen in `tests/test_distribution_consistency.py`.
- A test may be skipped only with an adjacent four-line exception block containing
  `JUSTIFICATION:`, a full `https://github.com/wesleysimplicio/simplicio/issues/<number>` URL,
  `OWNER:`, and `REMOVE-BY: YYYY-MM-DD`. Removal must be between today and 30 days from today.
  Decorators, `self.skipTest`, raised `SkipTest`, pytest skips, Node `.skip`, and `{skip: true}` are
  all enforced by `quality_policy.py`.
- Retries never hide failure: `flaky_check.py` records every attempt, labels mixed outcomes FLAKY,
  and returns non-zero if any attempt fails.

## Benchmark exceptions

`benchmarks/baseline.json` is reviewed code. A deliberate payload/performance increase must update
the baseline in the same PR with measurements and rationale. Emergency diagnosis may set
`SIMPLICIO_BENCHMARK_TOLERANCE_PERCENT`, but merges still require a linked exception issue and an
updated baseline; the environment override is not configured on protected branches.

## Release provenance

`publish-release` never renames a checked-in wrapper binary into a platform artifact. It requires
the version tag to exist, downloads every artifact from the exact version-bound URL declared in
`simplicio-update-manifest.json`, verifies its SHA256 and required signature metadata, then uploads
only that verified staging directory. A missing tag, drifting URL, missing signature, or hash
mismatch stops before the release action; the workflow never creates or moves a tag.

## Local parity

```text
python scripts/verify_distribution_consistency.py --strict
python scripts/quality_policy.py
coverage run --rcfile=.coveragerc scripts/run_python_tests.py --junit artifacts/unit/python-junit.xml
coverage report --fail-under=85
coverage report --include=scripts/verify_distribution_consistency.py --fail-under=90
node --test --experimental-test-coverage --test-coverage-lines=85 --test-coverage-functions=90 tests/node/installer-unit.test.cjs
node --test tests/node/installer-e2e.test.cjs
python scripts/security_scan.py
python scripts/benchmark_distribution.py
```

## Repository settings required after merge

The workflow file cannot enable its own control plane. An administrator must:

1. Enable GitHub Actions for `wesleysimplicio/simplicio`.
2. Update the active `master` ruleset to require pull requests and the `quality-gate` status check,
   require branches to be up to date, block force-push/deletion, and disallow bypass.
3. Confirm one PR exercises all jobs, artifacts are downloadable, and direct merge is rejected when
   any mandatory job fails.

Exceptions are never made by disabling a job or lowering thresholds. Use a linked, time-boxed issue;
keep `quality-gate` required and fix or formally revise the versioned contract through review.

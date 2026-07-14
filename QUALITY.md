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

`publish-release` is manual-only; merging a CI or manifest change cannot trigger publication. Its
required `artifact_base_url` input must be an HTTPS, version-segmented staging origin distinct from
the target GitHub release URL. The workflow reads tag and release state before any mutation, then a
reusable Python planner chooses exactly one mode:

- `idempotent`: an existing tag manifest matches version plus artifact name/URL/SHA256/signature and
  every remote artifact has the declared SHA256 digest. Download, metadata, and publish steps are skipped.
- `publish`: neither tag nor release exists and the staging URL is safe. Artifacts are downloaded from
  staging, never from the not-yet-existing target release, and their bytes plus signature metadata are
  verified before release creation with `overwrite_files: false`. The destination must start empty;
  before metadata its entries must equal the manifest artifact names exactly, and after metadata the
  only additions allowed are `simplicio-update-manifest.json` and `SHA256SUMS`. Directories, symlinks,
  stale files, and unmanifested files fail closed. Checksums iterate that allowlist rather than a glob.

The existing `v3.5.2` tag contains a `3.5.1` manifest, so the manual workflow is intentionally blocked
for that tag and must not move it or replace its assets. Preparing a fresh version, immutable tag, and
signed staging set is separate release work.

The strict distribution audit parses workflow YAML using pinned PyYAML and validates the actual trigger,
input, `jobs.release.steps`, executable commands, action inputs, conditions, and ordering. Comments and
environment variables cannot satisfy executable-step requirements. The topology is closed-world: one
release job, nine unique ordered step IDs, three approved actions, exact environment maps, and six
canonical single-command script invocations. Any extra job/step/key/action/command or appended shell
separator fails the audit. Workflow permissions default to `contents: read`; only that exact release job
elevates to `contents: write`. The publish action's complete `with` mapping is canonical; changing its
tag/name/body/prerelease/latest/overwrite/file inputs or adding another input fails the audit.

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

## Summary

<!-- What distribution behavior changes, and why? -->

## Tracking issue

<!-- Required: Related: #number -->

## Quality evidence

- [ ] `quality-gate` is green.
- [ ] A bug fix includes a regression test that fails before the fix.
- [ ] Coverage remains >=85% globally and >=90% for critical release-integrity code.
- [ ] Installer/package behavior was exercised in dry-run mode on the supported matrix.
- [ ] No test is skipped. If an external dependency requires a skip, the adjacent
      exception includes `JUSTIFICATION:`, repository issue URL, `OWNER:`, and a `REMOVE-BY:` date
      no more than 30 days away.
- [ ] Benchmark changes are within `benchmarks/baseline.json`, or this PR updates the baseline with
      measured rationale.

## Regression test

<!-- Name the exact test file and case. Documentation-only work: explain why no runtime path changed. -->

## Exceptions

<!-- None, or link the owner + removal-date issue. Exceptions never disable quality-gate. -->

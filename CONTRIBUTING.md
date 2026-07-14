# Contributing

This repo is the public **distribution** repo for `simplicio`: committed
release binaries plus the packaging/tooling around them (npm/pypi/Homebrew
wrappers, install scripts, docs, release manifests). It does not contain the
agent's Rust source, so there is no `cargo test`/`cargo check`/`cargo build`
here.

## Running tests

Official test command for this repo's Python tooling
(`scripts/verify_distribution_consistency.py` today; more modules will be
added under `tests/unit` as the testing epic — issue #8 — progresses):

```bash
pip install -r requirements-dev.txt
python -m pytest tests/unit -v --cov=scripts --cov-report=term-missing --cov-fail-under=85
```

- Test layout: `tests/unit/`, one `test_<module>.py` per `scripts/<module>.py`,
  shared fixtures/builders in `tests/unit/conftest.py`.
- Tests must be deterministic and isolated: no network access, no dependence
  on the real wall clock (freeze `datetime.date` via `monkeypatch` if a
  function reads it), and no reliance on execution order — each test builds
  its own throwaway fixture tree under pytest's `tmp_path`.
- CI runs the same command via `.github/workflows/tests.yml` on every push/PR
  touching `scripts/`, `tests/`, or the test config.

See [docs/testing-strategy.md](docs/testing-strategy.md) for the full
rationale, current coverage, and what's left for the rest of the epic.

## Making changes

- Keep PRs scoped; this repo mixes release artifacts with tooling/docs, so
  please don't bundle binary/version bumps with unrelated tooling changes.
- If you touch `scripts/verify_distribution_consistency.py`, add/update the
  corresponding test(s) in `tests/unit/test_verify_distribution_consistency.py`
  in the same PR.

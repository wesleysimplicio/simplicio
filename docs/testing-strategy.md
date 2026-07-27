# Testing strategy (this repo)

Tracks issue #8 ("[Quality Epic] Implantar estratégia completa de testes
automatizados no pacote principal"). This file documents what is tested here,
how, and what is intentionally out of scope, plus the plan for finishing the
epic across multiple PRs.

## What this repo actually is

`wesleysimplicio/simplicio` is the **public distribution repo**: committed
release binaries (`simplicio.exe`, `simplicio-linux-x64`, ...), package-manager
wrappers (`npm/`, `pypi/`), install scripts (`install.sh`,
`install.ps1`), and docs/manifests describing a release. There is no Rust
source (`Cargo.toml`, `*.rs`) checked into this repo — the actual `simplicio`
agent source lives elsewhere. That means:

- We do **not** run `cargo test` / `cargo check` / `cargo build` here — there
  is nothing for cargo to build.
- The "pacote principal" testable from *this* repo is its own tooling: the
  Python consistency-checker script and, longer-term, the npm installer
  scripts and PowerShell/bash installers.

## Scope of this PR

- `scripts/verify_distribution_consistency.py` — the packaging/version-drift
  auditor — now has a full unit test suite:
  `tests/unit/test_verify_distribution_consistency.py` plus a fixture builder
  in `tests/unit/conftest.py` (`RepoBuilder`) that assembles a throwaway fake
  repo tree per test under pytest's `tmp_path`.
- Every finding branch in the script is covered: happy path, each `ERROR`
  case (branch policy text missing, `/main/` references, version.txt/manifest
  mismatch), each `WARN` case (wrapper version drift, ecosystem doc drift,
  stale/unparseable beta date, contradictory beta copy), and the parser
  helpers' error paths (malformed pyproject version strings).
- The suite is deterministic: `date.today()` is frozen via monkeypatch in
  every test that touches the beta-date check, so no test depends on the
  real wall clock. No test touches the network or mutates the real repo —
  everything runs inside `tmp_path`.
- Coverage: `scripts/verify_distribution_consistency.py` is at 98% line
  coverage from this suite (`--cov-fail-under=85` gate; see below), which
  clears the 85%/90% acceptance thresholds for this module.
- CI: `.github/workflows/tests.yml` runs the suite (with the coverage gate)
  on every push/PR that touches `scripts/`, `tests/`, or the test config,
  independent of the existing binary-release workflow.

## Running and debugging the suite

```bash
pip install -r requirements-dev.txt
python -m pytest tests/unit -v --cov=scripts --cov-report=term-missing --cov-fail-under=85
```

- Run a single test: `python -m pytest tests/unit -k stale_beta_until -v`
- Drop into a debugger on failure: `python -m pytest tests/unit --pdb`
- The suite never depends on execution order — each test builds its own
  `tmp_path` repo tree via the `repo` fixture, so tests may run in any order
  or in parallel (`pytest -p xdist -n auto`, once `pytest-xdist` is added).

## Known pre-existing drift (not fixed by this PR)

Running `python scripts/verify_distribution_consistency.py` against the real
repo currently reports real ERROR/WARN findings (e.g. `version.txt` vs.
`simplicio-update-manifest.json` mismatch, stale `beta_until`). Fixing that
drift is a separate, unrelated content/release-hygiene fix, not a testing
concern — this PR verifies the *checker* is correct, it does not silence or
paper over what the checker (correctly) flags. The CI job added here is
scoped to `scripts/`/`tests/` changes rather than every push, specifically so
it doesn't block unrelated work on this pre-existing, already-flagged drift.

## Remaining work for this epic (tracked for follow-up PRs)

This issue is explicitly an epic ("cobertura mínima de 85%/90% no projeto
inteiro, branch coverage monitorada, todos os módulos críticos"), which is
larger than one PR. Suggested follow-ups, roughly in priority order:

1. **npm installers** (`npm/simplicio/install.js`,
   `npm/simplicio-installer/install.js`, `npm/simplicio-unscoped/install.js`):
   add a Node test runner (`node --test` or `vitest`) with fakes for
   filesystem/network calls (these currently hit the real npm registry /
   GitHub releases — needs dependency injection or mocking before they're
   testable in isolation).
2. **Install scripts** (`install.sh`, `install.ps1`): add `bats`/Pester-based
   tests against a faked download/checksum step.
3. **Branch coverage**: wire `coverage.py`'s branch mode
   (`--cov-branch`) once module #1 above exists, so the 85%/90% target is
   measured project-wide rather than per-module.
4. Add a repo-wide coverage roll-up job once (1) and (2) land, and only then
   close out issue #8 — right now this PR closes the *initial slice*
   (convention, fixtures, first fully-covered module, CI wiring, docs) per
   the issue's own step 4 ("Adicionar testes por módulo começando pelos
   componentes de maior risco"), not the entire epic.

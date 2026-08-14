# Test infra probe & adaptive DoD (#526 Etapa 3 full detail)

The 7-dimension DoD (`scripts/pr_dod_review.py` `DOD_DIMENSIONS` / CLAUDE.md — implementation, unit,
integration, system, regression, benchmark, coverage) stays the target. What Etapa 3 changes is
**how it's sized**: a repository that has no test project, no coverage tooling, and no CI running
tests cannot produce `unit`/coverage/benchmark evidence no matter how many turns the loop spends
trying — that's a fact about the repo, not a quality failure. `scripts/test_infra_probe.py`
answers that fact deterministically (glob + grep, never an LLM guess), and `scripts/task_anchor.py`
uses it to size the gate to what the repo actually HAS.

## 1. The probe

```bash
python3 scripts/test_infra_probe.py probe --root .
python3 scripts/test_infra_probe.py probe --root . --anchor .simplicio/orchestrator/loop/anchor.json
```

Output is a MEASURED dict: `schema`, `measured: true`, a per-ecosystem breakdown (`unit`,
`coverage`, `ci` booleans + the matched files as `*_markers`), `detected_ecosystems`, and the
compact summary written onto the anchor:

```json
{"test_infra": {"unit": "present", "coverage": "absent", "ci": "present"}}
```

`--anchor PATH` records that summary onto `anchor.json`'s `test_infra` key — the same "record onto
the anchor" convention as `scripts/route_mode.py`'s `route_mode` key and
`scripts/diff_escalation.py`'s `diff_escalation` key.

### Detection table (six ecosystems)

| Ecosystem | Unit-test signal | Coverage-tooling signal | CI-runs-tests signal |
|---|---|---|---|
| **.NET** | `*Tests.csproj` / `*.Tests.csproj` / `*Test.csproj` / `*.Test.csproj`, or any `*.csproj` referencing `Microsoft.NET.Test.Sdk` | `coverlet.runsettings`, `*.coverage`, `coverage.cobertura.xml`, or a `*.csproj` referencing `coverlet` | a CI config running `dotnet test` |
| **Node** | `jest.config.*`, `vitest.config.*`, `.mocharc*`, `karma.conf.*`, `ava.config.*`, or `package.json` naming `jest`/`mocha`/`vitest`/`ava`/`tape` | `.nycrc*`, `.c8rc*`, `package.json` naming `nyc`/`c8`/`@vitest/coverage-*`/`istanbul`, or a jest config with `collectCoverage` | a CI config running `npm test` / `yarn test` / `pnpm test` / `npx jest`/`vitest`/`mocha`/`ava` |
| **Python** | `pytest.ini`, `conftest.py`, `test_*.py`, `*_test.py`, or `pyproject.toml`'s `[tool.pytest...]` / `setup.cfg`'s `[tool:pytest]` | `.coveragerc`, or `pyproject.toml`'s `[tool.coverage...]` / `setup.cfg`'s `[coverage:...]` | a CI config running `pytest`, `python -m pytest`, or `tox` |
| **Go** | `*_test.go` | `.codecov.yml`/`codecov.yml`, or a `Makefile` using `-cover` | a CI config running `go test` |
| **Rust** | `tests/*.rs`, or any `src/*.rs`/`src/**/*.rs` containing `#[test]` | `tarpaulin.toml`, or `Cargo.toml` referencing `tarpaulin` | a CI config running `cargo test` |
| **Java** | `src/test/java/*.java` (recursive), or `pom.xml` referencing `maven-surefire-plugin` | `pom.xml` or `build.gradle*` referencing `jacoco` | a CI config running `mvn ... test`, `./gradlew test`, or `gradle test` |

CI files scanned: `.github/workflows/*.yml`/`*.yaml`, `azure-pipelines.yml`, `.gitlab-ci.yml`,
`Jenkinsfile`, `.circleci/config.yml`. Detection is deterministic (fnmatch + regex on real file
content) — same repo, same answer, every run; it is a heuristic over REAL markers, not a guarantee
every possible test-runner convention is covered, so a hit is authoritative but a miss on an unusual
in-house convention is possible (extend the table above, in both this doc and
`scripts/test_infra_probe.py`'s `ECOSYSTEMS`, when a real repo needs a marker it doesn't have yet).

## 2. Three states per dimension (`task_anchor.py gate`)

Each acceptance criterion tracked by `scripts/task_anchor.py` now has one of three states:

| Status | Meaning | Blocks `gate` READY? |
|---|---|---|
| `done` | verified, with `--evidence` (file:line / command output / harness receipt) | no |
| `waived:no-infra` | structurally impossible in THIS repo — excused, with a mandatory `--reason` | no |
| `pending` (default) / `partial` | not yet verified | **yes** |

```bash
python3 scripts/task_anchor.py mark --id AC2 --status waived:no-infra \
  --reason "no coverage tooling detected (test_infra_probe: coverage=absent)"
python3 scripts/task_anchor.py gate --exit-code
```

`gate` reaches `ready` once every criterion is `done` or `waived:no-infra` — zero genuinely
`pending`. **Every `waived:no-infra` criterion is printed unconditionally**, in both text and
`--json` mode, ready or blocked — a waiver can never be silently absent from the final report. A
`mark --status waived:no-infra` with no `--reason` is refused (exit 12): "no reason, no waiver."

`render_checklist` (the same renderer `pr_evidence.py` uses for the PR body) shows a `[w]` box with
the reason inline, and the coverage line calls out the waived count: `**Coverage:** 1/3 criteria
verified · 2 waived:no-infra.`

## 3. The "external harness" evidence form (Etapa 3.2)

When `test_infra.unit == "absent"` AND the delivery contract forbids new files in the target repo
(a common shape: "fix this one function, don't scaffold a whole test project"), the `unit`/`testes`
dimension accepts an **external harness in the caller's own scratchpad** as evidence — not a
lowered bar, a different, still-mechanical bar. Three artifacts are REQUIRED; absence of any one of
the three invalidates the whole evidence (no 2-out-of-3 pass):

1. **harness source** — the harness's own code (e.g. a small script that re-implements/exercises
   the target function against known inputs/outputs). Must be non-empty.
2. **execution log with named PASS/FAIL cases** — a real run's output, one line per case, e.g.
   `case_add_negative PASS`. At least one named case is required; a log with output but no
   recognizable `<name> PASS|FAIL` line does not count.
3. **hash of the replicated code snippet** — a sha256 hex digest of the exact source text the
   harness claims to mirror. This is what makes the harness provably test the REAL diff instead of
   an imagined one: `task_anchor.py verify_harness` can recompute the sha256 of the actual file in
   the target repo and require it to match.

```bash
python3 scripts/task_anchor.py verify_harness \
  --harness-dir /scratch/session/harness \
  --snippet src/Calc.cs
```

`--harness-dir DIR` resolves the 3 artifacts by convention (`harness_source.*`, `run.log`,
`snippet.sha256` inside DIR); or pass `--harness-source`/`--harness-log`/`--harness-hash`
explicitly. `--snippet PATH` is the real file in the TARGET repo the harness claims to mirror —
when given, its live sha256 must equal the hash artifact's digest, or the evidence is rejected.
Any FAILed case in the log also invalidates the evidence (a harness that ran and failed is not
"tests pass"). On success: `harness-ok` plus an `EVIDENCE: external-harness ...` line usable
directly as `task_anchor.py mark --evidence "<that line>"`. On any missing/empty/mismatched
artifact: `harness-invalid` + the specific reason, `--exit-code` → 12.

The pure validation logic (`verify_harness_content` in `scripts/task_anchor.py`) is exercised
in-memory by `task_anchor.py selftest` — no files touched by the selftest itself; the file-reading
wrapper (`verify_harness_artifacts`) is what the CLI verb calls against real scratchpad paths.

## 4. Worked example: a .NET repo with no test project

Goal: fix one function in `src/Calc.cs`. The repo has no `*.csproj` test project, no coverage
tooling, no CI. The delivery contract forbids creating new files in the repo.

```bash
python3 scripts/test_infra_probe.py probe --root . --anchor .simplicio/orchestrator/loop/anchor.json
# -> test_infra: {"unit": "absent", "coverage": "absent", "ci": "absent"}

python3 scripts/task_anchor.py set --item 526-fixture --goal "Fix Calc.Add" \
  --ac "Unit tests pass" --ac "Coverage >=85%" --ac "Benchmark within budget"

# unit: build + run a harness entirely in the scratchpad, hash-bound to the real src/Calc.cs
python3 scripts/task_anchor.py verify_harness --harness-dir "$SCRATCH/harness" --snippet src/Calc.cs
python3 scripts/task_anchor.py mark --id AC1 --status done \
  --evidence "external-harness $SCRATCH/harness (2 cases, all PASS, hash <sha256>)"

# coverage/benchmark: structurally impossible without tooling this repo doesn't have
python3 scripts/task_anchor.py mark --id AC2 --status waived:no-infra \
  --reason "no coverage tooling detected (test_infra_probe: coverage=absent)"
python3 scripts/task_anchor.py mark --id AC3 --status waived:no-infra \
  --reason "no perf harness detected (test_infra_probe: no benchmark tooling)"

python3 scripts/task_anchor.py gate --exit-code   # => ready, exit 0
```

No file is created anywhere under the target repo — the harness's 3 artifacts live entirely under
`$SCRATCH` (the caller's own scratchpad), never inside the repo being fixed. See
`tests/test_task_anchor_infra_gate.py` (`test_dotnet_no_test_project_fixture_reaches_ready_via_harness_and_waivers`)
for the exact reproduction the AC calls for.

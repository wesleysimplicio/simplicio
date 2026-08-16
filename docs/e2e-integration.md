# Integration / E2E — validating real flows across the Simplicio ecosystem

> Implements the minimum scope of issue #9 for this repo:
> `wesleysimplicio/simplicio` is the **public distribution repo** (compiled
> runtime binary + npm/PyPI wrappers). The runtime source, mapper,
> dev-cli, loop and agent components live in sibling repos and are consumed
> here only as optional PATH adapters (`simplicio version --json` →
> `components`). This repo does not build the Rust runtime (no
> `cargo build`/`cargo test` here — see `INSTALL.md` "Building from Source"
> for that flow in `simplicio-runtime`), so the tests below exercise the
> **already-compiled, committed binary** end to end, exactly as a real user
> or CI consumer would.

## What it validates

`scripts/e2e_ecosystem.py` runs each of the following against a disposable,
ephemeral repo (`tempfile.mkdtemp`, deleted at the end — never against a
developer's real `~/.simplicio` state):

| # | Cenário mínimo (issue #9) | How it's exercised |
|---|----------------------------|---------------------|
| 1 | Instalação limpa e inicialização | `simplicio setup --repo <tmp>` on a brand-new repo; asserts `.simplicio/config.json` is created with `schema=simplicio.config/v1` |
| 2 | Config válida / inválida | `simplicio doctor --repo <tmp> --json` against the generated config, then again after corrupting `config.json` — asserts the runtime degrades with a diagnostic instead of crashing |
| 3 | Descoberta/mapeamento de projeto | `simplicio runtime map --repo <tmp> --json`, asserts `simplicio.map-result/v1` |
| 4 | Execução de uma tarefa completa | `simplicio edit '{"file":...}' --json` — a real mechanical edit; asserts the file content actually changed on disk (input → final result) |
| 5 | Propagação de erro/timeout/cancelamento | An edit with a pattern that doesn't exist (asserts non-zero exit + clear message), and `simplicio recover "exit 3" --attempts 2` (asserts retry-exhaustion is reported clearly, non-zero exit) |
| 6 | Persistência e retomada após falha | Runs `doctor` as a second, independent process against the same repo and asserts `.simplicio/` state (config, memory, runs, checkpoints) is unchanged/resumed, not re-initialized |
| 7 | Compatibilidade com dependências publicadas | `simplicio version --json` compatibility matrix (`components[*].minimum_version`), plus re-running the existing `scripts/verify_distribution_consistency.py` packaging-contract gate |

Each scenario prints `[PASS]`/`[FAIL]` with a one-line diagnostic. The
process exits `0` only if every scenario passed, `1` if any failed, and `2`
if no usable binary exists for the current OS/arch (an environment gap, not
a test failure).

## Running it

```bash
# Windows (repo ships simplicio-windows-x64.exe / simplicio.exe)
python scripts/e2e_ecosystem.py

# macOS / Linux (repo ships simplicio-darwin-x64 / simplicio-macos-arm64 / simplicio-linux-x64)
python3 scripts/e2e_ecosystem.py

# Explicit binary + machine-readable summary
python scripts/e2e_ecosystem.py --binary ./simplicio.exe --json
```

No network access, credentials, or `cargo` toolchain required — it only
invokes the binary already checked into the repo root.

## Evidence captured on 2026-07-14 (Windows, simplicio-windows-x64.exe v1.6.4)

```
Using binary: simplicio-windows-x64.exe
Platform: Windows AMD64

[PASS] 1. clean install & initialization (simplicio setup) — exit=0, config.json exists=True, schema=simplicio.config/v1
[PASS] 2a. doctor loads a valid repo config — exit=0
[PASS] 2b. doctor handles a corrupted config without crashing — exit=0, crashed=False
[PASS] 3. project discovery/mapping (simplicio runtime map) — exit=0
[PASS] 4. end-to-end task execution (simplicio edit, input->result) — exit=0, before="console.log('hi')", after="console.log('bye')"
[PASS] 5a. edit failure propagates non-zero exit + clear diagnostic — exit=1, message='simplicio: operation 0 (replace): pattern not found: "DOES_NOT_EXIST_IN_FILE"'
[PASS] 5b. retry exhaustion (simplicio recover) reports cancellation clearly — exit=1
[PASS] 6. state persists across independent process runs (.simplicio/) — state_dir_entries=[...]
[PASS] 7a. release manifest declares component compatibility matrix — components=['dev_cli', 'mapper', 'prompt', 'sprint']
[FAIL] 7b. published package/manifest versions agree (verify_distribution_consistency.py) — summary: 1 error(s), 4 warning(s), 1 ok

summary: 9/10 scenarios passed
```

This output is historical evidence from the v1.6.4 Windows snapshot. The
version drift shown there was corrected in the public v3.8.11 synchronization:
`version.txt`, the npm/PyPI source metadata, `SIMPLICIO_ECOSYSTEM.md`, and the
published update manifest now agree. Re-run the command against the current
root binary before using this transcript as release evidence.

## CI

`.github/workflows/e2e.yml` runs the same script on `windows-latest` for
pull requests and pushes touching the binaries, wrappers, manifest, or the
test script itself, plus `workflow_dispatch` for on-demand runs. The step
uploads full stdout/stderr as a build artifact so a failing run always has
attached diagnostics.

## Next steps (out of scope for this PR)

- Add macOS/Linux CI legs once hosted runners for this repo have `git`
  available in the default image path used by the ephemeral repo bootstrap
  (currently only exercised locally on those OSes).
- Extend scenario 5 with an actual long-running/cancelable task once the
  runtime exposes a stable cancellation-token flow via the CLI (today's
  `recover` covers retry-exhaustion but not mid-flight cancellation).
- Wire `simplicio contracts smoke` / `simplicio runtime smoke` (present in
  the compiled binary) into this suite once their expected fixture layout
  (`docs/SIMPLICIO_OPERATIONAL_MANUAL.md`, `examples/EXAMPLES.md`) is
  defined for a minimal ephemeral repo, instead of only the real one.

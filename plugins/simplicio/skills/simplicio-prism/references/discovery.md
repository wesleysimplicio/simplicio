# Capability discovery and confidence

Generate an inventory from the actual checkout or installed package before trusting an interface. The inventory is the evidence layer; the human-authored `capabilities.yaml` explains routing semantics.

## Evidence sources

| Surface | Primary evidence | Secondary evidence |
|---|---|---|
| CLI | `project.scripts`, `package.json.bin`, Cargo `[[bin]]`, optional `--help` probe | help fixtures and command modules |
| MCP | tool/resource decorators and server registrations | MCP schemas, `tools/list`, docs |
| Python API | AST public functions/classes and signatures | exported `__all__`, package metadata |
| Rust API | `pub` items and `#[pyfunction]`/`#[pymethods]` markers | Cargo metadata and docs |
| Configuration | packaging files, known dotenv/config files, manifests | docs and environment references |
| Errors | `raise`, `Result`, error enums, subprocess status checks | tests and error docs |
| Fallbacks | explicit fallback/degraded/retry signals | adapter and recovery docs |

## Confidence rules

- `observed`: directly present in packaging metadata or source syntax.
- `inferred`: derived from annotations, names, or static signals; verify before side effects.
- `requires_review`: cost, outputs, effects, or compatibility cannot be proven statically.
- `unavailable`: requested surface is not present in the checkout.

Never turn an inferred input/output, cost, effect, or fallback into a guaranteed contract without a test or manual override.

## Manual enrichment

Place `capability-overrides.json` at the repository root to add verified descriptions, schemas, error codes, measured costs, fallbacks, or compatibility notes. Overrides are keyed by capability `id` and are included in the evidence record.

## Versioning

Regenerate after source, packaging, CLI, MCP schema, dependency, or runtime changes. Store the repository revision, package versions, generator version, and generation timestamp in every inventory.

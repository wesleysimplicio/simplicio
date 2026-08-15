# Installing Simplicio

Simplicio is a terminal-based AI coding agent and runtime. It ships as a single
compiled binary with no external dependencies.

## Quick Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

### Windows (PowerShell)

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex"
```

### Manual Download

Download the binary for your platform from the
[releases](https://github.com/wesleysimplicio/simplicio/releases). Asset names
are canonical — see [`distribution/targets.json`](distribution/targets.json),
the single source of truth used by the release workflow, both installers and
`simplicio-update-manifest.json`:

| Target id      | Platform               | Asset                       |
|----------------|------------------------|------------------------------|
| `macos-arm64`  | macOS (Apple Silicon)  | `simplicio-macos-arm64`      |
| `macos-x64`    | macOS (Intel)          | `simplicio-macos-x64`        |
| `linux-x64`    | Linux x86_64           | `simplicio-linux-x64`        |
| `windows-x64`  | Windows x86_64         | `simplicio-windows-x64.exe`  |

Verify the SHA256 checksum against the `sha256` field for your target in
`simplicio-update-manifest.json` (published alongside each release) before
running the binary. Then place it somewhere on your `PATH` (e.g.
`/usr/local/bin` or `~/.local/bin`), naming it `simplicio` (or `simplicio.exe`
on Windows).

## Doctor / Uninstall

Both installers are idempotent and expose a health check and a clean,
data-preserving uninstall — safe to re-run at any time:

```bash
# macOS / Linux
sh install.sh --doctor
sh install.sh --uninstall
```

```powershell
# Windows
pwsh install.ps1 -Doctor
pwsh install.ps1 -Uninstall
```

Uninstall only removes the installed binary; it never deletes user data or
config under `~/.simplicio`.

## Verify Installation

```bash
simplicio help
```

Expected output starts with `simplicio 0.9.2`.

## Configuration

### LLM Provider (required for AI features)

Simplicio works with **local** or **remote** LLM providers.

#### Local (default, no API key needed)

Simplicio includes an in-process LLM engine (llama.cpp) that runs models locally.
The default model is `qwen/qwen3.5-2b:q6_k`.

```bash
# Force local inference
simplicio run "fix the bug" --repo . --local
```

#### Remote (OpenRouter, Anthropic, DeepSeek, etc.)

Set environment variables to use a remote provider:

```bash
export SIMPLICIO_MODEL="deepseek/deepseek-v4-flash"
export SIMPLICIO_BASE_URL="https://openrouter.ai/api/v1"
export SIMPLICIO_API_KEY="your-key-here"

simplicio run "fix the bug" --repo . --remote
```

### Runtime Profile

Control resource usage with profiles:

```bash
# Normal (default): 128 active agents, 512MB cache
simplicio runtime-profile use normal

# Full: 256 active agents, 2GB cache (for big machines)
simplicio runtime-profile use full

# Low: 64 active agents, 128MB cache (constrained environments)
simplicio runtime-profile use low
```

## Core Commands

```bash
# Map your repo (saves tokens vs reading files)
simplicio runtime map --repo . --for-llm markdown

# Recall from memory (don't re-derive known facts)
simplicio memory "how does auth work" --repo . --json

# Deterministic edit (zero LLM tokens for file writes)
simplicio edit '{"file":"src/main.rs","operations":[{"op":"replace","find":"old","with":"new"}]}'

# Coding loop (iterate until tests pass)
simplicio coding-loop "fix the failing test" --repo . --max-cycles 5

# Run a task with agents
simplicio run "add pagination to the API" --repo . --local --agents 4

# Delivery gates (quality check before shipping)
simplicio deliver check --repo .
simplicio deliver certify --repo . --json
```

## IDE Integration

Simplicio integrates with editors via the ACP adapter:

- **VS Code**: Install the Simplicio extension (search "simplicio" in marketplace)
- **JetBrains**: Use the Simplicio plugin
- **Zed**: ACP adapter built-in

## Using with AI Assistants

Simplicio is designed to be used **by** AI assistants (Claude, Codex, Gemini)
as their execution backbone:

1. The AI assistant reasons about the task
2. Simplicio provides: repo map, memory recall, deterministic edits, validation
3. The AI reviews results and iterates

### Claude Code

Add to your project's `CLAUDE.md`:

```markdown
## Simplicio Integration

Use `simplicio runtime map` before reading files.
Use `simplicio memory` before re-deriving facts.
Use `simplicio edit` for mechanical changes (zero tokens).
Use `simplicio deliver certify` before declaring done.
```

### OpenAI Codex / ChatGPT

Same workflow — Simplicio commands work from any terminal-based AI agent.

## Fontes Python no Runtime

O binário Runtime é o artefato de instalação e carrega as árvores de fontes
Python reais de Mapper, Dev CLI, Loop, Fast, Prompt e Sprint. Esses projetos não
são reescritos como Rust. A instalação padrão não instala pacotes Python, não
clona `simplicio-*` e não procura checkouts locais.

O Runtime ainda precisa de um interpretador Python 3 disponível para executar
os fontes embutidos. A sessão do Google é obrigatória, inclusive durante o beta:

```bash
simplicio auth login
simplicio auth status --json
```

Depois da instalação, valide o bundle e guarde o relatório opcional:

```bash
simplicio ecosystem verify --json
```

O relatório identifica o digest/tamanho do arquivo-fonte embutido, a versão, o
commit de proveniência, o modo de implementação e o estado de compatibilidade
de cada componente. Adaptadores externos/portáveis continuam disponíveis
somente para fluxos explicitamente legados; eles não são parte do caminho
normal e não podem substituir o Runtime verificado pelo instalador.

## Building from Source

Requires Rust toolchain + C/C++ compiler (for llama.cpp):

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install libclang (needed for llama.cpp bindings)
pip install libclang

# Build
export LIBCLANG_PATH=$(python -c "import clang; print(clang.__path__[0] + '/native')")
cargo build --release

# The binary is at target/release/simplicio
```

### Lean Build (no local LLM)

If you only need the deterministic tools (map, edit, deliver, validate) without
the in-process LLM engine:

```bash
cargo build --release --no-default-features --features tui
```

## Uninstall

```bash
# Remove the binary
rm $(which simplicio)

# Remove data (optional)
rm -rf ~/.simplicio
rm -rf .simplicio  # per-project data
```

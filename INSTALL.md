# Installing Simplicio

Simplicio is a terminal-based AI coding agent and runtime. The PyPI package
installs a small launcher with no runtime package dependencies. The launcher
resolves its versioned GitHub Release, verifies the signed manifest and target
asset, and refuses to finish when the public release contract is incomplete.

## Quick Install

### macOS / Linux

```bash
python3 -m pip install --upgrade simplicio-installer
simplicio install
```

### Windows (PowerShell)

```powershell
py -m pip install --upgrade simplicio-installer
simplicio install
```

### Direct terminal installer (without PyPI)

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex
```

The PyPI package is the recommended bootstrap: it installs the launcher, verifies
the signed SHA256/Ed25519 Runtime release, and installs the platform binary.
If the Python script directory is not already on `PATH`, add it before running
`simplicio install`.

After the Runtime registers MCP/hooks for every detected client, both direct
installers also reconcile native packages for installed Codex, Claude Code and
Gemini CLI hosts. Those are the host surfaces with documented non-interactive
plugin or extension installers. Other detected IDEs and harnesses remain on the
verified Runtime MCP integration instead of receiving guessed commands. Set
`SIMPLICIO_INSTALL_HOST_PLUGINS=0` only in managed/bootstrap environments that
already installed the package.

Known installer incidents and regression sentinels are tracked in
[docs/INSTALL_ERROR_REGISTRY.md](docs/INSTALL_ERROR_REGISTRY.md).

### Manual Download

Download the binary for your platform from the
[releases](https://github.com/wesleysimplicio/simplicio/releases). Asset names
are canonical — see [`distribution/targets.json`](distribution/targets.json),
the single source of truth used by the local/manual publisher, both installers and
`simplicio-update-manifest.json`:

| Target id      | Platform               | Asset                       |
|----------------|------------------------|------------------------------|
| `macos-arm64`  | macOS (Apple Silicon)  | `simplicio-macos-arm64`      |
| `macos-x64`    | macOS (Intel)          | `simplicio-macos-x64`        |
| `linux-x64`    | Linux x86_64           | `simplicio-linux-x64`        |
| `windows-x64`  | Windows x86_64         | `simplicio-windows-x64.exe`  |

Verify the SHA256 checksum against the `sha256` field for your target in
`simplicio-update-manifest.json` (published alongside each release) before
running the binary. The installer places it under `~/.simplicio/bin/simplicio`
on macOS/Linux or `%USERPROFILE%\.simplicio\bin\simplicio.exe` on Windows.
Manual installs can use another PATH directory, naming the file `simplicio` (or
`simplicio.exe` on Windows).

The installer does not pin a version. It resolves the current `latest` release,
selects the canonical asset for the host, verifies its SHA256 and signature, and
then checks the Runtime readiness contract before completing installation.

## Doctor / Uninstall

Both installers are idempotent and expose a read-only health check plus an
explicit data-preserving uninstall:

~~~bash
# macOS / Linux
sh install.sh --doctor
sh install.sh --uninstall --keep-data
sh install.sh --uninstall --purge       # confirmation required; preserves ~/.simplicio/.env
~~~

~~~powershell
# Windows
pwsh install.ps1 -Doctor
pwsh install.ps1 -Uninstall -KeepData
pwsh install.ps1 -Uninstall -Purge      # confirmation required; preserves .env
~~~

Uninstall removes the installed binary and keeps user data by default. This
includes the 30-day Google login state at `~/.simplicio/login.json`, which is
outside the executable and survives upgrades. Even an explicit purge removes
only Simplicio-managed state and preserves `~/.simplicio/.env`, where provider
credentials may live; purge intentionally removes the login state too. Set
SIMPLICIO_CONFIRM_PURGE=1 for a non-interactive purge.

## Verify Installation

```bash
# macOS / Linux
simplicio version
simplicio auth login
simplicio auth status --json
simplicio ecosystem verify --json
```

```powershell
# Windows (PowerShell)
simplicio.exe version
simplicio.exe auth login
simplicio.exe auth status --json
simplicio.exe ecosystem verify --json
```

The version command confirms the installed binary; `auth status` confirms the
Google session required by the Runtime before MCP or authenticated commands.

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

A política do produto exige que o binário carregue as árvores de fontes Python
reais de Mapper, Dev CLI, Loop, Fast, Prompt e Sprint. Esses projetos não devem
ser reescritos como Rust, instalados via `pip` ou baixados como `simplicio-*`.
O instalador valida o release `latest` antes de concluir. Se o contrato indicar
`source_code_distributed=false` ou chave pública ausente, ele recusa o binário
em vez de instalar um snapshot incompleto. Uma sessão Google ativa pode ser
concluída depois da instalação; as chamadas MCP continuam bloqueadas até lá.

Quando uma release compatível estiver publicada, a sessão do Google será
obrigatória, inclusive durante o beta:

```bash
simplicio auth login
simplicio auth status --json
```

Depois da instalação, valide o contrato e guarde o relatório opcional:

```bash
simplicio version --json
simplicio ecosystem doctor --json
```

O relatório identifica a versão, o commit de proveniência, o contrato de
segurança e o estado de compatibilidade de cada componente. Adaptadores externos/portáveis continuam disponíveis
somente para fluxos explicitamente legados; eles não são parte do caminho
normal e não podem substituir o Runtime verificado pelo instalador.

## Login e MCP

O login Google é obrigatório, inclusive durante o beta:

```bash
simplicio auth login
simplicio auth status --json
```

The installer automatically asks the installed Runtime to detect and register
every supported MCP host. Registration uses the installed binary with
`serve --mcp --stdio`, writes native hooks only for verified host hook APIs,
preserves existing configuration, and does not depend on Google login.

Protected MCP operations still require an active Google session and entitlement.
Restart open clients after installation. To inspect or repair the registration,
run `simplicio mcp register --binary "$(command -v simplicio)" --json`. A
registration failure terminates the installer instead of reporting success.

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

Use the installer so the binary and transaction journal are handled together:

~~~bash
sh install.sh --uninstall --keep-data       # default, preserves ~/.simplicio
sh install.sh --uninstall --purge            # removes Simplicio state; preserves ~/.simplicio/.env
~~~

~~~powershell
pwsh install.ps1 -Uninstall -KeepData
pwsh install.ps1 -Uninstall -Purge            # preserves ~/.simplicio/.env
~~~

Interactive purge requires typing PURGE. For non-interactive use, set
SIMPLICIO_CONFIRM_PURGE=1. Project-local .simplicio data is not removed by
--keep-data; inspect the target before choosing --purge. Provider credentials
stored in `.simplicio/.env` are preserved by both installers.

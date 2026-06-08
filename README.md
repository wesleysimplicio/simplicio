# simplicio

A terminal-based AI coding agent.

Single binary, zero runtime deps. Just download and run.

## Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh
```

### Windows (PowerShell)

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"
```

### npm / pnpm / bun (cross-platform)

```bash
npm install -g simplicio
pnpm add -g simplicio
bun add -g simplicio
```

### PyPI (Python)

```bash
pip install simplicio
```

The binary is downloaded on first run and cached in `~/.cache/simplicio/bin/`.

### Homebrew (macOS / Linux)

```bash
brew install wesleysimplicio/tap/simplicio
```

### Arch Linux (AUR)

```bash
paru -S simplicio-bin
yay -S simplicio-bin
```

### Manual (any platform)

```bash
curl -sSfL https://github.com/wesleysimplicio/simplicio/releases/latest/download/simplicio-v0.7.0-macos-aarch64.tar.gz \
  | tar xz -C /tmp
sudo mv /tmp/simplicio /usr/local/bin/
```

## Quick start

```bash
# Start a conversation
simplicio chat "hello" --repo .

# Interactive REPL
simplicio chat --repl --repo .

# Check your setup
simplicio doctor --repo .

# List all commands
simplicio --help
```

## System requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Storage | 5 MB | 1.5 GB (with local LLM) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | any modern terminal | WezTerm / Alacritty / Ghostty |

## What's included

- **Chat REPL** — conversational AI assistant
- **Agent mode** — multi-turn task execution
- **App runner** — launch bundled apps (exo AI Cluster, MoneyPrinter, etc.)
- **Gateways** — Telegram, Discord, Slack, WhatsApp bridges
- **ACP adapter** — Agent Client Protocol server
- **CLI commands** — doctor, config, model, skill, map, and more

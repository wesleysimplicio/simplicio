# 🔥 Simplicio — The AI Agent That SAVES UP TO 96% OF YOUR TOKENS

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#-installation">Install</a> ·
  <a href="#-what-it-does">Features</a> ·
  <a href="#-token-savings">96% Savings</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Website</a>
</p>

<p align="center">
  <strong>🌍 Languages:</strong><br>
  <a href="README.md">🇬🇧 English</a> |
  <a href="READMEs/README.pt-BR.md">🇧🇷 Português</a> |
  <a href="READMEs/README.es-ES.md">🇪🇸 Español</a> |
  <a href="READMEs/README.fr-FR.md">🇫🇷 Français</a> |
  <a href="READMEs/README.ja-JP.md">🇯🇵 日本語</a> |
  <a href="READMEs/README.ko-KR.md">🇰🇷 한국어</a> |
  <a href="READMEs/README.zh-CN.md">🇨🇳 简体中文</a> |
  <a href="READMEs/README.it-IT.md">🇮🇹 Italiano</a> |
  <a href="READMEs/README.ru-RU.md">🇷🇺 Русский</a> |
  <a href="READMEs/README.pl-PL.md">🇵🇱 Polski</a> |
  <a href="READMEs/README.hi-IN.md">🇮🇳 हिन्दी</a> |
  <a href="READMEs/README.ar-SA.md">🇸🇦 العربية</a> |
  <a href="READMEs/README.he-IL.md">🇮🇱 עברית</a> |
  <a href="READMEs/README.ms-MY.md">🇲🇾 Bahasa Melayu</a> |
  <a href="READMEs/README.id-ID.md">🇮🇩 Bahasa Indonesia</a>
</p>

---

## ⚡ TL;DR

**Simplicio** is a terminal AI coding agent — a single binary that replaces your
entire AI-assisted development workflow: chat, code generation, repository
context, planning, local multi-agent orchestration (64 → 600 agents), and
evidence-backed PR delivery.

**Runs on your machine. Your code never leaves your control. Remote models are
optional, not required.**

> **🔥 Save up to 96% of tokens vs traditional agents — more than Caveman (65%) or RTK (80%).**
> Every interaction shows exactly how many tokens you saved. Single Rust binary, zero deps.

## 🚀 Installation

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex"
```

Done. One command downloads the Runtime binary, verifies its checksum, and
validates the embedded ecosystem. No Python package manager, sibling checkout,
or model configuration is required.

### Embedded ecosystem

The Runtime release is the distribution boundary. The generated binary carries
the native capability surfaces for:

| Capability | Binary surface |
|---|---|
| Mapper | `simplicio map` and MapperStore-backed recall |
| Dev CLI | Runtime edit/validate/deliver workflows |
| Loop | `simplicio loop` orchestration and decision flow |
| Fast | `simplicio fast` snapshot/search/context workflow |
| Prompt | Prompt contract and runtime prompt handling |
| Sprint | Sprint projection/compatibility contract |

Verify a release after installation:

```bash
simplicio ecosystem verify --json
```

The verification output includes the embedded component versions, upstream
provenance commits, implementation mode, and compatibility status. Updating the
Runtime release updates this bundle; the installer does not call or import the
`simplicio-*` repositories. Legacy Python adapters and portable Claude skills
may still be used explicitly, but they are outside the normal installation
path and never replace the verified Runtime binary.

### Plugin marketplace

This public repository also publishes the Simplicio Claude Code marketplace:

```text
/plugin marketplace add wesleysimplicio/simplicio
/plugin install simplicio-loop@simplicio
/plugin install simplicio-prompt@simplicio
/plugin install simplicio-sprint@simplicio
```

The plugin bundle is documented in [`PLUGIN.md`](PLUGIN.md). These are optional
Claude Code skill surfaces; they are not required to obtain the Runtime's
embedded ecosystem. When present, the skills call the Runtime through
`simplicio serve --mcp --stdio`.

---

## 💰 Token Savings — 96% is Real

**Without Simplicio:** every AI session rediscovers your repo, loads too much
context, repeats prompts, burns paid tokens.

**With Simplicio:**

| Optimization | Savings |
|---|---|
| 🗺️ **Repo Map** — compressed context instead of reading raw files | ~70% |
| 🧠 **Memory Recall** — known facts are not re-derived | ~80% |
| ✏️ **Deterministic Editing** — changes without spending LLM tokens | 100% (output) |
| 🏠 **Local LLM** — classification, summarization, low-risk edits | ~90% |
| 📡 **Remote LLM** — only for planning and complex decisions | ~85% |
| 🔀 **Local Fan-out** — 64→600 agents before scaling to cloud | ~95% |
| **💎 Combined: up to 96% total savings** | **~96%** |

**Every Simplicio response shows real savings:** `Simplicio: ~X tokens spent · saved ~Y (Z%)`

---

## 🎯 What It Does

| Command | Description | Tokens |
|---|---|---|
| `simplicio map --repo .` | Maps the repository for LLMs | ~70% savings |
| `simplicio memory "query"` | Neural recall (FTS + vectors) | ~80% savings |
| `simplicio edit '{...}'` | Deterministic file editing | **Zero tokens** |
| `simplicio coding-loop "task"` | Iterates until tests pass | Auto-repair |
| `simplicio deliver certify` | 5 quality gates before shipping | Deterministic |
| `simplicio run "task" --agents N` | Multi-agent orchestration | Local-first |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Approach** | Output style compression | Shell command proxy | **Full agent runtime** |
| **Max savings** | ~65% output tokens | ~80% on shell commands | **Up to 96% total** |
| **Input compression** | ❌ | ✅ (filtered) | ✅ **Repo map + neural memory** |
| **Output compression** | ✅ (caveman-speak) | ❌ | ✅ **Zero-token deterministic edits** |
| **Local LLM** | ❌ | ❌ | ✅ **Built-in llama.cpp** |
| **Multi-agent** | ❌ | ❌ | ✅ **64 → 600 local agents** |
| **Memory across sessions** | ❌ | ❌ | ✅ **FTS + vector recall** |
| **Evidence chain** | ❌ | ❌ | ✅ **sha256 sealed receipts** |
| **Language** | JS/Python (skill) | Rust (binary) | **Rust (single binary)** |
| **License** | MIT | Apache 2.0 | Proprietary |
| **Stars** | 72.5k | 62.2k | ⭐ **You're early** |

**Bottom line:** Caveman makes the AI *talk* less. RTK makes commands *output* less.
Simplicio makes the AI *think* less — by remembering, mapping, editing deterministically,
and running locally before ever touching a paid LLM.

| **Simplicio saves 96% where Caveman saves 65% and RTK saves 80%.** |

---

## 🏗️ Architecture

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime (Rust)
  |                                   |
  | 1. Orient                         | simplicio map
  | 2. Recall                         | simplicio memory
  | 3. Decide                         |
  | 4. Edit  ───────────────────────> | simplicio edit (0 tokens)
  | 5. Verify <─────────────────────  | simplicio deliver certify
  | 6. Iterate                        | simplicio coding-loop
```

**The LLM reasons. Simplicio executes deterministically.**

---

## ✨ Features

- 🏠 **Local-first** — built-in llama.cpp, scales to remote only when needed
- 🪜 **Tiered agents** — 64 → 100 → 200 → 600 local agents before paid cloud
- 🔇 **Shannon novelty gate** — filters redundant outputs (zero tokens on dedup)
- 🔒 **Sealed receipts** — sha256 per artifact, tamper-proof evidence chain
- 🛡️ **5 delivery gates** — acceptance, validation, run-verify, regression, self-review
- ⚡ **Action gate** — risk classification + blocklist for chat-initiated mutations
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Gateways** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Skill system** — loads and chains reusable capabilities
- 💾 **Memory DB** — persistent FTS + vector recall across sessions
- 🔀 **LLM router** — no LLM → local LLM → remote LLM automatically
- 🖥️ **Cross-platform** — macOS, Linux, Windows, single binary

---

## 🎁 Free Public Beta

**Deterministic commands are FREE forever:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**AI features are free during the public beta with no end date.**
Billing will be defined in future updates.

```bash
simplicio license status
```

---

## 📋 Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Storage | 5 MB | 1.5 GB (with local LLM) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | any modern terminal | WezTerm / Alacritty / Ghostty |

---

## 🧪 Testing this repo's tooling

This repo ships committed release binaries plus the packaging/tooling around
them (npm/PyPI wrappers, install scripts, a distribution-consistency checker).
The official command to run that tooling's unit test suite:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/unit -v --cov=scripts --cov-report=term-missing --cov-fail-under=85
```

See [docs/testing-strategy.md](docs/testing-strategy.md) for what's covered,
what's intentionally out of scope, and the plan for the rest of the testing
epic. See also [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 🌐 Ecosystem

- [Website](https://simpleti.com.br/simplicio/#start) — full docs, benchmarks, install
- [Discord](https://discord.gg/wM6tr7xVb) — community and support

---

## 📄 License

Proprietary. Binary free to download and use. AI features free during the
public beta. See [LICENSE](LICENSE).

---

## ⭐ Star History

<a href="https://www.star-history.com/?repos=wesleysimplicio%2Fsimplicio&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
 </picture>
</a>

---

## 💬 Community

- [Discord](https://discord.gg/wM6tr7xVb) — chat, support, early access
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — bugs and feature requests

---

<p align="center">
  <strong>🔥 Simplicio — Your code, your machine, 96% cheaper. 🔥</strong>
</p>

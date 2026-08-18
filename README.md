# 🔥 Simplicio — The AI Agent That SAVES UP TO 96% OF YOUR TOKENS

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <img src="https://img.shields.io/badge/license-Proprietary-red" alt="License">
</p>

<p align="center">
  <a href="#-installation">Install</a> ·
  <a href="#-login-and-entitlement">Login</a> ·
  <a href="#-simplicio-mcp">MCP</a> ·
  <a href="#-what-it-does">Features</a> ·
  <a href="#-benchmarks-and-token-savings">Benchmarks</a> ·
  <a href="https://simpleti.com.br/simplicio/">Website</a>
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

> **🔥 Save up to 96% of tokens on controlled workloads.**
> Simplicio records the baseline and proof type; the actual result depends on the task and model.

## 🚀 Installation

The official installers download the latest Runtime release from this
repository, verify the published SHA256 manifest, validate the Runtime release
contract, require an active Simplicio account, and attempt to register the local
MCP endpoint. They do not clone or download the `simplicio-*` sibling repositories.

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex"
```

The default install location is `~/.local/bin/simplicio` on macOS/Linux and
`%USERPROFILE%\.local\bin\simplicio.exe` on Windows. Add that directory to
your `PATH` if the installer prints a PATH warning, then open a new terminal.

The installer intentionally does not pin a release. Every normal installation
and update resolves GitHub's `latest` release, verifies it, and keeps the
existing user data. To use another install directory:

```bash
SIMPLICIO_BIN_DIR="$HOME/.local/bin" \
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh)"
```

PowerShell supports the equivalent `SIMPLICIO_BIN_DIR` setting. Keep checksum
verification enabled. Only set
`SIMPLICIO_ALLOW_UNVERIFIED=1` when you have deliberately accepted an
unverified artifact and understand the supply-chain risk.

The resolved latest release must contain the six Python projects in the binary,
enable Google login, and ship the configured public key plus signed update
artifacts. The installer refuses to finish when any of these requirements,
checksums, or the release manifest is missing. A Runtime source build or a
private candidate is not a substitute for a published, verifiable release.

Check the installation:

```bash
simplicio --version
simplicio version --json
simplicio ecosystem doctor --json
sh install.sh --doctor                 # when running from a checkout
```

The doctor command is read-only. Uninstalling is idempotent and preserves user
data under `~/.simplicio`:

```bash
sh install.sh --uninstall              # macOS/Linux
pwsh install.ps1 -Uninstall             # Windows
```

### What the binary contains

The Runtime is the intended distribution boundary. A compliant release embeds
the real Python source trees and a Runtime bridge for Mapper, Dev CLI, Loop,
Fast, Prompt, and Sprint. They remain Python projects; they are not rewritten
as Rust, and a normal installation must not download their repositories or
install them with `pip`.

Use `simplicio version --json` and `simplicio ecosystem doctor --json` after
every update to confirm that the resolved latest release contains the embedded
projects and active distribution contract.

## 🔐 Login and entitlement

Simplicio uses a Google-backed device login. The CLI receives revocable
Simplicio tokens; your Google password is entered only on Google. Login is
required before product commands, MCP, and the ecosystem integration can be used.

Public beta access may be free, but beta does not bypass the active-entitlement
check. When beta access ends, the entitlement must come from an active
subscription.

### First login (compatible releases)

On a compatible release, the installer starts the login flow when no active
session exists. To start it manually:

```bash
simplicio login google
```

The CLI prints a verification URL and a short device code, then waits. Open
the URL in a normal browser, choose **Continue with Google**, and finish the
Google authentication or passkey prompt. Do not paste the device code, Google
password, access token, refresh token, or client secret into an issue, chat,
terminal log, or public repository.

For scripts that need machine-readable polling output:

```bash
simplicio login google --json
```

The website flow is also available at
[`simpleti.com.br/simplicio/login`](https://simpleti.com.br/simplicio/login).

Confirm only the state, not the full credential payload:

```bash
simplicio auth status --json
```

The successful result must report an enabled identity, an active login state,
and an allowed entitlement. If it reports `status: disabled` or any inactive
state, the session is not usable. Do not treat a zero process exit code alone
as proof of authentication; inspect the structured fields.

To revoke the local session:

```bash
simplicio logout --json
```

Logout removes the local session; it does not delete your Simplicio account or
subscription.

## 🔌 Simplicio MCP

MCP (Model Context Protocol) is the interface that lets an AI client discover
and call Simplicio's governed local tools. The client supplies intent and
structured arguments; the Simplicio Runtime performs repository mapping,
memory recall, deterministic edits, validation, and execution under its
authentication and safety gates. MCP is an invocation surface, not a second
installation of Mapper, Loop, or the other projects.

The Runtime exposes these tools:

| Tool | Purpose |
|---|---|
| `simplicio_map` | Build a compact structural map of a repository |
| `simplicio_memory` | Recall indexed project memory (FTS/vector backends) |
| `simplicio_edit` | Apply a structured, deterministic file-edit plan |
| `simplicio_gate` | Check mission/effect gates before a mutation |
| `simplicio_validate` | Run contract-oriented validation for a task |
| `simplicio_run` | Execute a governed task through the Runtime |
| `simplicio_symbol` | Navigate symbols and declarations |
| `simplicio_search` | Search repository content semantically/structurally |
| `simplicio_read` | Read files through the compact Runtime surface |
| `simplicio_exec` | Run a supervised, compact external command |

The client should call `tools/list` at startup and use the returned schemas;
the table above is a quick orientation, not a substitute for live schemas.

### Codex: local HTTP/OAuth MCP

The installer runs `simplicio mcp register`, which registers the local
Streamable HTTP endpoint used by Codex:
`http://127.0.0.1:8787/mcp`.

1. Complete `simplicio login google` first.
2. Open Codex **Settings → MCP**.
3. Find the **simplicio** server and click **Authenticate**.
4. Complete the Google-backed Simplicio login in the browser.
5. Reload the MCP settings or restart the host if the tool list was already
   cached.

If the row is missing, register it again and reload Codex:

```bash
simplicio mcp register
```

The Runtime validates the bearer token and active entitlement on every MCP
request. A visible **Authenticate** button is therefore expected for the
OAuth-capable Codex server; it is not a replacement for the CLI login.

### Other MCP clients: local STDIO

For Claude Code, Cursor, VS Code, Cline, Continue, and similar clients, add a
server entry using the installed binary:

```json
{
  "mcpServers": {
    "simplicio": {
      "command": "simplicio",
      "args": ["serve", "--mcp", "--stdio"]
    }
  }
}
```

Typical configuration locations are:

| Client | File |
|---|---|
| Claude Code | `~/.claude/settings.json` |
| Cursor | `~/.cursor/mcp.json` |
| VS Code | `.vscode/mcp.json` |
| Cline | `~/.config/cline/mcp_settings.json` |
| Continue | `~/.continue/config.json` |

Reload the client after saving its configuration. STDIO is local and does not
need a manually copied bearer token, but the Runtime still requires an active
Simplicio login.

Smoke-test the local server:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \\
  | simplicio serve --mcp --stdio
```

The response should contain the ten tool definitions. If the command says
login is required, authenticate first; do not disable the gate or insert a
token into a config file.

### MCP request flow

```text
AI client → tools/list / tools/call
          → Simplicio Runtime auth + entitlement gate
          → map / memory / edit / validate / exec surface
          → structured result + evidence
```

For the complete client matrix and protocol notes, see
[`MCP-CONNECT.md`](MCP-CONNECT.md).

### Plugin marketplace

This public repository also publishes the Simplicio Claude Code marketplace:

```text
/plugin marketplace add wesleysimplicio/simplicio
/plugin install simplicio-loop@simplicio
/plugin install simplicio-prompt@simplicio
/plugin install simplicio-sprint@simplicio
```

The plugin bundle is documented in [`PLUGIN.md`](PLUGIN.md). These are optional
Claude Code skill surfaces; they are not proof that the Runtime binary contains
the ecosystem sources. When present, the skills call the Runtime through
`simplicio serve --mcp --stdio`.

---

## 📊 Benchmarks and token savings

The **up to 96%** figure is a headline maximum measured on controlled
workloads that combine repository mapping, memory recall, deterministic edits,
local routing, and local fan-out. It is not a promise that every task or model
will save 96%. The component percentages below are directional measurements;
they must not be added together.

| Mechanism | Reference result | What is measured |
|---|---:|---|
| 🗺️ Repo map | ~70% less context | Compact structural context versus raw file reads |
| 🧠 Memory recall | ~80% less re-derivation | Reused indexed facts versus rediscovering them |
| ✏️ Deterministic edit | 100% LLM output avoided | Structured file mutation without a generation step |
| 🏠 Local routing | ~90% fewer remote tokens | Classification/low-risk work handled locally |
| 📡 Remote routing | ~85% fewer remote tokens | Remote models used for planning and hard decisions |
| 🔀 Local fan-out | ~95% fewer cloud-agent tokens | Local agents used before cloud escalation |
| **Combined controlled workload** | **up to 96%** | Baseline-to-Simplicio total token comparison |

Every measured run should report its proof type and its baseline:
`saved = baseline_tokens - actual_tokens` and
`saving_percent = saved / baseline_tokens * 100`.

### Run the Runtime benchmark

All Runtime benchmark commands require an active login because they execute
through the governed Runtime:

```bash
simplicio benchmark run --sample --json       # deterministic fixture rows
simplicio benchmark run --json                # measured Runtime timings
simplicio benchmark savings --json            # savings-oriented summary
```

For a real model/provider comparison, keep the task, repository snapshot,
model, temperature, and cold/warm state constant. Record the baseline and the
Simplicio run separately. Replace the example counts below with the actual
provider-reported values:

```bash
simplicio savings record \
  --spent 120 \
  --baseline 300 \
  --source codex \
  --task "map, recall, edit, and validate a small change" \
  --proof-kind measured

simplicio savings report --repo . --json
simplicio savings prove --repo . --json
```

Use `measured` only when the provider reports actual usage. Use `benchmark` for
fixed fixture runs, `replayed` for a reproducible recorded run, and
`estimated` only for a heuristic. Never present an `estimated` result as a
measured benchmark. To compare a captured run with an explicit baseline:

```bash
simplicio savings compare \
  --with-simplicio .simplicio/runs/<run-id> \
  --without-simplicio baseline.json \
  --proof-kind measured
```

### Distribution/tooling benchmark

This public repository also benchmarks its release consistency checker. It is
separate from AI token savings:

```bash
python3 scripts/bench_verify_distribution_consistency.py
```

The reference run used for this README was 25 iterations on the maintainer's
macOS ARM64 machine: median `4.158 ms`, versus the committed baseline of
`11.625 ms`, within the default `+150%` regression budget. Wall-clock values
vary by machine and CI runner; the command and pass/fail threshold are the
portable result.

The stricter distribution benchmark is:

```bash
python3 scripts/benchmark_distribution.py --repetitions 5
```

It intentionally refuses to publish a metric when the distribution audit has
warnings. A warning is a release-hygiene failure, not evidence of a token
saving. Inspect the audit before retrying:

```bash
python3 scripts/verify_distribution_consistency.py
```

---

## 🎯 What It Does

| Command | Description | Cost/effect |
|---|---|---|
| `simplicio runtime map --repo . --for-llm markdown` | Maps a repository for an LLM | Compact context |
| `simplicio memory query "query" --json` | Recalls indexed project memory | Reuses known facts |
| `simplicio edit --plan plan.json --repo .` | Applies a deterministic edit plan | No generation step |
| `simplicio validate "task" --repo .` | Runs contract-oriented validation | Deterministic gates |
| `simplicio run "task" --repo . --agents N` | Runs a governed multi-agent task | Local-first routing |
| `simplicio sprint sprint.md --repo . --evidence` | Executes a sprint with evidence | Auditable delivery |
| `simplicio benchmark run --sample --json` | Runs fixed benchmark fixtures | Reproducible rows |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Approach** | Output style compression | Shell command proxy | **Full agent runtime** |
| **Published scope** | Output-token reduction | Shell-command output reduction | **End-to-end controlled workloads** |
| **Input compression** | ❌ | ✅ (filtered) | ✅ **Repo map + neural memory** |
| **Output compression** | ✅ (caveman-speak) | ❌ | ✅ **Zero-token deterministic edits** |
| **Local LLM** | ❌ | ❌ | ✅ **Built-in llama.cpp** |
| **Multi-agent** | ❌ | ❌ | ✅ **64 → 600 local agents** |
| **Memory across sessions** | ❌ | ❌ | ✅ **FTS + vector recall** |
| **Evidence chain** | ❌ | ❌ | ✅ **sha256 sealed receipts** |
| **Language** | JS/Python (skill) | Rust (binary) | **Rust (single binary)** |
| **License** | MIT | Apache 2.0 | Proprietary |

These tools measure different surfaces, so this repository does not claim an
apples-to-apples Caveman/RTK benchmark. Caveman reduces how much an agent says;
RTK reduces command output; Simplicio also reduces repeated context and
deterministic mutation work. Use the reproducible commands in the benchmark
section when comparing a real workload.

---

## 🏗️ Architecture

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime
  |                                   |
  | 1. Orient                         | runtime map / MCP
  | 2. Recall                         | memory query / MCP
  | 3. Decide                         |
  | 4. Edit  ───────────────────────> | structured edit
  | 5. Verify <─────────────────────  | validate / evidence
  | 6. Iterate                        | run / sprint
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

## 🔄 Updates, diagnostics, and troubleshooting

Re-running the official installer is the simplest update path. It downloads
the latest release, verifies the checksum, validates the Runtime release
contract, and keeps `~/.simplicio` user data. Re-running the installer keeps
the installation on GitHub's `latest` release. The installer refuses
to replace a working binary with a release that lacks the embedded bundle,
Google login activation, or the signed-update key.

When the Runtime's background update checks are enabled, it checks in its
scheduled windows, notifies once per release, stages the verified asset, and
applies it on the next session. The current release channel is checksum
verified. If the latest executable reports a missing public update key or an
unsigned channel, that mismatch is a release blocker, not a reason to disable
verification.

The Runtime also exposes an authenticated update surface:

```bash
simplicio update check --json
simplicio update apply --json
simplicio update status --json
simplicio update rollback --json
```

Use `rollback` only when you have a verified previous release and understand
the compatibility trade-off. After any update, repeat:

```bash
simplicio --version
simplicio version --json
simplicio ecosystem doctor --json
simplicio auth status --json
simplicio mcp register
```

Common failures:

| Symptom | Resolution |
|---|---|
| `login required` | Run `simplicio login google`; confirm `active: true`. |
| Codex has no **Authenticate** button | Run `simplicio mcp register`, then reload Codex MCP settings. |
| `tools/list` is empty or stale | Restart/reload the MCP host and verify its command resolves to the intended `simplicio` binary. |
| Runtime release contract fails | Wait for a release with embedded sources, enabled Google login, and a configured public update key; do not bypass the gate. |
| Google says the browser is not secure | Use a normal Safari/Chrome window for the Google step, not an embedded webview; never disable the account security gate. |
| A command behaves differently across terminals | Run `which simplicio`, `simplicio --version`, and inspect `PATH` for an older binary. |

Useful diagnostic commands:

```bash
simplicio doctor --json
simplicio self-test --json
simplicio status --json
simplicio security --json
```

When reporting a problem, include the operating system, architecture,
`simplicio --version`, the redacted output of `simplicio auth status --json`,
and `simplicio version --json` plus `simplicio ecosystem doctor --json`.
Remove email addresses, device codes,
authorization headers, and every credential before sharing logs.

---

## 🎁 Public Beta

**Deterministic commands are FREE forever:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

AI features may be free while the public beta flag is active. Login and an
active entitlement are still required; when beta access ends, the entitlement
must come from an active subscription.

```bash
simplicio license status
```

---

## 📋 Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Storage | ~35–50 MB for the release binary | 1.5 GB+ with a local LLM |
| OS | macOS Apple Silicon, Linux x64, Windows x64 | macOS ARM64 |
| Python | Not required for the embedded Runtime projects | Current CPython 3 for optional external adapters |
| Browser | Safari, Chrome, or another supported browser for Google login | Current Safari/Chrome |
| Terminal | any modern terminal | WezTerm / Alacritty / Ghostty |

---

## 🧪 Testing this repo's tooling

This repo ships committed release binaries plus the packaging/tooling around
them (npm/PyPI wrappers, install scripts, a distribution-consistency checker).
The official command to run that tooling's unit test suite:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/unit -v --cov=scripts --cov-report=term-missing --cov-fail-under=85
python3 scripts/bench_verify_distribution_consistency.py
python3 scripts/verify_distribution_consistency.py
```

See [docs/testing-strategy.md](docs/testing-strategy.md) for what's covered,
what's intentionally out of scope, and the plan for the rest of the testing
epic. The consistency audit may report release-hygiene warnings even when the
unit suite is green; resolve all release warnings before treating the stricter
`benchmark_distribution.py` gate as a release pass. See also
[CONTRIBUTING.md](CONTRIBUTING.md).

---

## 🌐 Ecosystem

- [Website](https://simpleti.com.br/simplicio/) — product overview, benchmarks, install
- [Discord](https://discord.gg/wM6tr7xVb) — community and support

---

## 📄 License

The root Runtime distribution and its release artifacts are proprietary.
The binary is free to download and use during the public beta; AI feature
access still requires an active Simplicio entitlement. Plugin subdirectories
may carry their own license files and terms.

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
  <strong>🔥 Simplicio — Your code, your machine, up to 96% fewer tokens on controlled workloads. 🔥</strong>
</p>

# Token capture — how Simplicio really intercepts tokens

The **Simplicio Token Monitor** (`hooks/simplicio_dashboard.py`, `:9090`) only *displays* numbers.
The actual capture is done by the **Simplicio capture proxy** — the native, self-contained engine
`engine/simplicio_engine.py` (stdlib only, fail-open), a local HTTP server that sits transparently
between a runtime and its LLM provider (forwarding to the real upstream, no model swap). Every request
that flows through it is logged with `tok_before` / `tok_after` / `tok_saved` and written to
`proxy_savings.json` (lifetime totals + per-request `history`). No proxy in the path → no capture.

## The one rule

> A runtime's tokens are captured **only when its LLM HTTP traffic flows through the proxy.**

So "make capture work for runtime X" always means one of: route X's API base URL through the proxy,
or install the engine's durable integration for X. Some runtimes can do neither.

## Providers we intercept (the real breadth)

Interception is really about **providers**, not apps. From the Simplicio Agent/OpenCode provider lists
(`app/providers.json`, derived from `~/.hermes/models_dev_cache.json` + the active providers),
**141 of 144 providers (98%)** are interceptable — every OpenAI-compatible endpoint (139) plus
Anthropic (2). Only 3 are Google-native (`google`, `vertex`, `gemini`) and need their own shim.
So routing a client through the capture proxy intercepts essentially **any** provider it talks to
(deepseek, openai, openrouter, xai, groq, mistral, fireworks, cerebras, …). The dashboard shows the
live `141/144` count.

## Cross-platform (macOS · Linux · Windows)

The stack runs on all three:

| Piece | macOS | Linux | Windows |
|---|---|---|---|
| services (proxy/monitor/tray) | launchd (`setup_simplicio.sh`) | systemd `--user` | Startup-folder launchers |
| tray/widget | rumps (menu-bar text) | pystray | pystray |
| always-capture wire | `~/.zshrc` / `~/.bashrc` (`ANTHROPIC_BASE_URL` + `OPENAI_BASE_URL`) | shell profile | `setx` both |

One cross-platform entrypoint: `python3 scripts/install_services.py {install|uninstall|status|wire|unwire}`
detects the OS and does the right thing (resolves the engine binary, registers the three services,
routes `OPENAI_BASE_URL`). The tray (`app/simplicio_tray.py`) auto-selects rumps on macOS and pystray
elsewhere, with a headless print fallback.

## Interceptability matrix (honest)

| Tier | Runtimes | How capture is wired | Notes |
|---|---|---|---|
| **native** | Claude · Codex · VS Code (Copilot) · OpenClaw | `simplicio-cli capture init <client>` (engine's durable hooks + **transparent** provider routing) | Forwards to the client's REAL provider — does not change the model. |
| **base-url** | Simplicio Agent · Cursor · OpenCode | point the client's model `base_url` at `http://127.0.0.1:<port>` (OpenAI/Anthropic-compatible) | Simplicio Agent is wired this way today (→ DeepSeek). |
| **none** | Gemini · Kiro · Antigravity | — | Proprietary Google/AWS APIs the proxy can't speak; not interceptable yet. |

**7 of 10 runtimes are interceptable; 3 are not.** The dashboard shows this live with per-runtime
logos and tier badges, and dims the non-interceptable ones.

## Critical caveat — proxy backend

A single proxy forwards to **one upstream**. The proxy installed by `setup_simplicio.sh` targets
DeepSeek (for Simplicio Agent). If you route a *different* client (e.g. Codex) through that same proxy, its
requests also go to DeepSeek — that's a **model swap, not transparent capture**.

For real multi-runtime capture you want the engine's **transparent provider routing** (each client
forwarded to its own real provider). That is exactly what `simplicio-cli capture init <client>` sets up.
Wire each client through `init`; don't hand-point everything at the DeepSeek proxy.

## Commands

```bash
bash scripts/simplicio-capture.sh status        # read-only: proxy + per-client routing + lifetime savings
bash scripts/simplicio-capture.sh init           # durable capture for every INSTALLED native client
bash scripts/simplicio-capture.sh init claude    # one client
```

`status` runs the engine's `doctor`: proxy reachability/version, per-client routing, and lifetime
tokens/$ saved. `init` installs the transparent integration for each installed native client.

## Always-on (so it "just works")

`setup_simplicio.sh` registers two launchd services that auto-start and self-restart (KeepAlive):

- `ai.simplicio.proxy` — the capture proxy (data source).
- `ai.simplicio.token-monitor` — the dashboard on `:9090`.

After install, capture is active for any client wired via `init`/base-url, the proxy survives
reboots, and the monitor is always live. Verify any time with `scripts/simplicio-capture.sh status`.

## The token-economy module (one entrypoint)

`scripts/simplicio-economy.sh` ties the whole always-on stack together so token savings work
**after install without ever invoking simplicio-loop**:

```bash
bash scripts/simplicio-economy.sh status              # capture proxy + monitor + tray + operator + savings
bash scripts/simplicio-economy.sh up                  # ensure all three services are running
bash scripts/simplicio-economy.sh wire                # route Claude + Codex/OpenAI through the proxy (measured)
bash scripts/simplicio-economy.sh unwire              # reverse the routing
bash scripts/simplicio-economy.sh capture openai      # ad-hoc transparent proxy → api.openai.com (no model swap)
bash scripts/simplicio-economy.sh capture anthropic
```

`status` reports: capture proxy, token monitor (`:9090`), menu-bar tray, the deterministic operator
`simplicio-dev-cli`, the **auto-capture wiring** (Claude · Codex/OpenAI · Simplicio Agent), and lifetime savings.

### `wire` — all three runtimes measured, automatically

`wire` (run by `setup_simplicio.sh` at the end of install) makes the monitor measure **Simplicio
Agent + Claude + Codex** with no manual step. It sets, in the shell profile (cross-platform via
`install_services.py wire` — `setx` on Windows):

- `OPENAI_BASE_URL = http://127.0.0.1:<port>/v1` → Codex / Cursor / OpenCode / any OpenAI client
- `ANTHROPIC_BASE_URL = http://127.0.0.1:<port>` → Claude (**no `/v1`** — Claude appends `/v1/messages`)

The engine then **routes each model to its REAL provider** (`claude-*`→Anthropic, `gpt-*`→OpenAI,
`deepseek-*`→DeepSeek) — verified live: an unauth'd request for each returned that provider's own
auth error, proving transparent forwarding with **no model swap**. Effective on the next shell/tool
launch. Idempotent, reversible (`unwire`, plus a one-time `~/.zshrc.simplicio-bak`), and opt-outable
(`SIMPLICIO_NO_WIRE=1`). Without wiring, the economy still applies — the monitor just won't tally
Claude/Codex tokens.

## Verified — transparent capture is real

A **transparent** capture proxy (`--openai-api-url https://api.openai.com/v1`) was stood up and a real
`gpt-5.4` request sent through it: it returned a genuine OpenAI response (`model
gpt-5.4-2026-03-05`, `usage` 108+4 tokens) and the proxy's own `/stats` recorded
`api_requests: 4`, `primary_model: gpt-4o-mini`, `total_tokens_before: 124`. Proof that routing an
OpenAI client through the transparent proxy **captures its tokens without changing its model** — the
correct way to capture Codex/Cursor/OpenCode, kept separate from the Simplicio Agent→DeepSeek proxy.

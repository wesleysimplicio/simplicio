# 🔥 Simplicio — O Agente de IA que ECONOMIZA ATÉ 96% DOS SEUS TOKENS

<p align="center">
  <img src="../assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#-instalação">Instalação</a> ·
  <a href="#-o-que-faz">Features</a> ·
  <a href="#-token-savings">96% Economia</a> ·
  <a href="https://simpleti.com.br/simplicio/">Website</a>
</p>

<p align="center">
  <strong>🌍 Idiomas:</strong><br>
  <a href="../README.md">🇬🇧 English</a> |
  <a href="README.pt-BR.md">🇧🇷 Português</a> |
  <a href="README.es-ES.md">🇪🇸 Español</a> |
  <a href="README.fr-FR.md">🇫🇷 Français</a> |
  <a href="README.ja-JP.md">🇯🇵 日本語</a> |
  <a href="README.ko-KR.md">🇰🇷 한국어</a> |
  <a href="README.zh-CN.md">🇨🇳 简体中文</a> |
  <a href="README.it-IT.md">🇮🇹 Italiano</a> |
  <a href="README.ru-RU.md">🇷🇺 Русский</a> |
  <a href="README.pl-PL.md">🇵🇱 Polski</a> |
  <a href="README.hi-IN.md">🇮🇳 हिन्दी</a> |
  <a href="README.ar-SA.md">🇸🇦 العربية</a> |
  <a href="README.he-IL.md">🇮🇱 עברית</a> |
  <a href="README.ms-MY.md">🇲🇾 Bahasa Melayu</a> |
  <a href="README.id-ID.md">🇮🇩 Bahasa Indonesia</a>
</p>

---

## ⚡ Resumo

**Simplicio** é um agente de IA de terminal — um único binário que substitui
seu workflow inteiro de desenvolvimento assistido: chat, geração de código,
contexto do repositório, planejamento, orquestração multi-agente local
(64 → 600 agentes) e entrega de PRs com evidências.

**Roda na sua máquina. Seu código nunca sai do seu controle. Modelos remotos
são opcionais, não obrigatórios.**

> **🔥 Economize até 96% de tokens vs agentes tradicionais — mais que Caveman (65%) ou RTK (80%).**
> Cada interação mostra exatamente quantos tokens você economizou. Binário único em Rust, zero deps.

---

## 🚀 Instalação

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"
```

Pronto. Um comando. Nada de package manager, nada de configurar modelo.

---

## 💰 Token Savings — 96% é Real

**Sem Simplicio:** cada sessão de IA re-descobre seu repo, carrega contexto
demais, repete prompts, torra tokens pagos.

**Com Simplicio:**

| Otimização | Economia |
|---|---|
| 🗺️ **Repo Map** — contexto comprimido em vez de ler arquivos brutos | ~70% |
| 🧠 **Memory Recall** — fatos conhecidos não são re-derivados | ~80% |
| ✏️ **Edição Determinística** — alterações sem gastar tokens do LLM | 100% (output) |
| 🏠 **LLM Local** — classificação, sumarização, edições de baixo risco | ~90% |
| 📡 **LLM Remoto** — só para planejamento e decisões complexas | ~85% |
| 🔀 **Fan-out Local** — 64→600 agentes antes de escalar pra cloud | ~95% |
| **💎 Combinado: até 96% de economia total** | **~96%** |

**Cada resposta do Simplicio mostra a economia real:** `Simplicio: ~X tokens spent · saved ~Y (Z%)`

---

## 🎯 O Que Faz

| Comando | Descrição | Tokens |
|---|---|---|
| `simplicio map --repo .` | Mapeia o repositório para LLMs | ~70% savings |
| `simplicio memory "query"` | Recall neural (FTS + vetores) | ~80% savings |
| `simplicio edit '{...}'` | Edição determinística de arquivos | **Zero tokens** |
| `simplicio coding-loop "task"` | Itera até testes passarem | Auto-repair |
| `simplicio deliver certify` | 5 gates de qualidade antes de shipping | Determinístico |
| `simplicio run "task" --agents N` | Orquestração multi-agente | Local-first |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Abordagem** | Compressão de estilo | Proxy de comandos shell | **Runtime de agente completo** |
| **Economia máx.** | ~65% output tokens | ~80% em comandos shell | **Até 96% total** |
| **Compressão de input** | ❌ | ✅ (filtrado) | ✅ **Repo map + memória neural** |
| **Compressão de output** | ✅ (fala de caverna) | ❌ | ✅ **Edição determinística zero-token** |
| **LLM Local** | ❌ | ❌ | ✅ **llama.cpp integrado** |
| **Multi-agente** | ❌ | ❌ | ✅ **64 → 600 agentes locais** |
| **Memória entre sessões** | ❌ | ❌ | ✅ **FTS + vector recall** |
| **Cadeia de evidências** | ❌ | ❌ | ✅ **recibos sha256 selados** |
| **Linguagem** | JS/Python (skill) | Rust (binário) | **Rust (binário único)** |
| **Licença** | MIT | Apache 2.0 | Proprietária |
| **Stars** | 72.5k | 62.2k | ⭐ **Você chegou cedo** |

**Resumo:** Caveman faz a IA *falar* menos. RTK faz comandos *gerarem* menos output.
Simplicio faz a IA *pensar* menos — lembrando, mapeando, editando deterministicamente
e rodando local antes de tocar em qualquer LLM pago.

| **Simplicio economiza 96% onde Caveman economiza 65% e RTK economiza 80%.** |

---

## 🏗️ Arquitetura

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

**O LLM raciocina. O Simplicio executa deterministicamente.**

---

## ✨ Features

- 🏠 **Local-first** — llama.cpp integrado, escala pra remoto só quando necessário
- 🪜 **Agente escalonado** — 64 → 100 → 200 → 600 agentes locais antes de cloud paga
- 🔇 **Shannon novelty gate** — filtra outputs redundantes (zero tokens em dedup)
- 🔒 **Sealed receipts** — sha256 por artefato, cadeia de evidências à prova de adulteração
- 🛡️ **5 delivery gates** — acceptance, validation, run-verify, regression, self-review
- ⚡ **Action gate** — classificação de risco + blocklist para mutações iniciadas no chat
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Gateways** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Skill system** — carrega e encadeia capacidades reutilizáveis
- 💾 **Memory DB** — FTS persistente + vector recall entre sessões
- 🔀 **LLM router** — sem LLM → LLM local → LLM remoto automático
- 🖥️ **Cross-platform** — macOS, Linux, Windows, mesmo binário

---

## 🎁 Beta Pública Gratuita

**Comandos determinísticos são GRATUITOS para sempre:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Features de IA gratuitas durante a beta pública sem data de término.**
Cobrança será definida em atualizações futuras.

```bash
simplicio license status
```

---

## 📋 Requisitos

| Requisito | Mínimo | Recomendado |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Armazenamento | 5 MB | 1.5 GB (com LLM local) |
| SO | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | qualquer terminal moderno | WezTerm / Alacritty / Ghostty |

---

## 🌐 Ecossistema

- [Website](https://simpleti.com.br/simplicio/) — docs completas, benchmarks, instalação
- [Discord](https://discord.gg/simplicio) — comunidade e suporte

---

## 📄 Licença

Proprietária. Binário gratuito para download e uso. Features de IA gratuitas
durante a beta pública. Veja [LICENSE](LICENSE).

---

<p align="center">
  <strong>🔥 Simplicio — Seu código, sua máquina, 96% mais barato. 🔥</strong>
</p>

# 🔥 Simplicio — O Agente de IA que ECONOMIZA ATÉ 96% DOS SEUS TOKENS

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — Agente de IA para codificação" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Último Lançamento"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Estrelas"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="Licença"></a>
</p>

<p align="center">
  <a href="#-instalação">Instalar</a> ·
  <a href="#-o-que-faz">Funcionalidades</a> ·
  <a href="#-economia-de-tokens">96% de Economia</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Site</a>
</p>

<p align="center">
  <strong>🌍 Idiomas:</strong><br>
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

**Simplicio** é um agente de IA de codificação para terminal — um único binário que substitui
todo o seu fluxo de desenvolvimento assistido por IA: chat, geração de código, contexto
de repositório, planejamento, orquestração local multi-agente (64 → 600 agentes) e
entrega de PR com evidências verificáveis.

**Roda na sua máquina. Seu código nunca sai do seu controle. Modelos remotos são
opcionais, não obrigatórios.**

> **🔥 Economize até 96% de tokens comparado a agentes tradicionais — mais que Caveman (65%) ou RTK (80%).**
> Cada interação mostra exatamente quantos tokens você economizou. Um único binário Rust, zero dependências.

## 🚀 Instalação

### Instalar pelo plugin do Codex

Se você usa o Codex, pode instalar o Simplicio como um plugin. Adicione o Marketplace público, instale o plugin e inicie uma nova sessão do Codex; o plugin instala e inicializa o Runtime do Simplicio e disponibiliza suas skills e ferramentas MCP.

```bash
codex plugin marketplace add wesleysimplicio/simplicio --ref master
codex plugin add simplicio@simplicio-codex
```

Use o pacote oficial do PyPI. Ele instala o launcher Python, valida a release
assinada do Runtime e instala o binário correto para macOS, Linux ou Windows.

### Todos os sistemas via PyPI

macOS / Linux:

```bash
python3 -m pip install --upgrade simplicio-installer
simplicio install
simplicio version
simplicio auth login
simplicio auth status --json
simplicio ecosystem verify --json
```

No Windows (PowerShell), use `py -m pip install --upgrade simplicio-installer`
no lugar de `python3 -m pip ...`. O token do PyPI fica somente no ambiente de
publicação; nunca é copiado para o repositório.

### Instalação direta (sem PyPI)

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex
```

O launcher instala o Runtime verificado em `~/.local/bin/simplicio` no
macOS/Linux ou `%USERPROFILE%\.local\bin\simplicio.exe` no Windows. Garanta que
o diretório de scripts do Python e esse diretório estejam no `PATH`; o launcher
não altera o perfil do shell. O login Google é necessário antes de usar o MCP
ou comandos autenticados.

---

## 💰 Economia de Tokens — 96% é Real

### Prova medida no OpenRouter — criação + edição de CRUD (2026-09-01)

Uma execução controlada em duas etapas usou o OpenRouter e o modelo
`deepseek/deepseek-v4-flash-0731` nos dois fluxos (`seed=42`, `temperature=0`,
raciocínio desativado). A criação foi o controle. Na edição, o fluxo normal
reenviou e regenerou todo o HTML; o Simplicio enviou um plano compacto e o
aplicou via MCP.

| Etapa de edição | Sem Simplicio | Com Simplicio MCP | Redução |
|---|---:|---:|---:|
| Tokens de entrada | 5.430 | 415 | 92,36% |
| Tokens de saída | 5.144 | 58 | 98,87% |
| Tokens totais | 10.574 | 473 | **95,53%** |
| Custo no OpenRouter | US$ 0,00078559 | US$ 0,00002654 | **96,62%** |
| Latência | 17.615,78 ms | 1.296,79 ms | 92,64% |
| Verificações de qualidade | Falhou | Passou | — |

Nas duas etapas, o total caiu de 16.043 para 6.175 tokens (**61,51% menos**) e
de US$ 0,00132192 para US$ 0,00058617 (**55,66% menos**). O controle de criação
gastou 4,26% mais tokens com Simplicio; por isso, a edição — e não o controle —
é a evidência principal. É um único par de fluxos medido, não garantia universal
nem comparação de saídas idênticas. Cache e raciocínio ficaram em zero. Repita
o teste antes de alegações estatísticas. [Evidência legível por máquina](../docs/evidence/openrouter-deepseek-v4-crud-2026-09-01.json).

**Sem Simplicio:** a cada sessão de IA o repositório é redescoberto, carrega contexto
demais, repete prompts, queima tokens pagos.

**Com Simplicio:**

| Otimização | Economia |
|---|---|
| 🗺️ **Mapa do Repositório** — contexto comprimido em vez de ler arquivos brutos | ~70% |
| 🧠 **Memória Recorrente** — fatos conhecidos não são redescobertos | ~80% |
| ✏️ **Edição Determinística** — mudanças sem gastar tokens de LLM | 100% (saída) |
| 🏠 **LLM Local** — classificação, sumarização, edições de baixo risco | ~90% |
| 📡 **LLM Remoto** — apenas para planejamento e decisões complexas | ~85% |
| 🔀 **Fan-out Local** — 64→600 agentes antes de escalar para a nuvem | ~95% |
| **💎 Combinado: até 96% de economia total** | **~96%** |

**Toda resposta do Simplicio mostra a economia real:** `Simplicio: ~X tokens gastos · economizou ~Y (Z%)`

---

## 🎯 O Que Faz

| Comando | Descrição | Tokens |
|---|---|---|
| `simplicio map --repo .` | Mapeia o repositório para LLMs | ~70% de economia |
| `simplicio memory "consulta"` | Recuperação neural (FTS + vetores) | ~80% de economia |
| `simplicio edit '{...}'` | Edição determinística de arquivos | **Zero tokens** |
| `simplicio coding-loop "tarefa"` | Itera até os testes passarem | Auto-reparo |
| `simplicio deliver certify` | 5 portais de qualidade antes do envio | Determinístico |
| `simplicio run "tarefa" --agents N` | Orquestração multi-agente | Local-first |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Abordagem** | Compressão de estilo de saída | Proxy de comandos shell | **Runtime completo de agente** |
| **Economia máxima** | ~65% tokens de saída | ~80% em comandos shell | **Até 96% total** |
| **Compressão de entrada** | ❌ | ✅ (filtrada) | ✅ **Mapa do repositório + memória neural** |
| **Compressão de saída** | ✅ (fala de caverna) | ❌ | ✅ **Edições determinísticas de zero token** |
| **LLM Local** | ❌ | ❌ | ✅ **llama.cpp embutido** |
| **Multi-agente** | ❌ | ❌ | ✅ **64 → 600 agentes locais** |
| **Memória entre sessões** | ❌ | ❌ | ✅ **FTS + recall vetorial** |
| **Cadeia de evidências** | ❌ | ❌ | ✅ **Recibos lacrados com sha256** |
| **Linguagem** | JS/Python (skill) | Rust (binário) | **Rust (binário único)** |
| **Licença** | MIT | Apache 2.0 | Proprietária |
| **Estrelas** | 72.5k | 62.2k | ⭐ **Você é dos primeiros** |

**Conclusão:** Caveman faz a IA *falar* menos. RTK faz os comandos *saírem* menos.
Simplicio faz a IA *pensar* menos — ao lembrar, mapear, editar deterministicamente
e rodar localmente antes de tocar num LLM pago.

| **Simplicio economiza 96% enquanto Caveman economiza 65% e RTK economiza 80%.** |

---

## 🏗️ Arquitetura

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime (Rust)
  |                                   |
  | 1. Orientar                       | simplicio map
  | 2. Recuperar                      | simplicio memory
  | 3. Decidir                        |
  | 4. Editar ──────────────────────> | simplicio edit (0 tokens)
  | 5. Verificar <─────────────────── | simplicio deliver certify
  | 6. Iterar                         | simplicio coding-loop
```

**O LLM raciocina. O Simplicio executa deterministicamente.**

---

## ✨ Funcionalidades

- 🏠 **Local-first** — llama.cpp embutido, escala para remoto somente quando necessário
- 🪜 **Agentes em camadas** — 64 → 100 → 200 → 600 agentes locais antes da nuvem paga
- 🔇 **Portão de novidade Shannon** — filtra saídas redundantes (zero tokens em dedup)
- 🔒 **Recibos lacrados** — sha256 por artefato, cadeia de evidências à prova de adulteração
- 🛡️ **5 portais de entrega** — aceitação, validação, execução-verificação, regressão, auto-revisão
- ⚡ **Portão de ação** — classificação de risco + lista de bloqueio para mutações iniciadas por chat
- 🔌 **MCP/ACP** — Protocolo de Contexto de Modelo + Protocolo de Cliente Agente
- 🌐 **Gateways** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Sistema de skills** — carrega e encadeia capacidades reutilizáveis
- 💾 **Banco de memória** — FTS persistente + recall vetorial entre sessões
- 🔀 **Roteador de LLM** — sem LLM → LLM local → LLM remoto automaticamente
- 🖥️ **Multiplataforma** — macOS, Linux, Windows, binário único

---

## 🎁 Beta Público Gratuito

**Comandos determinísticos são GRATUITOS para sempre:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Funcionalidades de IA são gratuitas durante o beta público sem data de término.**
A cobrança será definida em atualizações futuras.

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

- [Site](https://simpleti.com.br/simplicio/#start) — documentação completa, benchmarks, instalação
- [Discord](https://discord.gg/wM6tr7xVb) — comunidade e suporte

---

## 📄 Licença

Proprietária. Binário gratuito para baixar e usar. Funcionalidades de IA gratuitas
durante o beta público. Consulte [LICENSE](LICENSE).

---

## ⭐ Histórico de Estrelas

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="Gráfico do Histórico de Estrelas" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 Comunidade

- [Discord](https://discord.gg/wM6tr7xVb) — chat, suporte, acesso antecipado
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — bugs e pedidos de funcionalidades

---

<p align="center">
  <strong>🔥 Simplicio — Seu código, sua máquina, 96% mais barato. 🔥</strong>
</p>

# simplicio

**Um binário. Zero configuração. Seu agente de IA para programação no terminal.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Resumo

`simplicio` é um agente de IA para programação em um único binário nativo de terminal. Baixe, execute e tenha um ambiente completo de desenvolvimento assistido por IA — chat, geração de código, mapeamento de contexto do repositório, planejamento de tarefas, orquestração de LLM local e entrega de PRs baseada em evidências.

Seu código fica na sua máquina. Modelos remotos são opcionais.

## Instalação

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh

# Homebrew
brew install wesleysimplicio/tap/simplicio

# npm / pnpm / bun
npm install -g simplicio

# Windows (PowerShell)
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"
```

## Comece rápido

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "tarefa" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Funcionalidades

Chat REPL, modo agente autônomo, mapeamento de repositório, LLM local (llama.cpp), execução paralela de 50–600+ subagentes, pipeline de evidências, automação de PR, gateways (Telegram, Discord, Slack, WhatsApp), servidor MCP e ACP, sistema de skills, memória persistente, roteador de LLM (sem LLM → local → remoto), edição determinística sem tokens de LLM e suporte a macOS, Linux e Windows.

## Beta público

**Tudo liberado gratuitamente até 30/06/2026.** Após o beta, recursos de IA exigem assinatura. Comandos determinísticos (map, validate, edit, deliver, checkpoint) continuam gratuitos para sempre.

Mais: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

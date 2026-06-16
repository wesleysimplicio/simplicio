# simplicio

**Un binario. Sin configuración. Tu agente de IA para programar en la terminal.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Resumen

`simplicio` es un agente de IA para programación en un solo binario nativo de terminal. Descárgalo, ejecútalo y tendrás un entorno completo de desarrollo asistido por IA — chat, generación de código, mapeo de contexto del repositorio, planificación de tareas, orquestación de LLM local y entrega de PRs basada en evidencia.

Tu código se queda en tu máquina. Los modelos remotos son opcionales.

## Instalación

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

## Inicio rápido

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "tarea" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Funcionalidades

Chat REPL, modo agente autónomo, mapeo de repositorio, LLM local (llama.cpp), ejecución paralela de 50–600+ subagentes, pipeline de evidencia, automatización de PR, gateways (Telegram, Discord, Slack, WhatsApp), servidor MCP y ACP, sistema de skills, memoria persistente, enrutador de LLM (sin LLM → local → remoto), edición determinística sin tokens de LLM y soporte para macOS, Linux y Windows.

## Beta público

**Todo desbloqueado gratis durante la beta pública sin fecha de término.** La facturación se definirá en futuras actualizaciones. Los comandos determinísticos (map, validate, edit, deliver, checkpoint) son gratuitos para siempre. Los comandos determinísticos (map, validate, edit, deliver, checkpoint) son gratuitos para siempre.

Más: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/#start)

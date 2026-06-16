# simplicio

**Un binario. Zero configurazione. Il tuo agente AI per programmare nel terminale.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Riassunto

`simplicio` è un agente AI per programmazione in un singolo binario nativo per terminale. Scaricalo, eseguilo e avrai un ambiente di sviluppo assistito completo — chat, generazione di codice, mappatura del contesto del repository, pianificazione delle attività, orchestrazione di LLM locale e consegna di PR basata su evidenze.

Il codice resta sulla tua macchina. I modelli remoti sono opzionali.

## Installazione

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

## Avvio rapido

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "compito" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Funzionalità

Chat REPL, modalità agente autonomo, mappatura repository, LLM locale (llama.cpp), esecuzione parallela di 50–600+ subagenti, pipeline di evidenze, automazione PR, gateway (Telegram, Discord, Slack, WhatsApp), server MCP e ACP, sistema di skill, memoria persistente, router LLM (nessun LLM → locale → remoto), editing deterministico senza token LLM, supporto per macOS, Linux e Windows.

## Beta pubblica

**Tutto sbloccato gratuitamente durante la beta pubblica senza data di termine.** La fatturazione sarà definita nei prossimi aggiornamenti. I comandi deterministici (map, validate, edit, deliver, checkpoint) rimangono gratuiti per sempre. I comandi deterministici (map, validate, edit, deliver, checkpoint) rimangono gratuiti per sempre.

Altro: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

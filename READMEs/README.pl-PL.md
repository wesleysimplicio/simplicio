# simplicio

**Jeden binarny plik. Zero konfiguracji. Twój agent AI do kodowania w terminalu.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Streszczenie

`simplicio` to pojedynczy, natywny binarny agent AI do kodowania w terminalu. Pobierz go, uruchom i uzyskaj pełne środowisko programistyczne wspomagane AI — czat, generowanie kodu, mapowanie kontekstu repozytorium, planowanie zadań, orkiestrację lokalnego LLM i dostarczanie PR-ów oparte na dowodach.

Twój kod pozostaje na twojej maszynie. Modele zdalne są opcjonalne.

## Instalacja

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

## Szybki start

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "zadanie" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Funkcje

Chat REPL, tryb autonomicznego agenta, mapowanie repozytorium, lokalny LLM (llama.cpp), równoległe wykonanie 50–600+ pod-agentów, potok dowodów, automatyzacja PR, bramy (Telegram, Discord, Slack, WhatsApp), serwer MCP i ACP, system umiejętności, trwała pamięć, router LLM (bez LLM → lokalnie → zdalnie), deterministyczna edycja bez tokenów LLM, obsługa macOS, Linux i Windows.

## Publiczna beta

**Wszystko odblokowane za darmo do 30 czerwca 2026.** Po zakończeniu bety funkcje AI wymagają subskrypcji. Polecenia deterministyczne (map, validate, edit, deliver, checkpoint) pozostają darmowe na zawsze.

Więcej: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

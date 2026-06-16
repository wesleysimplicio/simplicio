# simplicio

**Один бинарник. Без настройки. Ваш ИИ-агент для программирования в терминале.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Кратко

`simplicio` — это один бинарник, нативный ИИ-агент для программирования в терминале. Скачайте и запустите — получите полную среду разработки с ИИ-помощью: чат, генерация кода, картирование контекста репозитория, планирование задач, оркестрация локальной LLM и создание PR на основе доказательств.

Ваш код остаётся на вашей машине. Удалённые модели опциональны.

## Установка

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

## Быстрый старт

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "задача" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Возможности

Chat REPL, автономный режим агента, картирование репозитория, локальная LLM (llama.cpp), параллельное выполнение 50–600+ под-агентов, конвейер доказательств, автоматизация PR, шлюзы (Telegram, Discord, Slack, WhatsApp), сервер MCP и ACP, система навыков, постоянная память, маршрутизатор LLM (без LLM → локально → удалённо), детерминированное редактирование без токенов LLM, поддержка macOS, Linux и Windows.

## Публичная бета

**Всё бесплатно до 30 июня 2026 г.** После беты функции ИИ требуют подписки. Детерминированные команды (map, validate, edit, deliver, checkpoint) остаются бесплатными навсегда.

Подробнее: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

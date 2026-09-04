# 🔥 Simplicio — AI-агент, который ЭКОНОМИТ ДО 96% ВАШИХ ТОКЕНОВ

<p align="center">
  <img src="../assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="../plugins/simplicio/LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#установка">Установка</a> ·
  <a href="#что-он-делает">Что он делает</a> ·
  <a href="#экономия-токенов--96-реальны">Экономия токенов — 96% реальны</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Сайт</a>
</p>

<p align="center">
  <strong>🌍 Языки:</strong><br>
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

## ⚡ TL;DR

**Simplicio** — это терминальный AI-агент для кода: один бинарный файл, который заменяет весь
ваш AI-ассистируемый рабочий процесс: чат, генерацию кода, контекст репозитория,
планирование, локальную многoагентную оркестрацию (64 → 600 агентов) и
доставку PR с подтверждением.

**Работает на вашей машине. Ваш код никогда не покидает вашего контроля. Удалённые модели
необязательны, не обязательны.**

> **🔥 Экономьте до 96% токенов по сравнению с традиционными агентами — больше, чем Caveman (65%) или RTK (80%).**
> Каждое взаимодействие показывает, сколько токенов вы сэкономили. Один бинарный файл на Rust, без зависимостей.

## 🚀 Установка

### Установка через плагин Codex

Если вы используете Codex, Simplicio можно установить как плагин. Добавьте публичный Marketplace, установите плагин и запустите новый сеанс Codex; плагин установит и запустит Simplicio Runtime и предоставит его skills и инструменты MCP.

```bash
codex plugin marketplace add wesleysimplicio/simplicio --ref master
codex plugin add simplicio@simplicio-codex
```

### npm / npx (любая ОС)

```bash
npx simplicio install
```

### pip / PyPI (любая ОС)

```bash
pip install simplicio-installer
simplicio install
```

### Homebrew (macOS)

```bash
brew install simplicio
```

### Bun

```bash
bunx simplicio install
```

### macOS / Linux

```bash
python3 -m pip install --upgrade simplicio-installer
simplicio install
```

### Windows

```powershell
py -m pip install --upgrade simplicio-installer
simplicio install
```

### Прямая установка (без PyPI)

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex
```

Готово. Одна команда. Никакого менеджера пакетов, никакой настройки модели.

---

## 💰 Экономия токенов — 96% реальны

### Измеренное доказательство OpenRouter — создание и правка CRUD (2026-09-01)

В контролируемом двухэтапном запуске оба потока использовали OpenRouter и
`deepseek/deepseek-v4-flash-0731` (`seed=42`, `temperature=0`, рассуждение
отключено). Создание было контролем. При правке обычный поток повторно отправил
и сгенерировал весь HTML; Simplicio отправил компактный план и применил его
через MCP.

| Этап правки | Без Simplicio | С Simplicio MCP | Снижение |
|---|---:|---:|---:|
| Входные токены | 5 430 | 415 | 92,36% |
| Выходные токены | 5 144 | 58 | 98,87% |
| Всего токенов | 10 574 | 473 | **95,53%** |
| Стоимость OpenRouter | $0,00078559 | $0,00002654 | **96,62%** |
| Задержка | 17 615,78 мс | 1 296,79 мс | 92,64% |
| Проверки качества | Не пройдены | Пройдены | — |

За оба этапа расход снизился с 16 043 до 6 175 токенов (**на 61,51%**) и с
$0,00132192 до $0,00058617 (**на 55,66%**). В контроле создания Simplicio
использовал на 4,26% больше токенов, поэтому основное доказательство — этап
правки, а не контроль. Это одна измеренная пара рабочих процессов, а не
универсальная гарантия или сравнение идентичных ответов. Кэш и токены
рассуждения равны нулю. Для статистических выводов повторите тест.
[Машиночитаемое доказательство](../docs/evidence/openrouter-deepseek-v4-crud-2026-09-01.json).

**Без Simplicio:** каждый сеанс AI заново исследует ваш репозиторий, загружает слишком много
контекста, повторяет промпты, сжигает платные токены.

**С Simplicio:**

| Оптимизация | Экономия |
|---|---|
| 🗺️ **Карта репозитория** — сжатый контекст вместо чтения сырых файлов | ~70% |
| 🧠 **Память** — известные факты не выводятся заново | ~80% |
| ✏️ **Детерминированное редактирование** — изменения без затрат токенов LLM | 100% (вывод) |
| 🏠 **Локальная LLM** — классификация, суммаризация, низкорисковые правки | ~90% |
| 📡 **Удалённая LLM** — только для планирования и сложных решений | ~85% |
| 🔀 **Локальный Fan-out** — 64→600 агентов до масштабирования в облако | ~95% |
| **💎 Комбинация: до 96% общей экономии** | **~96%** |

**Каждый ответ Simplicio показывает реальную экономию:** `Simplicio: ~X токенов потрачено · сэкономлено ~Y (Z%)`

---

## 🎯 Что он делает

| Команда | Описание | Токены |
|---|---|---|
| `simplicio map --repo .` | Создаёт карту репозитория для LLM | ~70% экономии |
| `simplicio memory "запрос"` | Нейронное recall (FTS + векторы) | ~80% экономии |
| `simplicio edit '{...}'` | Детерминированное редактирование файлов | **Ноль токенов** |
| `simplicio coding-loop "задача"` | Итерации до прохождения тестов | Автоисправление |
| `simplicio deliver certify` | 5 контрольных точек перед доставкой | Детерминированно |
| `simplicio run "задача" --agents N` | Многоагентная оркестрация | Локально в первую очередь |

---

## 🆚 Simplicio против Caveman против RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Подход** | Сжатие стиля вывода | Прокси команд оболочки | **Полноценный агентный рантайм** |
| **Макс. экономия** | ~65% токенов вывода | ~80% команд оболочки | **До 96% всего** |
| **Сжатие ввода** | ❌ | ✅ (фильтрация) | ✅ **Карта репозитория + нейронная память** |
| **Сжатие вывода** | ✅ (caveman-речь) | ❌ | ✅ **Детерминированные правки за 0 токенов** |
| **Локальная LLM** | ❌ | ❌ | ✅ **Встроенная llama.cpp** |
| **Многоагентность** | ❌ | ❌ | ✅ **64 → 600 локальных агентов** |
| **Память между сессиями** | ❌ | ❌ | ✅ **FTS + векторный recall** |
| **Цепочка доказательств** | ❌ | ❌ | ✅ **sha256 опечатанные квитанции** |
| **Язык** | JS/Python (навык) | Rust (бинарник) | **Rust (один бинарник)** |
| **Лицензия** | MIT | Apache 2.0 | Проприетарная |
| **Звёзды** | 72.5k | 62.2k | ⭐ **Вы на старте** |

**Суть:** Caveman заставляет AI *меньше говорить*. RTK заставляет команды *меньше выводить*.
Simplicio заставляет AI *меньше думать* — запоминая, картографируя, редактируя детерминированно
и работая локально, прежде чем обращаться к платной LLM.

| **Simplicio экономит 96% там, где Caveman экономит 65%, а RTK — 80%.** |

---

## 🏗️ Архитектура

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime (Rust)
  |                                   |
  | 1. Ориентация                     | simplicio map
  | 2. Воспоминание                   | simplicio memory
  | 3. Решение                        |
  | 4. Редактирование ──────────────> | simplicio edit (0 токенов)
  | 5. Проверка <───────────────────  | simplicio deliver certify
  | 6. Итерация                       | simplicio coding-loop
```

**LLM рассуждает. Simplicio выполняет детерминированно.**

---

## ✨ Возможности

- 🏠 **Локально в первую очередь** — встроенная llama.cpp, масштабирование на удалённые модели только при необходимости
- 🪜 **Уровневые агенты** — 64 → 100 → 200 → 600 локальных агентов до платного облака
- 🔇 **Шенноновский фильтр новизны** — отфильтровывает избыточные выводы (ноль токенов на дедупликацию)
- 🔒 **Опечатанные квитанции** — sha256 для каждого артефакта, защищённая от взлома цепочка доказательств
- 🛡️ **5 шлюзов доставки** — приёмка, валидация, запуск-проверка, регрессия, саморецензия
- ⚡ **Шлюз действий** — классификация рисков + блоклист для мутаций, инициированных чатом
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Шлюзы** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Система навыков** — загрузка и цепочки переиспользуемых возможностей
- 💾 **База памяти** — постоянный FTS + векторный recall между сессиями
- 🔀 **Маршрутизатор LLM** — без LLM → локальная LLM → удалённая LLM автоматически
- 🖥️ **Кроссплатформенность** — macOS, Linux, Windows, один бинарник

---

## 🎁 Бесплатная публичная бета

**Детерминированные команды БЕСПЛАТНЫ навсегда:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**AI-функции бесплатны в период публичной беты без указания даты окончания.**
Оплата будет определена в будущих обновлениях.

```bash
simplicio license status
```

---

## 📋 Требования

| Требование | Минимум | Рекомендуется |
|---|---|---|
| ОЗУ | 8 ГБ | 16 ГБ+ |
| Диск | 5 МБ | 1.5 ГБ (с локальной LLM) |
| ОС | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Терминал | любой современный терминал | WezTerm / Alacritty / Ghostty |

---

## 🌐 Экосистема

- [Веб-сайт](https://simpleti.com.br/simplicio/#start) — полная документация, бенчмарки, установка
- [Discord](https://discord.gg/wM6tr7xVb) — сообщество и поддержка

---

## 📄 Лицензия

Проприетарная. Бинарный файл можно бесплатно скачивать и использовать. AI-функции бесплатны в период
публичной беты. См. [LICENSE](../plugins/simplicio/LICENSE).

---

## ⭐ История звёзд

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 Сообщество

- [Discord](https://discord.gg/wM6tr7xVb) — чат, поддержка, ранний доступ
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — баги и запросы функций

---

<p align="center">
  <strong>🔥 Simplicio — Ваш код, ваша машина, на 96% дешевле. 🔥</strong>
</p>

# 🔥 Simplicio — Agent AI, KTÓRY OSZCZĘDZA DO 96% TWOICH TOKENÓW

<p align="center">
  <img src="../assets/simplicio-hero.png" alt="Simplicio — agent AI do kodowania" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#instalacja">Instalacja</a> ·
  <a href="#co-robi">Co robi</a> ·
  <a href="#oszczędność-tokenów--96-to-rzeczywistość">Oszczędność tokenów — 96% to rzeczywistość</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Strona WWW</a>
</p>

<p align="center">
  <strong>🌍 Języki:</strong><br>
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

**Simplicio** to terminalowy agent AI do kodowania — pojedynczy plik binarny, który zastępuje
cały twój workflow wspomagany AI: czat, generowanie kodu, kontekst repozytorium,
planowanie, lokalną orkiestrację wieloagentową (64 → 600 agentów) i
dostarczanie PR z potwierdzeniem dowodów.

**Działa na twojej maszynie. Twój kod nigdy nie opuszcza twojej kontroli. Modele zdalne są
opcjonalne, nie wymagane.**

> **🔥 Oszczędź do 96% tokenów w porównaniu z tradycyjnymi agentami — więcej niż Caveman (65%) czy RTK (80%).**
> Każda interakcja pokazuje dokładnie, ile tokenów zaoszczędziłeś. Pojedynczy plik binarny w Ruście, zero zależności.

## 🚀 Instalacja

### Instalacja przez wtyczkę Codex

Jeśli używasz Codex, możesz zainstalować Simplicio jako wtyczkę. Dodaj publiczny Marketplace, zainstaluj wtyczkę i uruchom nową sesję Codex; wtyczka zainstaluje i uruchomi Simplicio Runtime oraz udostępni jego skills i narzędzia MCP.

```bash
codex plugin marketplace add wesleysimplicio/simplicio --ref master
codex plugin add simplicio@simplicio-codex
```

### npm / npx (dowolny system)

```bash
npx simplicio install
```

### pip / PyPI (dowolny system)

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

### Instalacja bezpośrednia (bez PyPI)

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex
```

Gotowe. Jedno polecenie. Żaden menedżer pakietów, żadna konfiguracja modelu.

---

## 💰 Oszczędność tokenów — 96% to rzeczywistość

### Zmierzony dowód OpenRouter — tworzenie i edycja CRUD (2026-09-01)

Kontrolowany, dwuetapowy test używał OpenRouter oraz
`deepseek/deepseek-v4-flash-0731` w obu przepływach (`seed=42`,
`temperature=0`, rozumowanie wyłączone). Tworzenie było próbą kontrolną. Przy
edycji zwykły przepływ ponownie przesłał i wygenerował cały HTML; Simplicio
wysłał zwarty plan i zastosował go przez MCP.

| Etap edycji | Bez Simplicio | Z Simplicio MCP | Redukcja |
|---|---:|---:|---:|
| Tokeny wejściowe | 5 430 | 415 | 92,36% |
| Tokeny wyjściowe | 5 144 | 58 | 98,87% |
| Łącznie tokenów | 10 574 | 473 | **95,53%** |
| Koszt OpenRouter | 0,00078559 USD | 0,00002654 USD | **96,62%** |
| Opóźnienie | 17 615,78 ms | 1 296,79 ms | 92,64% |
| Kontrole jakości | Niepowodzenie | Powodzenie | — |

W obu etapach zużycie spadło z 16 043 do 6 175 tokenów (**o 61,51%**) oraz z
0,00132192 do 0,00058617 USD (**o 55,66%**). Próba kontrolna tworzenia zużyła z
Simplicio o 4,26% więcej tokenów, dlatego głównym dowodem jest edycja, nie
kontrola. To jedna zmierzona para przepływów, a nie uniwersalna gwarancja ani
porównanie identycznych odpowiedzi. Cache i tokeny rozumowania wyniosły zero.
Przed wnioskami statystycznymi powtórz test. [Dowód maszynowy](../docs/evidence/openrouter-deepseek-v4-crud-2026-09-01.json).

**Bez Simplicio:** każda sesja AI odkrywa twoje repozytorium na nowo, ładuje zbyt dużo
kontekstu, powtarza prompty, spala płatne tokeny.

**Z Simplicio:**

| Optymalizacja | Oszczędność |
|---|---|
| 🗺️ **Mapa repozytorium** — skompresowany kontekst zamiast czytania surowych plików | ~70% |
| 🧠 **Pamięć** — znane fakty nie są wyciągane na nowo | ~80% |
| ✏️ **Deterministyczna edycja** — zmiany bez wydawania tokenów LLM | 100% (output) |
| 🏠 **Lokalny LLM** — klasyfikacja, podsumowywanie, mało ryzykowne edycje | ~90% |
| 📡 **Zdalny LLM** — tylko do planowania i złożonych decyzji | ~85% |
| 🔀 **Lokalne rozgałęzianie** — 64→600 agentów przed skalowaniem do chmury | ~95% |
| **💎 Łącznie: do 96% całkowitych oszczędności** | **~96%** |

**Każda odpowiedź Simplicio pokazuje rzeczywiste oszczędności:** `Simplicio: ~X tokenów wydanych · zaoszczędzono ~Y (Z%)`

---

## 🎯 Co robi

| Polecenie | Opis | Tokeny |
|---|---|---|
| `simplicio map --repo .` | Mapuje repozytorium dla LLM-ów | ~70% oszczędności |
| `simplicio memory "query"` | Neuronowe przywoływanie (FTS + wektory) | ~80% oszczędności |
| `simplicio edit '{...}'` | Deterministyczna edycja plików | **Zero tokenów** |
| `simplicio coding-loop "task"` | Iteruje, aż testy przejdą | Auto-naprawa |
| `simplicio deliver certify` | 5 bram jakości przed wydaniem | Deterministyczne |
| `simplicio run "task" --agents N` | Orkiestracja wieloagentowa | Lokalnie najpierw |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Podejście** | Kompresja stylu wypowiedzi | Proxy poleceń powłoki | **Pełne środowisko uruchomieniowe agenta** |
| **Maks. oszczędność** | ~65% tokenów wyjściowych | ~80% na poleceniach powłoki | **Do 96% łącznie** |
| **Kompresja wejścia** | ❌ | ✅ (filtrowane) | ✅ **Mapa repozytorium + pamięć neuronowa** |
| **Kompresja wyjścia** | ✅ (język jaskiniowca) | ❌ | ✅ **Deterministyczne edycje za zero tokenów** |
| **Lokalny LLM** | ❌ | ❌ | ✅ **Wbudowany llama.cpp** |
| **Multi-agent** | ❌ | ❌ | ✅ **64 → 600 lokalnych agentów** |
| **Pamięć między sesjami** | ❌ | ❌ | ✅ **FTS + przywoływanie wektorowe** |
| **Łańcuch dowodów** | ❌ | ❌ | ✅ **Pieczęcie sha256** |
| **Język** | JS/Python (skill) | Rust (binarny) | **Rust (pojedynczy plik binarny)** |
| **Licencja** | MIT | Apache 2.0 | Proprietary |
| **Gwiazdki** | 72,5k | 62,2k | ⭐ **Jesteś wcześnie** |

**Podsumowanie:** Caveman sprawia, że AI *mówi* mniej. RTK sprawia, że polecenia *wyświetlają* mniej.
Simplicio sprawia, że AI *myśli* mniej — przez zapamiętywanie, mapowanie, deterministyczne edycje
i działanie lokalnie, zanim kiedykolwiek dotknie płatnego LLM-a.

| **Simplicio oszczędza 96%, podczas gdy Caveman oszczędza 65%, a RTK 80%.** |

---

## 🏗️ Architektura

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

**LLM rozumuje. Simplicio wykonuje deterministycznie.**

---

## ✨ Funkcje

- 🏠 **Lokalnie najpierw** — wbudowany llama.cpp, skaluje do zdalnych tylko gdy potrzebne
- 🪜 **Warstwowi agenci** — 64 → 100 → 200 → 600 lokalnych agentów przed płatną chmurą
- 🔇 **Bramka nowości Shannona** — filtruje zbędne wyjścia (zero tokenów na deduplikacji)
- 🔒 **Zapieczętowane paragony** — sha256 na artefakt, odporny na manipulacje łańcuch dowodów
- 🛡️ **5 bram dostarczania** — akceptacja, walidacja, uruchom-weryfikuj, regresja, samoocena
- ⚡ **Bramka akcji** — klasyfikacja ryzyka + lista blokowana dla mutacji inicjowanych z czatu
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Bramy** — Telegram, Discord, Slack, WhatsApp
- 🧩 **System umiejętności** — ładuje i łańcuchuje wielokrotnego użytku możliwości
- 💾 **Baza pamięci** — trwałe FTS + przywoływanie wektorowe między sesjami
- 🔀 **Router LLM** — brak LLM → lokalny LLM → zdalny LLM automatycznie
- 🖥️ **Wieloplatformowość** — macOS, Linux, Windows, pojedynczy plik binarny

---

## 🎁 Darmowa Beta Publiczna

**Deterministyczne polecenia są DARMOWE na zawsze:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Funkcje AI są darmowe podczas publicznej bety bez daty zakończenia.**
Rozliczenia zostaną zdefiniowane w przyszłych aktualizacjach.

```bash
simplicio license status
```

---

## 📋 Wymagania

| Wymaganie | Minimalne | Zalecane |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Miejsce na dysku | 5 MB | 1,5 GB (z lokalnym LLM) |
| System | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | dowolny nowoczesny terminal | WezTerm / Alacritty / Ghostty |

---

## 🌐 Ekosystem

- [Strona WWW](https://simpleti.com.br/simplicio/#start) — pełna dokumentacja, benchmarki, instalacja
- [Discord](https://discord.gg/wM6tr7xVb) — społeczność i wsparcie

---

## 📄 Licencja

Proprietary. Plik binarny darmowy do pobrania i użytku. Funkcje AI darmowe podczas
publicznej bety. Zobacz [LICENSE](../LICENSE).

---

## ⭐ Historia gwiazdek

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 Społeczność

- [Discord](https://discord.gg/wM6tr7xVb) — czat, wsparcie, wczesny dostęp
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — błędy i prośby o funkcje

---

<p align="center">
  <strong>🔥 Simplicio — Twój kod, twoja maszyna, 96% taniej. 🔥</strong>
</p>

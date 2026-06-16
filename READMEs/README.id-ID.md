# simplicio

**Satu binari. Nol konfigurasi. Agen AI coding Anda di terminal.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Ringkasan

`simplicio` adalah agen AI coding dalam satu binari native terminal. Unduh dan jalankan, dan Anda akan mendapatkan lingkungan pengembangan berbantuan AI yang lengkap — chat, pembuatan kode, pemetaan konteks repositori, perencanaan tugas, orkestrasi LLM lokal, dan pengiriman PR berbasis bukti.

Kode Anda tetap di mesin Anda. Model jarak jauh bersifat opsional.

## Instalasi

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

## Mulai cepat

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "tugas" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Fitur

Chat REPL, mode agen otonom, pemetaan repositori, LLM lokal (llama.cpp), eksekusi paralel 50–600+ sub-agen, pipeline bukti, otomatisasi PR, gateway (Telegram, Discord, Slack, WhatsApp), server MCP dan ACP, sistem skill, memori persisten, router LLM (tanpa LLM → lokal → jarak jauh), pengeditan deterministik tanpa token LLM, dukungan untuk macOS, Linux dan Windows.

## Beta publik

**Semua terbuka gratis hingga 30 Juni 2026.** Setelah beta, fitur AI memerlukan langganan. Perintah deterministik (map, validate, edit, deliver, checkpoint) tetap gratis selamanya.

Lainnya: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

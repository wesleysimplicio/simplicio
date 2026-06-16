# simplicio

**Satu binari. Sifar persediaan. Ejen AI pengekodan anda dalam terminal.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Ringkasan

`simplicio` ialah satu ejen AI pengekodan dalam satu binari asli terminal. Muat turun dan jalankannya, dan anda akan mendapat persekitaran pembangunan bantuan AI yang lengkap — sembang, penjanaan kod, pemetaan konteks repositori, perancangan tugas, orkestrasi LLM tempatan, dan penghantaran PR berasaskan bukti.

Kod anda kekal pada mesin anda. Model jauh adalah pilihan.

## Pemasangan

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

## Mula pantas

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "tugas" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Ciri-ciri

Chat REPL, mod ejen autonomi, pemetaan repositori, LLM tempatan (llama.cpp), pelaksanaan selari 50–600+ sub-ejen, saluran paip bukti, automasi PR, gerbang (Telegram, Discord, Slack, WhatsApp), pelayan MCP dan ACP, sistem kemahiran, ingatan kekal, penghala LLM (tiada LLM → tempatan → jauh), suntingan deterministik tanpa token LLM, sokongan untuk macOS, Linux dan Windows.

## Beta awam

**Semua dibuka secara percuma semasa beta awam tanpa tarikh tamat.** Pengebilan akan ditentukan dalam kemas kini akan datang. Perintah deterministik (map, validate, edit, deliver, checkpoint) kekal percuma selama-lamanya.** Selepas beta, ciri AI memerlukan langganan. Perintah deterministik (map, validate, edit, deliver, checkpoint) kekal percuma selamanya.

Lagi: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/#start)

# simplicio

**単一バイナリ。セットアップ不要。ターミナルで動作するAIコーディングエージェント。**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## 概要

`simplicio` は単一バイナリのターミナルネイティブAIコーディングエージェントです。ダウンロードして実行するだけで、チャット、コード生成、リポジトリマッピング、タスク計画、ローカルLLMオーケストレーション、エビデンスベースのPR提出まで、完全なAI支援開発環境が利用可能です。

コードはマシン上に残ります。リモートモデルはオプションです。

## インストール

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

## クイックスタート

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "タスク" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## 機能

Chat REPL、自律エージェントモード、リポジトリマッピング、ローカルLLM（llama.cpp）、50～600+の並列サブエージェント実行、エビデンスパイプライン、PR自動化、ゲートウェイ（Telegram、Discord、Slack、WhatsApp）、MCP/ACPサーバー、スキルシステム、永続メモリ、LLMルーター（LLMなし→ローカル→リモート）、トークン不要の決定論的編集、macOS・Linux・Windows対応。

## パブリックベータ

**無期限のパブリックベータ期間中はすべて無料で利用できます。** 請求は将来のアップデートで定義されます。決定論的コマンド（map、validate、edit、deliver、checkpoint）は永久に無料です。

詳細: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

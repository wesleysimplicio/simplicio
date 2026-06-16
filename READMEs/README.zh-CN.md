# simplicio

**一个二进制文件。零配置。你的终端 AI 编程助手。**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## 简介

`simplicio` 是一个单二进制文件、原生终端的 AI 编程助手。下载并运行后，即可获得完整的 AI 辅助开发环境——聊天、代码生成、仓库上下文映射、任务规划、本地 LLM 编排以及基于证据的 PR 提交。

你的代码保留在你的机器上。远程模型是可选项。

## 安装

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

## 快速开始

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "任务" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## 功能

Chat REPL、自主代理模式、仓库映射、本地 LLM (llama.cpp)、50–600+ 并行子代理执行、证据管道、PR 自动化、网关 (Telegram、Discord、Slack、WhatsApp)、MCP/ACP 服务器、技能系统、持久化记忆、LLM 路由器（无 LLM → 本地 → 远程）、无需令牌的确定性编辑、支持 macOS、Linux 和 Windows。

## 公开测试版

**公开测试期间无结束日期，所有功能免费。** 计费将在未来更新中定义。确定性命令（map、validate、edit、deliver、checkpoint）永久免费。

更多信息: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

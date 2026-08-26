# 🔥 Simplicio — 最多可节省高达 96% 的 Token 的 AI 智能体

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI 编程助手" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="最新版本"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="星标"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="下载量"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="许可证"></a>
</p>

<p align="center">
  <a href="#-安装">安装</a> ·
  <a href="#-功能简介">功能</a> ·
  <a href="#-token-节省">96% 节省</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">官网</a>
</p>

<p align="center">
  <strong>🌍 语言：</strong><br>
  <a href="README.md">🇬🇧 English</a> |
  <a href="READMEs/README.pt-BR.md">🇧🇷 Português</a> |
  <a href="READMEs/README.es-ES.md">🇪🇸 Español</a> |
  <a href="READMEs/README.fr-FR.md">🇫🇷 Français</a> |
  <a href="READMEs/README.ja-JP.md">🇯🇵 日本語</a> |
  <a href="READMEs/README.ko-KR.md">🇰🇷 한국어</a> |
  <a href="READMEs/README.zh-CN.md">🇨🇳 简体中文</a> |
  <a href="READMEs/README.it-IT.md">🇮🇹 Italiano</a> |
  <a href="READMEs/README.ru-RU.md">🇷🇺 Русский</a> |
  <a href="READMEs/README.pl-PL.md">🇵🇱 Polski</a> |
  <a href="READMEs/README.hi-IN.md">🇮🇳 हिन्दी</a> |
  <a href="READMEs/README.ar-SA.md">🇸🇦 العربية</a> |
  <a href="READMEs/README.he-IL.md">🇮🇱 עברית</a> |
  <a href="READMEs/README.ms-MY.md">🇲🇾 Bahasa Melayu</a> |
  <a href="READMEs/README.id-ID.md">🇮🇩 Bahasa Indonesia</a>
</p>

---

## ⚡ 快速概览

**Simplicio** 是一款终端 AI 编程代理——一个单一二进制文件即可替代你的
整个 AI 辅助开发工作流：聊天、代码生成、仓库上下文、
规划、本地多智能体编排（64 → 600 个代理）以及
基于证据的 PR 交付。

**运行在你的机器上。你的代码始终在你的掌控之中。远程模型是
可选项，而非必需项。**

> **🔥 相比传统代理，最多可节省 96% 的 Token——超过 Caveman (65%) 或 RTK (80%)。**
> 每次交互都会精确显示你节省了多少 Token。单一 Rust 二进制文件，零依赖。

## 🚀 安装

### npm / npx（支持所有操作系统）

```bash
npx simplicio install
```

### pip / PyPI（支持所有操作系统）

```bash
pip install simplicio-installer
simplicio install
```

### Homebrew（macOS）

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

完成。一条命令。无需包管理器，无需模型配置。

---

## 💰 Token 节省——96% 是真实可得的

**没有 Simplicio：** 每次 AI 会话都重新探索你的仓库，加载过多
上下文，重复提示，消耗付费 Token。

**有了 Simplicio：**

| 优化项 | 节省比例 |
|---|---|
| 🗺️ **仓库地图** — 压缩上下文，而非读取原始文件 | ~70% |
| 🧠 **记忆召回** — 已知事实无需重新推导 | ~80% |
| ✏️ **确定性编辑** — 无需消耗 LLM Token 即可完成更改 | 100%（输出端） |
| 🏠 **本地 LLM** — 分类、摘要、低风险编辑 | ~90% |
| 📡 **远程 LLM** — 仅用于规划和复杂决策 | ~85% |
| 🔀 **本地扇出** — 64→600 个代理，无需扩展至云端 | ~95% |
| **💎 综合：最高可节省 96%** | **~96%** |

**每次 Simplicio 响应都会显示真实节省：** `Simplicio: ~X 个 Token 已使用 · 节省 ~Y (Z%)`

---

## 🎯 功能简介

| 命令 | 描述 | Token |
|---|---|---|
| `simplicio map --repo .` | 为 LLM 映射仓库结构 | ~70% 节省 |
| `simplicio memory "query"` | 神经记忆召回（全文搜索 + 向量） | ~80% 节省 |
| `simplicio edit '{...}'` | 确定性文件编辑 | **零 Token** |
| `simplicio coding-loop "task"` | 迭代直到测试通过 | 自动修复 |
| `simplicio deliver certify` | 交付前通过 5 道质量关卡 | 确定性 |
| `simplicio run "task" --agents N` | 多智能体编排 | 本地优先 |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **方法** | 输出风格压缩 | Shell 命令代理 | **完整智能体运行时** |
| **最大节省** | ~65% 输出 Token | ~80% 在 shell 命令上 | **最高 96% 总计** |
| **输入压缩** | ❌ | ✅（过滤） | ✅ **仓库地图 + 神经记忆** |
| **输出压缩** | ✅（原始人语） | ❌ | ✅ **零 Token 确定性编辑** |
| **本地 LLM** | ❌ | ❌ | ✅ **内置 llama.cpp** |
| **多智能体** | ❌ | ❌ | ✅ **64 → 600 个本地代理** |
| **跨会话记忆** | ❌ | ❌ | ✅ **全文搜索 + 向量召回** |
| **证据链** | ❌ | ❌ | ✅ **sha256 密封收据** |
| **语言** | JS/Python（技能） | Rust（二进制） | **Rust（单一二进制）** |
| **许可证** | MIT | Apache 2.0 | 专有许可 |
| **星标** | 72.5k | 62.2k | ⭐ **你来得真早** |

**底线：** Caveman 让 AI *少说*。RTK 让命令 *少输出*。
Simplicio 让 AI *少想*——通过记忆、映射、确定性编辑，
以及在触及付费 LLM 之前在本地运行。

| **Simplicio 节省 96%，而 Caveman 节省 65%，RTK 节省 80%。** |

---

## 🏗️ 架构

```
LLM (Claude/Codex/Gemini)          Simplicio 运行时 (Rust)
  |                                   |
  | 1. 定位                           | simplicio map
  | 2. 回忆                           | simplicio memory
  | 3. 决策                           |
  | 4. 编辑  ───────────────────────> | simplicio edit (0 Token)
  | 5. 验证 <─────────────────────  | simplicio deliver certify
  | 6. 迭代                           | simplicio coding-loop
```

**LLM 负责推理。Simplicio 负责确定性执行。**

---

## ✨ 特性

- 🏠 **本地优先** — 内置 llama.cpp，仅在需要时扩展至远程
- 🪜 **分层代理** — 64 → 100 → 200 → 600 个本地代理，之后才使用付费云端
- 🔇 **Shannon 新颖性门控** — 过滤冗余输出（去重零 Token）
- 🔒 **密封收据** — 每个工件 sha256，防篡改证据链
- 🛡️ **5 道交付关卡** — 验收、验证、运行验证、回归、自审
- ⚡ **操作门控** — 针对聊天发起的变更的风险分类 + 黑名单
- 🔌 **MCP/ACP** — 模型上下文协议 + 智能体客户端协议
- 🌐 **网关** — Telegram、Discord、Slack、WhatsApp
- 🧩 **技能系统** — 加载并链式组合可复用的能力
- 💾 **记忆数据库** — 跨会话持久化的全文搜索 + 向量召回
- 🔀 **LLM 路由器** — 无 LLM → 本地 LLM → 远程 LLM 自动切换
- 🖥️ **跨平台** — macOS、Linux、Windows，单一二进制文件

---

## 🎁 免费公测

**确定性命令永久免费：**
`map`、`validate`、`edit`、`deliver`、`checkpoint`

**AI 功能在公测期间免费，无截止日期。**
计费方案将在未来更新中确定。

```bash
simplicio license status
```

---

## 📋 系统要求

| 要求 | 最低配置 | 推荐配置 |
|---|---|---|
| 内存 | 8 GB | 16 GB+ |
| 存储 | 5 MB | 1.5 GB（含本地 LLM） |
| 操作系统 | macOS 13+、Linux、Windows 10+ | macOS ARM64 |
| 终端 | 任意现代终端 | WezTerm / Alacritty / Ghostty |

---

## 🌐 生态系统

- [官网](https://simpleti.com.br/simplicio/#start) — 完整文档、基准测试、安装指南
- [Discord](https://discord.gg/wM6tr7xVb) — 社区与支持

---

## 📄 许可证

专有许可。二进制文件可免费下载和使用。AI 功能在公开
公测期间免费。详见 [LICENSE](LICENSE)。

---

## ⭐ 星标历史

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="星标历史图表" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 社区

- [Discord](https://discord.gg/wM6tr7xVb) — 聊天、支持、抢先体验
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — 报告问题和功能请求

---

<p align="center">
  <strong>🔥 Simplicio — 你的代码，你的机器，便宜 96%。 🔥</strong>
</p>

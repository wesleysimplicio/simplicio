# 🔥 Simplicio — トークンを最大96%削減するAIエージェント

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AIコーディングエージェント" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="最新リリース"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="スター"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="ダウンロード数"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="ライセンス"></a>
</p>

<p align="center">
  <a href="#インストール">インストール</a> ·
  <a href="#機能一覧">機能一覧</a> ·
  <a href="#トークン削減効果--96は現実です">トークン削減効果——96%は現実です</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">ウェブサイト</a>
</p>

<p align="center">
  <strong>🌍 言語:</strong><br>
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

## ⚡ TL;DR（概要）

**Simplicio** はターミナル上で動作するAIコーディングエージェントです——たった1つのバイナリで、チャット、コード生成、リポジトリコンテキスト、計画立案、ローカルでのマルチエージェントオーケストレーション（64 → 600エージェント）、エビデンス付きPR納品まで、AI支援開発ワークフロー全体を置き換えます。

**あなたのマシン上で動作します。コードがあなたの管理下から離れることはありません。リモートモデルはオプションであり、必須ではありません。**

> **🔥 従来のエージェントと比較して最大96%のトークンを削減——Caveman（65%）やRTK（80%）を上回ります。**
> すべての操作で、削減したトークン数が正確に表示されます。単一のRustバイナリ、依存関係ゼロ。

## 🚀 インストール

### npm / npx（全OS対応）

```bash
npx simplicio install
```

### pip / PyPI（全OS対応）

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

### 直接インストール（PyPIなし）

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex
```

完了。たった1つのコマンドです。パッケージマネージャーもモデル設定も不要です。

---

## 💰 トークン削減効果——96%は現実です

**Simplicioなしの場合:** AIセッションのたびにリポジトリを再検出し、過剰なコンテキストを読み込み、プロンプトを繰り返し、有料トークンを消費します。

**Simplicioありの場合:**

| 最適化 | 削減率 |
|---|---|
| 🗺️ **リポマップ** — 生ファイルを読む代わりに圧縮コンテキスト | ~70% |
| 🧠 **メモリーリコール** — 既知の事実を再導出しない | ~80% |
| ✏️ **決定論的編集** — LLMトークンを消費せずに変更 | 100%（出力） |
| 🏠 **ローカルLLM** — 分類、要約、低リスク編集 | ~90% |
| 📡 **リモートLLM** — 計画と複雑な判断のみに使用 | ~85% |
| 🔀 **ローカルファンアウト** — クラウド拡張前に64→600エージェント | ~95% |
| **💎 組み合わせ効果: 最大96%の総削減** | **~96%** |

**Simplicioのすべての応答に実際の削減効果が表示されます:** `Simplicio: ~X トークン消費 · ~Y 削減 (Z%)`

---

## 🎯 機能一覧

| コマンド | 説明 | トークン |
|---|---|---|
| `simplicio map --repo .` | LLM向けにリポジトリをマッピング | ~70%削減 |
| `simplicio memory "query"` | ニューラルリコール（FTS + ベクトル） | ~80%削減 |
| `simplicio edit '{...}'` | 決定論的ファイル編集 | **ゼロトークン** |
| `simplicio coding-loop "task"` | テストが通るまで反復 | 自動修復 |
| `simplicio deliver certify` | 出荷前に5つの品質ゲートを通過 | 決定論的 |
| `simplicio run "task" --agents N` | マルチエージェントオーケストレーション | ローカル優先 |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **アプローチ** | 出力スタイルの圧縮 | シェルコマンドプロキシ | **完全なエージェントランタイム** |
| **最大削減率** | ~65% 出力トークン | ~80% シェルコマンド | **最大96% 総合** |
| **入力圧縮** | ❌ | ✅（フィルタリング） | ✅ **リポマップ + ニューラルメモリー** |
| **出力圧縮** | ✅（原始的な話し方） | ❌ | ✅ **ゼロトークン決定論的編集** |
| **ローカルLLM** | ❌ | ❌ | ✅ **内蔵 llama.cpp** |
| **マルチエージェント** | ❌ | ❌ | ✅ **64 → 600 ローカルエージェント** |
| **セッション間メモリー** | ❌ | ❌ | ✅ **FTS + ベクトルリコール** |
| **エビデンスチェーン** | ❌ | ❌ | ✅ **sha256封印済みレシート** |
| **言語** | JS/Python（スキル） | Rust（バイナリ） | **Rust（単一バイナリ）** |
| **ライセンス** | MIT | Apache 2.0 | Proprietary |
| **スター数** | 72.5k | 62.2k | ⭐ **あなたが初期ユーザーです** |

**結論:** CavemanはAIの*発言*を減らします。RTKはコマンドの*出力*を減らします。
SimplicioはAIの*思考*を減らします——記憶、マッピング、決定論的編集、そして有料LLMに触れる前にローカルで実行することによって。

| **Simplicioは96%削減します。Cavemanは65%、RTKは80%です。** |

---

## 🏗️ アーキテクチャ

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime (Rust)
  |                                   |
  | 1. Orient（方向付け）              | simplicio map
  | 2. Recall（想起）                  | simplicio memory
  | 3. Decide（判断）                  |
  | 4. Edit（編集） ────────────────> | simplicio edit (0 tokens)
  | 5. Verify（検証）<──────────────  | simplicio deliver certify
  | 6. Iterate（反復）                 | simplicio coding-loop
```

**LLMが推論します。Simplicioが決定論的に実行します。**

---

## ✨ 特徴

- 🏠 **ローカル優先** — 内蔵llama.cpp、必要なときだけリモートに拡張
- 🪜 **階層型エージェント** — 有料クラウドの前に64 → 100 → 200 → 600のローカルエージェント
- 🔇 **シャノン新規性ゲート** — 冗長な出力をフィルタリング（重複排除でゼロトークン）
- 🔒 **封印レシート** — アーティファクトごとにsha256、改ざん防止のエビデンスチェーン
- 🛡️ **5つの納品ゲート** — 受入、検証、実行確認、回帰テスト、自己レビュー
- ⚡ **アクションゲート** — チャット発信の変更に対するリスク分類 + ブロックリスト
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **ゲートウェイ** — Telegram、Discord、Slack、WhatsApp
- 🧩 **スキルシステム** — 再利用可能な機能を読み込んで連鎖実行
- 💾 **メモリDB** — セッション間で永続的なFTS + ベクトルリコール
- 🔀 **LLMルーター** — LLMなし → ローカルLLM → リモートLLM を自動切替
- 🖥️ **クロスプラットフォーム** — macOS、Linux、Windows、単一バイナリ

---

## 🎁 無料パブリックベータ

**決定論的コマンドは永久無料です:**
`map`、`validate`、`edit`、`deliver`、`checkpoint`

**AI機能は期間無制限でパブリックベータ期間中無料です。**
課金は将来のアップデートで定義されます。

```bash
simplicio license status
```

---

## 📋 必要環境

| 要件 | 最小 | 推奨 |
|---|---|---|
| RAM | 8 GB | 16 GB以上 |
| ストレージ | 5 MB | 1.5 GB（ローカルLLM使用時） |
| OS | macOS 13+、Linux、Windows 10+ | macOS ARM64 |
| ターミナル | 任意のモダンなターミナル | WezTerm / Alacritty / Ghostty |

---

## 🌐 エコシステム

- [ウェブサイト](https://simpleti.com.br/simplicio/#start) — 完全なドキュメント、ベンチマーク、インストール
- [Discord](https://discord.gg/wM6tr7xVb) — コミュニティとサポート

---

## 📄 ライセンス

Proprietary（プロプライエタリ）。バイナリは無料でダウンロードして使用できます。AI機能はパブリックベータ期間中無料です。詳しくは [LICENSE](LICENSE) をご覧ください。

---

## ⭐ スター履歴

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="スター履歴チャート" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 コミュニティ

- [Discord](https://discord.gg/wM6tr7xVb) — チャット、サポート、早期アクセス
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — バグ報告と機能リクエスト

---

<p align="center">
  <strong>🔥 Simplicio — あなたのコード、あなたのマシン、96%のコスト削減。 🔥</strong>
</p>

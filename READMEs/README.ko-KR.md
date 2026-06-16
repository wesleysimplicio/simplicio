# 🔥 Simplicio — 토큰을 최대 96%까지 절약하는 AI 에이전트

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI 코딩 에이전트" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#설치">설치</a> ·
  <a href="#기능">기능</a> ·
  <a href="#토큰-절약--96는-실제입니다">토큰 절약 — 96%는 실제입니다</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">웹사이트</a>
</p>

<p align="center">
  <strong>🌍 언어:</strong><br>
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

## ⚡ TL;DR

**Simplicio**는 터미널 AI 코딩 에이전트입니다 — 단일 바이너리로 채팅, 코드 생성,
리포지토리 컨텍스트, 계획 수립, 로컬 멀티에이전트 오케스트레이션 (64 → 600개 에이전트),
증거 기반 PR 전달 등 AI 지원 개발 워크플로 전체를 대체합니다.

**사용자 머신에서 실행됩니다. 코드는 절대 사용자의 통제를 벗어나지 않습니다.
원격 모델은 선택 사항이지 필수가 아닙니다.**

> **🔥 기존 에이전트 대비 최대 96% 토큰 절약 — Caveman(65%)이나 RTK(80%)보다 뛰어납니다.**
> 모든 상호작용에서 정확히 얼마나 많은 토큰을 절약했는지 보여줍니다. 단일 Rust 바이너리, 종속성 제로.

## 🚀 설치

### npm / npx (모든 OS)

```bash
npx simplicio install
```

### pip / PyPI (모든 OS)

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
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"
```

끝. 하나의 명령어입니다. 패키지 매니저도, 모델 설정도 필요 없습니다.

---

## 💰 토큰 절약 — 96%는 실제입니다

**Simplicio 없이:** 매 AI 세션마다 리포지토리를 다시 탐색하고, 너무 많은 컨텍스트를
로드하며, 프롬프트를 반복하고, 유료 토큰을 소모합니다.

**Simplicio와 함께:**

| 최적화 | 절약 |
|---|---|
| 🗺️ **Repo Map** — 원시 파일을 읽는 대신 압축된 컨텍스트 사용 | ~70% |
| 🧠 **Memory Recall** — 이미 알려진 사실을 다시 도출하지 않음 | ~80% |
| ✏️ **Deterministic Editing** — LLM 토큰 소모 없이 변경 수행 | 100% (출력) |
| 🏠 **Local LLM** — 분류, 요약, 저위험 편집 | ~90% |
| 📡 **Remote LLM** — 계획 수립 및 복잡한 결정에만 사용 | ~85% |
| 🔀 **Local Fan-out** — 클라우드 확장 전 64→600개 에이전트 | ~95% |
| **💎 결합: 최대 96% 총 절약** | **~96%** |

**모든 Simplicio 응답에 실제 절약량이 표시됩니다:** `Simplicio: ~X 토큰 사용 · ~Y 절약 (Z%)`

---

## 🎯 기능

| 명령어 | 설명 | 토큰 |
|---|---|---|
| `simplicio map --repo .` | LLM을 위해 리포지토리 매핑 | ~70% 절약 |
| `simplicio memory "query"` | 신경망 검색 (FTS + 벡터) | ~80% 절약 |
| `simplicio edit '{...}'` | 결정론적 파일 편집 | **토큰 제로** |
| `simplicio coding-loop "task"` | 테스트 통과까지 반복 | 자동 복구 |
| `simplicio deliver certify` | 출시 전 5단계 품질 게이트 | 결정론적 |
| `simplicio run "task" --agents N` | 멀티에이전트 오케스트레이션 | 로컬 우선 |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **접근 방식** | 출력 스타일 압축 | 셸 명령 프록시 | **전체 에이전트 런타임** |
| **최대 절약** | 출력 토큰 ~65% | 셸 명령 ~80% | **최대 96% 전체** |
| **입력 압축** | ❌ | ✅ (필터링) | ✅ **Repo map + 신경 메모리** |
| **출력 압축** | ✅ (원시인 말투) | ❌ | ✅ **제로토큰 결정론적 편집** |
| **로컬 LLM** | ❌ | ❌ | ✅ **내장 llama.cpp** |
| **멀티에이전트** | ❌ | ❌ | ✅ **64 → 600개 로컬 에이전트** |
| **세션 간 메모리** | ❌ | ❌ | ✅ **FTS + 벡터 검색** |
| **증명 체인** | ❌ | ❌ | ✅ **sha256 봉인 영수증** |
| **언어** | JS/Python (스킬) | Rust (바이너리) | **Rust (단일 바이너리)** |
| **라이선스** | MIT | Apache 2.0 | Proprietary |
| **Stars** | 72.5k | 62.2k | ⭐ **당신이 먼저입니다** |

**결론:** Caveman은 AI가 *말을* 적게 하게 만듭니다. RTK는 명령어 *출력을* 적게 만듭니다.
Simplicio는 AI가 *생각을* 적게 하게 만듭니다 — 기억하고, 매핑하고, 결정론적으로 편집하며,
유료 LLM을 사용하기 전에 로컬에서 실행함으로써 가능합니다.

| **Caveman이 65%, RTK가 80%를 절약하는 곳에서 Simplicio는 96%를 절약합니다.** |

---

## 🏗️ 아키텍처

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

**LLM은 추론합니다. Simplicio는 결정론적으로 실행합니다.**

---

## ✨ 특징

- 🏠 **로컬 우선** — 내장 llama.cpp, 필요할 때만 원격으로 확장
- 🪜 **계층형 에이전트** — 유료 클라우드 전 64 → 100 → 200 → 600개 로컬 에이전트
- 🔇 **Shannon 참신성 게이트** — 중복 출력 필터링 (중복 제거 시 토큰 제로)
- 🔒 **봉인 영수증** — 아티팩트당 sha256, 변조 방지 증명 체인
- 🛡️ **5단계 전달 게이트** — 승인, 검증, 실행 확인, 회귀 테스트, 자체 검토
- ⚡ **액션 게이트** — 채팅 기반 변경에 대한 위험 분류 + 차단 목록
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **게이트웨이** — Telegram, Discord, Slack, WhatsApp
- 🧩 **스킬 시스템** — 재사용 가능한 기능 로드 및 체이닝
- 💾 **메모리 DB** — 세션 간 지속적 FTS + 벡터 검색
- 🔀 **LLM 라우터** — LLM 없음 → 로컬 LLM → 원격 LLM 자동 전환
- 🖥️ **크로스 플랫폼** — macOS, Linux, Windows, 단일 바이너리

---

## 🎁 무료 공개 베타

**결정론적 명령어는 영원히 무료입니다:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**AI 기능은 공개 베타 기간 동안 종료일 없이 무료입니다.**
과금은 향후 업데이트에서 정의됩니다.

```bash
simplicio license status
```

---

## 📋 시스템 요구사항

| 요구사항 | 최소 | 권장 |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| 저장공간 | 5 MB | 1.5 GB (로컬 LLM 포함 시) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| 터미널 | 모든 최신 터미널 | WezTerm / Alacritty / Ghostty |

---

## 🌐 생태계

- [웹사이트](https://simpleti.com.br/simplicio/#start) — 전체 문서, 벤치마크, 설치
- [Discord](https://discord.gg/wM6tr7xVb) — 커뮤니티 및 지원

---

## 📄 라이선스

Proprietary. 바이너리는 무료로 다운로드 및 사용 가능합니다. AI 기능은
공개 베타 기간 동안 무료입니다. [LICENSE](LICENSE)를 참조하세요.

---

## ⭐ 스타 기록

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <img src="https://api.star-history.com/svg?repos=wesleysimplicio/simplicio&type=Date" alt="Star History Chart" width="100%" />
</a>

---

## 💬 커뮤니티

- [Discord](https://discord.gg/wM6tr7xVb) — 채팅, 지원, 얼리 액세스
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — 버그 및 기능 요청

---

<p align="center">
  <strong>🔥 Simplicio — 당신의 코드, 당신의 머신, 96% 더 저렴하게. 🔥</strong>
</p>

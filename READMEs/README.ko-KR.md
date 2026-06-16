# simplicio

**하나의 바이너리. 설정 불필요. 터미널에서 작동하는 AI 코딩 에이전트.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## 요약

`simplicio`는 단일 바이너리 네이티브 터미널 AI 코딩 에이전트입니다. 다운로드하여 실행하면 채팅, 코드 생성, 리포지토리 맵핑, 작업 계획, 로컬 LLM 오케스트레이션, 증거 기반 PR 제출까지 완벽한 AI 지원 개발 환경을 사용할 수 있습니다.

코드는 사용자 기기에 남아 있습니다. 원격 모델은 선택 사항입니다.

## 설치

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

## 빠른 시작

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "작업" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## 기능

Chat REPL, 자율 에이전트 모드, 리포지토리 맵핑, 로컬 LLM (llama.cpp), 50~600+ 병렬 서브에이전트 실행, 증거 파이프라인, PR 자동화, 게이트웨이 (Telegram, Discord, Slack, WhatsApp), MCP/ACP 서버, 스킬 시스템, 영구 메모리, LLM 라우터 (LLM 없음 → 로컬 → 원격), 토큰 없는 결정론적 편집, macOS·Linux·Windows 지원.

## 퍼블릭 베타

**2026년 6월 30일까지 모든 기능을 무료로 이용할 수 있습니다.** 베타 종료 후 AI 기능은 구독이 필요합니다. 결정론적 명령어(map, validate, edit, deliver, checkpoint)는 영구적으로 무료입니다.

더보기: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

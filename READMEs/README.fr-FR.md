# simplicio

**Un binaire. Zéro configuration. Votre agent IA de codage dans le terminal.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## Résumé

`simplicio` est un agent IA de codage en un seul binaire natif pour le terminal. Téléchargez-le, exécutez-le et vous obtenez un environnement de développement assisté par IA complet — chat, génération de code, cartographie du contexte du dépôt, planification de tâches, orchestration de LLM local et livraison de PR basée sur des preuves.

Votre code reste sur votre machine. Les modèles distants sont facultatifs.

## Installation

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

## Démarrage rapide

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "tâche" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## Fonctionnalités

Chat REPL, mode agent autonome, cartographie de dépôt, LLM local (llama.cpp), exécution parallèle de 50–600+ sous-agents, pipeline de preuves, automatisation de PR, passerelles (Telegram, Discord, Slack, WhatsApp), serveur MCP et ACP, système de compétences, mémoire persistante, routeur LLM (pas de LLM → local → distant), édition déterministe sans tokens LLM, prise en charge de macOS, Linux et Windows.

## Bêta publique

**Tout est débloqué gratuitement pendant la bêta publique sans date de fin.** La facturation sera définie dans les prochaines mises à jour. Les commandes déterministes (map, validate, edit, deliver, checkpoint) restent gratuites pour toujours. Les commandes déterministes (map, validate, edit, deliver, checkpoint) restent gratuites pour toujours.

Plus: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

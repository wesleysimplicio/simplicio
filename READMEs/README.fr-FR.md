# 🔥 Simplicio — L'agent IA qui économise JUSQU'À 96 % DE VOS TOKENS

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> ·
  <a href="#ce-quil-fait">Ce Qu'il Fait</a> ·
  <a href="#économies-de-tokens--96-cest-réel">Économies de Tokens — 96 % C'est Réel</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Site Web</a>
</p>

<p align="center">
  <strong>🌍 Langues :</strong><br>
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

**Simplicio** est un agent de codage IA en terminal — un binaire unique qui remplace
l'intégralité de votre workflow de développement assisté par IA : chat, génération de code,
contexte de dépôt, planification, orchestration multi-agent locale (64 → 600 agents),
et livraison de PR avec preuves à l'appui.

**Tourne sur votre machine. Votre code ne quitte jamais votre contrôle. Les modèles distants
sont facultatifs, pas obligatoires.**

> **🔥 Économisez jusqu'à 96 % de tokens par rapport aux agents traditionnels — plus que Caveman (65 %) ou RTK (80 %).**
> Chaque interaction montre exactement combien de tokens vous avez économisés. Binaire Rust unique, zéro dépendance.

## 🚀 Installation

### npm / npx (tout OS)

```bash
npx simplicio install
```

### pip / PyPI (tout OS)

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

Terminé. Une seule commande. Pas de gestionnaire de paquets, pas de configuration de modèle.

---

## 💰 Économies de Tokens — 96 % C'est Réel

**Sans Simplicio :** chaque session IA redécouvre votre dépôt, charge trop de
contexte, répète les invites, brûle des tokens payants.

**Avec Simplicio :**

| Optimisation | Économies |
|---|---|
| 🗺️ **Plan du dépôt** — contexte compressé au lieu de lire les fichiers bruts | ~70 % |
| 🧠 **Rappel mémoire** — les faits connus ne sont pas redérivés | ~80 % |
| ✏️ **Édition déterministe** — modifications sans dépenser de tokens LLM | 100 % (sortie) |
| 🏠 **LLM local** — classification, résumé, modifications à faible risque | ~90 % |
| 📡 **LLM distant** — uniquement pour la planification et les décisions complexes | ~85 % |
| 🔀 **Fan-out local** — 64→600 agents avant de passer au cloud | ~95 % |
| **💎 Combiné : jusqu'à 96 % d'économies totales** | **~96 %** |

**Chaque réponse de Simplicio montre les économies réelles :** `Simplicio: ~X tokens dépensés · économisé ~Y (Z%)`

---

## 🎯 Ce Qu'il Fait

| Commande | Description | Tokens |
|---|---|---|
| `simplicio map --repo .` | Cartographie le dépôt pour les LLMs | ~70 % d'économies |
| `simplicio memory "query"` | Rappel neuronal (FTS + vecteurs) | ~80 % d'économies |
| `simplicio edit '{...}'` | Édition déterministe de fichiers | **Zéro token** |
| `simplicio coding-loop "task"` | Itère jusqu'à ce que les tests passent | Auto-réparation |
| `simplicio deliver certify` | 5 portes qualité avant livraison | Déterministe |
| `simplicio run "task" --agents N` | Orchestration multi-agent | Local d'abord |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Approche** | Compression du style de sortie | Proxy de commandes shell | **Runtime d'agent complet** |
| **Économies max** | ~65 % tokens de sortie | ~80 % sur les commandes shell | **Jusqu'à 96 % du total** |
| **Compression d'entrée** | ❌ | ✅ (filtrée) | ✅ **Plan du dépôt + mémoire neuronale** |
| **Compression de sortie** | ✅ (caveman-speak) | ❌ | ✅ **Éditions déterministes zéro token** |
| **LLM local** | ❌ | ❌ | ✅ **llama.cpp intégré** |
| **Multi-agent** | ❌ | ❌ | ✅ **64 → 600 agents locaux** |
| **Mémoire entre sessions** | ❌ | ❌ | ✅ **FTS + rappel vectoriel** |
| **Chaîne de preuves** | ❌ | ❌ | ✅ **Reçus scellés sha256** |
| **Langage** | JS/Python (skill) | Rust (binaire) | **Rust (binaire unique)** |
| **Licence** | MIT | Apache 2.0 | Propriétaire |
| **Étoiles** | 72,5k | 62,2k | ⭐ **Vous êtes en avance** |

**En résumé :** Caveman fait en sorte que l'IA *parle* moins. RTK fait en sorte que les commandes *produisent* moins.
Simplicio fait en sorte que l'IA *réfléchisse* moins — en se souvenant, en cartographiant, en éditant de manière déterministe,
et en s'exécutant localement avant même de toucher un LLM payant.

| **Simplicio économise 96 % là où Caveman économise 65 % et RTK 80 %.** |

---

## 🏗️ Architecture

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

**Le LLM raisonne. Simplicio exécute de manière déterministe.**

---

## ✨ Fonctionnalités

- 🏠 **Local d'abord** — llama.cpp intégré, passage au distant uniquement si nécessaire
- 🪜 **Agents hiérarchisés** — 64 → 100 → 200 → 600 agents locaux avant le cloud payant
- 🔇 **Porte de nouveauté Shannon** — filtre les sorties redondantes (zéro token sur déduplication)
- 🔒 **Reçus scellés** — sha256 par artefact, chaîne de preuves inviolable
- 🛡️ **5 portes de livraison** — acceptation, validation, exécution-vérification, régression, auto-examen
- ⚡ **Porte d'action** — classification des risques + liste de blocage pour les mutations initiées par chat
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Passerelles** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Système de compétences** — charge et enchaîne des capacités réutilisables
- 💾 **Base de données mémoire** — FTS persistant + rappel vectoriel entre sessions
- 🔀 **Routeur LLM** — aucun LLM → LLM local → LLM distant automatiquement
- 🖥️ **Multi-plateforme** — macOS, Linux, Windows, binaire unique

---

## 🎁 Bêta Publique Gratuite

**Les commandes déterministes sont GRATUITES pour toujours :**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Les fonctionnalités IA sont gratuites pendant la bêta publique sans date de fin.**
La facturation sera définie dans les futures mises à jour.

```bash
simplicio license status
```

---

## 📋 Prérequis

| Prérequis | Minimum | Recommandé |
|---|---|---|
| RAM | 8 Go | 16 Go+ |
| Stockage | 5 Mo | 1,5 Go (avec LLM local) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | tout terminal moderne | WezTerm / Alacritty / Ghostty |

---

## 🌐 Écosystème

- [Site Web](https://simpleti.com.br/simplicio/#start) — docs complètes, benchmarks, installation
- [Discord](https://discord.gg/wM6tr7xVb) — communauté et support

---

## 📄 Licence

Propriétaire. Binaire gratuit à télécharger et à utiliser. Fonctionnalités IA gratuites pendant la
bêta publique. Voir [LICENSE](LICENSE).

---

## ⭐ Star History

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 Communauté

- [Discord](https://discord.gg/wM6tr7xVb) — chat, support, accès anticipé
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — bugs et demandes de fonctionnalités

---

<p align="center">
  <strong>🔥 Simplicio — Votre code, votre machine, 96 % moins cher. 🔥</strong>
</p>

# 🔥 Simplicio — L'Agente AI CHE RISPARMIA FINO AL 96% DEI TUOI TOKEN

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Ultima versione"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stelle"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Download"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="Licenza"></a>
</p>

<p align="center">
  <a href="#-installazione">Installa</a> ·
  <a href="#-cosa-fa">Funzionalità</a> ·
  <a href="#-risparmio-token">96% Risparmio</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Sito web</a>
</p>

<p align="center">
  <strong>🌍 Lingue:</strong><br>
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

**Simplicio** è un agente AI da terminale — un singolo binario che sostituisce
l'intero flusso di lavoro di sviluppo assistito dall'AI: chat, generazione di codice,
contesto del repository, pianificazione, orchestrazione multi-agente locale (64 → 600 agenti),
e consegna di PR supportata da prove concrete.

**Funziona sulla tua macchina. Il tuo codice non lascia mai il tuo controllo. I modelli remoti sono
opzionali, non obbligatori.**

> **🔥 Risparmia fino al 96% di token rispetto agli agenti tradizionali — più di Caveman (65%) o RTK (80%).**
> Ogni interazione mostra esattamente quanti token hai risparmiato. Singolo binario Rust, zero dipendenze.

## 🚀 Installazione

### npm / npx (qualsiasi OS)

```bash
npx simplicio install
```

### pip / PyPI (qualsiasi OS)

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

Fatto. Un comando. Nessun package manager, nessuna configurazione del modello.

---

## 💰 Risparmio Token — Il 96% è Reale

**Senza Simplicio:** ogni sessione AI riscopre il tuo repository, carica troppo
contesto, ripete i prompt, brucia token a pagamento.

**Con Simplicio:**

| Ottimizzazione | Risparmio |
|---|---|
| 🗺️ **Mappa del Repository** — contesto compresso invece di leggere file grezzi | ~70% |
| 🧠 **Memoria Recupero** — i fatti noti non vengono ri-derivati | ~80% |
| ✏️ **Modifica Deterministica** — modifiche senza spendere token LLM | 100% (output) |
| 🏠 **LLM Locale** — classificazione, riepilogo, modifiche a basso rischio | ~90% |
| 📡 **LLM Remoto** — solo per pianificazione e decisioni complesse | ~85% |
| 🔀 **Fan-out Locale** — 64→600 agenti prima di scalare sul cloud | ~95% |
| **💎 Combinato: fino al 96% di risparmio totale** | **~96%** |

**Ogni risposta di Simplicio mostra il risparmio reale:** `Simplicio: ~X token spesi · risparmiati ~Y (Z%)`

---

## 🎯 Cosa Fa

| Comando | Descrizione | Token |
|---|---|---|
| `simplicio map --repo .` | Mappa il repository per gli LLM | ~70% risparmio |
| `simplicio memory "query"` | Recupero neurale (FTS + vettori) | ~80% risparmio |
| `simplicio edit '{...}'` | Modifica file deterministica | **Zero token** |
| `simplicio coding-loop "task"` | Itera finché i test non passano | Auto-riparazione |
| `simplicio deliver certify` | 5 gate di qualità prima del rilascio | Deterministico |
| `simplicio run "task" --agents N` | Orchestrazione multi-agente | Locale prima |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Approccio** | Compressione dello stile di output | Proxy di comandi shell | **Runtime agente completo** |
| **Risparmio max** | ~65% token output | ~80% su comandi shell | **Fino al 96% totale** |
| **Compressione input** | ❌ | ✅ (filtrato) | ✅ **Mappa repo + memoria neurale** |
| **Compressione output** | ✅ (linguaggio cavernicolo) | ❌ | ✅ **Modifiche deterministiche a zero token** |
| **LLM Locale** | ❌ | ❌ | ✅ **llama.cpp integrato** |
| **Multi-agente** | ❌ | ❌ | ✅ **64 → 600 agenti locali** |
| **Memoria tra sessioni** | ❌ | ❌ | ✅ **Recupero FTS + vettoriale** |
| **Catena di prove** | ❌ | ❌ | ✅ **Ricevute sigillate sha256** |
| **Linguaggio** | JS/Python (skill) | Rust (binario) | **Rust (singolo binario)** |
| **Licenza** | MIT | Apache 2.0 | Proprietaria |
| **Stelle** | 72.5k | 62.2k | ⭐ **Sei tra i primi** |

**In sintesi:** Caveman fa *parlare* meno l'AI. RTK fa *produrre* meno output ai comandi.
Simplicio fa *pensare* meno l'AI — ricordando, mappando, modificando deterministicamente,
ed eseguendo localmente prima di toccare un LLM a pagamento.

| **Simplicio risparmia il 96% dove Caveman risparmia il 65% e RTK l'80%.** |

---

## 🏗️ Architettura

```
LLM (Claude/Codex/Gemini)          Simplicio Runtime (Rust)
  |                                   |
  | 1. Orient                         | simplicio map
  | 2. Recall                         | simplicio memory
  | 3. Decide                         |
  | 4. Edit  ───────────────────────> | simplicio edit (0 token)
  | 5. Verify <─────────────────────  | simplicio deliver certify
  | 6. Iterate                        | simplicio coding-loop
```

**L'LLM ragiona. Simplicio esegue deterministicamente.**

---

## ✨ Funzionalità

- 🏠 **Locale prima** — llama.cpp integrato, scala su remoto solo quando necessario
- 🪜 **Agenti a livelli** — 64 → 100 → 200 → 600 agenti locali prima del cloud a pagamento
- 🔇 **Gate di novità Shannon** — filtra output ridondanti (zero token sul dedup)
- 🔒 **Ricevute sigillate** — sha256 per artefatto, catena di prove a prova di manomissione
- 🛡️ **5 gate di consegna** — accettazione, validazione, esecuzione-verifica, regressione, auto-revisione
- ⚡ **Gate d'azione** — classificazione del rischio + blocklist per mutazioni avviate da chat
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Gateway** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Sistema di skill** — carica e incatena capacità riutilizzabili
- 💾 **Database di memoria** — recupero FTS + vettoriale persistente tra sessioni
- 🔀 **Router LLM** — nessun LLM → LLM locale → LLM remoto automaticamente
- 🖥️ **Multi-piattaforma** — macOS, Linux, Windows, singolo binario

---

## 🎁 Beta Pubblica Gratuita

**I comandi deterministici sono GRATUITI per sempre:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Le funzionalità AI sono gratuite durante la beta pubblica senza data di scadenza.**
La fatturazione sarà definita in aggiornamenti futuri.

```bash
simplicio license status
```

---

## 📋 Requisiti

| Requisito | Minimo | Consigliato |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Archiviazione | 5 MB | 1.5 GB (con LLM locale) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminale | qualsiasi terminale moderno | WezTerm / Alacritty / Ghostty |

---

## 🌐 Ecosistema

- [Sito web](https://simpleti.com.br/simplicio/#start) — documentazione completa, benchmark, installazione
- [Discord](https://discord.gg/wM6tr7xVb) — community e supporto

---

## 📄 Licenza

Proprietaria. Binario gratuito da scaricare e utilizzare. Funzionalità AI gratuite durante la
beta pubblica. Vedi [LICENSE](LICENSE).

---

## ⭐ Cronologia Stelle

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="Grafico cronologia stelle" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 Community

- [Discord](https://discord.gg/wM6tr7xVb) — chat, supporto, accesso anticipato
- [Issue GitHub](https://github.com/wesleysimplicio/simplicio/issues) — bug e richieste di funzionalità

---

<p align="center">
  <strong>🔥 Simplicio — Il tuo codice, la tua macchina, il 96% più economico. 🔥</strong>
</p>

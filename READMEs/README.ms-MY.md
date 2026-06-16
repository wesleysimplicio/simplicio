# 🔥 Simplicio — Ejen AI Yang MENJIMATKAN SEHINGGA 96% TOKEN ANDA

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — ejen pengekodan AI" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=terkini" alt="Keluaran Terkini"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Bintang"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Muat Turun"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licensi-Proprietary-red" alt="Lesen"></a>
</p>

<p align="center">
  <a href="#-pemasangan">Pasang</a> ·
  <a href="#-apa-yang-ia-lakukan">Ciri</a> ·
  <a href="#-penjimatan-token">Penjimatan 96%</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Laman Web</a>
</p>

<p align="center">
  <strong>🌍 Bahasa:</strong><br>
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

## ⚡ RL;DR

**Simplicio** ialah ejen pengekodan AI terminal — satu binari yang menggantikan
keseluruhan aliran kerja pembangunan berbantu AI anda: sembang, penjanaan kod,
konteks repositori, perancangan, orkestrasi multi-ejen tempatan (64 → 600 ejen),
dan penghantaran PR berasaskan bukti.

**Berjalan di mesin anda. Kod anda tidak pernah meninggalkan kawalan anda. Model
jarak jauh adalah pilihan, bukan keperluan.**

> **🔥 Jimat sehingga 96% token berbanding ejen tradisional — lebih daripada Caveman (65%) atau RTK (80%).**
> Setiap interaksi menunjukkan dengan tepat berapa banyak token yang anda jimatkan. Binari Rust tunggal, sifar kebergantungan.

## 🚀 Pemasangan

### npm / npx (sebarang OS)

```bash
npx simplicio install
```

### pip / PyPI (sebarang OS)

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

Selesai. Satu arahan. Tiada pengurus pakej, tiada konfigurasi model.

---

## 💰 Penjimatan Token — 96% Adalah Nyata

**Tanpa Simplicio:** setiap sesi AI menemui semula repositori anda, memuatkan terlalu
banyak konteks, mengulang gesaan, membakar token berbayar.

**Dengan Simplicio:**

| Pengoptimuman | Penjimatan |
|---|---|
| 🗺️ **Peta Repo** — konteks dimampatkan dan bukannya membaca fail mentah | ~70% |
| 🧠 **Ingatan Semula** — fakta diketahui tidak diterbitkan semula | ~80% |
| ✏️ **Suntingan Deterministik** — perubahan tanpa menggunakan token LLM | 100% (output) |
| 🏠 **LLM Tempatan** — pengelasan, rumusan, suntingan berisiko rendah | ~90% |
| 📡 **LLM Jarak Jauh** — hanya untuk perancangan dan keputusan kompleks | ~85% |
| 🔀 **Fan-out Tempatan** — 64→600 ejen sebelum penskalaan ke awan | ~95% |
| **💎 Gabungan: sehingga 96% jumlah penjimatan** | **~96%** |

**Setiap respons Simplicio menunjukkan penjimatan sebenar:** `Simplicio: ~X token digunakan · jimat ~Y (Z%)`

---

## 🎯 Apa Yang Ia Lakukan

| Perintah | Penerangan | Token |
|---|---|---|
| `simplicio map --repo .` | Memetakan repositori untuk LLM | ~70% penjimatan |
| `simplicio memory "query"` | Ingatan semula neural (FTS + vektor) | ~80% penjimatan |
| `simplicio edit '{...}'` | Suntingan fail deterministik | **Sifar token** |
| `simplicio coding-loop "tugas"` | Berulang sehingga ujian lulus | Auto-pembaikan |
| `simplicio deliver certify` | 5 pintu kualiti sebelum penghantaran | Deterministik |
| `simplicio run "tugas" --agents N` | Orkestrasi multi-ejen | Tempatan-dahulu |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Pendekatan** | Mampatan gaya output | Proksi arahan shell | **Runtime ejen penuh** |
| **Penjimatan maks** | ~65% token output | ~80% pada arahan shell | **Sehingga 96% jumlah** |
| **Mampatan input** | ❌ | ✅ (ditapis) | ✅ **Peta repo + ingatan neural** |
| **Mampatan output** | ✅ (caveman-speak) | ❌ | ✅ **Suntingan deterministik sifar token** |
| **LLM Tempatan** | ❌ | ❌ | ✅ **llama.cpp terbina dalam** |
| **Multi-ejen** | ❌ | ❌ | ✅ **64 → 600 ejen tempatan** |
| **Ingatan merentas sesi** | ❌ | ❌ | ✅ **FTS + ingatan vektor** |
| **Rantaian bukti** | ❌ | ❌ | ✅ **Resit bermeterai sha256** |
| **Bahasa** | JS/Python (kemahiran) | Rust (binari) | **Rust (binari tunggal)** |
| **Lesen** | MIT | Apache 2.0 | Proprietari |
| **Bintang** | 72.5k | 62.2k | ⭐ **Anda awal** |

**Kesimpulan:** Caveman membuat AI *bercakap* kurang. RTK membuat arahan *output* kurang.
Simplicio membuat AI *berfikir* kurang — dengan mengingat, memetakan, menyunting secara
deterministik, dan berjalan secara tempatan sebelum menyentuh LLM berbayar.

| **Simplicio menjimatkan 96% di mana Caveman menjimatkan 65% dan RTK menjimatkan 80%.** |

---

## 🏗️ Seni Bina

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

**LLM menaakul. Simplicio melaksana secara deterministik.**

---

## ✨ Ciri

- 🏠 **Tempatan-dahulu** — llama.cpp terbina dalam, skala ke jarak jauh hanya apabila perlu
- 🪜 **Ejen bertingkat** — 64 → 100 → 200 → 600 ejen tempatan sebelum awan berbayar
- 🔇 **Gerbang kebaharuan Shannon** — menapis output berlebihan (sifar token pada dedup)
- 🔒 **Resit bermeterai** — sha256 setiap artifak, rantaian bukti kalis gangguan
- 🛡️ **5 pintu penghantaran** — penerimaan, pengesahan, laksana-verify, regresi, semakan sendiri
- ⚡ **Gerbang tindakan** — pengelasan risiko + senarai blok untuk mutasi cetusan sembang
- 🔌 **MCP/ACP** — Protokol Konteks Model + Protokol Klien Ejen
- 🌐 **Gerbang** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Sistem kemahiran** — memuat dan merantai kebolehan boleh guna semula
- 💾 **Pangkalan data ingatan** — FTS berterusan + ingatan vektor merentas sesi
- 🔀 **Penghala LLM** — tiada LLM → LLM tempatan → LLM jarak jauh secara automatik
- 🖥️ **Merentas platform** — macOS, Linux, Windows, binari tunggal

---

## 🎁 Beta Awam Percuma

**Perintah deterministik adalah PERCUMA selama-lamanya:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Ciri AI adalah percuma semasa beta awam tanpa tarikh tamat.**
Pengecasan akan ditentukan dalam kemas kini akan datang.

```bash
simplicio license status
```

---

## 📋 Keperluan

| Keperluan | Minimum | Disarankan |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Storan | 5 MB | 1.5 GB (dengan LLM tempatan) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | mana-mana terminal moden | WezTerm / Alacritty / Ghostty |

---

## 🌐 Ekosistem

- [Laman Web](https://simpleti.com.br/simplicio/#start) — dokumen penuh, penanda aras, pemasangan
- [Discord](https://discord.gg/wM6tr7xVb) — komuniti dan sokongan

---

## 📄 Lesen

Proprietari. Binari percuma untuk dimuat turun dan digunakan. Ciri AI percuma
semasa beta awam. Lihat [LICENSE](LICENSE).

---

## ⭐ Sejarah Bintang

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <img src="https://api.star-history.com/svg?repos=wesleysimplicio/simplicio&type=Date" alt="Carta Sejarah Bintang" width="100%" />
</a>

---

## 💬 Komuniti

- [Discord](https://discord.gg/wM6tr7xVb) — sembang, sokongan, akses awal
- [Isu GitHub](https://github.com/wesleysimplicio/simplicio/issues) — pepijat dan permintaan ciri

---

<p align="center">
  <strong>🔥 Simplicio — Kod anda, mesin anda, 96% lebih murah. 🔥</strong>
</p>

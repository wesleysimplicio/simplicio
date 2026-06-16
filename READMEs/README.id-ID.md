# 🔥 Simplicio — Agen AI yang MENGHEMAT HINGGA 96% TOKEN ANDA

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI coding agent" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Rilis Terbaru"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Bintang"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Unduhan"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="Lisensi"></a>
</p>

<p align="center">
  <a href="#instalasi">Instalasi</a> ·
  <a href="#yang-dilakukan">Yang Dilakukan</a> ·
  <a href="#penghematan-token--96-nyata">Penghematan Token — 96% Nyata</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Situs Web</a>
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

## ⚡ TL;DR

**Simplicio** adalah agen coding AI berbasis terminal — satu biner yang menggantikan
seluruh alur kerja pengembangan berbantuan AI Anda: obrolan, pembuatan kode, konteks
repositori, perencanaan, orkestrasi multi-agen lokal (64 → 600 agen), dan
pengiriman PR berbasis bukti.

**Berjalan di mesin Anda. Kode Anda tidak pernah meninggalkan kendali Anda. Model jarak jauh
bersifat opsional, tidak wajib.**

> **🔥 Hemat hingga 96% token dibandingkan agen tradisional — lebih dari Caveman (65%) atau RTK (80%).**
> Setiap interaksi menunjukkan persis berapa banyak token yang Anda hemat. Biner Rust tunggal, tanpa dependensi.

## 🚀 Instalasi

### npm / npx (OS apa saja)

```bash
npx simplicio install
```

### pip / PyPI (OS apa saja)

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

Selesai. Satu perintah. Tanpa manajer paket, tanpa konfigurasi model.

---

## 💰 Penghematan Token — 96% Nyata

**Tanpa Simplicio:** setiap sesi AI menemukan ulang repositori Anda, memuat terlalu
banyak konteks, mengulangi prompt, dan menghabiskan token berbayar.

**Dengan Simplicio:**

| Optimasi | Penghematan |
|---|---|
| 🗺️ **Peta Repo** — konteks terkompresi, bukan membaca file mentah | ~70% |
| 🧠 **Memori Panggil Ulang** — fakta yang diketahui tidak diulang kembali | ~80% |
| ✏️ **Pengeditan Deterministik** — perubahan tanpa menghabiskan token LLM | 100% (output) |
| 🏠 **LLM Lokal** — klasifikasi, perangkuman, suntingan berisiko rendah | ~90% |
| 📡 **LLM Jarak Jauh** — hanya untuk perencanaan dan keputusan kompleks | ~85% |
| 🔀 **Fan-out Lokal** — 64→600 agen sebelum naik ke cloud | ~95% |
| **💎 Gabungan: hingga 96% total penghematan** | **~96%** |

**Setiap respons Simplicio menunjukkan penghematan nyata:** `Simplicio: ~X token digunakan · hemat ~Y (Z%)`

---

## 🎯 Yang Dilakukan

| Perintah | Deskripsi | Token |
|---|---|---|
| `simplicio map --repo .` | Memetakan repositori untuk LLM | ~70% hemat |
| `simplicio memory "query"` | Panggil ulang neural (FTS + vektor) | ~80% hemat |
| `simplicio edit '{...}'` | Pengeditan file deterministik | **Nol token** |
| `simplicio coding-loop "task"` | Mengulang hingga pengujian lulus | Perbaikan-otomatis |
| `simplicio deliver certify` | 5 gerbang kualitas sebelum dikirim | Deterministik |
| `simplicio run "task" --agents N` | Orkestrasi multi-agen | Lokal-pertama |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Pendekatan** | Kompresi gaya output | Proksi perintah shell | **Runtime agen penuh** |
| **Hemat maksimal** | ~65% token output | ~80% pada perintah shell | **Hingga 96% total** |
| **Kompresi input** | ❌ | ✅ (difilter) | ✅ **Peta repo + memori neural** |
| **Kompresi output** | ✅ (caveman-speak) | ❌ | ✅ **Suntingan deterministik nol-token** |
| **LLM Lokal** | ❌ | ❌ | ✅ **llama.cpp bawaan** |
| **Multi-agen** | ❌ | ❌ | ✅ **64 → 600 agen lokal** |
| **Memori antar sesi** | ❌ | ❌ | ✅ **FTS + panggil ulang vektor** |
| **Rantai bukti** | ❌ | ❌ | ✅ **Tanda terima tersegel sha256** |
| **Bahasa** | JS/Python (skill) | Rust (biner) | **Rust (biner tunggal)** |
| **Lisensi** | MIT | Apache 2.0 | Kepemilikan |
| **Bintang** | 72,5k | 62,2k | ⭐ **Anda pelopor** |

**Intinya:** Caveman membuat AI *berbicara* lebih sedikit. RTK membuat perintah *mengeluarkan*
lebih sedikit. Simplicio membuat AI *berpikir* lebih sedikit — dengan mengingat, memetakan,
menyunting secara deterministik, dan berjalan secara lokal sebelum menyentuh LLM berbayar.

| **Simplicio menghemat 96% di mana Caveman menghemat 65% dan RTK menghemat 80%.** |

---

## 🏗️ Arsitektur

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

**LLM bernalar. Simplicio mengeksekusi secara deterministik.**

---

## ✨ Fitur

- 🏠 **Lokal-pertama** — llama.cpp bawaan, naik ke jarak jauh hanya jika diperlukan
- 🪜 **Agen bertingkat** — 64 → 100 → 200 → 600 agen lokal sebelum cloud berbayar
- 🔇 **Gerbang kebaruan Shannon** — menyaring output yang redundan (nol token saat dedup)
- 🔒 **Tanda terima tersegel** — sha256 per artefak, rantai bukti anti-rusak
- 🛡️ **5 gerbang pengiriman** — penerimaan, validasi, jalankan-verifikasi, regresi, tinjauan-mandiri
- ⚡ **Gerbang aksi** — klasifikasi risiko + blokir untuk mutasi yang dimulai dari obrolan
- 🔌 **MCP/ACP** — Model Context Protocol + Agent Client Protocol
- 🌐 **Gerbang** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Sistem skill** — memuat dan merantai kemampuan yang dapat digunakan ulang
- 💾 **DB Memori** — FTS persisten + panggil ulang vektor antar sesi
- 🔀 **Router LLM** — tanpa LLM → LLM lokal → LLM jarak jauh secara otomatis
- 🖥️ **Lintas-platform** — macOS, Linux, Windows, biner tunggal

---

## 🎁 Beta Publik Gratis

**Perintah deterministik GRATIS selamanya:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Fitur AI gratis selama beta publik tanpa tanggal akhir.**
Penagihan akan ditentukan di pembaruan mendatang.

```bash
simplicio license status
```

---

## 📋 Persyaratan

| Persyaratan | Minimum | Direkomendasikan |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Penyimpanan | 5 MB | 1,5 GB (dengan LLM lokal) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | terminal modern apa saja | WezTerm / Alacritty / Ghostty |

---

## 🌐 Ekosistem

- [Situs Web](https://simpleti.com.br/simplicio/#start) — dokumentasi lengkap, tolok ukur, instalasi
- [Discord](https://discord.gg/wM6tr7xVb) — komunitas dan dukungan

---

## 📄 Lisensi

Kepemilikan. Biner gratis untuk diunduh dan digunakan. Fitur AI gratis selama
beta publik. Lihat [LICENSE](LICENSE).

---

## ⭐ Riwayat Bintang

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <img src="https://api.star-history.com/svg?repos=wesleysimplicio/simplicio&type=Date" alt="Grafik Riwayat Bintang" width="100%" />
</a>

---

## 💬 Komunitas

- [Discord](https://discord.gg/wM6tr7xVb) — obrolan, dukungan, akses awal
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — laporan bug dan permintaan fitur

---

<p align="center">
  <strong>🔥 Simplicio — Kode Anda, mesin Anda, 96% lebih murah. 🔥</strong>
</p>

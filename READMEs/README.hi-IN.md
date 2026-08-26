# 🔥 Simplicio — AI एजेंट जो आपके 96% टोकन बचाता है

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — AI कोडिंग एजेंट" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Latest Release"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Stars"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Downloads"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="License"></a>
</p>

<p align="center">
  <a href="#इंस्टॉलेशन">इंस्टॉलेशन</a> ·
  <a href="#यह-क्या-करता-है">यह क्या करता है</a> ·
  <a href="#टोकन-बचत--96-वास्तविक-है">टोकन बचत — 96% वास्तविक है</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">वेबसाइट</a>
</p>

<p align="center">
  <strong>🌍 भाषाएँ:</strong><br>
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

**Simplicio** एक टर्मिनल AI कोडिंग एजेंट है — एक एकल बाइनरी जो आपके संपूर्ण
AI-सहायित विकास कार्यप्रवाह को बदल देता है: चैट, कोड जनरेशन, रिपॉजिटरी
संदर्भ, योजना, स्थानीय मल्टी-एजेंट ऑर्केस्ट्रेशन (64 → 600 एजेंट), और
साक्ष्य-समर्थित PR डिलीवरी।

**आपकी मशीन पर चलता है। आपका कोड कभी आपके नियंत्रण से बाहर नहीं जाता। रिमोट मॉडल
वैकल्पिक हैं, अनिवार्य नहीं।**

> **🔥 पारंपरिक एजेंटों की तुलना में 96% तक टोकन बचाएं — Caveman (65%) या RTK (80%) से अधिक।**
> हर इंटरैक्शन दिखाता है कि आपने कितने टोकन बचाए। एकल Rust बाइनरी, शून्य निर्भरताएँ।

## 🚀 इंस्टॉलेशन

### npm / npx (किसी भी OS पर)

```bash
npx simplicio install
```

### pip / PyPI (किसी भी OS पर)

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

### प्रत्यक्ष इंस्टॉलर (PyPI के बिना)

macOS / Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex
```

हो गया। एक कमांड। कोई पैकेज मैनेजर नहीं, कोई मॉडल कॉन्फ़िगरेशन नहीं।

---

## 💰 टोकन बचत — 96% वास्तविक है

**Simplicio के बिना:** हर AI सत्र आपके रिपॉजिटरी को फिर से खोजता है, बहुत अधिक
संदर्भ लोड करता है, प्रॉम्प्ट दोहराता है, भुगतान वाले टोकन जलाता है।

**Simplicio के साथ:**

| अनुकूलन | बचत |
|---|---|
| 🗺️ **रिपो मैप** — कच्ची फ़ाइलें पढ़ने के बजाय संपीड़ित संदर्भ | ~70% |
| 🧠 **मेमोरी रिकॉल** — ज्ञात तथ्य पुनः व्युत्पन्न नहीं होते | ~80% |
| ✏️ **निर्धारित संपादन** — LLM टोकन खर्च किए बिना बदलाव | 100% (आउटपुट) |
| 🏠 **स्थानीय LLM** — वर्गीकरण, सारांशीकरण, कम-जोखिम वाले संपादन | ~90% |
| 📡 **रिमोट LLM** — केवल योजना और जटिल निर्णयों के लिए | ~85% |
| 🔀 **स्थानीय फैन-आउट** — क्लाउड पर जाने से पहले 64→600 एजेंट | ~95% |
| **💎 संयुक्त: कुल 96% तक बचत** | **~96%** |

**हर Simplicio प्रतिक्रिया वास्तविक बचत दिखाती है:** `Simplicio: ~X टोकन खर्च · ~Y बचत (Z%)`

---

## 🎯 यह क्या करता है

| कमांड | विवरण | टोकन |
|---|---|---|
| `simplicio map --repo .` | LLM के लिए रिपॉजिटरी मैप करता है | ~70% बचत |
| `simplicio memory "query"` | न्यूरल रिकॉल (FTS + वेक्टर) | ~80% बचत |
| `simplicio edit '{...}'` | निर्धारित फ़ाइल संपादन | **शून्य टोकन** |
| `simplicio coding-loop "task"` | टेस्ट पास होने तक दोहराता है | ऑटो-रिपेयर |
| `simplicio deliver certify` | शिप करने से पहले 5 गुणवत्ता गेट | निर्धारित |
| `simplicio run "task" --agents N` | मल्टी-एजेंट ऑर्केस्ट्रेशन | स्थानीय-प्रथम |

---

## 🆚 Simplicio बनाम Caveman बनाम RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **दृष्टिकोण** | आउटपुट शैली संपीड़न | शेल कमांड प्रॉक्सी | **पूर्ण एजेंट रनटाइम** |
| **अधिकतम बचत** | ~65% आउटपुट टोकन | ~80% शेल कमांड पर | **कुल 96% तक** |
| **इनपुट संपीड़न** | ❌ | ✅ (फ़िल्टर्ड) | ✅ **रिपो मैप + न्यूरल मेमोरी** |
| **आउटपुट संपीड़न** | ✅ (गुफावासी बोली) | ❌ | ✅ **शून्य-टोकन निर्धारित संपादन** |
| **स्थानीय LLM** | ❌ | ❌ | ✅ **अंतर्निहित llama.cpp** |
| **मल्टी-एजेंट** | ❌ | ❌ | ✅ **64 → 600 स्थानीय एजेंट** |
| **सत्रों में मेमोरी** | ❌ | ❌ | ✅ **FTS + वेक्टर रिकॉल** |
| **साक्ष्य श्रृंखला** | ❌ | ❌ | ✅ **sha256 सीलबंद रसीदें** |
| **भाषा** | JS/Python (स्किल) | Rust (बाइनरी) | **Rust (एकल बाइनरी)** |
| **लाइसेंस** | MIT | Apache 2.0 | Proprietary |
| **स्टार्स** | 72.5k | 62.2k | ⭐ **आप जल्दी आए** |

**निचली पंक्ति:** Caveman AI को *कम बोलने* पर मजबूर करता है। RTK कमांड को *कम आउटपुट* देता है।
Simplicio AI को *कम सोचने* पर मजबूर करता है — याद रखकर, मैप करके, निर्धारित रूप से संपादित करके,
और किसी भी भुगतान वाले LLM को छूने से पहले स्थानीय रूप से चलाकर।

| **Simplicio 96% बचाता है जहाँ Caveman 65% और RTK 80% बचाता है।** |

---

## 🏗️ आर्किटेक्चर

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

**LLM तर्क करता है। Simplicio निर्धारित रूप से निष्पादित करता है।**

---

## ✨ सुविधाएँ

- 🏠 **स्थानीय-प्रथम** — अंतर्निहित llama.cpp, केवल ज़रूरत पड़ने पर रिमोट पर स्केल करें
- 🪜 **स्तरीय एजेंट** — भुगतान वाले क्लाउड से पहले 64 → 100 → 200 → 600 स्थानीय एजेंट
- 🔇 **शैनन नवीनता गेट** — डुप्लिकेट आउटपुट फ़िल्टर करता है (डीडुप पर शून्य टोकन)
- 🔒 **सीलबंद रसीदें** — प्रति आर्टिफैक्ट sha256, छेड़छाड़-रोधी साक्ष्य श्रृंखला
- 🛡️ **5 डिलीवरी गेट** — स्वीकृति, सत्यापन, रन-वेरिफाई, रिग्रेशन, सेल्फ-रिव्यू
- ⚡ **एक्शन गेट** — चैट-आरंभित म्यूटेशन के लिए जोखिम वर्गीकरण + ब्लॉकलिस्ट
- 🔌 **MCP/ACP** — मॉडल कॉन्टेक्स्ट प्रोटोकॉल + एजेंट क्लाइंट प्रोटोकॉल
- 🌐 **गेटवे** — टेलीग्राम, डिस्कॉर्ड, स्लैक, व्हाट्सएप
- 🧩 **स्किल सिस्टम** — पुन: प्रयोज्य क्षमताओं को लोड और चेन करता है
- 💾 **मेमोरी DB** — सत्रों में स्थायी FTS + वेक्टर रिकॉल
- 🔀 **LLM राउटर** — कोई LLM नहीं → स्थानीय LLM → रिमोट LLM स्वचालित रूप से
- 🖥️ **क्रॉस-प्लेटफ़ॉर्म** — macOS, Linux, Windows, एकल बाइनरी

---

## 🎁 मुफ्त सार्वजनिक बीटा

**निर्धारित कमांड हमेशा के लिए मुफ्त हैं:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**AI सुविधाएँ सार्वजनिक बीटा के दौरान बिना किसी समाप्ति तिथि के मुफ्त हैं।**
भविष्य के अपडेट में बिलिंग निर्धारित की जाएगी।

```bash
simplicio license status
```

---

## 📋 आवश्यकताएँ

| आवश्यकता | न्यूनतम | अनुशंसित |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| स्टोरेज | 5 MB | 1.5 GB (स्थानीय LLM के साथ) |
| OS | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| टर्मिनल | कोई भी आधुनिक टर्मिनल | WezTerm / Alacritty / Ghostty |

---

## 🌐 पारिस्थितिकी तंत्र

- [वेबसाइट](https://simpleti.com.br/simplicio/#start) — पूर्ण दस्तावेज़, बेंचमार्क, इंस्टॉल
- [डिस्कॉर्ड](https://discord.gg/wM6tr7xVb) — समुदाय और सहायता

---

## 📄 लाइसेंस

Proprietary. बाइनरी डाउनलोड और उपयोग करने के लिए मुफ्त है। AI सुविधाएँ
सार्वजनिक बीटा के दौरान मुफ्त हैं। [LICENSE](LICENSE) देखें।

---

## ⭐ स्टार इतिहास

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="स्टार हिस्ट्री चार्ट" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 समुदाय

- [डिस्कॉर्ड](https://discord.gg/wM6tr7xVb) — चैट, सहायता, प्रारंभिक पहुँच
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — बग और फीचर अनुरोध

---

<p align="center">
  <strong>🔥 Simplicio — आपका कोड, आपकी मशीन, 96% सस्ता। 🔥</strong>
</p>

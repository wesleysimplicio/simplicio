# simplicio

**एक बाइनरी। शून्य सेटअप। आपका AI कोडिंग एजेंट टर्मिनल में।**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## संक्षेप

`simplicio` एक एकल बाइनरी, टर्मिनल-नेटिव AI कोडिंग एजेंट है। इसे डाउनलोड करें, चलाएँ, और आपको एक पूर्ण AI-सहायता प्राप्त विकास वातावरण मिलेगा — चैट, कोड जनरेशन, रिपॉजिटरी संदर्भ मैपिंग, कार्य योजना, स्थानीय LLM ऑर्केस्ट्रेशन और साक्ष्य-आधारित PR डिलीवरी।

आपका कोड आपकी मशीन पर रहता है। रिमोट मॉडल वैकल्पिक हैं।

## इंस्टॉलेशन

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

## त्वरित आरंभ

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "कार्य" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## क्षमताएँ

Chat REPL, स्वायत्त एजेंट मोड, रिपॉजिटरी मैपिंग, स्थानीय LLM (llama.cpp), 50–600+ समानांतर उप-एजेंट निष्पादन, साक्ष्य पाइपलाइन, PR ऑटोमेशन, गेटवे (Telegram, Discord, Slack, WhatsApp), MCP और ACP सर्वर, कौशल प्रणाली, स्थायी स्मृति, LLM राउटर (कोई LLM नहीं → स्थानीय → रिमोट), बिना टोकन के निर्धारित संपादन, macOS, Linux और Windows के लिए समर्थन।

## सार्वजनिक बीटा

**बिना किसी समाप्ति तिथि के सार्वजनिक बीटा के दौरान सब कुछ मुफ़्त है।** बिलिंग भविष्य के अपडेट में परिभाषित की जाएगी। नियतात्मक कमांड (map, validate, edit, deliver, checkpoint) हमेशा के लिए मुफ़्त हैं।

और अधिक: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

# simplicio

**ملف ثنائي واحد. بدون إعداد. وكيل AI للبرمجة في الطرفية.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## ملخص

`simplicio` هو وكيل AI وحيد للبرمجة، ملف ثنائي واحد أصلي للطرفية. نزّله وشغّله لتحصل على بيئة تطوير كاملة مدعومة بالذكاء الاصطناعي — محادثة، توليد كود، رسم خريطة سياق المستودع، تخطيط المهام، تنسيق LLM المحلي، وتسليم PR المستند إلى الأدلة.

يبقى كودك على جهازك. النماذج البعيدة اختيارية.

## التثبيت

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

## بداية سريعة

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "مهمة" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## الميزات

Chat REPL، وضع الوكيل المستقل، رسم خريطة المستودع، LLM محلي (llama.cpp)، تنفيذ متوازي لـ 50–600+ وكيل فرعي، خط أنابيب الأدلة، أتمتة PR، بوابات (Telegram، Discord، Slack، WhatsApp)، خادم MCP و ACP، نظام المهارات، ذاكرة دائمة، موجه LLM (بدون LLM → محلي → بعيد)، تحرير حتمي بدون رموز LLM، دعم macOS و Linux و Windows.

## النسخة التجريبية العامة

**كل شيء مجاني خلال النسخة التجريبية العامة بدون تاريخ انتهاء.** سيتم تحديد الفوترة في التحديثات المستقبلية. الأوامر الحتمية (map، validate، edit، deliver، checkpoint) مجانية للأبد.** بعد النسخة التجريبية، تتطلب ميزات AI اشتراكًا. الأوامر الحتمية (map, validate, edit, deliver, checkpoint) تبقى مجانية إلى الأبد.

المزيد: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/#start)

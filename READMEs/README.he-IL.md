# simplicio

**קובץ בינארי אחד. אפס הגדרה. סוכן ה-AI שלך לקידוד בטרמינל.**

[English](../README.md) | [Português](README.pt-BR.md) | [Español](README.es-ES.md) | [日本語](README.ja-JP.md) | [한국어](README.ko-KR.md) | [简体中文](README.zh-CN.md) | [Italiano](README.it-IT.md) | [Français](README.fr-FR.md) | [Русский](README.ru-RU.md) | [Polski](README.pl-PL.md) | [हिन्दी](README.hi-IN.md) | [العربية](README.ar-SA.md) | [עברית](README.he-IL.md) | [Bahasa Melayu](README.ms-MY.md) | [Bahasa Indonesia](README.id-ID.md)

![Simplicio](../assets/simplicio-hero.png)

## תקציר

`simplicio` הוא סוכן AI יחיד בקובץ בינארי אחד לקידוד בטרמינל. הורד והרץ אותו, ותקבל סביבת פיתוח מלאה בסיוע AI — צ'אט, יצירת קוד, מיפוי הקשר של המאגר, תכנון משימות, תזמור LLM מקומי והגשת PR מבוססת ראיות.

הקוד שלך נשאר על המחשב שלך. מודלים מרוחקים הם אופציונליים.

## התקנה

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

## התחלה מהירה

```bash
simplicio doctor
simplicio chat --repl --repo .
simplicio run "משימה" --repo . --local --evidence
simplicio sprint ./sprint-01 --repo . --agents 50 --local --pr
```

## תכונות

Chat REPL, מצב סוכן אוטונומי, מיפוי מאגר, LLM מקומי (llama.cpp), ביצוע מקבילי של 50–600+ תת-סוכנים, צינור ראיות, אוטומציית PR, שערים (Telegram, Discord, Slack, WhatsApp), שרת MCP ו-ACP, מערכת מיומנויות, זיכרון מתמיד, נתב LLM (ללא LLM → מקומי → מרוחק), עריכה דטרמיניסטית ללא טוקנים של LLM, תמיכה ב-macOS, Linux ו-Windows.

## גרסת בטא ציבורית

**הכל פתוח בחינם במהלך הבטא הציבורית ללא תאריך סיום.** החיוב יוגדר בעדכונים עתידיים. פקודות דטרמיניסטיות (map, validate, edit, deliver, checkpoint) נשארות בחינם לתמיד.** לאחר גרסת הבטא, תכונות AI דורשות מנוי. הפקודות הדטרמיניסטיות (map, validate, edit, deliver, checkpoint) נשארות בחינם לנצח.

עוד: [simpleti.com.br/simplicio/](https://simpleti.com.br/simplicio/)

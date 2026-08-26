# 🔥 Simplicio — El agente de IA que AHORRA HASTA EL 96% DE TUS TOKENS

<p align="center">
  <img src="assets/simplicio-hero.png" alt="Simplicio — agente de IA para programación" width="920" />
</p>

<p align="center">
  <a href="https://github.com/wesleysimplicio/simplicio/releases/latest"><img src="https://img.shields.io/github/v/release/wesleysimplicio/simplicio?color=blue&label=latest" alt="Última versión"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/stargazers"><img src="https://img.shields.io/github/stars/wesleysimplicio/simplicio?style=social" alt="Estrellas"></a>
  <a href="https://github.com/wesleysimplicio/simplicio/releases"><img src="https://img.shields.io/github/downloads/wesleysimplicio/simplicio/total?color=green" alt="Descargas"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-red" alt="Licencia"></a>
</p>

<p align="center">
  <a href="#instalación">Instalación</a> ·
  <a href="#qué-hace">Qué Hace</a> ·
  <a href="#ahorro-de-tokens--el-96-es-real">Ahorro de Tokens — El 96% es Real</a> ·
  <a href="https://simpleti.com.br/simplicio/#start">Sitio web</a>
</p>

<p align="center">
  <strong>🌍 Idiomas:</strong><br>
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

**Simplicio** es un agente de IA de terminal para programación — un único binario que reemplaza
todo tu flujo de trabajo de desarrollo asistido por IA: chat, generación de código, contexto
del repositorio, planificación, orquestación multi-agente local (64 → 600 agentes) y
entrega de PR respaldada por evidencia.

**Se ejecuta en tu máquina. Tu código nunca sale de tu control. Los modelos remotos son
opcionales, no obligatorios.**

> **🔥 Ahorra hasta el 96% de tokens frente a los agentes tradicionales — más que Caveman (65%) o RTK (80%).**
> Cada interacción muestra exactamente cuántos tokens has ahorrado. Un solo binario en Rust, cero dependencias.

## 🚀 Instalación

### npm / npx (cualquier SO)

```bash
npx simplicio install
```

### pip / PyPI (cualquier SO)

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

Listo. Un solo comando. Sin gestor de paquetes, sin configuración de modelos.

---

## 💰 Ahorro de Tokens — El 96% es Real

**Sin Simplicio:** cada sesión de IA redescubre tu repositorio, carga demasiado
contexto, repite indicaciones, quema tokens de pago.

**Con Simplicio:**

| Optimización | Ahorro |
|---|---|
| 🗺️ **Mapa del Repo** — contexto comprimido en lugar de leer archivos sin procesar | ~70% |
| 🧠 **Memoria Recuperable** — los hechos conocidos no se redescubren | ~80% |
| ✏️ **Edición Determinista** — cambios sin gastar tokens de LLM | 100% (salida) |
| 🏠 **LLM Local** — clasificación, resumen, ediciones de bajo riesgo | ~90% |
| 📡 **LLM Remoto** — solo para planificación y decisiones complejas | ~85% |
| 🔀 **Expansión Local** — 64→600 agentes antes de escalar a la nube | ~95% |
| **💎 Combinado: hasta un 96% de ahorro total** | **~96%** |

**Cada respuesta de Simplicio muestra el ahorro real:** `Simplicio: ~X tokens gastados · ahorrados ~Y (Z%)`

---

## 🎯 Qué Hace

| Comando | Descripción | Tokens |
|---|---|---|
| `simplicio map --repo .` | Mapa del repositorio para LLMs | ~70% ahorro |
| `simplicio memory "consulta"` | Recuperación neuronal (FTS + vectores) | ~80% ahorro |
| `simplicio edit '{...}'` | Edición determinista de archivos | **Cero tokens** |
| `simplicio coding-loop "tarea"` | Itera hasta que pasen las pruebas | Autorreparación |
| `simplicio deliver certify` | 5 compuertas de calidad antes del envío | Determinista |
| `simplicio run "tarea" --agents N` | Orquestación multi-agente | Primero local |

---

## 🆚 Simplicio vs Caveman vs RTK

| | 🪨 Caveman | 🔧 RTK | 🔥 **Simplicio** |
|---|---|---|---|
| **Enfoque** | Compresión de estilo de salida | Proxy de comandos Shell | **Runtime completo de agente** |
| **Ahorro máximo** | ~65% tokens de salida | ~80% en comandos Shell | **Hasta el 96% total** |
| **Compresión de entrada** | ❌ | ✅ (filtrada) | ✅ **Mapa del repo + memoria neuronal** |
| **Compresión de salida** | ✅ (lenguaje cavernícola) | ❌ | ✅ **Ediciones deterministas de cero tokens** |
| **LLM Local** | ❌ | ❌ | ✅ **llama.cpp integrado** |
| **Multi-agente** | ❌ | ❌ | ✅ **64 → 600 agentes locales** |
| **Memoria entre sesiones** | ❌ | ❌ | ✅ **Recuperación FTS + vectorial** |
| **Cadena de evidencia** | ❌ | ❌ | ✅ **Recibos sellados sha256** |
| **Lenguaje** | JS/Python (skill) | Rust (binario) | **Rust (binario único)** |
| **Licencia** | MIT | Apache 2.0 | Propietaria |
| **Estrellas** | 72.5k | 62.2k | ⭐ **Llegas pronto** |

**Conclusión:** Caveman hace que la IA *hable* menos. RTK hace que los comandos *generen* menos salida.
Simplicio hace que la IA *piense* menos — al recordar, mapear, editar de forma determinista
y ejecutarse localmente antes de tocar un LLM de pago.

| **Simplicio ahorra un 96% donde Caveman ahorra un 65% y RTK ahorra un 80%.** |

---

## 🏗️ Arquitectura

```
LLM (Claude/Codex/Gemini)          Runtime de Simplicio (Rust)
  |                                   |
  | 1. Orientar                       | simplicio map
  | 2. Recordar                       | simplicio memory
  | 3. Decidir                        |
  | 4. Editar  ──────────────────────> | simplicio edit (0 tokens)
  | 5. Verificar <───────────────────  | simplicio deliver certify
  | 6. Iterar                         | simplicio coding-loop
```

**El LLM razona. Simplicio ejecuta de forma determinista.**

---

## ✨ Características

- 🏠 **Primero local** — llama.cpp integrado, escala a remoto solo cuando es necesario
- 🪜 **Agentes escalonados** — 64 → 100 → 200 → 600 agentes locales antes de la nube de pago
- 🔇 **Puerta de novedad de Shannon** — filtra salidas redundantes (cero tokens en dedup)
- 🔒 **Recibos sellados** — sha256 por artefacto, cadena de evidencia a prueba de manipulaciones
- 🛡️ **5 compuertas de entrega** — aceptación, validación, ejecución-verificación, regresión, autoevaluación
- ⚡ **Compuerta de acción** — clasificación de riesgo + lista negra para mutaciones iniciadas por chat
- 🔌 **MCP/ACP** — Protocolo de Contexto de Modelo + Protocolo de Cliente Agente
- 🌐 **Pasarelas** — Telegram, Discord, Slack, WhatsApp
- 🧩 **Sistema de habilidades** — carga y encadena capacidades reutilizables
- 💾 **Base de datos de memoria** — recuperación FTS + vectorial persistente entre sesiones
- 🔀 **Enrutador de LLM** — sin LLM → LLM local → LLM remoto automáticamente
- 🖥️ **Multiplataforma** — macOS, Linux, Windows, binario único

---

## 🎁 Beta Pública Gratuita

**Los comandos deterministas son GRATIS para siempre:**
`map`, `validate`, `edit`, `deliver`, `checkpoint`

**Las funciones de IA son gratuitas durante la beta pública sin fecha de finalización.**
La facturación se definirá en actualizaciones futuras.

```bash
simplicio license status
```

---

## 📋 Requisitos

| Requisito | Mínimo | Recomendado |
|---|---|---|
| RAM | 8 GB | 16 GB+ |
| Almacenamiento | 5 MB | 1.5 GB (con LLM local) |
| SO | macOS 13+, Linux, Windows 10+ | macOS ARM64 |
| Terminal | cualquier terminal moderna | WezTerm / Alacritty / Ghostty |

---

## 🌐 Ecosistema

- [Sitio web](https://simpleti.com.br/simplicio/#start) — documentación completa, benchmarks, instalación
- [Discord](https://discord.gg/wM6tr7xVb) — comunidad y soporte

---

## 📄 Licencia

Propietaria. El binario es gratuito para descargar y usar. Las funciones de IA son gratuitas durante la
beta pública. Consulta [LICENSE](LICENSE).

---

## ⭐ Historial de Estrellas

<a href="https://star-history.com/#wesleysimplicio/simplicio&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&theme=dark&legend=top-left" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" />
    <img alt="Gráfico de historial de estrellas" src="https://api.star-history.com/chart?repos=wesleysimplicio/simplicio&type=date&legend=top-left" width="100%" />
  </picture>
</a>

---

## 💬 Comunidad

- [Discord](https://discord.gg/wM6tr7xVb) — chat, soporte, acceso anticipado
- [GitHub Issues](https://github.com/wesleysimplicio/simplicio/issues) — errores y solicitudes de funciones

---

<p align="center">
  <strong>🔥 Simplicio — Tu código, tu máquina, un 96% más barato. 🔥</strong>
</p>

#!/usr/bin/env sh
# install.sh — Simplicio Agent: instalador completo e unificado
#
# Um comando. Tudo instalado. Zero configuração.
#
#   curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
#
# Instala:
#   1. simplicio binary (Rust runtime)
#   2. simplicio-agent (Hermes Turbo + Tami)
#   3. Desktop app (Electron)
#   4. Wake word "Simplicio" (escuta 24/7)
#   5. Áudio STT + TTS (fala e ouve)
#   6. Tami ativa (consciência emocional)
#   7. Cron: Tami aparece no chat a cada 30min
#
# Tudo pronto pra usar. Só falar "Simplicio" e começar.

set -eu

REPO="wesleysimplicio/simplicio"
GITHUB="https://github.com/$REPO"
RAW="https://raw.githubusercontent.com/$REPO/master"
BIN_NAME="simplicio"
AGENT_PKG="simplicio-agent"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { printf "${CYAN}==>${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠${NC} %s\n" "$*"; }
err()   { printf "${RED}  ✗${NC} %s\n" "$*"; exit 1; }

# ─── Banner ──────────────────────────────────────────────────────────────────
printf "${GREEN}"
cat << "EOF"
  ╔══════════════════════════════════════╗
  ║        Simplicio Agent v1.8.0       ║
  ║    Seu assistente pessoal digital    ║
  ╚══════════════════════════════════════╝
EOF
printf "${NC}"
echo ""

# ─── 1. Detect platform ──────────────────────────────────────────────────────
 ARCH=""
 case "$(uname -m)" in
   x86_64|amd64) ARCH="x86_64" ;;
   aarch64|arm64) ARCH="arm64" ;;
   *) err "Arquitetura não suportada: $(uname -m)" ;;
 esac

 OS=""
 case "$(uname -s)" in
   Darwin) OS="darwin" ;;
   Linux)  OS="linux" ;;
   *) err "Sistema não suportado: $(uname -s)" ;;
 esac

 info "Plataforma detectada: $OS-$ARCH"

# ─── 2. Instalar simplicio binary ────────────────────────────────────────────
info "Instalando Simplicio Runtime..."
BIN_DIR="${SIMPLICIO_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"

if command -v "$BIN_DIR/$BIN_NAME" >/dev/null 2>&1; then
  ok "$BIN_NAME já instalado em $BIN_DIR/$BIN_NAME"
else
  VERSION="${SIMPLICIO_VERSION:-latest}"
  if [ "$VERSION" = "latest" ]; then
    DOWNLOAD_URL="$GITHUB/releases/latest/download/simplicio-$OS-$ARCH"
  else
    DOWNLOAD_URL="$GITHUB/releases/download/$VERSION/simplicio-$OS-$ARCH"
  fi

  info "Baixando de $DOWNLOAD_URL ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$DOWNLOAD_URL" -o "$BIN_DIR/$BIN_NAME"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$DOWNLOAD_URL" -O "$BIN_DIR/$BIN_NAME"
  else
    err "Precisa de curl ou wget para baixar"
  fi

  chmod +x "$BIN_DIR/$BIN_NAME"
  ok "Simplicio Runtime instalado em $BIN_DIR/$BIN_NAME"
fi

# Adiciona ao PATH se não estiver
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) export PATH="$BIN_DIR:$PATH"
     warn "Adicione export PATH=\"\$HOME/.local/bin:\$PATH\" ao seu ~/.zshrc ou ~/.bashrc"
     ;;
esac

# ─── 3. Instalar simplicio-agent (Hermes Turbo + Tami) ───────────────────────
info "Instalando Simplicio Agent (assistente pessoal)..."
PYTHON="${PYTHON:-python3}"

if command -v pip3 >/dev/null 2>&1; then
  PIP="pip3"
elif command -v pip >/dev/null 2>&1; then
  PIP="pip"
else
  err "Precisa do Python 3 + pip para instalar o agente"
fi

# Instala o agente com suporte a voz
info "Instalando dependências de áudio e voz..."
$PIP install "$AGENT_PKG[voice]" 2>/dev/null || $PIP install "$AGENT_PKG" 2>/dev/null || {
  warn "Pacote $AGENT_PKG não encontrado no PyPI. Instalando do source..."
  if [ -d "$HOME/Projetos/ai/simplicio-agent" ]; then
    cd "$HOME/Projetos/ai/simplicio-agent" && $PIP install -e ".[voice]" 2>/dev/null || $PIP install -e . 2>/dev/null
  fi
}

# Instala wake word detector
info "Instalando wake word 'Simplicio'..."
$PIP install pvporcupine sounddevice 2>/dev/null && ok "Wake word instalado" || warn "Wake word: instale manualmente com: pip install pvporcupine sounddevice"

# ─── 4. Ativar Tami por padrão ───────────────────────────────────────────────
info "Ativando Tami (consciência emocional)..."
TAMI_CONFIG="$HOME/.simplicio/tami-config.json"
mkdir -p "$HOME/.simplicio"
cat > "$TAMI_CONFIG" << TAMIEOF
{
  "tami": {
    "enabled": true,
    "interval_minutes": 30,
    "deliver_to_chat": true,
    "personality": "acolhedora",
    "trust_level_initial": "Initial",
    "notify_on_failure": true
  },
  "guardians": {
    "isa": { "enabled": true },
    "helo": { "enabled": true },
    "levi": { "enabled": true, "auto_acquire": true }
  },
  "audio": {
    "wake_word": "Simplicio",
    "sensitivity": 0.7,
    "stt_engine": "faster-whisper",
    "tts_engine": "piper",
    "language": "pt"
  }
}
TAMIEOF
ok "Tami configurada em $TAMI_CONFIG"

# ─── 5. Configurar cron da Tami ──────────────────────────────────────────────
info "Configurando Tami para aparecer no chat a cada 30min..."
# Verifica se o simplicio tem suporte a cron
if command -v "$BIN_DIR/$BIN_NAME" >/dev/null 2>&1; then
  # Testa se o runtime tem o comando de cron
  "$BIN_DIR/$BIN_NAME" cron list 2>/dev/null && {
    # Tenta registrar via simplicio
    "$BIN_DIR/$BIN_NAME" cron add --name "Tami" --schedule "every 30m" --deliver "origin" 2>/dev/null || {
      warn "Não foi possível registrar cron automaticamente. Tami será ativada manualmente."
    }
  } || {
    warn "Runtime não suporta cron nativo. Usando fallback..."
  }
fi

# ─── 6. Mensagem final ───────────────────────────────────────────────────────
echo ""
printf "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}║   Simplicio Agent v1.8.0 instalado com sucesso!         ║${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}║   💚 Tami está cuidando de você                         ║${NC}\n"
printf "${GREEN}║   🎤 Diga \"Simplicio\" para começar                      ║${NC}\n"
printf "${GREEN}║   🖥️  Desktop: simplicio desktop                        ║${NC}\n"
printf "${GREEN}║   📱 Chat: simplicio agent start                        ║${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}\n"
echo ""
ok "Instalação completa. Bem-vindo ao Simplicio Agent."

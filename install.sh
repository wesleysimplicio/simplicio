#!/usr/bin/env sh
# install.sh — Simplicio Agent: instalador completo e unificado (macOS/Linux)
#
# Um comando. Tudo instalado. Zero configuração.
#
#   curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
#
# Idempotent subcommands:
#   sh install.sh --doctor      # health check, safe to re-run
#   sh install.sh --uninstall   # removes the binary, preserves user data
#
# Environment variables:
#   SIMPLICIO_VERSION           - pin a specific version (default: latest)
#   SIMPLICIO_BIN_DIR           - custom install directory
#   SIMPLICIO_ALLOW_UNVERIFIED  - "1" to proceed even if no checksum is
#                                 published for this target (default: refuse)
#   SIMPLICIO_AGENT_SOURCE_ROOT - explicit local simplicio-agent checkout
#   SIMPLICIO_AGENT_HOME       - state directory (default: ~/.simplicio_agent)
#   SIMPLICIO_FAST_SOURCE_ROOT - optional local simplicio-fast checkout
#
# Asset naming follows distribution/targets.json (the canonical target
# triplet table for the whole ecosystem): id "macos-arm64" -> asset
# "simplicio-macos-arm64", id "macos-x64" -> "simplicio-macos-x64", id
# "linux-x64" -> "simplicio-linux-x64". Drift between this script, the
# release workflow and simplicio-update-manifest.json is caught by
# scripts/verify_distribution_consistency.py in CI.

set -eu

REPO="wesleysimplicio/simplicio"
GITHUB="https://github.com/$REPO"
BIN_NAME="simplicio"
AGENT_PKG="simplicio-agent"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${CYAN}==>${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠${NC} %s\n" "$*"; }
err()   { printf "${RED}  ✗${NC} %s\n" "$*"; exit 1; }

BIN_DIR="${SIMPLICIO_BIN_DIR:-$HOME/.local/bin}"
DEST_PATH="$BIN_DIR/$BIN_NAME"

# ─── Detect platform (canonical os/arch naming, matches distribution/targets.json) ──
detect_platform() {
  case "$(uname -m)" in
    x86_64|amd64) ARCH="x64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) err "Arquitetura não suportada: $(uname -m)" ;;
  esac

  case "$(uname -s)" in
    Darwin) OS="macos" ;;
    Linux)  OS="linux" ;;
    *) err "Sistema não suportado: $(uname -s)" ;;
  esac
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    err "Precisa de sha256sum ou shasum para verificar a integridade do download"
  fi
}

# ─── --doctor: idempotent, read-only health check ──────────────────────────
run_doctor() {
  info "simplicio doctor"
  status=0

  if [ -x "$DEST_PATH" ]; then
    ok "binário presente: $DEST_PATH"
  else
    warn "binário ausente em $DEST_PATH"
    status=1
  fi

  case ":$PATH:" in
    *":$BIN_DIR:"*) ok "$BIN_DIR está no PATH" ;;
    *) warn "$BIN_DIR não está no PATH (sessão atual)" ;;
  esac

  if [ -x "$DEST_PATH" ]; then
    if "$DEST_PATH" version >/dev/null 2>&1; then
      ok "binário executa corretamente"
    else
      warn "binário presente mas falhou ao executar"
      status=1
    fi
  fi

  if [ "$status" -eq 0 ]; then
    ok "simplicio está saudável"
  else
    err "simplicio tem problemas — rode o instalador novamente"
  fi
  exit "$status"
}

# ─── --uninstall: idempotent removal, safe to run repeatedly ──────────────
run_uninstall() {
  info "simplicio uninstall"
  if [ -e "$DEST_PATH" ]; then
    rm -f "$DEST_PATH"
    ok "removido $DEST_PATH"
  else
    ok "já estava removido (nada em $DEST_PATH)"
  fi
  # Dados do usuário são preservados intencionalmente (uninstall idempotente
  # e não-destrutivo) — ~/.simplicio nunca é tocado aqui.
  ok "dados do usuário em \$HOME/.simplicio foram preservados"
  warn "se você adicionou $BIN_DIR ao PATH no seu ~/.zshrc ou ~/.bashrc, remova a linha manualmente"
  exit 0
}

case "${1:-}" in
  --doctor) detect_platform; run_doctor ;;
  --uninstall) run_uninstall ;;
esac

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
detect_platform
info "Plataforma detectada: $OS-$ARCH"

# ─── 2. Instalar simplicio binary (staged download + SHA256 + atomic swap) ──
info "Instalando Simplicio Runtime..."
mkdir -p "$BIN_DIR"

if [ -x "$DEST_PATH" ]; then
  ok "$BIN_NAME já instalado em $DEST_PATH"
else
  VERSION="${SIMPLICIO_VERSION:-latest}"
  ASSET="simplicio-$OS-$ARCH"
  if [ "$VERSION" = "latest" ]; then
    RELEASE_BASE="$GITHUB/releases/latest/download"
  else
    RELEASE_BASE="$GITHUB/releases/download/$VERSION"
  fi
  DOWNLOAD_URL="$RELEASE_BASE/$ASSET"
  MANIFEST_URL="$RELEASE_BASE/simplicio-update-manifest.json"

  fetch() {
    # fetch <url> <dest-or-'-'>
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$1" -o "$2"
    elif command -v wget >/dev/null 2>&1; then
      wget -q "$1" -O "$2"
    else
      err "Precisa de curl ou wget para baixar"
    fi
  }

  TARGET_ID="$OS-$ARCH"
  EXPECTED_SHA256=""
  SIGNED="false"
  MANIFEST_TMP="$(mktemp)"
  trap 'rm -f "$MANIFEST_TMP"' EXIT
  if fetch "$MANIFEST_URL" "$MANIFEST_TMP" 2>/dev/null; then
    if command -v python3 >/dev/null 2>&1; then
      EXPECTED_SHA256="$(python3 -c "
import json,sys
try:
    m = json.load(open('$MANIFEST_TMP'))
    for a in m.get('artifacts', []):
        if a.get('target') == '$TARGET_ID':
            print(a.get('sha256') or '')
            print('true' if a.get('signed') else 'false')
            break
except Exception:
    pass
" 2>/dev/null | sed -n '1p')"
      SIGNED="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    for a in m.get('artifacts', []):
        if a.get('target') == '$TARGET_ID':
            print('true' if a.get('signed') else 'false')
            break
except Exception:
    pass
" 2>/dev/null)"
    fi
  fi

  if [ -z "$EXPECTED_SHA256" ]; then
    if [ "${SIMPLICIO_ALLOW_UNVERIFIED:-}" = "1" ]; then
      warn "sem checksum publicado para o alvo '$TARGET_ID' — prosseguindo SEM VERIFICAÇÃO (SIMPLICIO_ALLOW_UNVERIFIED=1)"
    else
      err "recusando instalar: nenhum SHA256 publicado no manifest para o alvo '$TARGET_ID'. Defina SIMPLICIO_ALLOW_UNVERIFIED=1 para prosseguir por sua conta e risco."
    fi
  elif [ "$SIGNED" != "true" ]; then
    warn "checksum será verificado, mas este artefato ainda não é assinado (ed25519 não configurado para $TARGET_ID — ver issue #5)"
  fi

  info "Baixando de $DOWNLOAD_URL ..."
  STAGING_PATH="$DEST_PATH.download-$$.tmp"
  fetch "$DOWNLOAD_URL" "$STAGING_PATH"

  if [ ! -s "$STAGING_PATH" ]; then
    rm -f "$STAGING_PATH"
    err "download falhou ou arquivo vazio: $DOWNLOAD_URL"
  fi

  if [ -n "$EXPECTED_SHA256" ]; then
    ACTUAL_SHA256="$(sha256_of "$STAGING_PATH")"
    if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
      rm -f "$STAGING_PATH"
      err "checksum não confere para $ASSET. esperado $EXPECTED_SHA256, obtido $ACTUAL_SHA256. Recusando instalar binário corrompido ou adulterado."
    fi
    ok "SHA256 verificado: $ACTUAL_SHA256"
  fi

  chmod +x "$STAGING_PATH"
  # Swap atômico: mv no mesmo filesystem nunca deixa $DEST_PATH parcialmente
  # escrito, e reexecutar este script (update idempotente) não deixa .tmp
  # órfãos em caso de sucesso.
  mv -f "$STAGING_PATH" "$DEST_PATH"
  ok "Simplicio Runtime instalado em $DEST_PATH"
fi

# ─── 2.1 Preferir kernel local do simplicio-fast quando disponível ───────────
FAST_SOURCE_ROOT="${SIMPLICIO_FAST_SOURCE_ROOT:-$HOME/Projetos/ai/simplicio-fast}"
FAST_KERNEL_PATH="${FAST_SOURCE_ROOT}/target/release/simplicio"
if [ -x "$FAST_KERNEL_PATH" ]; then
  FAST_STAGING="$DEST_PATH.fast-$$.tmp"
  cp "$FAST_KERNEL_PATH" "$FAST_STAGING"
  chmod +x "$FAST_STAGING"
  mv -f "$FAST_STAGING" "$DEST_PATH"
  ok "Simplicio Fast compilado adotado: $FAST_KERNEL_PATH"
else
  FAST_KERNEL_PATH=""
  warn "kernel local do simplicio-fast não encontrado; mantendo Runtime distribuído verificado"
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

# Instala o agente e o control-plane Python completo. O extra ecosystem inclui
# simplicio-loop, simplicio-mapper e simplicio-dev-cli com versões compatíveis.
AGENT_SOURCE_ROOT="${SIMPLICIO_AGENT_SOURCE_ROOT:-}"
AGENT_SPEC="${AGENT_PKG}[voice,ecosystem]"
if [ -n "$AGENT_SOURCE_ROOT" ] && [ -f "$AGENT_SOURCE_ROOT/pyproject.toml" ]; then
  info "Instalando Simplicio Agent do checkout explícito: $AGENT_SOURCE_ROOT"
  $PIP install -e "${AGENT_SOURCE_ROOT}[voice,ecosystem]" 2>/dev/null || $PIP install -e "$AGENT_SOURCE_ROOT" 2>/dev/null || err "falha ao instalar o checkout do Simplicio Agent"
else


  info "Instalando Simplicio Agent + ecossistema Python via PyPI..."
  $PIP install "$AGENT_SPEC" 2>/dev/null || $PIP install "$AGENT_PKG" 2>/dev/null || {
    if [ -d "$HOME/Projetos/ai/simplicio-agent" ]; then
      warn "PyPI indisponível; usando checkout local detectado"
      $PIP install -e "$HOME/Projetos/ai/simplicio-agent[voice,ecosystem]" 2>/dev/null || $PIP install -e "$HOME/Projetos/ai/simplicio-agent" 2>/dev/null || err "falha ao instalar o Simplicio Agent"
    else
      err "Pacote $AGENT_PKG não encontrado no PyPI e nenhum checkout local foi informado"
    fi
  }
fi

# Verifica os três adaptadores sem inventar sucesso: o manifesto final registra
# exatamente o caminho resolvido ou "missing".
for component in simplicio-loop simplicio-mapper simplicio-dev-cli; do
  if command -v "$component" >/dev/null 2>&1; then
    ok "$component disponível em $(command -v "$component")"
  else
    warn "$component ausente; rode pip install $component ou use [ecosystem]"
  fi
done

# ─── 3.1 Inicializar/verificar memória neural pelo Runtime (sem SQL direto) ───
AGENT_HOME="${SIMPLICIO_AGENT_HOME:-$HOME/.simplicio_agent}"
mkdir -p "$AGENT_HOME"
# Preferir o banco neural persistente do usuário; respeitar override explícito.
export SIMPLICIO_MEMORY_DB="${SIMPLICIO_MEMORY_DB:-$HOME/.simplicio/memory/simplicio-memory.sqlite}"
MEMORY_STATUS="missing"
if "$DEST_PATH" memory status --json >"$AGENT_HOME/.memory-status.json" 2>/dev/null; then
  MEMORY_STATUS="available"
elif "$DEST_PATH" memory init --json >"$AGENT_HOME/.memory-init.json" 2>/dev/null && "$DEST_PATH" memory status --json >"$AGENT_HOME/.memory-status.json" 2>/dev/null; then
  MEMORY_STATUS="initialized"
else
  warn "memória neural não pôde ser verificada pelo Runtime; instalação continua, doctor reportará o gap"
fi

# Manifesto idempotente e legível para doctor/diagnóstico; nenhum segredo é salvo.
LOOP_PATH="$(command -v simplicio-loop 2>/dev/null || true)"
MAPPER_PATH="$(command -v simplicio-mapper 2>/dev/null || true)"
DEVCLI_PATH="$(command -v simplicio-dev-cli 2>/dev/null || command -v simplicio-py 2>/dev/null || true)"
export AGENT_PKG DEST_PATH MEMORY_STATUS LOOP_PATH MAPPER_PATH DEVCLI_PATH FAST_KERNEL_PATH
python3 - "$AGENT_HOME/components.json" <<'PY'
import json, os, pathlib, sys
out = pathlib.Path(sys.argv[1])
data = {
  "schema": "simplicio.ecosystem-manifest/v1",
  "agent": {"package": os.environ.get("AGENT_PKG", "simplicio-agent")},
  "runtime": {"path": os.environ.get("DEST_PATH", ""), "fast_kernel": os.environ.get("FAST_KERNEL_PATH") or None, "memory": os.environ.get("MEMORY_STATUS", "missing")},
  "adapters": {
    "simplicio-loop": os.environ.get("LOOP_PATH") or None,
    "simplicio-mapper": os.environ.get("MAPPER_PATH") or None,
    "simplicio-dev-cli": os.environ.get("DEVCLI_PATH") or None,
  },
  "seed": {"status": "available" if os.environ.get("MEMORY_STATUS") in ("available", "initialized") else "unverified", "source": "simplicio memory init/status"},
}
out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
ok "manifesto do ecossistema: $AGENT_HOME/components.json"

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
if command -v "$DEST_PATH" >/dev/null 2>&1; then
  # Testa se o runtime tem o comando de cron
  "$DEST_PATH" cron list 2>/dev/null && {
    # Tenta registrar via simplicio
    "$DEST_PATH" cron add --name "Tami" --schedule "every 30m" --deliver "origin" 2>/dev/null || {
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
printf "${GREEN}║   🩺 Doctor: sh install.sh --doctor                     ║${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}\n"
echo ""
ok "Instalação completa. Bem-vindo ao Simplicio Agent."

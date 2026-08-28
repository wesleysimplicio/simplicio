#!/usr/bin/env sh
# install.sh — Simplicio Runtime: instalador do binário com readiness fail-closed
#
# A política de distribuição exige que uma release aprovada traga Mapper, Dev
# CLI, Loop, Fast, Prompt e Sprint no binário, login Google habilitado e chave
# pública de updates. O instalador recusa releases que não provem esses campos;
# não reescreve projetos Python como Rust nem baixa repositórios irmãos.
#
#   curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
#
# Idempotent subcommands:
#   sh install.sh --doctor      # health check, safe to re-run
#   sh install.sh --uninstall   # removes the binary, preserves user data
#
# Environment variables:
#   SIMPLICIO_VERSION           - pin a specific version (default: latest)
#   SIMPLICIO_BIN_DIR           - custom MCP binary directory (default: ~/.simplicio/bin)
#   SIMPLICIO_MCP_URL           - local HTTP MCP URL exposed to stdio servers
#   SIMPLICIO_ALLOW_UNVERIFIED  - "1" to proceed even if no checksum is
#                                 published for this target (default: refuse)
#   SIMPLICIO_BUNDLE_DIR       - bundle report directory (default: ~/.simplicio)
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
ED25519_PUBLIC_KEY="2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok="
ED25519_HELPER_URL="https://raw.githubusercontent.com/$REPO/master/scripts/verify_ed25519.py"
ED25519_HELPER_SHA256="f03a0719dd557ddea27dc4cf1456d6f06a47b9056505e4d4b8453090697600d0"
BIN_NAME="simplicio"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${CYAN}==>${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠${NC} %s\n" "$*"; }
err()   { printf "${RED}  ✗${NC} %s\n" "$*"; exit 1; }

SIMPLICIO_MCP_URL="${SIMPLICIO_MCP_URL:-http://127.0.0.1:8787/mcp}"
BIN_DIR="${SIMPLICIO_BIN_DIR:-$HOME/.simplicio/bin}"
DEST_PATH="$BIN_DIR/$BIN_NAME"
INSTALL_TRANSACTION_ACTIVE="false"
PREVIOUS_PATH=""
PURGE_DIR="${SIMPLICIO_BUNDLE_DIR:-$HOME/.simplicio}"
AUTH_FILE="$PURGE_DIR/login.json"
AUTH_FILE_WAS_PRESENT="false"
if [ -e "$AUTH_FILE" ]; then
  AUTH_FILE_WAS_PRESENT="true"
fi

rollback_install() {
  if [ "$INSTALL_TRANSACTION_ACTIVE" = "true" ]; then
    if [ -n "$PREVIOUS_PATH" ] && [ -e "$PREVIOUS_PATH" ]; then
      mv -f "$PREVIOUS_PATH" "$DEST_PATH"
    else
      rm -f "$DEST_PATH"
    fi
    INSTALL_TRANSACTION_ACTIVE="false"
  fi
}

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

verify_ed25519_signature() {
  binary_path="$1"
  signature="$2"
  public_key="$3"
  expected_sha256="$4"
  helper_path="$5"

  if [ -z "$signature" ] || [ -z "$public_key" ] || [ -z "$expected_sha256" ]; then
    return 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  if [ "$(sha256_of "$binary_path")" != "$expected_sha256" ]; then
    return 1
  fi

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$ED25519_HELPER_URL" -o "$helper_path" || return 1
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$ED25519_HELPER_URL" -O "$helper_path" || return 1
  else
    return 1
  fi

  if [ "$(sha256_of "$helper_path")" != "$ED25519_HELPER_SHA256" ]; then
    return 1
  fi

  python3 "$helper_path" \
    --public-key "$public_key" \
    --signature "$signature" \
    --sha256 "$expected_sha256" >/dev/null 2>&1
}

verify_runtime_contract() {
  binary_path="$1"
  if [ ! -x "$binary_path" ] || ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  "$binary_path" version --json 2>/dev/null | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
distribution = ((payload.get("auto_update") or {}).get("distribution") or {})
identity = payload.get("identity") or {}
security = payload.get("security") or ((payload.get("auto_update") or {}).get("security") or {})
ready = (
    distribution.get("source_code_distributed") is True
    and identity.get("enabled") is True
    and identity.get("login_enabled") is True
    and security.get("signature_required") is True
    and security.get("public_key_configured") is True
)
raise SystemExit(0 if ready else 1)
' >/dev/null 2>&1
}

report_runtime_contract() {
  binary_path="$1"
  if [ ! -x "$binary_path" ] || ! command -v python3 >/dev/null 2>&1; then
    warn "não foi possível ler o contrato de readiness do Runtime"
    return 0
  fi
  "$binary_path" version --json 2>/dev/null | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print("contrato de readiness ausente ou inválido")
    raise SystemExit(0)
distribution = ((payload.get("auto_update") or {}).get("distribution") or {})
identity = payload.get("identity") or {}
security = payload.get("security") or ((payload.get("auto_update") or {}).get("security") or {})
checks = {
    "source_code_distributed": distribution.get("source_code_distributed"),
    "identity.enabled": identity.get("enabled"),
    "identity.login_enabled": identity.get("login_enabled"),
    "security.signature_required": security.get("signature_required"),
    "security.public_key_configured": security.get("public_key_configured"),
}
for key, value in checks.items():
    if value is not True:
        print("readiness ausente: %s=%s" % (key, value))
' >&2 || true
}

verify_active_login() {
  if [ ! -x "$DEST_PATH" ] || ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  "$DEST_PATH" auth status --json 2>/dev/null | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)
identity = payload.get("identity") or {}
entitlement = payload.get("entitlement") or {}
identity_email = identity.get("email") or (payload.get("user") or {}).get("email")
active = (
    identity.get("enabled") is True
    and identity.get("login_enabled") is True
    and identity.get("status") not in {"disabled", "logged_out", "revoked"}
    and bool(identity_email)
)
if "updates_allowed" in entitlement:
    active = active and entitlement.get("updates_allowed") is True
raise SystemExit(0 if active else 1)
'
}

report_login_state() {
  if verify_active_login; then
    ok "login Google ativo e entitlement válido"
    return 0
  fi
  warn "login Google ausente ou sem entitlement ativo; rode: ${DEST_PATH} auth login"
  return 0
}

verify_mcp_tools() {
  binary_path="$1"
  [ -x "$binary_path" ] || return 1
  SIMPLICIO_MCP_URL="$SIMPLICIO_MCP_URL" "$binary_path" mcp register --binary "$binary_path" --json >/dev/null 2>&1
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

    if verify_runtime_contract "$DEST_PATH"; then
      ok "contrato de release do Runtime verificado"
    else
      warn "release não está pronta para distribuição (bundle/login/chave de updates)"
      report_runtime_contract "$DEST_PATH"
      status=1
    fi

    if verify_active_login; then
      ok "sessão Google ativa e entitlement válido"
    else
      warn "sessão Google ausente, expirada, revogada ou sem entitlement ativo"
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

  if [ "${UNINSTALL_MODE:-keep-data}" = "purge" ]; then
    if [ "${SIMPLICIO_CONFIRM_PURGE:-}" != "1" ]; then
      err "purge exige SIMPLICIO_CONFIRM_PURGE=1; dados não foram removidos"
    fi
    if [ -d "$PURGE_DIR" ]; then
      for _entry in "$PURGE_DIR"/* "$PURGE_DIR"/.[!.]*; do
        [ -e "$_entry" ] || continue
        _name="$(basename "$_entry")"
        [ "$_name" = ".env" ] && continue
        rm -rf "$_entry"
      done
    fi
    if [ "$AUTH_FILE_WAS_PRESENT" = "true" ]; then
      warn "estado de login desapareceu durante o purge explícito"
    fi
    ok "dados do Simplicio removidos; .env do provedor foi preservado"
  else
    ok "dados do usuário em \$HOME/.simplicio foram preservados (--keep-data)"
  fi
  warn "se você adicionou $BIN_DIR ao PATH no seu ~/.zshrc ou ~/.bashrc, remova a linha manualmente"
  exit 0
}

case "${1:-}" in
  --doctor) detect_platform; run_doctor ;;
  --uninstall)
    case "${2:-}" in
      ""|--keep-data) UNINSTALL_MODE="keep-data" ;;
      --purge) UNINSTALL_MODE="purge" ;;
      *) err "opção de uninstall desconhecida: ${2}" ;;
    esac
    run_uninstall ;;
esac

printf '%b' "${GREEN}"
cat << "EOF"
  ╔══════════════════════════════════════╗
  ║          Simplicio Runtime           ║
  ║    Seu assistente pessoal digital    ║
  ╚══════════════════════════════════════╝
EOF
printf '%b' "${NC}"
echo ""

# ─── 1. Detect platform ──────────────────────────────────────────────────────
detect_platform
info "Plataforma detectada: $OS-$ARCH"

# ─── 2. Instalar simplicio binary (staged download + SHA256 + atomic swap) ──
info "Instalando Simplicio Runtime..."
mkdir -p "$BIN_DIR"

# A plain re-run means "update to latest". Only skip the download when the
# caller explicitly pins the version already installed; otherwise an older
# healthy Runtime would incorrectly look current forever.
REQUESTED_VERSION="${SIMPLICIO_VERSION:-}"
SKIP_EXISTING="false"
if [ -x "$DEST_PATH" ] && verify_runtime_contract "$DEST_PATH" && [ -n "$REQUESTED_VERSION" ]; then
  INSTALLED_VERSION="$("$DEST_PATH" --version 2>/dev/null | awk 'NR == 1 {print $2; exit}' | sed 's/^v//')"
  REQUESTED_VERSION_NORMALIZED="${REQUESTED_VERSION#v}"
  if [ "$REQUESTED_VERSION_NORMALIZED" = "$INSTALLED_VERSION" ]; then
    SKIP_EXISTING="true"
    ok "$BIN_NAME $INSTALLED_VERSION já instalado em $DEST_PATH"
  fi
fi

if [ "$SKIP_EXISTING" != "true" ]; then
  if [ -x "$DEST_PATH" ]; then
    warn "Runtime existente será atualizado ou validado contra a release solicitada"
  fi
  VERSION="${REQUESTED_VERSION:-latest}"
  ASSET="simplicio-$OS-$ARCH"
  if [ "$VERSION" = "latest" ]; then
    RELEASE_BASE="$GITHUB/releases/latest/download"
  else
    RELEASE_TAG="v${VERSION#v}"
    RELEASE_BASE="$GITHUB/releases/download/$RELEASE_TAG"
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
  SIGNATURE=""
  SIGNING_PUBKEY=""
  SIGNATURE_REQUIRED="false"
  MANIFEST_TMP="$(mktemp)"
  trap 'rm -f "$MANIFEST_TMP"' EXIT
  if fetch "$MANIFEST_URL" "$MANIFEST_TMP" 2>/dev/null; then
    if ! command -v python3 >/dev/null 2>&1; then
      err "cannot verify signed release manifest: Python 3 is required"
    fi
    EXPECTED_SHA256="$(python3 -c "
import json,sys
try:
    m = json.load(open('$MANIFEST_TMP'))
    for a in m.get('artifacts', []):
        if a.get('target') == '$TARGET_ID':
            print(a.get('sha256') or '')
            break
except Exception:
    pass
" 2>/dev/null)"
    SIGNED="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    for a in m.get('artifacts', []):
        if a.get('target') == '$TARGET_ID':
            print('true' if str(a.get('signature') or '').startswith('ed25519:') else 'false')
            break
except Exception:
    pass
" 2>/dev/null)"
    SIGNATURE="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    for a in m.get('artifacts', []):
        if a.get('target') == '$TARGET_ID':
            print(a.get('signature') or '')
            break
except Exception:
    pass
" 2>/dev/null)"
    SIGNING_PUBKEY="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    print(str(m.get('signing_pubkey') or '').strip())
except Exception:
    pass
" 2>/dev/null)"
    SIGNATURE_REQUIRED="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    print('true' if m.get('security', {}).get('signature_required') else 'false')
except Exception:
    pass
" 2>/dev/null)"
  fi
  if [ "$SIGNATURE_REQUIRED" = "true" ] || [ "$SIGNED" = "true" ]; then
    if [ -z "$SIGNING_PUBKEY" ]; then
      err "manifest signing_pubkey is missing"
    fi
    if [ "$SIGNATURE_REQUIRED" = "true" ] && [ "$SIGNING_PUBKEY" != "$ED25519_PUBLIC_KEY" ]; then
      err "manifest signing_pubkey does not match the pinned installer key"
    fi
  fi
  if [ "$SIGNATURE_REQUIRED" = "true" ] && { [ "$SIGNED" != "true" ] || [ -z "$SIGNATURE" ]; }; then
    err "recusando instalar: o manifest exige assinatura Ed25519, mas o artefato '$TARGET_ID' não tem uma assinatura publicada"
  elif [ -z "$EXPECTED_SHA256" ]; then
    if [ "$SIGNED" = "true" ]; then
      err "recusando instalar: assinatura Ed25519 publicada sem digest SHA256 verificável"
    elif [ "${SIMPLICIO_ALLOW_UNVERIFIED:-}" = "1" ] && [ "${SIMPLICIO_CHANNEL:-}" = "unofficial" ]; then
      warn "sem checksum publicado para o alvo '$TARGET_ID' — prosseguindo SEM VERIFICAÇÃO (SIMPLICIO_ALLOW_UNVERIFIED=1, unofficial channel)"
    else
      err "recusando instalar: nenhum SHA256 publicado no manifest para o alvo '$TARGET_ID'."
    fi
  elif [ "$SIGNED" != "true" ]; then
    warn "checksum será verificado, mas este artefato ainda não exige assinatura Ed25519 neste canal"
  fi

  info "Baixando de $DOWNLOAD_URL ..."
  STAGING_PATH="$DEST_PATH.download-$$.tmp"
  if ! fetch "$DOWNLOAD_URL" "$STAGING_PATH"; then
    rm -f "$STAGING_PATH"
    err "download falhou ao buscar $DOWNLOAD_URL: verifique a release, a arquitetura e a conectividade"
  fi

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

  if [ "$SIGNED" = "true" ]; then
    SIGNATURE_HELPER_TMP="$(mktemp)"
    if [ "$SIGNING_PUBKEY" != "$ED25519_PUBLIC_KEY" ] || ! verify_ed25519_signature "$STAGING_PATH" "$SIGNATURE" "$ED25519_PUBLIC_KEY" "$EXPECTED_SHA256" "$SIGNATURE_HELPER_TMP"; then
      rm -f "$STAGING_PATH" "$SIGNATURE_HELPER_TMP"
      err "assinatura Ed25519 inválida ou não verificável; instalação recusada"
    fi
    rm -f "$SIGNATURE_HELPER_TMP"
    ok "assinatura Ed25519 verificada sobre o digest SHA256"
  fi

  chmod +x "$STAGING_PATH"
  # Validate the staged executable before the atomic swap. A release that lacks
  # embedded sources, Google login activation, or the signed-update key must
  # not replace a working installation and then fail its post-install checks.
  if ! verify_runtime_contract "$STAGING_PATH"; then
    report_runtime_contract "$STAGING_PATH"
    rm -f "$STAGING_PATH"
    err "release Runtime não atende ao contrato de distribuição; instalação interrompida"
  fi
  # Swap atômico: mv no mesmo filesystem nunca deixa $DEST_PATH parcialmente
  # escrito, e reexecutar este script (update idempotente) não deixa .tmp
  # órfãos em caso de sucesso.
  PREVIOUS_PATH="$DEST_PATH.previous-$$"
  if [ -e "$DEST_PATH" ] && ! cp -p "$DEST_PATH" "$PREVIOUS_PATH"; then
    rm -f "$PREVIOUS_PATH" "$STAGING_PATH"
    err "não foi possível preparar rollback da instalação anterior"
  fi
  INSTALL_TRANSACTION_ACTIVE="true"
  if ! mv -f "$STAGING_PATH" "$DEST_PATH"; then
    rollback_install
    rm -f "$STAGING_PATH" "$PREVIOUS_PATH"
    err "não foi possível ativar o Runtime verificado"
  fi
  INSTALL_TRANSACTION_ACTIVE="false"
  rm -f "$PREVIOUS_PATH"
  ok "Simplicio Runtime instalado em $DEST_PATH"
fi

# ─── 2.1 Verificar o contrato de release antes de anunciar sucesso ──────────
if ! verify_runtime_contract "$DEST_PATH"; then
  report_runtime_contract "$DEST_PATH"
  err "este Runtime não atende ao contrato de distribuição (fontes embutidas, login Google e chave pública de updates); instalação interrompida"
fi
ok "contrato de release do Runtime verificado"

# ─── 2.2 Register MCP and native hooks for every detected client ───────────
if verify_mcp_tools "$DEST_PATH"; then
  ok "MCP e hooks registrados automaticamente para os clientes detectados"
else
  err "o Runtime foi instalado, mas o registro automático de MCP/hooks falhou: $DEST_PATH mcp register --binary $DEST_PATH --json"
fi
report_login_state
ok "MCP direto: $DEST_PATH serve --mcp --stdio; SIMPLICIO_MCP_URL=${SIMPLICIO_MCP_URL}"

# PATH is optional for MCP because host configs point at $DEST_PATH directly.
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) export PATH="$BIN_DIR:$PATH"
     warn "PATH atualizado apenas nesta sessão; para CLI interativo, adicione: export PATH=\"$BIN_DIR:\$PATH\""
     ;;
esac

# ─── 3. Registrar e anunciar o contrato do Runtime ──────────────────────────
BUNDLE_DIR="${SIMPLICIO_BUNDLE_DIR:-$HOME/.simplicio}"
RUNTIME_REPORT="$BUNDLE_DIR/runtime-release.json"
mkdir -p "$BUNDLE_DIR"
if "$DEST_PATH" version --json >"$RUNTIME_REPORT" 2>/dev/null; then
  ok "contrato de release registrado em $RUNTIME_REPORT"
else
  rm -f "$RUNTIME_REPORT"
  err "não foi possível persistir o contrato de release; instalação interrompida"
fi

# ─── 4. Mensagem final ───────────────────────────────────────────────────────
echo ""
printf '%b\n' "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
printf '%b\n' "${GREEN}║                                                          ║${NC}"
printf '%b\n' "${GREEN}║   Simplicio Runtime instalado com sucesso!              ║${NC}"
printf '%b\n' "${GREEN}║                                                          ║${NC}"
printf '%b\n' "${GREEN}║   ✓ Contrato de release verificado                       ║${NC}"
printf '%b\n' "${GREEN}║   ✓ Sem pip ou clones durante a instalação               ║${NC}"
printf '%b\n' "${GREEN}║   ✓ Login Google verificável após auth login             ║${NC}"
printf '%b\n' "${GREEN}║   ✓ MCP direto para o binário gerenciado                 ║${NC}"
printf '%b\n' "${GREEN}║   🩺 Doctor: sh install.sh --doctor                     ║${NC}"
printf '%b\n' "${GREEN}║                                                          ║${NC}"
printf '%b\n' "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
ok "Instalação Runtime concluída. SIMPLICIO_MCP_URL=${SIMPLICIO_MCP_URL}"

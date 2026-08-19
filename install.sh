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
#   SIMPLICIO_BIN_DIR           - custom install directory
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

fetch_url() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$1" -O "$2"
  else
    err "Precisa de curl ou wget para baixar"
  fi
}

configure_codex_stdio() {
  codex_dir="${CODEX_HOME:-$HOME/.codex}"
  codex_config="$codex_dir/config.toml"
  codex_hooks="$codex_dir/hooks.json"
  hook_dir="$HOME/.simplicio/hooks"
  hook_path="$hook_dir/mcp-route.sh"
  hook_tmp="$hook_path.download-$$.tmp"
  mkdir -p "$codex_dir" "$hook_dir"

  info "Configurando MCP stdio e hooks do Codex"
  hook_ref="${SIMPLICIO_CODEX_HOOK_REF:-master}"
  fetch_url "$GITHUB/raw/$hook_ref/codex/mcp-route.sh" "$hook_tmp" || err "não foi possível baixar o hook do Codex"
  chmod 755 "$hook_tmp"
  mv -f "$hook_tmp" "$hook_path"

  python3 - "$codex_config" "$codex_hooks" "$DEST_PATH" "$hook_path" <<'PY'
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

config_path, hooks_path, binary, hook_path = map(Path, sys.argv[1:])


def backup_once(path: Path) -> None:
    if path.exists():
        backup = Path(str(path) + ".simplicio.bak")
        if not backup.exists():
            shutil.copy2(path, backup)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(str(path) + ".simplicio.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


backup_once(config_path)
config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
toml_binary = str(binary).replace("\\", "\\\\").replace('"', '\\"')
stdio_block = (
    "[mcp_servers.simplicio]\n"
    f'command = "{toml_binary}"\n'
    'args = ["serve", "--mcp", "--stdio"]\n'
)
section = re.compile(r"(?ms)^\[mcp_servers\.simplicio\]\r?\n.*?(?=^\[|\Z)")
if section.search(config):
    config = section.sub(stdio_block, config, count=1)
else:
    config = config.rstrip() + ("\n\n" if config.strip() else "") + stdio_block
atomic_write(config_path, config)


backup_once(hooks_path)
if hooks_path.exists():
    try:
        root = json.loads(hooks_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"hooks.json inválido; preservado sem alteração: {exc}")
else:
    root = {}
if not isinstance(root, dict):
    raise SystemExit("hooks.json precisa conter um objeto JSON; preservado sem alteração")
hooks = root.setdefault("hooks", {})
if not isinstance(hooks, dict):
    raise SystemExit("hooks.json: campo hooks inválido; preservado sem alteração")

command = f"bash {shlex.quote(str(hook_path))}"
hook_command = {
    "command": command,
    "timeout": 8,
    "type": "command",
    "statusMessage": "Routing through Simplicio MCP",
}


def upsert(event: str, entry: dict) -> None:
    items = hooks.get(event, [])
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise SystemExit(f"hooks.json: evento {event} inválido; preservado sem alteração")
    for item in items:
        if not isinstance(item, dict):
            continue
        existing_hooks = item.get("hooks", [])
        if not isinstance(existing_hooks, list):
            continue
        for existing in existing_hooks:
            if isinstance(existing, dict) and "mcp-route.sh" in str(existing.get("command", "")):
                existing.update(hook_command)
                if "matcher" in entry:
                    item["matcher"] = entry["matcher"]
                hooks[event] = items
                return
    entry = dict(entry)
    entry["hooks"] = [dict(hook_command)]
    items.append(entry)
    hooks[event] = items


upsert("PreToolUse", {"matcher": "Bash|apply_patch|Edit|Write"})
for event, matcher in (("SessionStart", "startup|resume|clear|compact"),
                       ("SubagentStart", ""),
                       ("UserPromptSubmit", "")):
    upsert(event, {"matcher": matcher})
atomic_write(hooks_path, json.dumps(root, indent=2, ensure_ascii=False) + "\n")
PY
  ok "Codex configurado para simplicio serve --mcp --stdio"
  ok "hooks do Codex instalados em $hook_path"
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

require_active_login() {
  if verify_active_login; then
    return 0
  fi
  info "Login Google obrigatório para ativar o Simplicio Runtime"
  "$DEST_PATH" login google || err "login não concluído; instalação bloqueada"
  verify_active_login || err "sessão ausente, expirada, revogada ou sem entitlement ativo; instalação bloqueada"
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
  ║          Simplicio Runtime           ║
  ║    Seu assistente pessoal digital    ║
  ╚══════════════════════════════════════╝
EOF
printf "${NC}"
echo ""

# ─── 1. Detect platform ──────────────────────────────────────────────────────
detect_platform
info "Plataforma detectada: $OS-$ARCH"
if [ "$OS" = "macos" ] && [ "$ARCH" = "x64" ]; then
  err "esta release publica apenas macOS Apple Silicon; não há asset macOS Intel com checksum"
fi

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
    RELEASE_BASE="$GITHUB/releases/download/$VERSION"
  fi
  DOWNLOAD_URL="$RELEASE_BASE/$ASSET"
  MANIFEST_URL="$RELEASE_BASE/simplicio-update-manifest.json"

  TARGET_ID="$OS-$ARCH"
  EXPECTED_SHA256=""
  SIGNED="false"
  SIGNATURE=""
  SIGNATURE_REQUIRED="false"
  MANIFEST_TMP="$(mktemp)"
  trap 'rm -f "$MANIFEST_TMP"' EXIT
  if fetch_url "$MANIFEST_URL" "$MANIFEST_TMP" 2>/dev/null; then
    if command -v python3 >/dev/null 2>&1; then
      EXPECTED_SHA256="$(python3 -c "
import json,sys
try:
    m = json.load(open('$MANIFEST_TMP'))
    for a in m.get('artifacts', []):
        if a.get('target') == '$TARGET_ID':
            print(a.get('sha256') or '')
            print('true' if a.get('signed') or str(a.get('signature') or '').startswith('ed25519:') else 'false')
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
            print('true' if a.get('signed') or str(a.get('signature') or '').startswith('ed25519:') else 'false')
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
      SIGNATURE_REQUIRED="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    print('true' if m.get('security', {}).get('signature_required') else 'false')
except Exception:
    pass
" 2>/dev/null)"
    fi
  fi

  if [ "$SIGNATURE_REQUIRED" = "true" ] && { [ "$SIGNED" != "true" ] || [ -z "$SIGNATURE" ]; }; then
    err "recusando instalar: o manifest exige assinatura Ed25519, mas o artefato '$TARGET_ID' não tem uma assinatura publicada"
  elif [ -z "$EXPECTED_SHA256" ]; then
    if [ "${SIMPLICIO_ALLOW_UNVERIFIED:-}" = "1" ]; then
      warn "sem checksum publicado para o alvo '$TARGET_ID' — prosseguindo SEM VERIFICAÇÃO (SIMPLICIO_ALLOW_UNVERIFIED=1)"
    else
      err "recusando instalar: nenhum SHA256 publicado no manifest para o alvo '$TARGET_ID'. Defina SIMPLICIO_ALLOW_UNVERIFIED=1 para prosseguir por sua conta e risco."
    fi
  elif [ "$SIGNED" != "true" ]; then
    warn "checksum será verificado, mas este artefato ainda não exige assinatura Ed25519 neste canal"
  fi

  info "Baixando de $DOWNLOAD_URL ..."
  STAGING_PATH="$DEST_PATH.download-$$.tmp"
  fetch_url "$DOWNLOAD_URL" "$STAGING_PATH"

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
  mv -f "$STAGING_PATH" "$DEST_PATH"
  ok "Simplicio Runtime instalado em $DEST_PATH"
fi

# ─── 2.1 Verificar o contrato de release antes de anunciar sucesso ──────────
if ! verify_runtime_contract "$DEST_PATH"; then
  report_runtime_contract "$DEST_PATH"
  err "este Runtime não atende ao contrato de distribuição (fontes embutidas, login Google e chave pública de updates); instalação interrompida"
fi
ok "contrato de release do Runtime verificado"

# ─── 2.2 Login obrigatório: beta não elimina a sessão ativa ────────────────
require_active_login
ok "login Google ativo e entitlement válido"

# Codex runs the installed binary directly over STDIO. This avoids the local
# HTTP daemon latency and keeps the same Google login/entitlement gate in the
# Runtime process. Existing Codex settings and hooks are merged, not replaced.
configure_codex_stdio

# Adiciona ao PATH se não estiver
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) export PATH="$BIN_DIR:$PATH"
     warn "Adicione export PATH=\"\$HOME/.local/bin:\$PATH\" ao seu ~/.zshrc ou ~/.bashrc"
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
printf "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}║   Simplicio Runtime instalado com sucesso!              ║${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}║   ✓ Contrato de release verificado                       ║${NC}\n"
printf "${GREEN}║   ✓ Sem pip ou clones durante a instalação               ║${NC}\n"
printf "${GREEN}║   ✓ Login Google ativo                                   ║${NC}\n"
printf "${GREEN}║   🩺 Doctor: sh install.sh --doctor                     ║${NC}\n"
printf "${GREEN}║                                                          ║${NC}\n"
printf "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}\n"
echo ""
ok "Instalação Runtime concluída."

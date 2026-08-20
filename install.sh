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
#   sh install.sh --doctor                    # read-only health check
#   sh install.sh --uninstall --keep-data     # removes binary, keeps data
#   sh install.sh --uninstall --purge         # removes binary and data (confirmed)
#
# Environment variables:
#   SIMPLICIO_VERSION           - pin a specific version (default: latest)
#   SIMPLICIO_BIN_DIR           - custom install directory
#   SIMPLICIO_ALLOW_UNVERIFIED  - "1" to proceed even if no checksum is
#                                 published for this target (default: refuse)
#   SIMPLICIO_BUNDLE_DIR        - bundle report/data directory
#   SIMPLICIO_CONFIRM_PURGE     - "1" confirms non-interactive --purge
#
# Asset naming follows distribution/targets.json (the canonical target
# triplet table for the whole ecosystem): id "macos-arm64" -> asset
# "simplicio-macos-arm64", id "macos-x64" -> "simplicio-macos-x64", id
# "linux-x64" -> "simplicio-linux-x64". Published manifests from older
# release tooling may use Rust-style aliases (macos-aarch64, macos-x86_64,
# linux-x86_64); the lookup below accepts both without changing asset URLs.
# Drift between this script, the release workflow and
# simplicio-update-manifest.json is caught by CI.

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
err() {
  printf "${RED}  ✗${NC} %s\n" "$*"
  if [ "${INSTALL_TRANSACTION_ACTIVE:-false}" = true ]; then rollback_install; fi
  exit 1
}

BIN_DIR="${SIMPLICIO_BIN_DIR:-$HOME/.local/bin}"
DEST_PATH="$BIN_DIR/$BIN_NAME"
PREVIOUS_PATH="$DEST_PATH.simplicio.previous"
PURGE_DIR="${SIMPLICIO_BUNDLE_DIR:-$HOME/.simplicio}"
INSTALL_TRANSACTION_ACTIVE=false
UNINSTALL_KEEP_DATA=true

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

rollback_install() {
  [ "${INSTALL_TRANSACTION_ACTIVE:-false}" = true ] || return 0
  if [ -f "${PREVIOUS_PATH:-}" ]; then
    mv -f "$PREVIOUS_PATH" "$DEST_PATH" || true
    warn "rollback concluído: versão anterior restaurada em $DEST_PATH"
  else
    rm -f "$DEST_PATH"
    warn "rollback concluído: binário novo removido; não havia versão anterior"
  fi
  if [ -n "${STAGING_PATH:-}" ]; then rm -f "$STAGING_PATH"; fi
  INSTALL_TRANSACTION_ACTIVE=false
}

verify_ed25519_signature() {
  binary_path="$1"
  signature="$2"
  public_key="$3"
  digest="$4"
  helper_path="$5"
  if ! command -v python3 >/dev/null 2>&1 || ! fetch_url "$ED25519_HELPER_URL" "$helper_path" 2>/dev/null; then
    return 1
  fi
  if [ "$(sha256_of "$helper_path")" != "$ED25519_HELPER_SHA256" ]; then
    return 1
  fi
  python3 "$helper_path" --public-key "$public_key" --signature "$signature" --sha256 "$digest" >/dev/null 2>&1
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
  installed_version="$("$DEST_PATH" --version 2>/dev/null | awk 'NR == 1 {print $2; exit}' | sed 's/^v//')"
  hook_ref="${SIMPLICIO_CODEX_HOOK_REF:-v${installed_version:-unknown}}"
  [ "$hook_ref" != "vunknown" ] || err "não foi possível derivar uma referência versionada para o hook do Codex"
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

def remove_legacy_hooks() -> None:
    for event in list(hooks):
        items = hooks.get(event, [])
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            raise SystemExit(f"hooks.json: evento {event} inválido; preservado sem alteração")
        kept_items = []
        for item in items:
            if not isinstance(item, dict):
                kept_items.append(item)
                continue
            existing_hooks = item.get("hooks")
            if not isinstance(existing_hooks, list):
                kept_items.append(item)
                continue
            kept_hooks = []
            for legacy_hook in existing_hooks:
                command_text = str(legacy_hook.get("command", "")) if isinstance(legacy_hook, dict) else ""
                lowered = command_text.lower()
                is_legacy_simplicio = (
                    re.search(r"mcp-route\.sh|simplicio-mcp-route", command_text, re.I)
                    or ("/bin/bash" in lowered and "simplicio" in lowered)
                )
                if not is_legacy_simplicio:
                    kept_hooks.append(legacy_hook)
            if kept_hooks:
                item["hooks"] = kept_hooks
                kept_items.append(item)
        if kept_items:
            hooks[event] = kept_items
        else:
            del hooks[event]


remove_legacy_hooks()

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


upsert("PreToolUse", {"matcher": ".*"})
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

verify_mcp_tools() {
  binary_path="$1"
  if [ ! -x "$binary_path" ] || ! command -v python3 >/dev/null 2>&1; then
    return 1
  fi
  python3 - "$binary_path" <<'PY'
import json
import subprocess
import sys

required = {
    "simplicio_map", "simplicio_memory", "simplicio_edit", "simplicio_gate",
    "simplicio_validate", "simplicio_run", "simplicio_symbol", "simplicio_search",
    "simplicio_read", "simplicio_exec",
}
payload = "".join(json.dumps(request) + "\n" for request in (
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
))
try:
    result = subprocess.run(
        [sys.argv[1], "serve", "--mcp", "--stdio", "--json"],
        input=payload, capture_output=True, text=True, timeout=30, check=False,
    )
    responses = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            responses.append(value)
    tools_result = next((r.get("result") for r in responses if r.get("id") == 2), {})
    names = {t.get("name") for t in (tools_result or {}).get("tools", []) if isinstance(t, dict)}
    missing = sorted(required - names)
    if result.returncode != 0 or missing:
        print("MCP tool surface incomplete: missing=" + ",".join(missing), file=sys.stderr)
        raise SystemExit(1)
except (OSError, subprocess.TimeoutExpired) as exc:
    print("MCP tools/list failed: " + str(exc), file=sys.stderr)
    raise SystemExit(1)
PY
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
  "$DEST_PATH" login google || return 1
  verify_active_login
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

    if verify_mcp_tools "$DEST_PATH"; then
      ok "MCP expõe as 10 tools documentadas"
    else
      warn "MCP incompleto após autenticação: o binário não expõe todas as tools documentadas"
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

# ─── --uninstall: transactional removal with explicit data policy ──────────
confirm_purge() {
  if [ "${SIMPLICIO_CONFIRM_PURGE:-0}" = "1" ]; then
    return 0
  fi
  if [ -t 0 ]; then
    printf 'Digite PURGE para apagar os dados em %s: ' "$PURGE_DIR" >&2
    IFS= read -r answer
    [ "$answer" = "PURGE" ] || err "purge cancelado; confirme digitando PURGE"
    return 0
  fi
  err "--purge exige SIMPLICIO_CONFIRM_PURGE=1 em execução não interativa"
}

run_uninstall() {
  info "simplicio uninstall"
  if [ "$UNINSTALL_PURGE" = true ]; then
    confirm_purge
  fi
  if [ -e "$DEST_PATH" ]; then
    rm -f "$DEST_PATH"
    ok "removido $DEST_PATH"
  else
    ok "já estava removido (nada em $DEST_PATH)"
  fi
  rm -f "$PREVIOUS_PATH"
  if [ "$UNINSTALL_PURGE" = true ]; then
    case "$PURGE_DIR" in
      ""|"/"|"$HOME") err "recusando purge de um diretório amplo: $PURGE_DIR" ;;
    esac
    rm -rf "$PURGE_DIR"
    ok "dados do usuário removidos de $PURGE_DIR"
  else
    ok "dados do usuário em $PURGE_DIR foram preservados (--keep-data)"
  fi
  warn "se você adicionou $BIN_DIR ao PATH no seu perfil, remova a linha manualmente"
  exit 0
}

DOCTOR=false
UNINSTALL=false
UNINSTALL_PURGE=false
for arg in "$@"; do
  case "$arg" in
    --doctor) DOCTOR=true ;;
    --uninstall) UNINSTALL=true ;;
    --keep-data) UNINSTALL_KEEP_DATA=true ;;
    --purge) UNINSTALL_PURGE=true ;;
    --help|-h)
      printf '%s\n' 'uso: sh install.sh [--doctor] [--uninstall [--keep-data|--purge]]'
      exit 0
      ;;
    *) err "argumento desconhecido: $arg" ;;
  esac
done
if [ "$UNINSTALL_PURGE" = true ] && [ "${UNINSTALL:-false}" != true ]; then
  err "--purge só pode ser usado com --uninstall"
fi
if [ "$DOCTOR" = true ]; then
  detect_platform
  run_doctor
fi
if [ "$UNINSTALL" = true ]; then
  run_uninstall
fi

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
# macOS Intel is a supported distribution target. The canonical target
# table and signed manifest provide the macos-x64 asset/checksum mapping.

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
  # Keep installer/distribution IDs stable while accepting aliases emitted by
  # the v3.8.17 release manifest. A valid signed artifact must not be treated
  # as unsigned merely because the manifest uses a Rust-style target name.
  MANIFEST_TARGET_ID="$TARGET_ID"
  case "$TARGET_ID" in
    macos-arm64) MANIFEST_TARGET_ID="macos-aarch64" ;;
    macos-x64) MANIFEST_TARGET_ID="macos-x86_64" ;;
    linux-x64) MANIFEST_TARGET_ID="linux-x86_64" ;;
  esac
  EXPECTED_SHA256=""
  SIGNED="false"
  SIGNATURE=""
  SIGNING_PUBKEY=""
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
        if a.get('target') in {'$MANIFEST_TARGET_ID', '$TARGET_ID'}:
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
        if a.get('target') in {'$MANIFEST_TARGET_ID', '$TARGET_ID'}:
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
        if a.get('target') in {'$MANIFEST_TARGET_ID', '$TARGET_ID'}:
            print(a.get('signature') or '')
            break
except Exception:
    pass
" 2>/dev/null)"
      SIGNING_PUBKEY="$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST_TMP'))
    print(m.get('signing_pubkey') or '')
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
  elif [ "$SIGNATURE_REQUIRED" = "true" ] && [ "$SIGNING_PUBKEY" != "$ED25519_PUBLIC_KEY" ]; then
    err "recusando instalar: a chave pública Ed25519 do manifest não corresponde à chave pinada"
  elif [ -z "$EXPECTED_SHA256" ]; then
    if [ "$SIGNED" = "true" ]; then
      err "recusando instalar: assinatura Ed25519 publicada sem digest SHA256 verificável"
    elif [ "${SIMPLICIO_ALLOW_UNVERIFIED:-}" = "1" ]; then
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
  # A clean HOME has no authenticated session yet. Validate only the offline
  # Runtime release contract before the swap; MCP initialize/tools/list is an
  # authenticated gate and runs after require_active_login below.
  if ! verify_runtime_contract "$STAGING_PATH"; then
    report_runtime_contract "$STAGING_PATH"
    rm -f "$STAGING_PATH"
    err "release Runtime não atende ao contrato de distribuição; instalação interrompida"
  fi
  # Journal the previous executable before the atomic swap. Any later
  # fail-closed error calls rollback_install through err().
  if [ -e "$DEST_PATH" ]; then
    cp -p "$DEST_PATH" "$PREVIOUS_PATH" || err "não foi possível guardar a versão anterior para rollback"
  else
    rm -f "$PREVIOUS_PATH"
  fi
  INSTALL_TRANSACTION_ACTIVE=true
  mv -f "$STAGING_PATH" "$DEST_PATH"
  ok "Simplicio Runtime instalado em $DEST_PATH"
fi

# ─── 2.1 Verificar o contrato de release antes de anunciar sucesso ──────────
if ! verify_runtime_contract "$DEST_PATH"; then
  report_runtime_contract "$DEST_PATH"
  err "este Runtime não atende ao contrato de distribuição (fontes embutidas, login Google e chave pública de updates); instalação interrompida"
fi
ok "contrato de release do Runtime verificado"

# ─── 2.2 Login obrigatório antes do handshake MCP ───────────────────────────
if ! require_active_login; then
  err "login não concluído ou sessão sem entitlement ativo; instalação bloqueada"
fi
ok "login Google ativo e entitlement válido"

# MCP tools/list is intentionally post-login: clean installs must bootstrap the
# binary and establish the session before invoking the authenticated surface.
if ! verify_mcp_tools "$DEST_PATH"; then
  err "este Runtime não expõe a superfície MCP completa após o login; instalação interrompida"
fi
ok "superfície MCP verificada (10 tools documentadas)"
# Codex integration is opt-in. MCP registration and routing hooks remain
# separate, and the hook reference is versioned/pinned inside the function.
if [ "${SIMPLICIO_INSTALL_CODEX:-0}" = "1" ]; then
  configure_codex_stdio
else
  info "integração Codex não instalada automaticamente; use SIMPLICIO_INSTALL_CODEX=1 para ativá-la"
fi

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
if [ "${INSTALL_TRANSACTION_ACTIVE:-false}" = true ]; then
  rm -f "$PREVIOUS_PATH"
  INSTALL_TRANSACTION_ACTIVE=false
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

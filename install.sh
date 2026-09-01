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
# Host plugins are deliberately outside this installer transaction. The
# Runtime/MCP/hook install completes first; a separate explicit consent flow
# owned by `simplicio host-plugins` may be started afterwards.
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
PUBLIC_ROUTE_REF="68b4c7f7ac27d07624ffa4ddf0673a43e180c3e5"
PUBLIC_ROUTE_URL="https://raw.githubusercontent.com/$REPO/$PUBLIC_ROUTE_REF/codex/mcp-route.sh"
PUBLIC_ROUTE_SHA256="d91200cae4816c79fe0c903fc6eedc01835a557827e8d3d0480304f3bdce5118"
BIN_NAME="simplicio"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SIMPLICIO_MCP_URL="${SIMPLICIO_MCP_URL:-http://127.0.0.1:8787/mcp}"
BIN_DIR="${SIMPLICIO_BIN_DIR:-$HOME/.simplicio/bin}"
DEST_PATH="$BIN_DIR/$BIN_NAME"
INSTALL_TRANSACTION_ACTIVE="false"
PREVIOUS_PATH=""
PURGE_DIR="${SIMPLICIO_BUNDLE_DIR:-$HOME/.simplicio}"
AUTH_FILE="$PURGE_DIR/login.json"
INSTALL_RECEIPT="$PURGE_DIR/install-receipt.json"
INSTALL_STAGE="preflight"
INSTALL_EFFECT_STARTED="false"
RUNTIME_INSTALLED="false"
MCP_REGISTERED="false"
HOOK_INSTALLED="false"
HOST_PLUGINS_STATE="unavailable"
HOST_PLUGINS_COMMAND=""
HOST_PLUGINS_REASON="Runtime host-plugins capability was not checked"
AUTH_FILE_WAS_PRESENT="false"
if [ -e "$AUTH_FILE" ]; then
  AUTH_FILE_WAS_PRESENT="true"
fi

info()  { printf "${CYAN}==>${NC} %s\n" "$*"; }
ok()    { printf "${GREEN}  ✓${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}  ⚠${NC} %s\n" "$*"; }

json_escape() {
  # POSIX od is available before Python and lets the fallback produce valid
  # JSON even when a user-controlled path contains a newline or control byte.
  for json_byte in $(printf '%s' "$1" | od -An -tu1 -v); do
    case "$json_byte" in
      8) printf '%s' '\b' ;;
      9) printf '%s' '\t' ;;
      10) printf '%s' '\n' ;;
      12) printf '%s' '\f' ;;
      13) printf '%s' '\r' ;;
      34) printf '%s' '\"' ;;
      92) printf '%s' "\\\\" ;;
      [0-9]|[12][0-9]|3[01]) printf '\\u%04x' "$json_byte" ;;
      *)
        json_octal="$(printf '%03o' "$json_byte")"
        printf '%b' "\\$json_octal"
        ;;
    esac
  done
}

render_install_receipt() {
  receipt_status="$1"
  receipt_exit_code="$2"
  receipt_failure_code="$3"
  receipt_failure_reason="$4"
  if command -v python3 >/dev/null 2>&1; then
    if RECEIPT_STATUS="$receipt_status" \
      RECEIPT_EXIT_CODE="$receipt_exit_code" \
      RECEIPT_STAGE="$INSTALL_STAGE" \
      RECEIPT_FAILURE_CODE="$receipt_failure_code" \
      RECEIPT_FAILURE_REASON="$receipt_failure_reason" \
      RECEIPT_RUNTIME_INSTALLED="$RUNTIME_INSTALLED" \
      RECEIPT_MCP_REGISTERED="$MCP_REGISTERED" \
      RECEIPT_HOOK_INSTALLED="$HOOK_INSTALLED" \
      RECEIPT_HOST_PLUGINS_STATE="$HOST_PLUGINS_STATE" \
      RECEIPT_HOST_PLUGINS_COMMAND="$HOST_PLUGINS_COMMAND" \
      RECEIPT_HOST_PLUGINS_REASON="$HOST_PLUGINS_REASON" \
      python3 - <<'PY'
import json
import os


def env_bool(name):
    return os.environ.get(name) == "true"


failure_code = os.environ.get("RECEIPT_FAILURE_CODE", "")
failure = None
if failure_code:
    failure = {
        "code": failure_code,
        "reason": os.environ.get("RECEIPT_FAILURE_REASON", ""),
    }

receipt = {
    "schema": "simplicio-install-receipt/v1",
    "status": os.environ["RECEIPT_STATUS"],
    "exit_code": int(os.environ["RECEIPT_EXIT_CODE"]),
    "stage": os.environ["RECEIPT_STAGE"],
    "failure": failure,
    "runtime": {"installed": env_bool("RECEIPT_RUNTIME_INSTALLED")},
    "mcp": {"registered": env_bool("RECEIPT_MCP_REGISTERED")},
    "hook": {"installed": env_bool("RECEIPT_HOOK_INSTALLED")},
    "host_plugins": {
        "state": os.environ["RECEIPT_HOST_PLUGINS_STATE"],
        "owner": "simplicio-runtime",
        "command": os.environ.get("RECEIPT_HOST_PLUGINS_COMMAND") or None,
        "mutated": False,
        "reason": os.environ["RECEIPT_HOST_PLUGINS_REASON"],
    },
}
print(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")))
PY
    then
      return 0
    fi
  fi

  # Pre-Python failures still get valid JSON through the byte-safe POSIX
  # fallback above, without relying on the missing prerequisite.
  if [ -n "$receipt_failure_code" ]; then
    receipt_failure="{\"code\":\"$(json_escape "$receipt_failure_code")\",\"reason\":\"$(json_escape "$receipt_failure_reason")\"}"
  else
    receipt_failure="null"
  fi
  if [ -n "$HOST_PLUGINS_COMMAND" ]; then
    receipt_host_command="\"$(json_escape "$HOST_PLUGINS_COMMAND")\""
  else
    receipt_host_command="null"
  fi
  printf '{"schema":"simplicio-install-receipt/v1","status":"%s","exit_code":%s,"stage":"%s","failure":%s,"runtime":{"installed":%s},"mcp":{"registered":%s},"hook":{"installed":%s},"host_plugins":{"state":"%s","owner":"simplicio-runtime","command":%s,"mutated":false,"reason":"%s"}}\n' \
    "$(json_escape "$receipt_status")" \
    "$receipt_exit_code" \
    "$(json_escape "$INSTALL_STAGE")" \
    "$receipt_failure" \
    "$RUNTIME_INSTALLED" \
    "$MCP_REGISTERED" \
    "$HOOK_INSTALLED" \
    "$(json_escape "$HOST_PLUGINS_STATE")" \
    "$receipt_host_command" \
    "$(json_escape "$HOST_PLUGINS_REASON")"
}

persist_install_receipt() {
  receipt_status="$1"
  receipt_exit_code="$2"
  receipt_failure_code="$3"
  receipt_failure_reason="$4"
  if ! mkdir -p "$PURGE_DIR"; then
    return 1
  fi
  receipt_tmp="$INSTALL_RECEIPT.tmp.$$"
  if ! (umask 077; render_install_receipt "$receipt_status" "$receipt_exit_code" "$receipt_failure_code" "$receipt_failure_reason" >"$receipt_tmp"); then
    rm -f "$receipt_tmp"
    return 1
  fi
  if ! chmod 0600 "$receipt_tmp" || ! mv -f "$receipt_tmp" "$INSTALL_RECEIPT"; then
    rm -f "$receipt_tmp"
    return 1
  fi
}

fail_install() {
  failure_code="$1"
  shift
  failure_reason="$*"
  failure_status="failed"
  if [ "$INSTALL_EFFECT_STARTED" = "true" ]; then
    failure_status="partial"
  fi
  if ! persist_install_receipt "$failure_status" 1 "$failure_code" "$failure_reason"; then
    render_install_receipt "$failure_status" 1 "$failure_code" "$failure_reason" >&2
  fi
  printf "${RED}  ✗${NC} %s\n" "$failure_reason" >&2
  exit 1
}
err() {
  fail_install "${INSTALL_STAGE}_failed" "$*"
}

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

HOOK_FAILURE_CODE=""
HOOK_FAILURE_REASON=""
hook_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    return 1
  fi
}

reconcile_public_route_overlay() {
  HOOK_FAILURE_CODE=""
  HOOK_FAILURE_REASON=""
  hook_dir="$PURGE_DIR/hooks"
  hook_path="$hook_dir/mcp-route.sh"

  if [ -f "$hook_path" ]; then
    if ! hook_current_sha="$(hook_sha256 "$hook_path")"; then
      HOOK_FAILURE_CODE="hook_checksum_tool_missing"
      HOOK_FAILURE_REASON="Could not calculate SHA256 for existing hook: $hook_path"
      return 1
    fi
    if [ "$hook_current_sha" = "$PUBLIC_ROUTE_SHA256" ]; then
      return 0
    fi
  fi

  if ! mkdir -p "$hook_dir"; then
    HOOK_FAILURE_CODE="hook_directory_create_failed"
    HOOK_FAILURE_REASON="Could not create hook directory: $hook_dir"
    return 1
  fi
  hook_tmp="$hook_dir/.mcp-route.sh.download-$$"
  hook_capture_dir="$(mktemp -d "${TMPDIR:-/tmp}/simplicio-hook.XXXXXX")" || {
    HOOK_FAILURE_CODE="hook_output_capture_failed"
    HOOK_FAILURE_REASON="Could not create bounded hook download capture"
    return 1
  }
  hook_stdout="$hook_capture_dir/stdout"
  hook_stderr="$hook_capture_dir/stderr"
  hook_stdout_fifo="$hook_capture_dir/stdout.fifo"
  hook_stderr_fifo="$hook_capture_dir/stderr.fifo"
  hook_code_path="$hook_capture_dir/code"
  hook_reason_path="$hook_capture_dir/reason"
  if ! mkfifo "$hook_stdout_fifo" "$hook_stderr_fifo"; then
    rm -f "$hook_tmp" "$hook_stdout_fifo" "$hook_stderr_fifo" || true
    rmdir "$hook_capture_dir" 2>/dev/null || true
    HOOK_FAILURE_CODE="hook_output_capture_failed"
    HOOK_FAILURE_REASON="Could not create bounded hook download streams"
    return 1
  fi
  if command -v curl >/dev/null 2>&1; then
    hook_downloader="curl"
  elif command -v wget >/dev/null 2>&1; then
    hook_downloader="wget"
  else
    rm -f "$hook_tmp" "$hook_stdout_fifo" "$hook_stderr_fifo" || true
    rmdir "$hook_capture_dir" 2>/dev/null || true
    HOOK_FAILURE_CODE="hook_downloader_missing"
    HOOK_FAILURE_REASON="Neither curl nor wget is available to download the public hook"
    return 1
  fi
  capture_stream_bounded "$hook_stdout" "$hook_stdout.truncated" 8192 <"$hook_stdout_fifo" &
  hook_stdout_pid=$!
  capture_stream_bounded "$hook_stderr" "$hook_stderr.truncated" 8192 <"$hook_stderr_fifo" &
  hook_stderr_pid=$!
  if [ "$hook_downloader" = "curl" ]; then
    if curl -fsSL "$PUBLIC_ROUTE_URL" -o "$hook_tmp" >"$hook_stdout_fifo" 2>"$hook_stderr_fifo"; then
      hook_download_exit=0
    else
      hook_download_exit=$?
    fi
  else
    if wget -q "$PUBLIC_ROUTE_URL" -O "$hook_tmp" >"$hook_stdout_fifo" 2>"$hook_stderr_fifo"; then
      hook_download_exit=0
    else
      hook_download_exit=$?
    fi
  fi
  if wait "$hook_stdout_pid"; then hook_stdout_ok=true; else hook_stdout_ok=false; fi
  if wait "$hook_stderr_pid"; then hook_stderr_ok=true; else hook_stderr_ok=false; fi
  rm -f "$hook_stdout_fifo" "$hook_stderr_fifo" || true

  if [ "$hook_stdout_ok" != "true" ] || [ "$hook_stderr_ok" != "true" ]; then
    HOOK_FAILURE_CODE="hook_output_capture_failed"
    HOOK_FAILURE_REASON="Hook download output could not be drained safely"
    hook_download_exit=125
  elif [ "$hook_download_exit" -ne 0 ]; then
    if python3 - "$hook_stdout" "$hook_stderr" "$hook_code_path" "$hook_reason_path" "$hook_download_exit" <<'PY'
import json
import os
import sys

marker = "\n...[output truncated at 8192 bytes]"


def captured(path):
    with open(path, "rb") as handle:
        text = handle.read(8192).decode("utf-8", errors="replace")
    return text + (marker if os.path.exists(path + ".truncated") else "")


stdout = captured(sys.argv[1])
stderr = captured(sys.argv[2])
payload = None
for candidate in [stdout.strip(), *reversed([line.strip() for line in stdout.splitlines() if line.strip()])]:
    try:
        decoded = json.loads(candidate)
    except (TypeError, ValueError):
        continue
    if isinstance(decoded, dict):
        payload = decoded
        break
failure = payload.get("failure") if isinstance(payload, dict) else None
error = payload.get("error") if isinstance(payload, dict) else None
failure = failure if isinstance(failure, dict) else {}
error_object = error if isinstance(error, dict) else {}
code = failure.get("code") or (payload.get("code") if payload else None) or (payload.get("error_code") if payload else None) or error_object.get("code") or "hook_download_failed"
reason = failure.get("reason") or (payload.get("reason") if payload else None) or (payload.get("message") if payload else None) or error_object.get("reason") or error_object.get("message") or (error if isinstance(error, str) else None)
if not isinstance(reason, str) or not reason:
    reason = stderr.strip() or stdout.strip() or f"Hook download failed with exit code {sys.argv[5]}"
with open(sys.argv[3], "w", encoding="utf-8", newline="") as handle:
    handle.write(str(code))
with open(sys.argv[4], "w", encoding="utf-8", newline="") as handle:
    handle.write(reason[:8192])
PY
    then
      capture_sentinel="__SIMPLICIO_CAPTURE_EOF__"
      HOOK_FAILURE_CODE="$(cat "$hook_code_path"; printf '%s' "$capture_sentinel")"
      HOOK_FAILURE_CODE="${HOOK_FAILURE_CODE%"$capture_sentinel"}"
      HOOK_FAILURE_REASON="$(cat "$hook_reason_path"; printf '%s' "$capture_sentinel")"
      HOOK_FAILURE_REASON="${HOOK_FAILURE_REASON%"$capture_sentinel"}"
    else
      HOOK_FAILURE_CODE="hook_download_failed"
      HOOK_FAILURE_REASON="Hook download failed with exit code $hook_download_exit"
    fi
  fi

  rm -f "$hook_stdout" "$hook_stderr" "$hook_stdout.truncated" "$hook_stderr.truncated" "$hook_code_path" "$hook_reason_path" || true
  rmdir "$hook_capture_dir" 2>/dev/null || true
  if [ "$hook_download_exit" -ne 0 ]; then
    rm -f "$hook_tmp" || true
    return 1
  fi
  if ! hook_download_sha="$(hook_sha256 "$hook_tmp")"; then
    rm -f "$hook_tmp" || true
    HOOK_FAILURE_CODE="hook_checksum_failed"
    HOOK_FAILURE_REASON="Could not calculate SHA256 for downloaded hook"
    return 1
  fi
  if [ "$hook_download_sha" != "$PUBLIC_ROUTE_SHA256" ]; then
    rm -f "$hook_tmp" || true
    HOOK_FAILURE_CODE="hook_checksum_mismatch"
    HOOK_FAILURE_REASON="Downloaded hook SHA256 mismatch: expected $PUBLIC_ROUTE_SHA256, got $hook_download_sha"
    return 1
  fi
  if ! grep -q 'simplicio-hook-version: 3240-v12' "$hook_tmp"; then
    rm -f "$hook_tmp" || true
    HOOK_FAILURE_CODE="hook_marker_missing"
    HOOK_FAILURE_REASON="Downloaded hook is missing simplicio-hook-version: 3240-v12"
    return 1
  fi
  if ! chmod 0755 "$hook_tmp"; then
    rm -f "$hook_tmp" || true
    HOOK_FAILURE_CODE="hook_permission_failed"
    HOOK_FAILURE_REASON="Could not make downloaded hook executable: $hook_tmp"
    return 1
  fi
  if ! mv -f "$hook_tmp" "$hook_path"; then
    rm -f "$hook_tmp" || true
    HOOK_FAILURE_CODE="hook_activation_failed"
    HOOK_FAILURE_REASON="Could not activate verified hook at $hook_path"
    return 1
  fi
  return 0
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
session_verification = payload.get("session_verification") or {}
identity_email = identity.get("email") or (payload.get("user") or {}).get("email")
active = (
    identity.get("enabled") is True
    and identity.get("login_enabled") is True
    and identity.get("status") == "active"
    and bool(identity_email)
    and entitlement.get("updates_allowed") is True
    and session_verification.get("verified") is True
    and session_verification.get("cached") is False
)
raise SystemExit(0 if active else 1)
'
}

report_login_state() {
  if verify_active_login; then
    ok "sessão Google verificada de forma fresh e entitlement válido"
    return 0
  fi
  warn "sessão Google não verificada de forma fresh (ausente, cacheada ou sem entitlement); rode: ${DEST_PATH} auth login"
  return 0
}

capture_stream_bounded() {
  capture_output_path="$1"
  capture_truncated_path="$2"
  capture_limit="$3"
  python3 -c '
import os
import sys

output_path, truncated_path, raw_limit = sys.argv[1:]
limit = int(raw_limit)
remaining = limit
truncated = False
with open(output_path, "wb") as output:
    while True:
        chunk = sys.stdin.buffer.read(65536)
        if not chunk:
            break
        kept_length = 0
        if remaining:
            kept = chunk[:remaining]
            output.write(kept)
            remaining -= len(kept)
            kept_length = len(kept)
        if len(chunk) > kept_length:
            truncated = True
if truncated:
    with open(truncated_path, "wb"):
        pass
' "$capture_output_path" "$capture_truncated_path" "$capture_limit"
}

MCP_FAILURE_CODE=""
MCP_FAILURE_REASON=""
verify_mcp_tools() {
  binary_path="$1"
  MCP_FAILURE_CODE=""
  MCP_FAILURE_REASON=""
  if [ ! -x "$binary_path" ]; then
    MCP_FAILURE_CODE="mcp_binary_missing"
    MCP_FAILURE_REASON="Runtime binary is missing or not executable: $binary_path"
    return 1
  fi

  capture_dir="$(mktemp -d "${TMPDIR:-/tmp}/simplicio-mcp-register.XXXXXX")" || {
    MCP_FAILURE_CODE="mcp_output_capture_failed"
    MCP_FAILURE_REASON="Could not create a bounded capture directory for Runtime MCP registration output"
    return 1
  }
  stdout_path="$capture_dir/stdout"
  stderr_path="$capture_dir/stderr"
  stdout_fifo="$capture_dir/stdout.fifo"
  stderr_fifo="$capture_dir/stderr.fifo"
  code_path="$capture_dir/code"
  reason_path="$capture_dir/reason"
  if ! mkfifo "$stdout_fifo" "$stderr_fifo"; then
    rm -f "$stdout_fifo" "$stderr_fifo"
    rmdir "$capture_dir" 2>/dev/null || true
    MCP_FAILURE_CODE="mcp_output_capture_failed"
    MCP_FAILURE_REASON="Could not create bounded Runtime MCP output streams"
    return 1
  fi

  capture_stream_bounded "$stdout_path" "$stdout_path.truncated" 8192 <"$stdout_fifo" &
  stdout_drain_pid=$!
  capture_stream_bounded "$stderr_path" "$stderr_path.truncated" 8192 <"$stderr_fifo" &
  stderr_drain_pid=$!

  if SIMPLICIO_MCP_URL="$SIMPLICIO_MCP_URL" "$binary_path" mcp register --binary "$binary_path" --json >"$stdout_fifo" 2>"$stderr_fifo"; then
    mcp_exit_code=0
  else
    mcp_exit_code=$?
  fi
  if wait "$stdout_drain_pid"; then stdout_drain_ok=true; else stdout_drain_ok=false; fi
  if wait "$stderr_drain_pid"; then stderr_drain_ok=true; else stderr_drain_ok=false; fi
  rm -f "$stdout_fifo" "$stderr_fifo"
  if [ "$stdout_drain_ok" != "true" ] || [ "$stderr_drain_ok" != "true" ]; then
    rm -f "$stdout_path" "$stderr_path" "$stdout_path.truncated" "$stderr_path.truncated" "$code_path" "$reason_path"
    rmdir "$capture_dir" 2>/dev/null || true
    MCP_FAILURE_CODE="mcp_output_capture_failed"
    MCP_FAILURE_REASON="Runtime MCP output could not be drained safely"
    return 1
  fi
  if [ "$mcp_exit_code" -eq 0 ]; then
    rm -f "$stdout_path" "$stderr_path" "$stdout_path.truncated" "$stderr_path.truncated" "$code_path" "$reason_path"
    rmdir "$capture_dir" 2>/dev/null || true
    return 0
  fi

  if python3 - "$stdout_path" "$stderr_path" "$code_path" "$reason_path" "$mcp_exit_code" <<'PY'
import json
import os
import sys


LIMIT = 8192
TRUNCATED = "\n...[output truncated at 8192 bytes]"


def read_bounded(path):
    with open(path, "rb") as handle:
        payload = handle.read(LIMIT)
    truncated = os.path.exists(path + ".truncated")
    text = payload.decode("utf-8", errors="replace")
    return text + (TRUNCATED if truncated else "")


def text_value(value):
    if isinstance(value, str) and value:
        return value
    if value is not None and not isinstance(value, (dict, list)):
        return str(value)
    return ""


stdout = read_bounded(sys.argv[1])
stderr = read_bounded(sys.argv[2])
payload = None
candidates = [stdout.strip()]
candidates.extend(line.strip() for line in reversed(stdout.splitlines()) if line.strip())
for candidate in candidates:
    try:
        decoded = json.loads(candidate)
    except (TypeError, ValueError):
        continue
    if isinstance(decoded, dict):
        payload = decoded
        break

failure = payload.get("failure") if isinstance(payload, dict) else None
error = payload.get("error") if isinstance(payload, dict) else None
failure = failure if isinstance(failure, dict) else {}
error_object = error if isinstance(error, dict) else {}

code = (
    text_value(failure.get("code"))
    or (text_value(payload.get("code")) if payload else "")
    or (text_value(payload.get("error_code")) if payload else "")
    or text_value(error_object.get("code"))
    or "mcp_registration_failed"
)
reason = (
    text_value(failure.get("reason"))
    or (text_value(payload.get("reason")) if payload else "")
    or (text_value(payload.get("message")) if payload else "")
    or text_value(error_object.get("reason"))
    or text_value(error_object.get("message"))
    or (text_value(error) if not isinstance(error, dict) else "")
)
if not reason:
    fallback = []
    if stderr.strip():
        fallback.append(stderr.strip())
    if stdout.strip() and stdout.strip() not in fallback:
        fallback.append(stdout.strip())
    reason = "\n".join(fallback)
if not reason:
    reason = f"Runtime MCP registration failed with exit code {sys.argv[5]}"

reason_bytes = reason.encode("utf-8")
if len(reason_bytes) > LIMIT:
    reason = reason_bytes[:LIMIT].decode("utf-8", errors="ignore") + TRUNCATED

with open(sys.argv[3], "w", encoding="utf-8", newline="") as handle:
    handle.write(code)
with open(sys.argv[4], "w", encoding="utf-8", newline="") as handle:
    handle.write(reason)
PY
  then
    capture_sentinel="__SIMPLICIO_CAPTURE_EOF__"
    MCP_FAILURE_CODE="$(cat "$code_path"; printf '%s' "$capture_sentinel")"
    MCP_FAILURE_CODE="${MCP_FAILURE_CODE%"$capture_sentinel"}"
    MCP_FAILURE_REASON="$(cat "$reason_path"; printf '%s' "$capture_sentinel")"
    MCP_FAILURE_REASON="${MCP_FAILURE_REASON%"$capture_sentinel"}"
  else
    MCP_FAILURE_CODE="mcp_registration_failed"
    capture_sentinel="__SIMPLICIO_CAPTURE_EOF__"
    MCP_FAILURE_REASON="$(head -c 8192 "$stderr_path"; printf '%s' "$capture_sentinel")"
    MCP_FAILURE_REASON="${MCP_FAILURE_REASON%"$capture_sentinel"}"
    if [ -z "$MCP_FAILURE_REASON" ]; then
      MCP_FAILURE_REASON="$(head -c 8192 "$stdout_path"; printf '%s' "$capture_sentinel")"
      MCP_FAILURE_REASON="${MCP_FAILURE_REASON%"$capture_sentinel"}"
    fi
    if [ -z "$MCP_FAILURE_REASON" ]; then
      MCP_FAILURE_REASON="Runtime MCP registration failed with exit code $mcp_exit_code"
    fi
  fi

  rm -f "$stdout_path" "$stderr_path" "$stdout_path.truncated" "$stderr_path.truncated" "$code_path" "$reason_path"
  rmdir "$capture_dir" 2>/dev/null || true
  return 1
}


probe_host_plugins_capability() {
  HOST_PLUGINS_STATE="unavailable"
  HOST_PLUGINS_COMMAND=""
  HOST_PLUGINS_REASON="Runtime host-plugins capability is unavailable"
  if [ ! -x "$DEST_PATH" ]; then
    HOST_PLUGINS_REASON="Runtime binary is missing; host-plugins capability was not checked"
    return 1
  fi
  host_capture_dir="$(mktemp -d "${TMPDIR:-/tmp}/simplicio-host-plugins.XXXXXX")" || {
    HOST_PLUGINS_REASON="Could not create bounded host-plugins capability capture"
    return 1
  }
  host_stdout="$host_capture_dir/stdout"
  host_stderr="$host_capture_dir/stderr"
  host_stdout_fifo="$host_capture_dir/stdout.fifo"
  host_stderr_fifo="$host_capture_dir/stderr.fifo"
  if ! mkfifo "$host_stdout_fifo" "$host_stderr_fifo"; then
    rm -f "$host_stdout_fifo" "$host_stderr_fifo"
    rmdir "$host_capture_dir" 2>/dev/null || true
    HOST_PLUGINS_REASON="Could not create bounded host-plugins capability streams"
    return 1
  fi
  capture_stream_bounded "$host_stdout" "$host_stdout.truncated" 8192 <"$host_stdout_fifo" &
  host_stdout_pid=$!
  capture_stream_bounded "$host_stderr" "$host_stderr.truncated" 8192 <"$host_stderr_fifo" &
  host_stderr_pid=$!
  if "$DEST_PATH" host-plugins --help >"$host_stdout_fifo" 2>"$host_stderr_fifo"; then
    host_exit_code=0
  else
    host_exit_code=$?
  fi
  if wait "$host_stdout_pid"; then host_stdout_ok=true; else host_stdout_ok=false; fi
  if wait "$host_stderr_pid"; then host_stderr_ok=true; else host_stderr_ok=false; fi
  rm -f "$host_stdout_fifo" "$host_stderr_fifo"

  host_contract_valid=false
  if [ "$host_exit_code" -eq 0 ] && [ "$host_stdout_ok" = "true" ] && [ "$host_stderr_ok" = "true" ]; then
    if python3 - "$host_stdout" "$host_stderr" <<'PY'
import sys

help_text = "\n".join(
    open(path, "rb").read(8192).decode("utf-8", errors="replace")
    for path in sys.argv[1:]
)
required = (
    "simplicio.host-plugins/cli-v1",
    "simplicio host-plugins plan",
    "simplicio host-plugins apply",
    "simplicio host-plugins pending",
    "simplicio host-plugins reconcile",
)
raise SystemExit(0 if all(marker in help_text for marker in required) else 1)
PY
    then
      host_contract_valid=true
    fi
  fi

  if [ "$host_contract_valid" = "true" ]; then
    HOST_PLUGINS_STATE="pending_consent"
    HOST_PLUGINS_COMMAND="simplicio host-plugins plan --all"
    HOST_PLUGINS_REASON="Host plugins require separate explicit user consent."
    host_supported=true
  else
    if [ "$host_exit_code" -eq 0 ] && [ "$host_stdout_ok" = "true" ] && [ "$host_stderr_ok" = "true" ]; then
      host_diagnostic="Runtime returned exit code 0 without the required simplicio.host-plugins/cli-v1 contract marker and commands"
    else
      capture_sentinel="__SIMPLICIO_CAPTURE_EOF__"
      host_diagnostic="$(cat "$host_stderr"; printf '%s' "$capture_sentinel")"
      host_diagnostic="${host_diagnostic%"$capture_sentinel"}"
      if [ -z "$host_diagnostic" ]; then
        host_diagnostic="$(cat "$host_stdout"; printf '%s' "$capture_sentinel")"
        host_diagnostic="${host_diagnostic%"$capture_sentinel"}"
      fi
      if [ -z "$host_diagnostic" ]; then
        host_diagnostic="Runtime exited with code $host_exit_code"
      fi
    fi
    HOST_PLUGINS_REASON="Runtime host-plugins capability unavailable: $host_diagnostic"
    host_supported=false
  fi
  rm -f "$host_stdout" "$host_stderr" "$host_stdout.truncated" "$host_stderr.truncated"
  rmdir "$host_capture_dir" 2>/dev/null || true
  [ "$host_supported" = "true" ]
}

report_host_plugin_consent() {
  if [ "$HOST_PLUGINS_STATE" = "pending_consent" ]; then
    info "plugins de hosts aguardam consentimento separado; nenhum plugin de host foi alterado"
    info "revise o plano somente pelo Runtime: $DEST_PATH host-plugins plan --all"
  else
    warn "capacidade host-plugins indisponível neste Runtime; nenhum plugin de host foi alterado"
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

    if verify_runtime_contract "$DEST_PATH"; then
      ok "contrato de release do Runtime verificado"
    else
      warn "release não está pronta para distribuição (bundle/login/chave de updates)"
      report_runtime_contract "$DEST_PATH"
      status=1
    fi

    if verify_active_login; then
      ok "sessão Google verificada de forma fresh e entitlement válido"
    else
      warn "sessão Google não verificada de forma fresh (ausente, cacheada, expirada, revogada ou sem entitlement)"
      status=1
    fi
  fi

  if [ "$status" -eq 0 ]; then
    ok "simplicio está saudável"
  else
    warn "simplicio tem problemas — rode o instalador novamente"
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
  --doctor) run_doctor ;;
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
INSTALL_STAGE="platform_detection"
detect_platform
info "Plataforma detectada: $OS-$ARCH"

# ─── 2. Instalar simplicio binary (staged download + SHA256 + atomic swap) ──
INSTALL_STAGE="runtime_install"
info "Instalando Simplicio Runtime..."
mkdir -p "$BIN_DIR" || err "não foi possível criar o diretório do Runtime: $BIN_DIR"

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
  MANIFEST_TMP="$(mktemp)" || err "não foi possível criar o arquivo temporário do manifest de release"
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
    SIGNATURE_HELPER_TMP="$(mktemp)" || err "não foi possível criar o arquivo temporário do verificador Ed25519"
    if [ "$SIGNING_PUBKEY" != "$ED25519_PUBLIC_KEY" ] || ! verify_ed25519_signature "$STAGING_PATH" "$SIGNATURE" "$ED25519_PUBLIC_KEY" "$EXPECTED_SHA256" "$SIGNATURE_HELPER_TMP"; then
      rm -f "$STAGING_PATH" "$SIGNATURE_HELPER_TMP"
      err "assinatura Ed25519 inválida ou não verificável; instalação recusada"
    fi
    rm -f "$SIGNATURE_HELPER_TMP"
    ok "assinatura Ed25519 verificada sobre o digest SHA256"
  fi

  chmod +x "$STAGING_PATH" || { rm -f "$STAGING_PATH"; err "não foi possível tornar o Runtime baixado executável"; }
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
  INSTALL_EFFECT_STARTED="true"
  RUNTIME_INSTALLED="true"
  INSTALL_TRANSACTION_ACTIVE="false"
  if ! rm -f "$PREVIOUS_PATH"; then
    err "o Runtime foi ativado, mas o backup temporário não pôde ser removido: $PREVIOUS_PATH"
  fi
  ok "Simplicio Runtime instalado em $DEST_PATH"
fi

# ─── 2.1 Verificar o contrato de release antes de anunciar sucesso ──────────
INSTALL_STAGE="runtime_contract"
if ! verify_runtime_contract "$DEST_PATH"; then
  report_runtime_contract "$DEST_PATH"
  err "este Runtime não atende ao contrato de distribuição (fontes embutidas, login Google e chave pública de updates); instalação interrompida"
fi
RUNTIME_INSTALLED="true"
ok "contrato de release do Runtime verificado"

# ─── 2.2 Register MCP and native hooks for every detected client ───────────
INSTALL_STAGE="mcp_registration"
# Registration may update several client configs before returning a failure.
# From this point an error is conservatively recorded as a partial effect.
INSTALL_EFFECT_STARTED="true"
  if verify_mcp_tools "$DEST_PATH"; then
    MCP_REGISTERED="true"
    ok "MCP e hooks registrados automaticamente para os clientes detectados"
  else
    fail_install "${MCP_FAILURE_CODE:-mcp_registration_failed}" "${MCP_FAILURE_REASON:-Runtime MCP registration failed without a diagnostic}"
  fi
INSTALL_STAGE="hook_registration"
if reconcile_public_route_overlay; then
  HOOK_INSTALLED="true"
  ok "hook público v12 verificado e reconciliado após o registro do Runtime"
else
  fail_install "${HOOK_FAILURE_CODE:-hook_registration_failed}" "${HOOK_FAILURE_REASON:-Public hook registration failed without a diagnostic}"
fi

# Host-specific plugin changes require a second, explicit consent transaction.
# This installer never invokes host CLIs and never downloads a mutable plugin
# archive. The Runtime owns planning, application, receipts and reconciliation.
probe_host_plugins_capability || true
report_host_plugin_consent
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
INSTALL_STAGE="runtime_report"
BUNDLE_DIR="${SIMPLICIO_BUNDLE_DIR:-$HOME/.simplicio}"
RUNTIME_REPORT="$BUNDLE_DIR/runtime-release.json"
mkdir -p "$BUNDLE_DIR" || err "não foi possível criar o diretório do relatório do Runtime: $BUNDLE_DIR"
if "$DEST_PATH" version --json >"$RUNTIME_REPORT" 2>/dev/null; then
  ok "contrato de release registrado em $RUNTIME_REPORT"
else
  if ! rm -f "$RUNTIME_REPORT"; then
    err "o Runtime falhou ao gerar o relatório e o arquivo parcial não pôde ser removido: $RUNTIME_REPORT"
  fi
  err "não foi possível persistir o contrato de release; instalação interrompida"
fi

INSTALL_STAGE="complete"
if ! persist_install_receipt "succeeded" 0 "" ""; then
  INSTALL_STAGE="receipt_persistence"
  err "Runtime/MCP/hook foram instalados, mas o recibo estruturado da instalação não pôde ser persistido"
fi
ok "recibo estruturado da instalação registrado em $INSTALL_RECEIPT"

# ─── 4. Mensagem final ───────────────────────────────────────────────────────
echo ""
printf '%b\n' "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
printf '%b\n' "${GREEN}║                                                          ║${NC}"
printf '%b\n' "${GREEN}║   Simplicio Runtime instalado com sucesso!              ║${NC}"
printf '%b\n' "${GREEN}║                                                          ║${NC}"
printf '%b\n' "${GREEN}║   ✓ Contrato de release verificado                       ║${NC}"
printf '%b\n' "${GREEN}║   ✓ Sem pip ou clones durante a instalação               ║${NC}"
if verify_active_login; then
  printf '%b\n' "${GREEN}║   ✓ Sessão Google fresh verificada                       ║${NC}"
else
  printf '%b\n' "${YELLOW}║   ⚠ Login Google pendente: execute auth login            ║${NC}"
fi
printf '%b\n' "${GREEN}║   ✓ MCP direto para o binário gerenciado                 ║${NC}"
if [ "$HOST_PLUGINS_STATE" = "pending_consent" ]; then
  printf '%b\n' "${GREEN}║   ⏳ Plugins aguardam consentimento separado             ║${NC}"
else
  printf '%b\n' "${YELLOW}║   ⚠ Plugins indisponíveis neste Runtime                  ║${NC}"
fi
printf '%b\n' "${GREEN}║   🩺 Doctor: sh install.sh --doctor                     ║${NC}"
printf '%b\n' "${GREEN}║                                                          ║${NC}"
printf '%b\n' "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
ok "Instalação Runtime concluída. SIMPLICIO_MCP_URL=${SIMPLICIO_MCP_URL}"

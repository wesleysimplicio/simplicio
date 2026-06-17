#!/usr/bin/env sh
# install.sh — Install the simplicio binary
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh
#
# The script:
#   1. Detects OS and architecture
#   2. Downloads the correct binary from GitHub
#   3. Places it in /usr/local/bin (or $HOME/.local/bin as fallback)
#   4. Verifies with simplicio version
#
# Environment variables:
#   SIMPLICIO_VERSION  - pin a specific version (default: latest)
#   SIMPLICIO_BIN_DIR  - custom install directory
#   SIMPLICIO_SKIP_SELF_CHECK - skip binary verification

set -eu

# ─── Config ──────────────────────────────────────────────────────────────────
REPO="wesleysimplicio/simplicio"
GITHUB="https://github.com/$REPO"
RAW="https://raw.githubusercontent.com/$REPO/main"

BIN_NAME="simplicio"

# ─── Colors ──────────────────────────────────────────────────────────────────
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

# ─── Detect platform ─────────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"

# Asset OS/arch must match the published release names:
#   simplicio-linux-x64 · simplicio-darwin-arm64 · simplicio-windows-x64
case "$OS" in
  Darwin)
    OS_TARGET="darwin"
    ;;
  Linux)
    OS_TARGET="linux"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    OS_TARGET="windows"
    BIN_NAME="simplicio.exe"
    ;;
  *)
    err "unsupported OS: $OS (we support macOS, Linux, and Windows)"
    ;;
esac

case "$ARCH" in
  x86_64|amd64)
    ARCH_TARGET="x64"
    ;;
  aarch64|arm64)
    ARCH_TARGET="arm64"
    ;;
  *)
    warn "untested architecture: $ARCH (assuming x64)"
    ARCH_TARGET="x64"
    ;;
esac

info "detected: $OS_TARGET-$ARCH_TARGET"

# ─── Determine install dir ──────────────────────────────────────────────────
if [ -n "${SIMPLICIO_BIN_DIR:-}" ]; then
  INSTALL_DIR="$SIMPLICIO_BIN_DIR"
elif [ -d "$HOME/.local/bin" ] && echo ":$PATH:" | grep -q ":$HOME/.local/bin:"; then
  INSTALL_DIR="$HOME/.local/bin"
else
  INSTALL_DIR="/usr/local/bin"
fi

# Fallback if target isn't writable
if [ ! -w "$INSTALL_DIR" ]; then
  INSTALL_DIR="$HOME/.local/bin"
  mkdir -p "$INSTALL_DIR"
fi

info "install directory: $INSTALL_DIR"

# ─── Determine version ──────────────────────────────────────────────────────
VERSION="${SIMPLICIO_VERSION:-}"
if [ -z "$VERSION" ]; then
  info "fetching latest version..."
  VERSION=$(curl -sSfL "https://api.github.com/repos/$REPO/releases/latest" \
    | grep '"tag_name":' \
    | head -1 \
    | cut -d'"' -f4 2>/dev/null || echo "")
  if [ -z "$VERSION" ]; then
    VERSION="latest"
    warn "could not determine latest version, using 'latest'"
  else
    ok "latest version: $VERSION"
  fi
fi

# ─── Download binary ─────────────────────────────────────────────────────────
# Release assets are raw binaries named simplicio-<os>-<arch> (no tarball).
ASSET="simplicio-$OS_TARGET-$ARCH_TARGET"
TAGGED_URL="$GITHUB/releases/download/$VERSION/$ASSET"
LATEST_URL="$GITHUB/releases/latest/download/$ASSET"

info "downloading $ASSET..."

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# Try the pinned tag first, then the 'latest' redirect (covers VERSION=latest /
# API hiccups). Both are raw binaries from the PUBLIC simplicio repo.
BINARY_SRC=""
for _u in "$TAGGED_URL" "$LATEST_URL"; do
  if curl -sSfL --max-time 60 "$_u" -o "$TMP_DIR/$BIN_NAME" 2>/dev/null && [ -s "$TMP_DIR/$BIN_NAME" ]; then
    BINARY_SRC="$TMP_DIR/$BIN_NAME"
    break
  fi
done

if [ -z "$BINARY_SRC" ] || [ ! -s "$BINARY_SRC" ]; then
  err "download failed for $ASSET — get it at https://github.com/wesleysimplicio/simplicio/releases/latest"
fi

chmod +x "$BINARY_SRC"

# ─── Install ─────────────────────────────────────────────────────────────────
info "installing to $INSTALL_DIR/$BIN_NAME"
cp "$BINARY_SRC" "$INSTALL_DIR/$BIN_NAME"
chmod +x "$INSTALL_DIR/$BIN_NAME"

ok "installed: $INSTALL_DIR/$BIN_NAME"

# ─── Verify ──────────────────────────────────────────────────────────────────
if [ -z "${SIMPLICIO_SKIP_SELF_CHECK:-}" ]; then
  if "$INSTALL_DIR/$BIN_NAME" version 2>/dev/null; then
    ok "simplicio is ready!"
  else
    warn "binary installed but 'simplicio version' failed"
  fi
fi

# ─── Claude Code statusline badge ────────────────────────────────────────────
# Shows a green [SIMPLICIO] badge in Claude Code when the repo is simplicio-enabled.
if command -v python3 >/dev/null 2>&1; then
  CLAUDE_DIR="$HOME/.claude"
  mkdir -p "$CLAUDE_DIR/hooks"
  cat > "$CLAUDE_DIR/hooks/simplicio-statusline.sh" <<'SLEOF'
#!/bin/bash
# Simplicio statusline — prints a green [SIMPLICIO] badge when the current
# repo is simplicio-enabled (.simplicio/ dir or .simplicio.toml present).
# If the user already had a statusLine command before install, it was saved
# at ~/.claude/hooks/.simplicio-statusline-prev and is chained first.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("workspace",{}).get("current_dir") or d.get("cwd") or "")' 2>/dev/null)

OUT=""
PREV="$HOME/.claude/hooks/.simplicio-statusline-prev"
if [ -s "$PREV" ]; then
  OUT=$(printf '%s' "$INPUT" | sh -c "$(cat "$PREV")" 2>/dev/null) || OUT=""
fi

if [ -n "$CWD" ] && { [ -d "$CWD/.simplicio" ] || [ -f "$CWD/.simplicio.toml" ]; }; then
  [ -n "$OUT" ] && OUT="$OUT "
  OUT="$OUT$(printf '\033[38;5;42m[SIMPLICIO]\033[0m')"
fi

printf '%s' "$OUT"
SLEOF
  chmod +x "$CLAUDE_DIR/hooks/simplicio-statusline.sh"
  python3 - "$CLAUDE_DIR/settings.json" <<'PY' 2>/dev/null || true
import json, os, sys
p = sys.argv[1]
try:
    d = json.load(open(p)) if os.path.exists(p) else {}
except Exception:
    d = {}
sl_cmd = "bash ~/.claude/hooks/simplicio-statusline.sh"
sl = d.get("statusLine") or {}
prev = sl.get("command", "")
if "simplicio-statusline" not in prev:
    if prev:
        open(os.path.expanduser("~/.claude/hooks/.simplicio-statusline-prev"), "w").write(prev)
    d["statusLine"] = {"type": "command", "command": sl_cmd}
os.makedirs(os.path.dirname(p), exist_ok=True)
json.dump(d, open(p, "w"), indent=2)
PY
  ok "Claude Code statusline badge installed ([SIMPLICIO])"
fi

# ─── Editor badge (VS Code, Cursor, Windsurf, Antigravity) ───────────────────
VSIX="$HOME/.simplicio/simplicio-badge.vsix"
mkdir -p "$HOME/.simplicio"
if curl -fsSL "https://simpleti.com.br/simplicio/dist/simplicio-badge.vsix" -o "$VSIX" 2>/dev/null; then
  for ed in code cursor windsurf antigravity codium; do
    if command -v "$ed" >/dev/null 2>&1; then
      "$ed" --install-extension "$VSIX" >/dev/null 2>&1 && ok "[SIMPLICIO] badge installed in $ed" || true
    fi
  done
fi

# ─── PATH hint ───────────────────────────────────────────────────────────────
case ":$PATH:" in
  *:"$INSTALL_DIR":*)
    ;;
  *)
    echo ""
    warn "$INSTALL_DIR is not in PATH"
    echo "  Add it to your shell profile:"
    echo ""
    echo "    export PATH=\"\$PATH:$INSTALL_DIR\""
    echo ""
    ;;
esac

echo ""
ok "${BOLD}simplicio $VERSION ($OS_TARGET-$ARCH_TARGET) installed successfully${NC}"
echo ""
echo "  Run:  simplicio chat 'hello' --repo ."
echo "  REPL: simplicio chat --repl --repo ."
echo "  Help: simplicio --help"
echo ""

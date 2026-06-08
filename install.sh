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

case "$OS" in
  Darwin)
    OS_TARGET="macos"
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
    ARCH_TARGET="x86_64"
    ;;
  aarch64|arm64)
    ARCH_TARGET="aarch64"
    ;;
  *)
    warn "untested architecture: $ARCH (assuming x86_64)"
    ARCH_TARGET="x86_64"
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
DOWNLOAD_URL="$GITHUB/releases/download/$VERSION/simplicio-$VERSION-$OS_TARGET-$ARCH_TARGET.tar.gz"
FALLBACK_URL="$GITHUB/releases/download/$VERSION/simplicio-$OS_TARGET-$ARCH_TARGET.tar.gz"
BINARY_URL="$RAW/$BIN_NAME"

info "downloading simplicio..."

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

# Try release tarball first, fall back to raw binary
if curl -sSfL "$DOWNLOAD_URL" -o "$TMP_DIR/release.tar.gz" 2>/dev/null; then
  info "extracting release tarball..."
  tar xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR"
  # Find the binary inside the extracted dir
  BINARY_SRC=$(find "$TMP_DIR" -name "$BIN_NAME" -type f | head -1)
  if [ -z "$BINARY_SRC" ]; then
    err "binary not found in release tarball"
  fi
elif curl -sSfL "$FALLBACK_URL" -o "$TMP_DIR/release.tar.gz" 2>/dev/null; then
  info "extracting release tarball (fallback url)..."
  tar xzf "$TMP_DIR/release.tar.gz" -C "$TMP_DIR"
  BINARY_SRC=$(find "$TMP_DIR" -name "$BIN_NAME" -type f | head -1)
  if [ -z "$BINARY_SRC" ]; then
    err "binary not found in release tarball"
  fi
else
  # Raw binary fallback
  info "downloading raw binary..."
  curl -sSfL "$BINARY_URL" -o "$TMP_DIR/$BIN_NAME"
  BINARY_SRC="$TMP_DIR/$BIN_NAME"
fi

if [ ! -f "$BINARY_SRC" ]; then
  err "download failed (no binary found)"
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

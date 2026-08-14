#!/usr/bin/env sh
set -eu

# Simplicio ecosystem installer for macOS and Linux.
# The source of truth is GitHub releases from the component repositories.
# Runtime assets are selected newest-first per OS/architecture. Component
# wheels are selected newest-first and fall back to older releases when the
# newest release has no published wheel.

REPO="wesleysimplicio/simplicio"
API_ROOT="https://api.github.com/repos"
INSTALL_DIR="${SIMPLICIO_BIN_DIR:-$HOME/.local/bin}"
STATE_DIR="${SIMPLICIO_STATE_DIR:-$HOME/.simplicio}"
VENV_DIR="${SIMPLICIO_COMPONENT_VENV:-$STATE_DIR/components-venv}"
MANIFEST="$STATE_DIR/components.json"
TMP_DIR="${TMPDIR:-/tmp}/simplicio-install-$$"

info() { printf '%s\n' "==> $*"; }
ok() { printf '%s\n' "  ✓ $*"; }
warn() { printf '%s\n' "  ! $*" >&2; }
fail() { printf '%s\n' "  ✗ $*" >&2; exit 1; }

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT INT TERM

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    return 1
  fi
}

verify_digest() {
  path=$1
  digest=$2
  [ -n "$digest" ] || { warn "sem digest SHA-256 publicado para $(basename "$path"); instalação continua"; return 0; }
  case "$digest" in
    sha256:*) digest=${digest#sha256:} ;;
  esac
  actual=$(sha256_file "$path" 2>/dev/null || true)
  [ -n "$actual" ] || { warn "não foi possível calcular SHA-256 para $(basename "$path"); instalação continua"; return 0; }
  [ "$actual" = "$(printf '%s' "$digest" | tr '[:upper:]' '[:lower:]')" ] || fail "SHA-256 inválido para $(basename "$path")";
  ok "SHA-256 verificado: $(basename "$path")"
}

download_asset() {
  url=$1
  destination=$2
  digest=$3
  staging="$destination.download-$$"
  rm -f "$staging"
  curl -fL --retry 3 --retry-delay 1 -sS "$url" -o "$staging" || fail "download falhou: $url"
  [ -s "$staging" ] || fail "asset vazio: $url"
  verify_digest "$staging" "$digest"
  mv -f "$staging" "$destination"
}

fetch_releases() {
  repo=$1
  version=${2:-}
  if [ -n "$version" ]; then
    url="$API_ROOT/$repo/releases/tags/$version"
  else
    url="$API_ROOT/$repo/releases?per_page=100"
  fi
  curl -fL --retry 3 --retry-delay 1 -sS \
    -H 'Accept: application/vnd.github+json' \
    -H 'User-Agent: simplicio-installer' \
    "$url"
}

# Read a release JSON document from stdin and return:
# release-tag|asset-name|download-url|sha256-digest
select_asset() {
  "$PYTHON" -c '
import fnmatch
import json
import sys

payload = json.load(sys.stdin)
releases = [payload] if isinstance(payload, dict) else payload
patterns = sys.argv[1:]

for release in releases or []:
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        continue
    for asset in release.get("assets") or []:
        name = asset.get("name", "")
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
            url = asset.get("browser_download_url")
            if url:
                print("|".join([
                    str(release.get("tag_name", "")),
                    name,
                    url,
                    str(asset.get("digest") or ""),
                ]))
                raise SystemExit(0)
raise SystemExit(1)
' "$@"
}

uninstall() {
  info "Removendo Simplicio Runtime e componentes gerenciados"
  rm -f "$INSTALL_DIR/simplicio"
  if [ -d "$VENV_DIR/bin" ]; then
    for candidate in "$INSTALL_DIR"/simplicio-* "$INSTALL_DIR/sendsprint"; do
      [ -L "$candidate" ] || continue
      target=$(readlink "$candidate" 2>/dev/null || true)
      case "$target" in
        "$VENV_DIR/bin/"*) rm -f "$candidate" ;;
      esac
    done
  fi
  rm -rf "$VENV_DIR"
  rm -f "$MANIFEST"
  ok "componentes removidos; configurações fora da virtualenv foram preservadas"
}

doctor() {
  ok_state=0
  if [ -x "$INSTALL_DIR/simplicio" ]; then
    "$INSTALL_DIR/simplicio" version >/dev/null 2>&1 && ok "Runtime executável" || { warn "Runtime não executa"; ok_state=1; }
  else
    warn "Runtime ausente: $INSTALL_DIR/simplicio"
    ok_state=1
  fi
  for command_name in simplicio-mapper simplicio-dev-cli simplicio-fast simplicio-loop simplicio-subagents sendsprint; do
    if [ -x "$INSTALL_DIR/$command_name" ]; then
      ok "$command_name disponível"
    else
      warn "$command_name ausente"
      ok_state=1
    fi
  done
  if [ -f "$MANIFEST" ]; then ok "manifesto: $MANIFEST"; else warn "manifesto ausente: $MANIFEST"; ok_state=1; fi
  return "$ok_state"
}

action=${1:-install}
case "$action" in
  --uninstall|-u)
    uninstall
    exit 0
    ;;
  --doctor|-d)
    doctor
    exit $?
    ;;
  --help|-h)
    printf '%s\n' 'Uso: sh install.sh [--doctor|--uninstall]' 'Variáveis: SIMPLICIO_VERSION, SIMPLICIO_BIN_DIR, SIMPLICIO_STATE_DIR, SIMPLICIO_COMPONENT_VENV'
    exit 0
    ;;
  install)
    ;;
  *)
    fail "argumento desconhecido: $action"
    ;;
esac

if [ -n "${SIMPLICIO_PYTHON:-}" ]; then
  PYTHON=$SIMPLICIO_PYTHON
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
  PYTHON=$(command -v python)
else
  fail 'Python 3.11+ não encontrado'
fi

"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || fail 'Python 3.11 ou superior é necessário para todos os componentes'
command -v curl >/dev/null 2>&1 || fail 'curl não encontrado'

OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$OS:$ARCH" in
  linux:x86_64|linux:amd64)
    RUNTIME_TARGET='linux-x64'
    RUNTIME_PATTERNS='simplicio-linux-x64 simplicio-linux-x86_64'
    ;;
  linux:aarch64|linux:arm64)
    RUNTIME_TARGET='linux-arm64'
    RUNTIME_PATTERNS='simplicio-linux-arm64 simplicio-linux-aarch64'
    ;;
  darwin:arm64|darwin:aarch64)
    RUNTIME_TARGET='macos-arm64'
    RUNTIME_PATTERNS='simplicio-macos-arm64 simplicio-darwin-arm64'
    ;;
  darwin:x86_64|darwin:amd64)
    RUNTIME_TARGET='macos-x64'
    RUNTIME_PATTERNS='simplicio-macos-x64 simplicio-darwin-x64'
    ;;
  *)
    fail "plataforma não suportada: $OS/$ARCH"
    ;;
esac

mkdir -p "$INSTALL_DIR" "$STATE_DIR" "$TMP_DIR"

info "Procurando o binário Runtime mais recente para $RUNTIME_TARGET"
runtime_json=$(fetch_releases "$REPO" "${SIMPLICIO_VERSION:-}") || fail 'não foi possível consultar as releases do Runtime'
set -- $RUNTIME_PATTERNS
runtime_selection=$(printf '%s' "$runtime_json" | select_asset "$@" 2>/dev/null) \
  || fail "nenhum asset Runtime encontrado para $RUNTIME_TARGET nas releases disponíveis"
IFS='|' read -r runtime_release runtime_asset runtime_url runtime_digest <<EOF
$runtime_selection
EOF
runtime_download="$TMP_DIR/$runtime_asset"
download_asset "$runtime_url" "$runtime_download" "$runtime_digest"
chmod +x "$runtime_download"
mv -f "$runtime_download" "$INSTALL_DIR/simplicio"
ok "Runtime $runtime_release instalado: $INSTALL_DIR/simplicio"

# Prompt is installed before Dev CLI because Dev CLI declares it as a runtime
# dependency. All six component packages still come from their GitHub release
# wheels, not from a source checkout.
COMPONENTS='simplicio-mapper|wesleysimplicio/simplicio-mapper|simplicio_mapper-*.whl
simplicio-prompt|wesleysimplicio/simplicio-prompt|simplicio_prompt-*.whl
simplicio-dev-cli|wesleysimplicio/simplicio-dev-cli|simplicio_cli-*.whl
simplicio-fast|wesleysimplicio/simplicio-fast|simplicio_fast-*.whl
simplicio-loop|wesleysimplicio/simplicio-loop|simplicio_loop-*.whl
simplicio-sprint|wesleysimplicio/simplicio-sprint|simplicio_sprint-*.whl'

mkdir -p "$(dirname "$VENV_DIR")"
"$PYTHON" -m venv "$VENV_DIR" || fail "não foi possível criar a virtualenv: $VENV_DIR"
VENV_PYTHON="$VENV_DIR/bin/python"
[ -x "$VENV_PYTHON" ] || fail "Python da virtualenv não encontrado: $VENV_PYTHON"
"$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade pip >/dev/null \
  || fail 'não foi possível preparar o pip da virtualenv'

COMPONENT_RECORDS=''
while IFS='|' read -r component component_repo wheel_pattern; do
  [ -n "$component" ] || continue
  info "Procurando wheel de $component"
  component_json=$(fetch_releases "$component_repo" '') \
    || fail "não foi possível consultar as releases de $component_repo"
  component_selection=$(printf '%s' "$component_json" | select_asset "$wheel_pattern" 2>/dev/null) \
    || fail "nenhuma wheel encontrada para $component em $component_repo"
  IFS='|' read -r component_release component_asset component_url component_digest <<EOF
$component_selection
EOF
  wheel_path="$TMP_DIR/$component_asset"
  download_asset "$component_url" "$wheel_path" "$component_digest"
  "$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade --force-reinstall "$wheel_path" \
    || fail "falha ao instalar $component ($component_release)"
  COMPONENT_RECORDS="${COMPONENT_RECORDS}${component}|${component_release}|${component_asset}
"
  ok "$component $component_release instalado"
done <<EOF
$COMPONENTS
EOF

# Expose every console script generated by the six installed wheels through
# the same bin directory as the native Runtime. Symlinks keep updates atomic
# and do not duplicate the Python entry-point files.
for executable in "$VENV_DIR/bin"/simplicio-* "$VENV_DIR/bin"/sendsprint; do
  [ -e "$executable" ] || continue
  name=$(basename "$executable")
  ln -sfn "$executable" "$INSTALL_DIR/$name"
done

export MANIFEST RUNTIME_TARGET runtime_release runtime_asset VENV_DIR INSTALL_DIR COMPONENT_RECORDS
"$PYTHON" - "$MANIFEST" <<'PY'
import json
import os
import pathlib
import sys

manifest = pathlib.Path(sys.argv[1])
records = []
for line in os.environ.get("COMPONENT_RECORDS", "").splitlines():
    if line:
        name, release, asset = line.split("|", 2)
        records.append({"name": name, "release": release, "asset": asset})

venv = pathlib.Path(os.environ["VENV_DIR"]).resolve()
bin_dir = pathlib.Path(os.environ["INSTALL_DIR"])
managed = [str(bin_dir / "simplicio")]
for candidate in list(bin_dir.glob("simplicio-*")) + [bin_dir / "sendsprint"]:
    if not candidate.is_symlink():
        continue
    try:
        target = candidate.resolve()
    except OSError:
        continue
    if str(target).startswith(str(venv) + os.sep):
        managed.append(str(candidate))

payload = {
    "schema": "simplicio.ecosystem-manifest/v2",
    "source": "github-releases",
    "runtime": {
        "repository": "wesleysimplicio/simplicio",
        "target": os.environ["RUNTIME_TARGET"],
        "release": os.environ["runtime_release"],
        "asset": os.environ["runtime_asset"],
        "path": str(bin_dir / "simplicio"),
    },
    "components": records,
    "python_venv": str(venv),
    "managed_paths": sorted(set(managed)),
}
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

ok "manifesto gravado: $MANIFEST"
printf '%s\n' '' 'Instalação concluída.' "MCP: simplicio serve --mcp --stdio" "PATH: adicione $INSTALL_DIR ao PATH se necessário."

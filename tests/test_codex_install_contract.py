"""Static contract checks for the public Codex integration."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_installers_configure_direct_stdio_and_hooks():
    for name in ("install.sh", "install.ps1"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "config.toml" in text
        assert "hooks.json" in text
        assert "serve" in text and "--mcp" in text and "--stdio" in text
        assert "mcp-route" in text
        assert "mcp register" not in text


def test_installers_preserve_existing_codex_state():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "simplicio.bak" in shell
    assert "atomic_write" in shell
    assert "simplicio.bak" in powershell
    assert "Write-AtomicText" in powershell


def test_installers_preserve_stable_login_state_during_upgrades():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "SIMPLICIO_AUTH_FILE" in shell
    assert "SIMPLICIO_AUTH_FILE" in powershell
    assert "login.json" in shell
    assert "login.json" in powershell


def test_windows_installer_migrates_legacy_unix_hooks():
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    # Existing Windows users may have the old global hook, which invokes
    # /bin/bash against a .sh path. The installer must remove only that legacy
    # Simplicio entry before adding the PowerShell hook.
    assert "mcp-route\\.sh" in powershell
    assert "/bin/bash" in powershell
    assert "Remove-Legacy-CodexHooks" in powershell
    assert "mcp-route.ps1" in powershell


def test_unix_installer_migrates_legacy_hook_events():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    # The same stale global entry can survive under a legacy snake_case event
    # on macOS/Linux; the shell installer must remove it before upserting the
    # current command.
    assert "def remove_legacy_hooks" in shell
    assert "simplicio-mcp-route" in shell
    assert "list(hooks)" in shell
    assert "del hooks[event]" in shell


def test_unix_installer_accepts_release_manifest_target_aliases():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    # The v3.8.15 manifest uses Rust-style target names while the public
    # distribution table uses stable installer IDs. Keep signature lookup
    # fail-closed, but accept both names.
    assert 'MANIFEST_TARGET_ID="$TARGET_ID"' in shell
    assert 'macos-arm64) MANIFEST_TARGET_ID="macos-aarch64"' in shell
    assert 'macos-x64) MANIFEST_TARGET_ID="macos-x86_64"' in shell
    assert 'linux-x64) MANIFEST_TARGET_ID="linux-x86_64"' in shell
    assert "a.get('target') in {'$MANIFEST_TARGET_ID', '$TARGET_ID'}" in shell


def test_codex_hooks_have_all_required_lifecycle_events():
    shell_hook = (ROOT / "codex/mcp-route.sh").read_text(encoding="utf-8")
    powershell_hook = (ROOT / "codex/mcp-route.ps1").read_text(encoding="utf-8")
    # Claude's current PreToolUse protocol rejects the legacy top-level
    # {decision: allow|deny} response. Both platform hooks must emit the
    # event-specific permissionDecision envelope.
    assert "permissionDecision" in shell_hook
    assert "permissionDecision" in powershell_hook
    assert "hookEventName" in shell_hook
    assert "hookEventName" in powershell_hook
    assert "Use simplicio_file_read / simplicio_read / simplicio_search instead of" in shell_hook
    assert "Use simplicio_file_read / simplicio_read / simplicio_search instead of" in powershell_hook
    for event in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
        assert event in shell_hook
        assert event in powershell_hook
    assert "PreToolUse" in (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "PreToolUse" in (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert '"matcher": ".*"' in (ROOT / "install.sh").read_text(encoding="utf-8")
    assert '".*"' in (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "simplicio_map" in shell_hook
    assert "simplicio_context" in shell_hook


def test_docs_describe_stdio_instead_of_codex_http_authenticate_flow():
    for name in ("README.md", "MCP-CONNECT.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "local STDIO MCP" in text
        assert "serve --mcp --stdio" in text
        assert "HTTP/OAuth" not in text
        assert "Authenticate" not in text

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


def test_windows_installer_migrates_legacy_unix_hooks():
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    # Existing Windows users may have the old global hook, which invokes
    # /bin/bash against a .sh path. The installer must remove only that legacy
    # Simplicio entry before adding the PowerShell hook.
    assert "mcp-route\\.sh" in powershell
    assert "/bin/bash" in powershell
    assert "Remove-Legacy-CodexHooks" in powershell
    assert "mcp-route.ps1" in powershell


def test_codex_hooks_have_all_required_lifecycle_events():
    shell_hook = (ROOT / "codex/mcp-route.sh").read_text(encoding="utf-8")
    powershell_hook = (ROOT / "codex/mcp-route.ps1").read_text(encoding="utf-8")
    for event in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
        assert event in shell_hook
        assert event in powershell_hook
    assert "PreToolUse" in (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "PreToolUse" in (ROOT / "install.ps1").read_text(encoding="utf-8")


def test_docs_describe_stdio_instead_of_codex_http_authenticate_flow():
    for name in ("README.md", "MCP-CONNECT.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "local STDIO MCP" in text
        assert "serve --mcp --stdio" in text
        assert "HTTP/OAuth" not in text
        assert "Authenticate" not in text

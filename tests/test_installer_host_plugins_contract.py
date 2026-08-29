from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shell_installs_documented_native_plugins_after_runtime_registration() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    registration = 'verify_mcp_tools "$DEST_PATH"'
    plugin_install = "install_detected_host_plugins"

    assert 'command -v codex' in text
    assert 'codex plugin marketplace add "$REPO" --ref master' in text
    assert "codex plugin add simplicio@simplicio-codex" in text
    assert 'command -v claude' in text
    assert 'claude plugin marketplace add "$REPO"' in text
    assert "claude plugin install simplicio@simplicio --scope user" in text
    assert 'command -v gemini' in text
    assert 'gemini extensions install "$plugin_dir" --consent' in text
    assert text.index(registration) < text.index(plugin_install, text.index(registration))


def test_powershell_installs_documented_native_plugins_after_runtime_registration() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")
    registration = "Test-McpToolSurface $DestPath"
    plugin_install = "Install-DetectedHostPlugins"

    assert "Get-Command codex -CommandType Application" in text
    assert '@("plugin", "marketplace", "add", $Repo, "--ref", "master")' in text
    assert '@("plugin", "add", "simplicio@simplicio-codex")' in text
    assert "Get-Command claude -CommandType Application" in text
    assert '@("plugin", "marketplace", "add", $Repo)' in text
    assert '@("plugin", "install", "simplicio@simplicio", "--scope", "user")' in text
    assert "Get-Command gemini -CommandType Application" in text
    assert '@("extensions", "install", $manifest.DirectoryName, "--consent")' in text
    assert text.index(registration) < text.index(plugin_install, text.index(registration))


def test_host_plugin_bootstrap_is_idempotent_and_does_not_guess_unsupported_clis() -> None:
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    bootstrap = (
        ROOT / "plugins/simplicio/bin/simplicio-mcp-bootstrap.js"
    ).read_text(encoding="utf-8")

    for text in (shell, powershell):
        assert "SIMPLICIO_INSTALL_HOST_PLUGINS" in text
        for unsupported in (
            "cursor plugin install",
            "code plugin install",
            "kiro plugin install",
            "qwen plugin install",
        ):
            assert unsupported not in text.lower()

    assert 'SIMPLICIO_INSTALL_HOST_PLUGINS: "0"' in bootstrap

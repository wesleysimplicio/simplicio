from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shell_installs_documented_native_plugins_after_runtime_registration() -> None:
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    registration = 'verify_mcp_tools "$DEST_PATH"'
    plugin_install = "install_detected_host_plugins"

    assert 'command -v codex' in text
    assert 'codex plugin marketplace add "$REPO" --ref master \\' in text
    assert "--sparse .agents/plugins --sparse plugins/simplicio" in text
    assert "codex plugin add simplicio@simplicio-codex" in text
    assert 'command -v claude' in text
    assert 'claude plugin marketplace add "$REPO"' in text
    assert 'MARKETPLACE_PLUGINS="simplicio simplicio-loop simplicio-prompt simplicio-sprint simplicio-hermes"' in text
    assert 'claude plugin install "$plugin_name@simplicio" --scope user' in text
    assert 'command -v gemini' in text
    assert 'gemini extensions install "$plugin_dir" --consent' in text
    assert 'command -v copilot' in text
    assert 'copilot plugin install "$plugin_name@simplicio"' in text
    assert 'command -v qwen' in text
    assert 'qwen extensions install "$REPO:$plugin_name"' in text
    assert 'command -v hermes' in text
    assert 'hermes plugins install "$REPO/plugins/simplicio-hermes" --force --enable' in text
    assert 'hermes plugins doctor simplicio-hermes --ci' in text
    assert '"$HOME/.cursor/plugins/local/simplicio"' in text
    assert '"$HOME/.kiro/powers/simplicio"' in text
    assert 'err "Runtime/MCP estão prontos, mas a instalação automática' in text
    assert text.index(registration) < text.index(plugin_install, text.index(registration))


def test_powershell_installs_documented_native_plugins_after_runtime_registration() -> None:
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")
    registration = "Test-McpToolSurface $DestPath"
    plugin_install = "Install-DetectedHostPlugins"

    assert "Get-Command codex -CommandType Application" in text
    assert '"plugin", "marketplace", "add", $Repo, "--ref", "master",' in text
    assert '"--sparse", ".agents/plugins", "--sparse", "plugins/simplicio"' in text
    assert '@("plugin", "add", "simplicio@simplicio-codex")' in text
    assert "Get-Command claude -CommandType Application" in text
    assert '@("plugin", "marketplace", "add", $Repo)' in text
    assert '$MarketplacePlugins = @("simplicio", "simplicio-loop", "simplicio-prompt", "simplicio-sprint", "simplicio-hermes")' in text
    assert '@("plugin", "install", "$pluginName@simplicio", "--scope", "user")' in text
    assert "Get-Command gemini -CommandType Application" in text
    assert '@("extensions", "install", $manifest.DirectoryName, "--consent")' in text
    assert "Get-Command copilot -CommandType Application" in text
    assert '@("plugin", "install", "$pluginName@simplicio")' in text
    assert "Get-Command qwen -CommandType Application" in text
    assert '@("extensions", "install", "${Repo}:$pluginName")' in text
    assert "Get-Command hermes -CommandType Application" in text
    assert '@("plugins", "install", "$Repo/plugins/simplicio-hermes", "--force", "--enable")' in text
    assert '@("plugins", "doctor", "simplicio-hermes", "--ci")' in text
    assert '".cursor\\plugins\\local\\simplicio"' in text
    assert '".kiro\\powers\\simplicio"' in text
    assert 'Write-Error "Runtime/MCP are ready, but automatic installation' in text
    assert text.index(registration) < text.index(plugin_install, text.index(registration))


def test_host_plugin_bootstrap_is_idempotent_and_uses_documented_surfaces() -> None:
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    bootstrap = (
        ROOT / "plugins/simplicio/bin/simplicio-mcp-bootstrap.js"
    ).read_text(encoding="utf-8")

    for text in (shell, powershell):
        assert "SIMPLICIO_INSTALL_HOST_PLUGINS" in text
        for unsupported in ("cursor plugin install", "code plugin install", "kiro plugin install"):
            assert unsupported not in text.lower()

    assert 'SIMPLICIO_INSTALL_HOST_PLUGINS: "0"' in bootstrap

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shell_defers_mcp_handshake_until_after_login():
    text = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert text.rindex('require_active_login') < text.rindex('verify_mcp_tools \"$DEST_PATH\"')
    assert 'verify_mcp_tools \"$STAGING_PATH\"' not in text


def test_powershell_defers_mcp_handshake_until_after_login():
    text = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert text.rindex('Require-ActiveLogin') < text.rindex('Test-McpToolSurface $DestPath')
    assert 'Test-McpToolSurface $StagingPath' not in text

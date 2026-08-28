from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shell_defers_mcp_handshake_until_after_login():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    registration = 'verify_mcp_tools "$DEST_PATH"'
    assert registration in text
    assert "require_active_login" not in text
    assert text.index(registration) < text.index("report_login_state", text.index(registration))
    assert 'verify_mcp_tools "$STAGING_PATH"' not in text
    assert 'RELEASE_TAG="v${VERSION#v}"' in text


def test_powershell_defers_mcp_handshake_until_after_login():
    text = (ROOT / "install.ps1").read_text(encoding="utf-8")
    registration = "Test-McpToolSurface $DestPath"
    assert registration in text
    assert "Require-ActiveLogin" not in text
    assert text.index(registration) < text.index("Report-LoginState", text.index(registration))
    assert "Test-McpToolSurface $StagingPath" not in text
    assert '$ReleaseTag = if ($Version.StartsWith("v"))' in text

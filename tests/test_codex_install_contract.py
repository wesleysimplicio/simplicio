"""Static contract checks for the public Codex integration."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_pretooluse_allow_unchanged_emits_no_permission_decision():
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "simplicio__simplicio_read",
        "tool_input": {"path": "src/main.rs"},
        "cwd": "/tmp",
    }
    completed = subprocess.run(
        ["bash", str(ROOT / "codex" / "mcp-route.sh")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env={**os.environ, "SIMPLICIO_BIN": "/nonexistent"},
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""


def test_installers_configure_direct_stdio_and_hooks():
    for name in ("install.sh", "install.ps1"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "SIMPLICIO_MCP_URL" in text
        assert "serve" in text and "--mcp" in text and "--stdio" in text
        if name == "install.sh":
            assert "mcp register" in text
        else:
            assert '@("mcp", "register", "--binary", $BinaryPath, "--json")' in text
        assert "--binary" in text
        assert "--json" in text

def test_plain_install_registers_all_detected_hosts_without_codex_opt_in():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "SIMPLICIO_INSTALL_CODEX" not in shell
    assert "SIMPLICIO_CODEX_HOOK_REF" not in shell
    assert "if require_active_login; then" not in shell
    assert 'mcp register --binary "$binary_path" --json' in shell

    assert "SIMPLICIO_INSTALL_CODEX" not in powershell
    assert "SIMPLICIO_CODEX_HOOK_REF" not in powershell
    assert "if (Require-ActiveLogin)" not in powershell
    assert '@("mcp", "register", "--binary", $BinaryPath, "--json")' in powershell


def test_installers_preserve_existing_codex_state():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "mcp register" in shell
    assert '@("mcp", "register", "--binary", $BinaryPath, "--json")' in powershell
    assert "Resolve-RuntimeFailure" in powershell
    assert "$script:McpFailureReason" in powershell


def test_installers_preserve_stable_login_state_during_upgrades():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "report_login_state" in shell
    assert "Report-LoginState" in powershell
    assert "auth login" in shell
    assert "auth login" in powershell


def test_windows_installer_reconciles_the_pinned_public_hook_after_runtime_registration():
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    hook_digest = hashlib.sha256((ROOT / "codex" / "mcp-route.ps1").read_bytes()).hexdigest()
    assert "Install-CodexRouteHook" not in powershell
    assert "SIMPLICIO_CODEX_HOOK_REF" not in powershell
    assert '@("mcp", "register", "--binary", $BinaryPath, "--json")' in powershell
    assert '$PublicRouteRef = "68b4c7f7ac27d07624ffa4ddf0673a43e180c3e5"' in powershell
    assert f'$PublicRouteSha256 = "{hook_digest}"' in powershell
    assert "Sync-PublicRouteOverlay" in powershell
    assert powershell.index("Test-McpToolSurface $DestPath") < powershell.index("if (Sync-PublicRouteOverlay)")


def test_unix_installer_reconciles_the_pinned_public_hook_after_runtime_registration():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    hook_digest = hashlib.sha256((ROOT / "codex" / "mcp-route.sh").read_bytes()).hexdigest()
    assert "CODEX_ROUTE_HOOK_URL" not in shell
    assert "install_codex_route_hook" not in shell
    assert "SIMPLICIO_CODEX_HOOK_REF" not in shell
    assert 'mcp register --binary "$binary_path" --json' in shell
    assert 'PUBLIC_ROUTE_REF="68b4c7f7ac27d07624ffa4ddf0673a43e180c3e5"' in shell
    assert f'PUBLIC_ROUTE_SHA256="{hook_digest}"' in shell
    assert "reconcile_public_route_overlay" in shell
    assert shell.index('if verify_mcp_tools "$DEST_PATH"') < shell.index("if reconcile_public_route_overlay")

def test_unix_installer_accepts_release_manifest_target_aliases():
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    # The v3.8.15 manifest uses Rust-style target names while the public
    # distribution table uses stable installer IDs. Keep signature lookup
    # fail-closed, but accept both names.
    assert 'TARGET_ID="$OS-$ARCH"' in shell
    assert "a.get('target') == '$TARGET_ID'" in shell


def test_codex_hooks_have_all_required_lifecycle_events():
    shell_hook = (ROOT / "codex/mcp-route.sh").read_text(encoding="utf-8")
    powershell_hook = (ROOT / "codex/mcp-route.ps1").read_text(encoding="utf-8")
    # Codex rejects a bare PreToolUse permissionDecision=allow. Allowing an
    # unchanged call is represented by successful empty stdout on both hosts.
    assert '"permissionDecision": "allow"' not in shell_hook
    assert "permissionDecision = 'allow'" not in powershell_hook
    assert '"permissionDecision": "deny"' in shell_hook
    assert "permissionDecision = 'deny'" in powershell_hook
    assert "hookEventName" in shell_hook
    assert "hookEventName" in powershell_hook
    assert "simplicio-hook-version: 3240-v12" in shell_hook
    assert "simplicio-hook-version: 3240-v12" in powershell_hook
    assert "Empty stdout is the portable allow-unchanged contract" in shell_hook
    assert "No decision means allow unchanged" in powershell_hook
    assert "Allow-Unchanged" in powershell_hook
    assert "Simplicio MCP is mandatory" not in shell_hook
    assert "Simplicio MCP is mandatory" not in powershell_hook
    for event in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
        assert event in shell_hook
        assert event in powershell_hook
    assert "mcp register" in (ROOT / "install.sh").read_text(encoding="utf-8")
    assert '@("mcp", "register", "--binary", $BinaryPath, "--json")' in (
        ROOT / "install.ps1"
    ).read_text(encoding="utf-8")
    assert "result=subprocess.run([binary,'map','--repo'" in shell_hook
    assert "simplicio_context" in shell_hook
    assert 'SIMPLICIO_BIN="${SIMPLICIO_BIN:-${SIMPLICIO_BIN_DIR:-${HOME}/.simplicio/bin}/simplicio}"' in shell_hook
    assert 'which("simplicio")' not in shell_hook
    assert "Join-Path (Join-Path $UserHome '.simplicio\\bin') 'simplicio.exe'" in powershell_hook
    assert "Get-Command simplicio" not in powershell_hook


def test_docs_describe_stdio_instead_of_codex_http_authenticate_flow():
    for name in ("README.md", "MCP-CONNECT.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "local STDIO MCP" in text
        assert "serve --mcp --stdio" in text
        assert "HTTP/OAuth" not in text
        assert "Authenticate" not in text

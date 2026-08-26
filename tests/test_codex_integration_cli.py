import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / 'scripts/codex_integration.py'


def call(home, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args, '--home', str(home), '--source-root', str(ROOT)], capture_output=True, text=True)


def test_cli_install_status_uninstall_is_reversible():
    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        installed = call(home, 'install', '--platform', 'unix', '--version', 'v3.8.16', '--hook-ref', 'v3.8.16')
        assert installed.returncode == 0, installed.stderr
        state = json.loads(call(home, 'status').stdout)
        assert state['status'] == 'installed'
        assert 'mcp_servers.simplicio' in (home / '.codex/config.toml').read_text()
        removed = call(home, 'uninstall')
        assert removed.returncode == 0, removed.stderr
        assert json.loads(call(home, 'status').stdout)['status'] == 'absent'


def test_windows_binary_path_is_toml_safe_and_uses_forward_slashes():
    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        windows_binary = r"C:\Users\mathe\Downloads\simplicio-windows-x64.exe"
        installed = call(
            home,
            "install",
            "--platform",
            "windows",
            "--version",
            "v3.8.30",
            "--hook-ref",
            "v3.8.30",
            "--binary",
            windows_binary,
        )
        assert installed.returncode == 0, installed.stderr
        config = (home / ".codex/config.toml").read_text(encoding="utf-8")
        expected = "C:/Users/mathe/Downloads/simplicio-windows-x64.exe"
        assert f'command = "{expected}"' in config
        assert tomllib.loads(config)["mcp_servers"]["simplicio"]["command"] == expected


def test_installers_are_opt_in_and_do_not_use_mutable_master_hook_ref():
    shell = (ROOT / 'install.sh').read_text(encoding='utf-8')
    powershell = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert 'SIMPLICIO_INSTALL_CODEX' in shell and 'SIMPLICIO_INSTALL_CODEX' in powershell
    assert 'hook_ref="${SIMPLICIO_CODEX_HOOK_REF:-master}"' not in shell
    assert 'else { "master" }' not in powershell

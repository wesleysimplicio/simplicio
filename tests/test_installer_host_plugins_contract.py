import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
RELEASE_VERSION = "3.8.40"
SHELL_HOOK_SHA256 = "d91200cae4816c79fe0c903fc6eedc01835a557827e8d3d0480304f3bdce5118"
FAKE_MCP_FAILURE_CODE = "runtime_mcp_registration_denied"
FAKE_MCP_FAILURE_REASON = "Runtime refused MCP registration\nhost config policy\tdenied"
FRESH_AUTH = {
    "identity": {
        "enabled": True,
        "login_enabled": True,
        "status": "active",
        "email": "qa@example.test",
    },
    "entitlement": {"updates_allowed": True},
    "session_verification": {"verified": True, "cached": False},
}
CACHED_AUTH = {
    **FRESH_AUTH,
    "session_verification": {"verified": True, "cached": True},
}
MISSING_AUTH_FIELDS = {
    "identity": {"enabled": True, "login_enabled": True, "email": "qa@example.test"},
}


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_runtime(path: Path) -> None:
    _write_executable(
        path,
        """#!/bin/sh
set -eu
printf '%s\n' "$*" >>"$FAKE_RUNTIME_LOG"
case "${1:-}:${2:-}" in
  --version:)
    printf '%s\n' 'simplicio 3.8.40'
    ;;
  version:--json)
    cat <<'JSON'
{
  "version": "3.8.40",
  "auto_update": {"distribution": {"source_code_distributed": true}},
  "identity": {"enabled": true, "login_enabled": true},
  "security": {"signature_required": true, "public_key_configured": true}
}
JSON
    ;;
  version:)
    printf '%s\n' 'simplicio 3.8.40'
    ;;
    mcp:register)
    if [ "${FAKE_MCP_EXIT:-0}" -ne 0 ]; then
      cat <<'JSON'
{"failure":{"code":"runtime_mcp_registration_denied","reason":"Runtime refused MCP registration\\nhost config policy\\tdenied"}}
JSON
      printf '%s\n' 'fallback diagnostic must not replace the structured Runtime reason' >&2
      if [ "${FAKE_MCP_BURST:-0}" = "1" ]; then
        awk 'BEGIN { for (i = 0; i < 262144; i++) printf "o"; print "" }'
        awk 'BEGIN { for (i = 0; i < 262144; i++) printf "e"; print "" }' >&2
      fi
    fi
    exit "${FAKE_MCP_EXIT:-0}"
    ;;
    auth:status)
    if [ -n "${FAKE_AUTH_JSON:-}" ]; then
      printf '%s\n' "$FAKE_AUTH_JSON"
      exit 0
    fi
    cat <<'JSON'
{
  "identity": {
    "enabled": true,
    "login_enabled": true,
    "status": "active",
    "email": "qa@example.test"
  },
    "entitlement": {"updates_allowed": true},
    "session_verification": {"verified": true, "cached": false}
}
JSON
    ;;
  host-plugins:--help)
    if [ "${FAKE_HOST_PLUGINS_EXIT:-2}" -eq 0 ]; then
      case "${FAKE_HOST_PLUGINS_HELP_MODE:-contract}" in
        contract)
          cat <<'HELP'
simplicio.host-plugins/cli-v1
simplicio host-plugins plan (--all | --host HOST)
simplicio host-plugins apply (--all | --host HOST) --plan-digest sha256:HEX --yes
simplicio host-plugins verify (--all | --host HOST)
simplicio host-plugins status
simplicio host-plugins pending
simplicio host-plugins snapshot --receipt-id sha256:HEX
simplicio host-plugins reconcile --receipt-id sha256:HEX
HELP
          ;;
        wrong) printf '%s\n' 'Usage: simplicio shell --repo PATH -- COMMAND' ;;
        empty) : ;;
      esac
      exit 0
    fi
    printf '%s\n' '{"code":"host_plugins_unavailable","message":"host-plugins is unavailable in Runtime 3.8.40"}'
    exit "${FAKE_HOST_PLUGINS_EXIT:-2}"
    ;;
  *)
    exit 0
    ;;
esac
""",
    )


def _shell_fixture(
    tmp_path: Path,
    mcp_exit: int,
    *,
    host_plugins_exit: int = 2,
    host_plugins_help_mode: str = "contract",
    mcp_burst: bool = False,
) -> tuple[dict[str, str], Path, Path]:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    install_bin = bundle / "bin"
    runtime = install_bin / "simplicio"
    runtime_log = tmp_path / "runtime.log"
    host_log = tmp_path / "host.log"
    fake_bin = tmp_path / "fake-bin"

    _fake_runtime(runtime)
    hook = bundle / "hooks" / "mcp-route.sh"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("# test hook; hash is supplied by the fake checksum tool\n", encoding="utf-8")
    _write_executable(
        fake_bin / "sha256sum",
        f"""#!/bin/sh
if [ "${{FAKE_BAD_HOOK_HASH:-0}}" = "1" ]; then
  printf '%064d  %s\n' 0 "$1"
else
  printf '%s  %s\n' '{SHELL_HOOK_SHA256}' "$1"
fi
""",
    )
    for host in ("codex", "claude", "gemini", "copilot", "qwen", "hermes", "cursor", "kiro"):
        _write_executable(
            fake_bin / host,
            "#!/bin/sh\nprintf '%s\\n' \"$0 $*\" >>\"$FAKE_HOST_LOG\"\nexit 97\n",
        )
    _write_executable(
        fake_bin / "curl",
        """#!/bin/sh
printf '%s\n' '{"failure":{"code":"hook_fetch_denied","reason":"public hook download denied by fixture"}}'
printf '%s\n' 'fallback hook diagnostic' >&2
exit "${FAKE_HOOK_DOWNLOAD_EXIT:-22}"
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(install_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "SIMPLICIO_VERSION": RELEASE_VERSION,
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "FAKE_HOST_LOG": str(host_log),
            "FAKE_MCP_EXIT": str(mcp_exit),
            "FAKE_MCP_BURST": "1" if mcp_burst else "0",
            "FAKE_HOST_PLUGINS_EXIT": str(host_plugins_exit),
            "FAKE_HOST_PLUGINS_HELP_MODE": host_plugins_help_mode,
            "PATH": os.pathsep.join((str(fake_bin), os.environ["PATH"])),
        }
    )
    return env, bundle, host_log


def _run_shell_installer(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(ROOT / "install.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_shell_code_1_preserves_exact_partial_receipt(tmp_path: Path) -> None:
    env, bundle, host_log = _shell_fixture(tmp_path, mcp_exit=1)

    result = _run_shell_installer(env)

    assert result.returncode == 1
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["schema"] == "simplicio-install-receipt/v1"
    assert receipt["status"] == "partial"
    assert receipt["exit_code"] == 1
    assert receipt["stage"] == "mcp_registration"
    assert receipt["failure"] == {
        "code": FAKE_MCP_FAILURE_CODE,
        "reason": FAKE_MCP_FAILURE_REASON,
    }
    assert FAKE_MCP_FAILURE_REASON in result.stderr
    assert "fallback diagnostic must not replace" not in receipt["failure"]["reason"]
    assert receipt["runtime"] == {"installed": True}
    assert receipt["mcp"] == {"registered": False}
    assert receipt["hook"] == {"installed": False}
    assert receipt["host_plugins"]["state"] == "unavailable"
    assert receipt["host_plugins"]["mutated"] is False
    assert (bundle / "install-receipt.json").stat().st_size < 16_384
    assert not host_log.exists()


def test_shell_drains_oversized_runtime_output_without_expanding_receipt(tmp_path: Path) -> None:
    env, bundle, _ = _shell_fixture(tmp_path, mcp_exit=1, mcp_burst=True)

    result = _run_shell_installer(env)

    assert result.returncode == 1
    receipt_path = bundle / "install-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["failure"] == {
        "code": FAKE_MCP_FAILURE_CODE,
        "reason": FAKE_MCP_FAILURE_REASON,
    }
    assert receipt_path.stat().st_size < 16_384


def test_shell_pre_python_failure_receipt_escapes_control_bytes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    fake_bin = tmp_path / "fake-bin"
    blocked_bin = tmp_path / "blocked\nruntime\tbin"
    blocked_bin.write_text("not a directory", encoding="utf-8")
    _write_executable(fake_bin / "python3", "#!/bin/sh\nexit 127\n")
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(blocked_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "SIMPLICIO_VERSION": RELEASE_VERSION,
            "PATH": os.pathsep.join((str(fake_bin), "/bin", "/usr/bin")),
        }
    )

    result = _run_shell_installer(env)

    assert result.returncode == 1
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["failure"] == {
        "code": "runtime_install_failed",
        "reason": f"não foi possível criar o diretório do Runtime: {blocked_bin}",
    }


def test_shell_doctor_failure_never_mutates_existing_partial_receipt(tmp_path: Path) -> None:
    env, bundle, _ = _shell_fixture(tmp_path, mcp_exit=0)
    runtime = Path(env["SIMPLICIO_BIN_DIR"]) / "simplicio"
    runtime.unlink()
    receipt_path = bundle / "install-receipt.json"
    original = (
        b'{"schema":"simplicio-install-receipt/v1","status":"partial",'
        b'"failure":{"code":"preserve_me","reason":"original bytes"}}\n'
    )
    receipt_path.write_bytes(original)
    os.utime(receipt_path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    before = receipt_path.stat()
    before_digest = hashlib.sha256(original).hexdigest()

    result = subprocess.run(
        ["sh", str(ROOT / "install.sh"), "--doctor"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert receipt_path.read_bytes() == original
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == before_digest
    after = receipt_path.stat()
    assert after.st_mtime_ns == before.st_mtime_ns


def test_shell_doctor_unsupported_platform_never_mutates_receipt(tmp_path: Path) -> None:
    env, bundle, _ = _shell_fixture(tmp_path, mcp_exit=0)
    runtime = Path(env["SIMPLICIO_BIN_DIR"]) / "simplicio"
    runtime.unlink()
    fake_bin = Path(env["PATH"].split(os.pathsep, 1)[0])
    uname_log = tmp_path / "uname-called.log"
    _write_executable(
        fake_bin / "uname",
        f"""#!/bin/sh
printf '%s\n' "$1" >>'{uname_log}'
case "$1" in
  -s) printf '%s\n' 'Plan9' ;;
  -m) printf '%s\n' 'riscv128' ;;
esac
""",
    )
    receipt_path = bundle / "install-receipt.json"
    original = (
        b'{"schema":"simplicio-install-receipt/v1","status":"partial",'
        b'"failure":{"code":"unsupported_preserve","reason":"original bytes"}}\n'
    )
    receipt_path.write_bytes(original)
    os.utime(receipt_path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    before = receipt_path.stat()
    before_digest = hashlib.sha256(original).hexdigest()

    result = subprocess.run(
        ["sh", str(ROOT / "install.sh"), "--doctor"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert not uname_log.exists(), "--doctor must not execute platform detection"
    assert receipt_path.read_bytes() == original
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == before_digest
    after = receipt_path.stat()
    assert after.st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize(
    ("payload", "expected_code", "fresh_verified"),
    [
        (FRESH_AUTH, 0, True),
        (CACHED_AUTH, 1, False),
        (MISSING_AUTH_FIELDS, 1, False),
    ],
)
def test_shell_doctor_requires_fresh_complete_login_evidence(
    tmp_path: Path,
    payload: dict[str, object],
    expected_code: int,
    fresh_verified: bool,
) -> None:
    env, _, _ = _shell_fixture(tmp_path, mcp_exit=0)
    env["FAKE_AUTH_JSON"] = json.dumps(payload)

    result = subprocess.run(
        ["sh", str(ROOT / "install.sh"), "--doctor"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == expected_code
    assert ("sessão Google verificada de forma fresh" in result.stdout) is fresh_verified


def test_shell_repeat_is_idempotent_and_reports_plugins_unavailable(tmp_path: Path) -> None:
    env, bundle, host_log = _shell_fixture(tmp_path, mcp_exit=0)

    first = _run_shell_installer(env)
    second = _run_shell_installer(env)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "capacidade host-plugins indisponível" in first.stdout
    assert "capacidade host-plugins indisponível" in second.stdout
    receipt_path = bundle / "install-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "succeeded"
    assert receipt["exit_code"] == 0
    assert receipt["runtime"] == {"installed": True}
    assert receipt["mcp"] == {"registered": True}
    assert receipt["hook"] == {"installed": True}
    assert receipt["host_plugins"]["state"] == "unavailable"
    assert receipt["host_plugins"]["command"] is None
    assert "host-plugins capability unavailable" in receipt["host_plugins"]["reason"]
    assert receipt["host_plugins"]["mutated"] is False
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    assert not list(bundle.glob("install-receipt.json.tmp.*"))
    assert not host_log.exists()


def test_shell_marks_plugins_pending_only_when_runtime_capability_exists(tmp_path: Path) -> None:
    env, bundle, host_log = _shell_fixture(
        tmp_path,
        mcp_exit=0,
        host_plugins_exit=0,
    )

    result = _run_shell_installer(env)

    assert result.returncode == 0, result.stderr
    runtime_calls = Path(env["FAKE_RUNTIME_LOG"]).read_text(encoding="utf-8")
    assert "host-plugins --help" in runtime_calls
    assert "host-plugins plan --all" not in runtime_calls
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["host_plugins"] == {
        "state": "pending_consent",
        "owner": "simplicio-runtime",
        "command": "simplicio host-plugins plan --all",
        "mutated": False,
        "reason": "Host plugins require separate explicit user consent.",
    }
    assert "nenhum plugin de host foi alterado" in result.stdout
    assert not host_log.exists()


@pytest.mark.parametrize("help_mode", ["wrong", "empty"])
def test_shell_exit_zero_without_host_plugin_contract_is_unavailable(
    tmp_path: Path,
    help_mode: str,
) -> None:
    env, bundle, host_log = _shell_fixture(
        tmp_path,
        mcp_exit=0,
        host_plugins_exit=0,
        host_plugins_help_mode=help_mode,
    )

    result = _run_shell_installer(env)

    assert result.returncode == 0, result.stderr
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["host_plugins"]["state"] == "unavailable"
    assert receipt["host_plugins"]["command"] is None
    assert "simplicio.host-plugins/cli-v1" in receipt["host_plugins"]["reason"]
    assert receipt["host_plugins"]["mutated"] is False
    runtime_calls = Path(env["FAKE_RUNTIME_LOG"]).read_text(encoding="utf-8")
    assert "host-plugins --help" in runtime_calls
    assert "host-plugins plan --all" not in runtime_calls
    assert not host_log.exists()


def test_shell_hook_failure_preserves_structured_code_and_reason(tmp_path: Path) -> None:
    env, bundle, _ = _shell_fixture(tmp_path, mcp_exit=0)
    env["FAKE_BAD_HOOK_HASH"] = "1"

    result = _run_shell_installer(env)

    assert result.returncode == 1
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "partial"
    assert receipt["stage"] == "hook_registration"
    assert receipt["failure"] == {
        "code": "hook_fetch_denied",
        "reason": "public hook download denied by fixture",
    }
    assert receipt["mcp"] == {"registered": True}
    assert receipt["hook"] == {"installed": False}


def test_installers_delegate_plugins_only_to_runtime_after_consent() -> None:
    installers = [
        (ROOT / "install.sh").read_text(encoding="utf-8"),
        (ROOT / "install.ps1").read_text(encoding="utf-8"),
    ]
    forbidden = (
        "archive/refs/heads/master.zip",
        "codex plugin marketplace add",
        "claude plugin marketplace add",
        "gemini extensions install",
        "copilot plugin marketplace add",
        "qwen extensions install",
        "hermes plugins install",
        ".cursor/plugins/local/simplicio",
        ".kiro/powers/simplicio",
    )
    for text in installers:
        assert "simplicio-install-receipt/v1" in text
        assert "pending_consent" in text
        assert "host-plugins" in text
        assert "--help" in text
        assert "simplicio host-plugins plan --all" in text
        assert all(token not in text for token in forbidden)
    assert "Login Google verificável após auth login" not in installers[0]
    assert "active Google login is verified after auth login" not in installers[1]
    assert "if verify_active_login; then" in installers[0]
    assert "if (Test-ActiveLogin)" in installers[1]
    assert "não alterou nenhum host" not in installers[0]
    assert "changed no host" not in installers[1]
    assert "SetAccessRuleProtection" in installers[1]
    assert "FileSystemAccessRule" in installers[1]
    assert "Set-Acl -Path $Path" in installers[1]


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
@pytest.mark.parametrize("mcp_burst", [False, True])
def test_powershell_code_1_preserves_partial_receipt(
    tmp_path: Path,
    mcp_burst: bool,
) -> None:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    install_bin = bundle / "bin"
    source_runtime = tmp_path / "simplicio-runtime"
    runtime_log = tmp_path / "runtime-pwsh.log"
    _fake_runtime(source_runtime)
    digest = hashlib.sha256(source_runtime.read_bytes()).hexdigest()

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(install_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "FAKE_RUNTIME_SOURCE": str(source_runtime),
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "FAKE_MCP_EXIT": "1",
            "FAKE_MCP_BURST": "1" if mcp_burst else "0",
            "FAKE_RUNTIME_SHA256": digest,
            "INSTALLER_PATH": str(ROOT / "install.ps1"),
        }
    )
    harness = r"""
function Invoke-RestMethod {
  param([string]$Uri, [object]$ErrorAction)
  return [pscustomobject]@{
    artifacts = @([pscustomobject]@{
      target = "windows-x64"
      sha256 = $env:FAKE_RUNTIME_SHA256
      signed = $false
      signature = ""
    })
    signing_pubkey = ""
    security = [pscustomobject]@{ signature_required = $false }
  }
}
function Invoke-WebRequest {
  param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing, [object]$ErrorAction)
  Copy-Item -Force -Path $env:FAKE_RUNTIME_SOURCE -Destination $OutFile
}
& $env:INSTALLER_PATH -Version "3.8.40"
"""

    result = subprocess.run(
        [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", harness],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "partial"
    assert receipt["exit_code"] == 1
    assert receipt["stage"] == "mcp_registration"
    assert receipt["failure"] == {
        "code": FAKE_MCP_FAILURE_CODE,
        "reason": FAKE_MCP_FAILURE_REASON,
    }
    assert FAKE_MCP_FAILURE_REASON in result.stderr
    assert "fallback diagnostic must not replace" not in receipt["failure"]["reason"]
    assert receipt["runtime"] == {"installed": True}
    assert receipt["mcp"] == {"registered": False}
    assert receipt["host_plugins"]["state"] == "unavailable"
    assert receipt["host_plugins"]["mutated"] is False


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
def test_powershell_hook_failure_preserves_concrete_code_and_reason(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    install_bin = bundle / "bin"
    source_runtime = tmp_path / "simplicio-runtime"
    runtime_log = tmp_path / "runtime-pwsh-hook.log"
    _fake_runtime(source_runtime)
    digest = hashlib.sha256(source_runtime.read_bytes()).hexdigest()
    hook = bundle / "hooks" / "mcp-route.ps1"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("# deliberately invalid hook\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(install_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "FAKE_RUNTIME_SOURCE": str(source_runtime),
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "FAKE_MCP_EXIT": "0",
            "FAKE_RUNTIME_SHA256": digest,
            "INSTALLER_PATH": str(ROOT / "install.ps1"),
        }
    )
    harness = r"""
function Invoke-RestMethod {
  param([string]$Uri, [object]$ErrorAction)
  return [pscustomobject]@{
    artifacts = @([pscustomobject]@{
      target = "windows-x64"
      sha256 = $env:FAKE_RUNTIME_SHA256
      signed = $false
      signature = ""
    })
    signing_pubkey = ""
    security = [pscustomobject]@{ signature_required = $false }
  }
}
function Invoke-WebRequest {
  param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing, [object]$ErrorAction)
  if ($Uri -like "*mcp-route.ps1") {
    throw "public hook download denied by fixture"
  }
  Copy-Item -Force -Path $env:FAKE_RUNTIME_SOURCE -Destination $OutFile
}
& $env:INSTALLER_PATH -Version "3.8.40"
"""

    result = subprocess.run(
        [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", harness],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "partial"
    assert receipt["stage"] == "hook_registration"
    assert receipt["failure"] == {
        "code": "hook_download_failed",
        "reason": "public hook download denied by fixture",
    }
    assert receipt["mcp"] == {"registered": True}
    assert receipt["hook"] == {"installed": False}


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
@pytest.mark.parametrize(
    ("host_plugins_exit", "host_plugins_help_mode", "expected_state"),
    [
        (2, "contract", "unavailable"),
        (0, "contract", "pending_consent"),
        (0, "wrong", "unavailable"),
        (0, "empty", "unavailable"),
    ],
)
def test_powershell_repeat_is_idempotent_and_gates_host_plugins(
    tmp_path: Path,
    host_plugins_exit: int,
    host_plugins_help_mode: str,
    expected_state: str,
) -> None:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    install_bin = bundle / "bin"
    source_runtime = tmp_path / "simplicio-runtime"
    runtime_log = tmp_path / "runtime-pwsh-success.log"
    _fake_runtime(source_runtime)
    digest = hashlib.sha256(source_runtime.read_bytes()).hexdigest()
    hook = bundle / "hooks" / "mcp-route.ps1"
    hook.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "codex" / "mcp-route.ps1", hook)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(install_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "FAKE_RUNTIME_SOURCE": str(source_runtime),
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "FAKE_MCP_EXIT": "0",
            "FAKE_HOST_PLUGINS_EXIT": str(host_plugins_exit),
            "FAKE_HOST_PLUGINS_HELP_MODE": host_plugins_help_mode,
            "FAKE_RUNTIME_SHA256": digest,
            "INSTALLER_PATH": str(ROOT / "install.ps1"),
        }
    )
    harness = r"""
function Invoke-RestMethod {
  param([string]$Uri, [object]$ErrorAction)
  return [pscustomobject]@{
    artifacts = @([pscustomobject]@{
      target = "windows-x64"
      sha256 = $env:FAKE_RUNTIME_SHA256
      signed = $false
      signature = ""
    })
    signing_pubkey = ""
    security = [pscustomobject]@{ signature_required = $false }
  }
}
function Invoke-WebRequest {
  param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing, [object]$ErrorAction)
  Copy-Item -Force -Path $env:FAKE_RUNTIME_SOURCE -Destination $OutFile
}
& $env:INSTALLER_PATH -Version "3.8.40"
"""

    first = subprocess.run(
        [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", harness],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    second = subprocess.run(
        [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", harness],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    runtime_calls = runtime_log.read_text(encoding="utf-8")
    assert "host-plugins --help" in runtime_calls
    assert "host-plugins plan --all" not in runtime_calls
    if expected_state == "pending_consent":
        assert "host plugins are pending separate consent" in first.stdout
        assert "host plugins are pending separate consent" in second.stdout
    else:
        assert "host-plugins capability is unavailable" in first.stdout + first.stderr
        assert "host-plugins capability is unavailable" in second.stdout + second.stderr
    receipt = json.loads((bundle / "install-receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "succeeded"
    assert receipt["exit_code"] == 0
    assert receipt["runtime"] == {"installed": True}
    assert receipt["mcp"] == {"registered": True}
    assert receipt["hook"] == {"installed": True}
    assert receipt["host_plugins"]["state"] == expected_state
    expected_command = (
        "simplicio host-plugins plan --all" if expected_state == "pending_consent" else None
    )
    assert receipt["host_plugins"]["command"] == expected_command
    assert receipt["host_plugins"]["mutated"] is False
    assert stat.S_IMODE((bundle / "install-receipt.json").stat().st_mode) == 0o600
    assert not list(bundle.glob("install-receipt.json.tmp.*"))
    assert not list(bundle.glob("install-receipt.json.backup.*"))


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
def test_powershell_acl_failure_restores_previous_receipt(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    install_bin = bundle / "bin"
    source_runtime = tmp_path / "simplicio-runtime"
    runtime_log = tmp_path / "runtime-pwsh-acl.log"
    _fake_runtime(source_runtime)
    digest = hashlib.sha256(source_runtime.read_bytes()).hexdigest()
    hook = bundle / "hooks" / "mcp-route.ps1"
    hook.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "codex" / "mcp-route.ps1", hook)
    receipt_path = bundle / "install-receipt.json"
    original = (
        b'{"schema":"simplicio-install-receipt/v1","status":"partial",'
        b'"failure":{"code":"acl_preserve","reason":"original secure receipt"}}\n'
    )
    receipt_path.write_bytes(original)
    os.chmod(receipt_path, 0o640)
    os.utime(receipt_path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    before_stat = receipt_path.stat()

    def permission_snapshot(path: Path) -> str:
        if os.name != "nt":
            return oct(stat.S_IMODE(path.stat().st_mode))
        completed = subprocess.run(
            [
                shutil.which("pwsh"),
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-Acl -LiteralPath $args[0]).Sddl",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return completed.stdout.strip()

    before_permission = permission_snapshot(receipt_path)
    fake_bin = tmp_path / "fake-acl-bin"
    fake_bin.mkdir(parents=True)
    chmod_counter = tmp_path / "chmod-counter"
    _write_executable(
        fake_bin / "chmod",
        """#!/bin/sh
count=0
if [ -f "$FAKE_CHMOD_COUNTER" ]; then count=$(cat "$FAKE_CHMOD_COUNTER"); fi
count=$((count + 1))
printf '%s\n' "$count" >"$FAKE_CHMOD_COUNTER"
if [ "$count" -ge 2 ]; then
  printf '%s\n' 'fixture chmod ACL failure' >&2
  exit 1
fi
exec /bin/chmod "$@"
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(install_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "FAKE_RUNTIME_SOURCE": str(source_runtime),
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "FAKE_MCP_EXIT": "0",
            "FAKE_HOST_PLUGINS_EXIT": "0",
            "FAKE_HOST_PLUGINS_HELP_MODE": "contract",
            "FAKE_RUNTIME_SHA256": digest,
            "FAKE_CHMOD_COUNTER": str(chmod_counter),
            "INSTALLER_PATH": str(ROOT / "install.ps1"),
            "PATH": os.pathsep.join((str(fake_bin), os.environ["PATH"])),
        }
    )
    harness = r"""
function Invoke-RestMethod {
  param([string]$Uri, [object]$ErrorAction)
  return [pscustomobject]@{
    artifacts = @([pscustomobject]@{
      target = "windows-x64"
      sha256 = $env:FAKE_RUNTIME_SHA256
      signed = $false
      signature = ""
    })
    signing_pubkey = ""
    security = [pscustomobject]@{ signature_required = $false }
  }
}
function Invoke-WebRequest {
  param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing, [object]$ErrorAction)
  Copy-Item -Force -Path $env:FAKE_RUNTIME_SOURCE -Destination $OutFile
}
$script:ReceiptAclCalls = 0
function global:Set-Acl {
  param([string]$Path, [object]$AclObject)
  $script:ReceiptAclCalls += 1
  if ($script:ReceiptAclCalls -ge 2) { throw "fixture Set-Acl failure" }
  Microsoft.PowerShell.Security\Set-Acl -Path $Path -AclObject $AclObject
}
& $env:INSTALLER_PATH -Version "3.8.40"
"""

    result = subprocess.run(
        [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", harness],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert receipt_path.read_bytes() == original
    assert receipt_path.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert permission_snapshot(receipt_path) == before_permission
    assert not list(bundle.glob("install-receipt.json.tmp.*"))
    assert not list(bundle.glob("install-receipt.json.backup.*"))


@pytest.mark.skipif(shutil.which("pwsh") is None, reason="PowerShell is not installed")
@pytest.mark.parametrize(
    ("payload", "expected_code", "fresh_verified"),
    [
        (FRESH_AUTH, 0, True),
        (CACHED_AUTH, 1, False),
        (MISSING_AUTH_FIELDS, 1, False),
    ],
)
def test_powershell_doctor_requires_fresh_complete_login_evidence(
    tmp_path: Path,
    payload: dict[str, object],
    expected_code: int,
    fresh_verified: bool,
) -> None:
    home = tmp_path / "home"
    bundle = home / ".simplicio"
    install_bin = bundle / "bin"
    runtime = install_bin / "simplicio.exe"
    runtime_log = tmp_path / "runtime-pwsh-doctor.log"
    _fake_runtime(runtime)
    receipt_path = bundle / "install-receipt.json"
    original_receipt = (
        b'{"schema":"simplicio-install-receipt/v1","status":"partial",'
        b'"failure":{"code":"pwsh_doctor_preserve","reason":"original bytes"}}\n'
    )
    receipt_path.write_bytes(original_receipt)
    os.utime(receipt_path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    receipt_before = receipt_path.stat()
    receipt_digest = hashlib.sha256(original_receipt).hexdigest()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "SIMPLICIO_BIN_DIR": str(install_bin),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "FAKE_AUTH_JSON": json.dumps(payload),
        }
    )

    result = subprocess.run(
        [
            shutil.which("pwsh"),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "install.ps1"),
            "-Doctor",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == expected_code
    assert ("fresh Google session and entitlement verified" in result.stdout) is fresh_verified
    assert receipt_path.read_bytes() == original_receipt
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == receipt_digest
    assert receipt_path.stat().st_mtime_ns == receipt_before.st_mtime_ns

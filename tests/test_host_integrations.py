from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1] / "pypi" / "simplicio"
sys.path.insert(0, str(PACKAGE_ROOT))

from simplicio.host_integrations import (
    COMPATIBILITY_MATRIX_HOST_IDS,
    HOSTS,
    build_summary,
    compatibility_matrix,
    detect_hosts,
    write_summary,
)


def _command(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def test_matrix_has_unique_ids_and_all_parent_children() -> None:
    ids = [spec.host_id for spec in HOSTS]
    assert len(ids) == len(set(ids))
    assert all(spec.minimum_version for spec in HOSTS)
    for expected in {
        "claude-code",
        "cursor",
        "deepseek-harness",
        "opencode",
        "vscode",
        "antigravity",
        "kiro",
        "pi",
        "oh-my-pi",
        "orca",
        "command-code",
    }:
        assert expected in ids


def test_detection_uses_exact_executable_and_app_evidence(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "claude")
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    (home / ".cursor" / "mcp.json").write_text("{}", encoding="utf-8")
    snapshot = detect_hosts(home=home, env={"PATH": str(bin_dir)})
    by_id = {item["id"]: item for item in snapshot}
    assert by_id["claude-code"]["status"] == "detected"
    assert by_id["claude-code"]["executable"].endswith("/claude")
    assert by_id["cursor"]["status"] == "absent"
    assert by_id["deepseek-harness"]["status"] == "unsupported"


def test_claude_code_has_runtime_verification_contract() -> None:
    claude = next(spec for spec in HOSTS if spec.host_id == "claude-code")
    assert claude.executable_names == ("claude",)
    assert claude.config_paths == ("~/.claude/settings.json", "~/.claude/.mcp.json")
    assert claude.capability == "runtime-mcp"
    assert claude.verification_command[-1] == "--json"
    assert "<absolute-path>" in claude.verification_command
    assert claude.mcp_environment == (("SIMPLICIO_RUNTIME_MODE", "mapper-only"),)


def test_cursor_declares_user_and_workspace_scopes() -> None:
    cursor = next(spec for spec in HOSTS if spec.host_id == "cursor")
    assert cursor.executable_names == ("cursor",)
    assert cursor.scopes == ("user", "workspace")
    assert cursor.default_scope == "user"
    assert cursor.config_paths == ("~/.cursor/mcp.json", ".cursor/mcp.json")


def test_deepseek_harness_is_fail_closed_until_contract_is_verified() -> None:
    deepseek = next(spec for spec in HOSTS if spec.host_id == "deepseek-harness")
    assert deepseek.executable_names == ()
    assert deepseek.capability == "unsupported"
    assert deepseek.contract == "unverified"
    assert deepseek.verification_command == ()


def test_opencode_has_runtime_registration_contract() -> None:
    opencode = next(spec for spec in HOSTS if spec.host_id == "opencode")
    assert opencode.executable_names == ("opencode",)
    assert opencode.config_paths == ("~/.config/opencode/opencode.json", "opencode.json")
    assert opencode.capability == "runtime-mcp"
    assert opencode.verification_command[:3] == ("simplicio", "mcp", "register")
    assert opencode.default_scope == "user"


def test_vscode_declares_all_supported_configuration_scopes() -> None:
    vscode = next(spec for spec in HOSTS if spec.host_id == "vscode")
    assert vscode.executable_names == ("code", "code-insiders")
    assert vscode.scopes == ("user", "workspace", "remote")
    assert vscode.default_scope == "user"
    assert vscode.config_paths == ("~/.vscode/mcp.json", ".vscode/mcp.json")
    assert vscode.verification_command[-1] == "--json"


def test_antigravity_is_fail_closed_until_public_contract_is_verified() -> None:
    antigravity = next(spec for spec in HOSTS if spec.host_id == "antigravity")
    assert antigravity.executable_names == ()
    assert antigravity.capability == "unsupported"
    assert antigravity.contract == "unverified"
    assert antigravity.verification_command == ()


def test_kiro_has_runtime_registration_contract() -> None:
    kiro = next(spec for spec in HOSTS if spec.host_id == "kiro")
    assert kiro.executable_names == ("kiro-cli",)
    assert kiro.config_paths == ("~/.kiro/settings/mcp.json", ".kiro/settings/mcp.json")
    assert kiro.capability == "runtime-mcp"
    assert kiro.verification_command[:3] == ("simplicio", "mcp", "register")


def test_pi_and_oh_my_pi_use_separate_exact_host_entries() -> None:
    pi = next(spec for spec in HOSTS if spec.host_id == "pi")
    omp = next(spec for spec in HOSTS if spec.host_id == "oh-my-pi")
    assert pi.executable_names == ("pi",)
    assert omp.executable_names == ("omp",)
    assert pi.host_id != omp.host_id
    assert pi.capability == omp.capability == "runtime-mcp"
    assert pi.verification_command == omp.verification_command


def test_orca_uses_portable_cli_verification_without_worktree_mutation() -> None:
    orca = next(spec for spec in HOSTS if spec.host_id == "orca")
    assert orca.executable_names == ("orca",)
    assert orca.capability == "portable-cli"
    assert orca.contract == "documented-cli"
    assert orca.verification_command == ("orca", "status", "--json")
    assert "worktrees" in orca.reason


def test_compatibility_matrix_covers_every_requested_remaining_host() -> None:
    by_id = {spec.host_id: spec for spec in HOSTS}
    assert COMPATIBILITY_MATRIX_HOST_IDS <= set(by_id)
    assert len(COMPATIBILITY_MATRIX_HOST_IDS) == 22
    for host_id in COMPATIBILITY_MATRIX_HOST_IDS - {"oh-my-pi"}:
        spec = by_id[host_id]
        assert spec.contract == "unverified"
        assert spec.capability == "unsupported"
        assert spec.executable_names == ()


def test_compatibility_matrix_is_complete_and_redacted() -> None:
    matrix = compatibility_matrix()
    assert len(matrix) == len(HOSTS)
    assert {row["id"] for row in matrix} == {spec.host_id for spec in HOSTS}
    for row in matrix:
        assert set(row) == {
            "id", "name", "capability", "contract", "executable_names",
            "scopes", "verification", "documentation",
        }
        assert "token" not in json.dumps(row).lower()
        if row["contract"] == "unverified":
            assert row["capability"] == "unsupported"
            assert row["executable_names"] == []


def test_command_code_is_fail_closed_until_official_contract_is_confirmed() -> None:
    command_code = next(spec for spec in HOSTS if spec.host_id == "command-code")
    assert command_code.executable_names == ()
    assert command_code.capability == "unsupported"
    assert command_code.contract == "unverified"
    assert command_code.verification_command == ()


def test_skip_controls_are_explicit_and_do_not_touch_host_files(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "cursor")
    home = tmp_path / "home"
    snapshot = detect_hosts(
        home=home,
        env={"PATH": str(bin_dir), "SIMPLICIO_SKIP_CURSOR": "1"},
    )
    cursor = next(item for item in snapshot if item["id"] == "cursor")
    assert cursor["status"] == "skipped"
    assert not home.exists()


def test_summary_reconciles_runtime_receipt_without_claiming_unknown_hosts(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "claude")
    summary = build_summary(
        runtime_report={"status": "passed", "registered": ["claude-code"]},
        home=tmp_path / "home",
        env={"PATH": str(bin_dir)},
    )
    by_id = {item["id"]: item for item in summary["hosts"]}
    assert by_id["claude-code"]["status"] == "registered"
    assert by_id["deepseek-harness"]["status"] == "unsupported"
    assert summary["runtime_registration"] == {"status": "passed"}


def test_summary_is_atomic_and_restrictive(tmp_path: Path) -> None:
    target = tmp_path / "state" / "host-integrations.json"
    write_summary(target, {"schema": "test", "hosts": []})
    assert json.loads(target.read_text(encoding="utf-8"))["schema"] == "test"
    assert os.stat(target).st_mode & 0o777 == 0o600
    assert not list(target.parent.glob("host-integrations.json.*"))

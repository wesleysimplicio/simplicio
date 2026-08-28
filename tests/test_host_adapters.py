from __future__ import annotations

import json
from pathlib import Path

from simplicio.host_adapters import install_detected_hosts
from simplicio.host_integrations import HOSTS, HostSpec


def _command(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def _spec(host_id: str = "fixture") -> HostSpec:
    return HostSpec(
        host_id=host_id,
        name="Fixture Host",
        executable_names=(host_id,),
        config_paths=("~/.fixture/config.json",),
        capability="runtime-mcp",
        contract="delegated-to-runtime",
        scopes=("user",),
    )


def test_multi_host_install_preserves_unrelated_json_and_is_idempotent(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "fixture")
    home = tmp_path / "home"
    config = home / ".fixture" / "config.json"
    config.parent.mkdir(parents=True)
    original = {"theme": "dark", "servers": {"other": {"command": "other"}}}
    config.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

    first = install_detected_hosts(
        "/opt/simplicio/bin/simplicio",
        home=home,
        cwd=tmp_path,
        env={"PATH": str(bin_dir)},
        specs=(_spec(),),
    )
    assert first["failed_hosts"] == []
    assert first["counts"]["registered"] == 1
    assert json.loads(config.read_text(encoding="utf-8"))["theme"] == "dark"
    assert config.with_name("config.json.simplicio.bak").is_file()

    second = install_detected_hosts(
        "/opt/simplicio/bin/simplicio",
        home=home,
        cwd=tmp_path,
        env={"PATH": str(bin_dir)},
        specs=(_spec(),),
    )
    assert second["failed_hosts"] == []
    assert second["results"][0]["reason_code"] == "already_registered"


def test_dry_run_and_skip_do_not_mutate_files(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "fixture")
    home = tmp_path / "home"
    result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio",
        home=home,
        cwd=tmp_path,
        env={"PATH": str(bin_dir), "SIMPLICIO_SKIP_FIXTURE": "1"},
        dry_run=True,
        specs=(_spec(),),
    )
    assert result["counts"] == {"skipped": 1}
    assert not home.exists()


def test_malformed_config_isolated_as_failure(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "fixture")
    home = tmp_path / "home"
    config = home / ".fixture" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text("not json", encoding="utf-8")
    result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio",
        home=home,
        cwd=tmp_path,
        env={"PATH": str(bin_dir)},
        specs=(_spec(),),
    )
    assert result["failed_hosts"] == ["fixture"]
    assert config.read_text(encoding="utf-8") == "not json"


def test_claude_code_contract_uses_exact_probe_and_user_scope(tmp_path: Path) -> None:
    spec = next(item for item in HOSTS if item.host_id == "claude-code")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "claude")
    home = tmp_path / "home"
    config = home / ".claude" / "settings.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"model": "sonnet"}) + "\n", encoding="utf-8")

    result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio",
        home=home,
        cwd=tmp_path,
        env={"PATH": str(bin_dir)},
        specs=(spec,),
    )

    assert result["failed_hosts"] == []
    assert result["results"][0]["status"] == "registered"
    document = json.loads(config.read_text(encoding="utf-8"))
    assert document["mcpServers"]["simplicio"]["command"] == "/opt/simplicio/bin/simplicio"
    assert not (home / ".claude" / "settings.json.simplicio.bak").is_symlink()


def test_cursor_contract_selects_requested_user_or_workspace_scope(tmp_path: Path) -> None:
    spec = next(item for item in HOSTS if item.host_id == "cursor")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "cursor")
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    (home / ".cursor").mkdir(parents=True)
    (workspace / ".cursor").mkdir(parents=True)

    user = install_detected_hosts(
        "/opt/simplicio/bin/simplicio", home=home, cwd=workspace,
        env={"PATH": str(bin_dir)}, scope="user", specs=(spec,)
    )
    workspace_result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio", home=home, cwd=workspace,
        env={"PATH": str(bin_dir)}, scope="workspace", specs=(spec,)
    )

    assert user["failed_hosts"] == []
    assert workspace_result["failed_hosts"] == []
    assert json.loads((home / ".cursor/mcp.json").read_text())["mcpServers"]["simplicio"]
    assert json.loads((workspace / ".cursor/mcp.json").read_text())["mcpServers"]["simplicio"]


def test_unverified_deepseek_harness_fails_closed_without_mutation(tmp_path: Path) -> None:
    spec = next(item for item in HOSTS if item.host_id == "deepseek-harness")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "deepseek")
    home = tmp_path / "home"
    result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio",
        home=home,
        cwd=tmp_path,
        env={"PATH": str(bin_dir)},
        specs=(spec,),
    )

    assert result["failed_hosts"] == []
    assert result["results"] == [{
        "host_id": "deepseek-harness",
        "status": "unsupported",
        "scope": "user",
        "config": None,
        "capability": "unsupported",
        "verification": "none",
        "reason_code": "unsupported",
        "changed": False,
        "backup": None,
    }]
    assert not home.exists()


def test_opencode_contract_registers_documented_user_config(tmp_path: Path) -> None:
    spec = next(item for item in HOSTS if item.host_id == "opencode")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "opencode")
    home = tmp_path / "home"
    config = home / ".config/opencode/opencode.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"provider": "local"}) + "\n", encoding="utf-8")

    result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio", home=home, cwd=tmp_path,
        env={"PATH": str(bin_dir)}, specs=(spec,)
    )

    assert result["failed_hosts"] == []
    document = json.loads(config.read_text(encoding="utf-8"))
    assert document["provider"] == "local"
    assert document["mcpServers"]["simplicio"]["args"] == ["serve", "--mcp", "--stdio"]


def test_vscode_contract_supports_user_workspace_and_remote_scopes(tmp_path: Path) -> None:
    spec = next(item for item in HOSTS if item.host_id == "vscode")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "code")
    home = tmp_path / "home"
    workspace = tmp_path / "remote-workspace"
    (home / ".vscode").mkdir(parents=True)
    (workspace / ".vscode").mkdir(parents=True)

    for scope in ("user", "workspace", "remote"):
        result = install_detected_hosts(
            "/opt/simplicio/bin/simplicio", home=home, cwd=workspace,
            env={"PATH": str(bin_dir)}, scope=scope, specs=(spec,)
        )
        assert result["failed_hosts"] == []

    assert json.loads((home / ".vscode/mcp.json").read_text())["mcpServers"]["simplicio"]
    assert json.loads((workspace / ".vscode/mcp.json").read_text())["mcpServers"]["simplicio"]


def test_unverified_antigravity_is_reported_without_guessing_a_binary(tmp_path: Path) -> None:
    spec = next(item for item in HOSTS if item.host_id == "antigravity")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _command(bin_dir / "antigravity")
    result = install_detected_hosts(
        "/opt/simplicio/bin/simplicio", home=tmp_path / "home", cwd=tmp_path,
        env={"PATH": str(bin_dir)}, specs=(spec,)
    )

    assert result["results"][0]["status"] == "unsupported"
    assert result["results"][0]["reason_code"] == "unsupported"

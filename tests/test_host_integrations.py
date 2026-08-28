from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1] / "pypi" / "simplicio"
sys.path.insert(0, str(PACKAGE_ROOT))

from simplicio.host_integrations import (
    HOSTS,
    build_summary,
    detect_hosts,
    write_summary,
)


def _command(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)


def test_matrix_has_unique_ids_and_all_parent_children() -> None:
    ids = [spec.host_id for spec in HOSTS]
    assert len(ids) == len(set(ids))
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

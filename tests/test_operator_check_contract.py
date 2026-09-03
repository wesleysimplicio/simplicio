"""Regression coverage for synthetic operator-check fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "plugin/scripts/operator_check.py"


def test_selftest_does_not_copy_published_operator_versions() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "0.23.1" not in source
    assert "0.24.0" not in source
    assert "0.0.0-test" in source
    assert "0.0.1-test" in source


def test_operator_check_selftest_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "selftest"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "operator_check selftest: PASS" in result.stdout

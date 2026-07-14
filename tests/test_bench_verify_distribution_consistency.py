"""Unit tests for scripts/bench_verify_distribution_consistency.py.

Exercises the benchmark/regression-gate mechanism itself (baseline
creation, pass, regression, missing-baseline) without depending on real
wall-clock noise mattering for pass/fail.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bench_verify_distribution_consistency.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("bench_verify_distribution_consistency", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fresh_module(tmp_path, monkeypatch, runs=2):
    bench = _load_module()
    # Keep tests fast and point the baseline at a throwaway file so we
    # never touch the real committed baseline.
    bench.RUNS = runs
    bench.BASELINE_PATH = tmp_path / "benchmark-baseline.json"
    monkeypatch.delenv("BENCH_REGRESSION_THRESHOLD_PCT", raising=False)
    return bench


def test_measure_returns_positive_duration(tmp_path, monkeypatch):
    bench = _fresh_module(tmp_path, monkeypatch)
    assert bench.measure(runs=2) >= 0.0


def test_main_writes_baseline_with_update_flag(tmp_path, monkeypatch):
    bench = _fresh_module(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["bench", "--update-baseline"])
    assert bench.main() == 0
    baseline = json.loads(bench.BASELINE_PATH.read_text(encoding="utf-8"))
    assert baseline["median_ms"] >= 0.0


def test_main_fails_when_baseline_missing(tmp_path, monkeypatch):
    bench = _fresh_module(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["bench"])
    assert not bench.BASELINE_PATH.exists()
    assert bench.main() == 1


def test_main_passes_within_generous_threshold(tmp_path, monkeypatch):
    bench = _fresh_module(tmp_path, monkeypatch)
    bench.BASELINE_PATH.write_text(json.dumps({"median_ms": 10_000.0}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bench"])
    assert bench.main() == 0


def test_main_fails_on_real_regression(tmp_path, monkeypatch):
    bench = _fresh_module(tmp_path, monkeypatch)
    bench.BASELINE_PATH.write_text(json.dumps({"median_ms": 0.0}), encoding="utf-8")
    monkeypatch.setenv("BENCH_REGRESSION_THRESHOLD_PCT", "0")
    monkeypatch.setattr(sys, "argv", ["bench"])
    # Force a measured duration that cannot fit under a 0ms baseline + 5ms floor.
    monkeypatch.setattr(bench, "measure", lambda runs=bench.RUNS: 50.0)
    assert bench.main() == 1

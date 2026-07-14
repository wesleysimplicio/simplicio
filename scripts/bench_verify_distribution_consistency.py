#!/usr/bin/env python3
"""Micro-benchmark + regression gate for the distribution consistency audit.

This is the first vertical slice of the "benchmark with baseline and
configurable regression limit" requirement from issue #10. The audited
script is tiny today, so the interesting part is the *mechanism*
(baseline file + configurable threshold + CI wiring), not the absolute
numbers. When perf-sensitive code lands in this repo, point this same
pattern at it.

Usage:
    python3 scripts/bench_verify_distribution_consistency.py [--update-baseline]

Environment:
    BENCH_REGRESSION_THRESHOLD_PCT   Allowed slowdown vs. baseline, as a
                                      percentage (default: "150", i.e. the
                                      median run may be up to 2.5x the
                                      baseline before this fails). Kept
                                      generous by default because this
                                      script's runtime is sub-millisecond
                                      and dominated by CI runner noise, not
                                      by real work.

Exit code:
    0  measurement is within the allowed regression threshold
    1  measurement regressed beyond the threshold
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_distribution_consistency.py"
BASELINE_PATH = REPO_ROOT / ".github" / "quality-gate" / "benchmark-baseline.json"
RUNS = 25
DEFAULT_THRESHOLD_PCT = 150.0


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("verify_distribution_consistency", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def measure(runs: int = RUNS) -> float:
    """Return the median wall-clock time (in milliseconds) of ``main()``."""
    vdc = _load_audit_module()
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            # Explicit empty argv: vdc.main() takes an optional argv and
            # falls back to parsing sys.argv (this benchmark script's own
            # argv, e.g. --update-baseline) when called with none.
            vdc.main([])
        samples.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(samples)


def main() -> int:
    update_baseline = "--update-baseline" in sys.argv
    threshold_pct = float(os.environ.get("BENCH_REGRESSION_THRESHOLD_PCT", DEFAULT_THRESHOLD_PCT))

    median_ms = measure()
    print(f"median runtime over {RUNS} runs: {median_ms:.3f} ms")

    if update_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps({"benchmark": "verify_distribution_consistency.main", "median_ms": median_ms}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline written to {BASELINE_PATH}")
        return 0

    if not BASELINE_PATH.exists():
        print(f"no baseline at {BASELINE_PATH}; run with --update-baseline to create one", file=sys.stderr)
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_ms = float(baseline["median_ms"])
    allowed_ms = baseline_ms * (1 + threshold_pct / 100.0)
    # Never punish a benchmark for being faster than a near-zero baseline;
    # give it at least a 5ms floor so CI noise doesn't cause false failures.
    allowed_ms = max(allowed_ms, baseline_ms + 5.0)

    print(f"baseline: {baseline_ms:.3f} ms, allowed up to: {allowed_ms:.3f} ms (+{threshold_pct:.0f}%)")

    if median_ms > allowed_ms:
        print(
            f"REGRESSION: {median_ms:.3f} ms exceeds allowed {allowed_ms:.3f} ms "
            f"(baseline {baseline_ms:.3f} ms + {threshold_pct:.0f}%)",
            file=sys.stderr,
        )
        return 1

    print("OK: within regression threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

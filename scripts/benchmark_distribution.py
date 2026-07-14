#!/usr/bin/env python3
"""Compare deterministic distribution metrics with a versioned baseline."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

try:
    from .verify_distribution_consistency import run_audit
except ImportError:  # direct script execution
    from verify_distribution_consistency import run_audit

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_FILES = (
    "install.sh",
    "install.ps1",
    "npm/simplicio/install.js",
    "npm/simplicio-installer/install.js",
    "npm/simplicio-unscoped/install.js",
    "pypi/simplicio/simplicio/__main__.py",
)


@dataclass(frozen=True)
class MetricResult:
    name: str
    measured: float
    maximum: float
    passed: bool


def payload_bytes(root: Path = ROOT) -> int:
    return sum((root / relative).stat().st_size for relative in PAYLOAD_FILES)


def audit_median_ms(root: Path = ROOT, repetitions: int = 5) -> float:
    samples: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        findings = run_audit(root)
        if any(item.level in {"ERROR", "WARN"} for item in findings):
            raise RuntimeError("distribution audit is not clean")
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples)


def evaluate(measured: Mapping[str, float], baseline: Mapping[str, dict], override: float | None = None) -> list[MetricResult]:
    results: list[MetricResult] = []
    for name, value in measured.items():
        contract = baseline[name]
        tolerance = float(override if override is not None else contract["max_regression_percent"])
        maximum = float(contract["baseline"]) * (1 + tolerance / 100)
        results.append(MetricResult(name, float(value), maximum, float(value) <= maximum))
    return results


def write_junit(path: Path, results: Sequence[MetricResult]) -> None:
    suite = ET.Element(
        "testsuite",
        name="distribution-benchmark",
        tests=str(len(results)),
        failures=str(sum(not result.passed for result in results)),
    )
    for result in results:
        case = ET.SubElement(suite, "testcase", name=result.name)
        detail = f"measured={result.measured:.3f}; maximum={result.maximum:.3f}"
        if result.passed:
            ET.SubElement(case, "system-out").text = detail
        else:
            ET.SubElement(case, "failure", message="regression budget exceeded").text = detail
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--baseline", type=Path, default=ROOT / "benchmarks/baseline.json")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    contract = json.loads(args.baseline.read_text(encoding="utf-8"))["metrics"]
    measured = {
        "installer_payload_bytes": payload_bytes(args.root),
        "audit_median_ms": audit_median_ms(args.root, args.repetitions),
    }
    override_value = os.environ.get("SIMPLICIO_BENCHMARK_TOLERANCE_PERCENT")
    results = evaluate(measured, contract, float(override_value) if override_value else None)
    payload = [result.__dict__ for result in results]
    print(json.dumps(payload, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.junit:
        write_junit(args.junit, results)
    return int(any(not result.passed for result in results))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Repeat a test command; any inconsistent or failed attempt blocks the gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Attempt:
    number: int
    returncode: int
    duration_seconds: float
    output: str


def run_attempts(command: Sequence[str], attempts: int) -> list[Attempt]:
    results: list[Attempt] = []
    for number in range(1, attempts + 1):
        started = time.perf_counter()
        process = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        results.append(Attempt(number, process.returncode, time.perf_counter() - started, process.stdout))
    return results


def classification(results: Sequence[Attempt]) -> str:
    codes = {result.returncode for result in results}
    if codes == {0}:
        return "PASS"
    if 0 in codes:
        return "FLAKY"
    return "FAIL"


def write_junit(path: Path, results: Sequence[Attempt], verdict: str) -> None:
    suite = ET.Element("testsuite", name="flaky-check", tests=str(len(results)), failures=str(verdict != "PASS"))
    for result in results:
        case = ET.SubElement(
            suite,
            "testcase",
            name=f"attempt-{result.number}",
            time=f"{result.duration_seconds:.6f}",
        )
        ET.SubElement(case, "system-out").text = result.output
        if result.returncode:
            ET.SubElement(case, "failure", message=f"exit {result.returncode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.attempts < 2 or not command:
        parser.error("provide a command and at least two attempts")
    results = run_attempts(command, args.attempts)
    verdict = classification(results)
    write_junit(args.junit, results, verdict)
    for result in results:
        print(f"attempt={result.number} exit={result.returncode} duration={result.duration_seconds:.3f}s")
    print(f"flaky-check: {verdict}")
    return int(verdict != "PASS")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run unittest discovery and emit a dependency-free JUnit report."""

from __future__ import annotations

import argparse
import sys
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes: list[unittest.case.TestCase] = []

    def addSuccess(self, test):  # noqa: N802 - unittest API
        self.successes.append(test)
        super().addSuccess(test)


def write_junit(path: Path, result: RecordingResult, duration: float) -> None:
    suite = ET.Element(
        "testsuite",
        name="python-unit",
        tests=str(result.testsRun),
        failures=str(len(result.failures)),
        errors=str(len(result.errors)),
        skipped=str(len(result.skipped)),
        time=f"{duration:.6f}",
    )
    outcomes = {str(test): ("failure", detail) for test, detail in result.failures}
    outcomes.update({str(test): ("error", detail) for test, detail in result.errors})
    skipped = {str(test): reason for test, reason in result.skipped}
    all_tests = list(result.successes) + [test for test, _ in result.failures + result.errors + result.skipped]
    for test in all_tests:
        case = ET.SubElement(suite, "testcase", name=str(test))
        if str(test) in outcomes:
            kind, detail = outcomes[str(test)]
            ET.SubElement(case, kind, message=kind).text = detail
        elif str(test) in skipped:
            ET.SubElement(case, "skipped", message=skipped[str(test)])
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-directory", default="tests")
    parser.add_argument("--pattern", default="test_*.py")
    parser.add_argument("--junit", type=Path, required=True)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(args.start_directory, pattern=args.pattern)
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    write_junit(args.junit, result, time.perf_counter() - started)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    sys.exit(main())

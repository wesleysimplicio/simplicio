#!/usr/bin/env python3
"""Reject ignored tests unless an issue-linked justification is adjacent."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
ISSUE_URL = "https://github.com/wesleysimplicio/simplicio/issues/"
SKIP_PATTERNS = (
    re.compile(r"@(?:unittest\.)?skip(?:If|Unless)?\b"),
    re.compile(r"pytest\.skip\s*\("),
    re.compile(r"pytest\.mark\.skip"),
    re.compile(r"\b(?:test|it|describe)\.skip\s*\("),
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    text: str


def test_files(root: Path) -> Iterable[Path]:
    tests = root / "tests"
    if not tests.exists():
        return []
    return (
        path
        for path in tests.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".js", ".cjs", ".mjs", ".ts"}
    )


def find_violations(root: Path = ROOT) -> list[Violation]:
    violations: list[Violation] = []
    for path in test_files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not any(pattern.search(line) for pattern in SKIP_PATTERNS):
                continue
            context = "\n".join(lines[max(0, index - 2) : index + 1])
            if "JUSTIFICATION:" not in context or ISSUE_URL not in context:
                violations.append(Violation(path.relative_to(root).as_posix(), index + 1, line.strip()))
    return violations


def write_junit(path: Path, violations: Sequence[Violation]) -> None:
    suite = ET.Element("testsuite", name="skip-policy", tests="1", failures=str(bool(violations)))
    case = ET.SubElement(suite, "testcase", name="all-skips-have-issue-linked-justification")
    if violations:
        detail = "\n".join(f"{item.path}:{item.line}: {item.text}" for item in violations)
        ET.SubElement(case, "failure", message="unjustified ignored tests").text = detail
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--junit", type=Path)
    args = parser.parse_args(argv)
    violations = find_violations(args.root)
    if args.junit:
        write_junit(args.junit, violations)
    if violations:
        for item in violations:
            print(f"[ERROR] {item.path}:{item.line}: ignored test lacks JUSTIFICATION + issue URL")
        return 1
    print("skip-policy: PASS (no unjustified ignored tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

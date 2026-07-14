#!/usr/bin/env python3
"""Reject ignored tests unless an issue-linked justification is adjacent."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
ISSUE_URL = "https://github.com/wesleysimplicio/simplicio/issues/"
ISSUE_RE = re.compile(re.escape(ISSUE_URL) + r"\d+\b")
OWNER_RE = re.compile(r"\bOWNER:\s*([^\s#]+)")
REMOVE_BY_RE = re.compile(r"\bREMOVE-BY:\s*(\d{4}-\d{2}-\d{2})\b")
SKIP_PATTERNS = (
    re.compile(r"@(?:unittest\.)?skip(?:If|Unless)?\b"),
    re.compile(r"pytest\.skip\s*\("),
    re.compile(r"pytest\.mark\.skip"),
    re.compile(r"\b(?:test|it|describe)\.skip\s*\("),
    re.compile(r"\bself\.skipTest\s*\("),
    re.compile(r"\braise\s+(?:unittest\.)?SkipTest\b"),
    re.compile(r"\bskip\s*:\s*true\b"),
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    text: str
    reason: str


def test_files(root: Path) -> Iterable[Path]:
    tests = root / "tests"
    if not tests.exists():
        return []
    return (
        path
        for path in tests.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".js", ".cjs", ".mjs", ".ts"}
    )


def justification_error(context: str, today: date) -> str | None:
    if "JUSTIFICATION:" not in context:
        return "missing JUSTIFICATION"
    if not ISSUE_RE.search(context):
        return "missing repository issue URL"
    if not OWNER_RE.search(context):
        return "missing OWNER"
    remove_by_match = REMOVE_BY_RE.search(context)
    if not remove_by_match:
        return "missing or invalid REMOVE-BY"
    remove_by = date.fromisoformat(remove_by_match.group(1))
    if remove_by < today:
        return "REMOVE-BY is expired"
    if remove_by > today + timedelta(days=30):
        return "REMOVE-BY exceeds 30 days"
    return None


def find_violations(root: Path = ROOT, *, today: date | None = None) -> list[Violation]:
    today = today or date.today()
    violations: list[Violation] = []
    for path in test_files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not any(pattern.search(line) for pattern in SKIP_PATTERNS):
                continue
            context = "\n".join(lines[max(0, index - 4) : index + 1])
            reason = justification_error(context, today)
            if reason:
                violations.append(Violation(path.relative_to(root).as_posix(), index + 1, line.strip(), reason))
    return violations


def write_junit(path: Path, violations: Sequence[Violation]) -> None:
    suite = ET.Element("testsuite", name="skip-policy", tests="1", failures=str(bool(violations)))
    case = ET.SubElement(suite, "testcase", name="all-skips-have-issue-linked-justification")
    if violations:
        detail = "\n".join(f"{item.path}:{item.line}: {item.reason}: {item.text}" for item in violations)
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
            print(f"[ERROR] {item.path}:{item.line}: ignored test exception invalid: {item.reason}")
        return 1
    print("skip-policy: PASS (no unjustified ignored tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

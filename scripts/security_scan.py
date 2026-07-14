#!/usr/bin/env python3
"""Small deterministic secret scanner for tracked text distribution files."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".js", ".json", ".md", ".ps1", ".py", ".rb", ".sh", ".toml", ".txt", ".yml", ".yaml"}
PATTERNS = (
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{30,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("private-key", re.compile("-" * 5 + r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY")),
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    kind: str


def tracked_text_files(root: Path = ROOT) -> Iterable[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    for raw in output.split(b"\0"):
        if not raw:
            continue
        relative = Path(raw.decode("utf-8"))
        if relative.parts and relative.parts[0] in {".simplicio", "artifacts"}:
            continue
        path = root / relative
        if path.suffix.lower() in TEXT_SUFFIXES and path.is_file():
            yield path


def scan(root: Path = ROOT) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in tracked_text_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for kind, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(SecretFinding(path.relative_to(root).as_posix(), number, kind))
        if path.suffix.lower() == ".py":
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    findings.append(SecretFinding(path.relative_to(root).as_posix(), node.lineno, "dynamic-code-execution"))
                shell_enabled = any(
                    keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                    for keyword in node.keywords
                )
                if shell_enabled and node.args and not isinstance(node.args[0], ast.Constant):
                    findings.append(SecretFinding(path.relative_to(root).as_posix(), node.lineno, "dynamic-shell-command"))
    return findings


def write_junit(path: Path, findings: Sequence[SecretFinding]) -> None:
    suite = ET.Element("testsuite", name="secret-scan", tests="1", failures=str(bool(findings)))
    case = ET.SubElement(suite, "testcase", name="tracked-text-has-no-high-confidence-secrets")
    if findings:
        detail = "\n".join(f"{item.path}:{item.line}: {item.kind}" for item in findings)
        ET.SubElement(case, "failure", message="potential secrets found").text = detail
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--junit", type=Path)
    args = parser.parse_args(argv)
    findings = scan(args.root)
    if args.junit:
        write_junit(args.junit, findings)
    for finding in findings:
        print(f"[ERROR] {finding.path}:{finding.line}: {finding.kind}")
    if not findings:
        print("secret-scan: PASS")
    return int(bool(findings))


if __name__ == "__main__":
    sys.exit(main())

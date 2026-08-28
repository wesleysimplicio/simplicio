#!/usr/bin/env python3
"""Fail-closed source-tree policy for the public repository."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


FORBIDDEN_PARTS = {".simplicio", "target", "node_modules", "dist"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".gguf", ".exe", ".log"}
FORBIDDEN_NAMES = {"simplicio", "simplicio-linux-x64", "simplicio-windows-x64"}
SECRET_RE = re.compile(
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}"
)
PRIVATE_PATH_RE = re.compile(rb"(?:/home/[^/\s]+|/Users/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+)")


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def path_findings(root: Path, paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if parts & FORBIDDEN_PARTS:
            findings.append(f"generated/build path is tracked: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name in FORBIDDEN_NAMES:
            findings.append(f"generated/binary file is tracked: {relative}")
        try:
            payload = path.read_bytes()
        except OSError as exc:
            findings.append(f"could not read tracked file {relative}: {exc}")
            continue
        if SECRET_RE.search(payload):
            findings.append(f"secret-like material is tracked: {relative}")
        if relative.parts[0] not in {"docs", "README.md", "READMEs", "tests", "plugin"} and relative.name != "MCP-CONNECT.md" and PRIVATE_PATH_RE.search(payload):
            findings.append(f"personal absolute path is tracked outside docs: {relative}")
    return findings


def audit(root: Path) -> list[str]:
    root = root.resolve()
    return path_findings(root, tracked_files(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    findings = audit(args.root)
    if findings:
        for finding in findings:
            print(f"ERROR: {finding}")
        return 1
    print("repository policy: clean tracked source tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Promote a fast-path route when the measured git diff exceeds safe bounds."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "simplicio.diff-escalation/v1"
DEFAULT_MAX_FILES = 2
DEFAULT_MAX_LINES = 80
SENSITIVE_MARKERS = (
    "schema",
    "migration",
    "contract",
    "pyproject.toml",
    "package.json",
    "cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "lock",
)


def _norm(value: str) -> str:
    return value.replace("\\", "/").strip().lstrip("./").casefold()


def _sensitive(path: str) -> bool:
    normalized = _norm(path)
    return any(marker in normalized for marker in SENSITIVE_MARKERS)


def _path_from_numstat(path: str) -> str:
    path = path.strip()
    if "{" in path and " => " in path and "}" in path:
        prefix, body = path.split("{", 1)
        old, new = body.split("}", 1)[0].split(" => ", 1)
        return (prefix + new + path.split("}", 1)[1]).strip()
    if " => " in path:
        return path.rsplit(" => ", 1)[1].strip()
    return path


def parse_numstat(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added_raw, deleted_raw, path = parts
        try:
            added = 0 if added_raw == "-" else max(0, int(added_raw))
            deleted = 0 if deleted_raw == "-" else max(0, int(deleted_raw))
        except ValueError:
            continue
        rows.append(
            {
                "path": _path_from_numstat(path),
                "added": added,
                "deleted": deleted,
            }
        )
    return rows


def _git(root: Path, args: Sequence[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("git unavailable: %s" % exc) from exc
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "git failed").strip())
    return completed.stdout


def _status_paths(text: str) -> tuple[list[str], list[str]]:
    changed: set[str] = set()
    new_files: set[str] = set()
    for line in text.splitlines():
        if len(line) < 3:
            continue
        status = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        path = path.strip('"')
        if not path:
            continue
        changed.add(path)
        if status == "??" or "A" in status:
            new_files.add(path)
    return sorted(changed), sorted(new_files)


def read_git_snapshot(root: str | Path, baseline: str = "HEAD") -> dict[str, Any]:
    root_path = Path(root)
    status_text = _git(root_path, ["status", "--porcelain=v1", "--untracked-files=all"])
    numstat_text = _git(root_path, ["diff", "--numstat", baseline, "--"])
    numstat = parse_numstat(numstat_text)
    status_paths, new_files = _status_paths(status_text)
    measured_paths = set(status_paths)
    measured_paths.update(row["path"] for row in numstat)
    changed_files = sorted(measured_paths)
    added_lines = sum(row["added"] for row in numstat)
    deleted_lines = sum(row["deleted"] for row in numstat)
    sensitive_files = [path for path in changed_files if _sensitive(path)]
    return {
        "changed_files": changed_files,
        "added_lines": added_lines,
        "deleted_lines": deleted_lines,
        "new_files": new_files,
        "sensitive_files": sensitive_files,
        "numstat": numstat,
        "status": status_text.splitlines(),
        "baseline": baseline,
    }


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def evaluate(
    mode: str,
    changed_files: Sequence[str],
    added_lines: int,
    deleted_lines: int,
    new_files: Sequence[str],
    sensitive_files: Sequence[str],
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> dict[str, Any]:
    files = sorted(set(str(path) for path in changed_files))
    new = sorted(set(str(path) for path in new_files))
    sensitive = sorted(set(str(path) for path in sensitive_files))
    total_lines = max(0, int(added_lines)) + max(0, int(deleted_lines))
    measurements = {
        "changed_files": files,
        "changed_file_count": len(files),
        "added_lines": max(0, int(added_lines)),
        "deleted_lines": max(0, int(deleted_lines)),
        "total_lines": total_lines,
        "new_files": new,
        "sensitive_files": sensitive,
        "max_files": max_files,
        "max_lines": max_lines,
    }
    if mode == "converge":
        return {
            "schema": SCHEMA,
            "measured": True,
            "mode": "converge",
            "promoted": False,
            "monotonic": True,
            "reason": "already converge; no demotion",
            "fingerprint": "",
            "violations": [],
            "measurements": measurements,
        }

    violations: list[str] = []
    if len(files) > max_files:
        violations.append("diff %d files > %d" % (len(files), max_files))
    if total_lines > max_lines:
        violations.append("diff %d lines > %d" % (total_lines, max_lines))
    if new:
        violations.append("new file: %s" % new[0])
    if sensitive:
        violations.append("sensitive surface: %s" % sensitive[0])
    promoted = bool(violations)
    reason = "promoted: " + "; ".join(violations) if promoted else (
        "within budget: diff %d files, %d lines" % (len(files), total_lines)
    )
    stable = {
        "mode": "fast-path",
        "violations": violations,
        "measurements": measurements,
    }
    return {
        "schema": SCHEMA,
        "measured": True,
        "mode": "converge" if promoted else "fast-path",
        "promoted": promoted,
        "monotonic": True,
        "reason": reason,
        "fingerprint": _fingerprint(stable) if promoted else "",
        "violations": violations,
        "measurements": measurements,
    }


def record_anchor(anchor_path: str | Path, result: Mapping[str, Any]) -> bool:
    path = Path(anchor_path)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        route = data.get("route_mode")
        route_data = dict(route) if isinstance(route, Mapping) else {}
        route_data.update(
            {
                "mode": result["mode"],
                "justification": result["reason"],
                "diff_escalation": dict(result),
            }
        )
        data["route_mode"] = route_data
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return True
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        return False


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def record_journal(
    journal_path: str | Path,
    result: Mapping[str, Any],
    iteration: int,
) -> bool:
    if not result.get("promoted"):
        return False
    path = Path(journal_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "iteration": int(iteration),
        "action": "promote fast-path to converge",
        "hypothesis": "real diff exceeded the fast-path budget",
        "gate": "pass",
        "fingerprint": result.get("fingerprint", ""),
        "note": result.get("reason", ""),
        "source": "diff_escalation",
        "route_mode": result.get("mode"),
        "diff": result.get("measurements", {}),
        "ts": _now(),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--mode", choices=("fast-path", "converge"), default="fast-path")
    parser.add_argument("--baseline", default="HEAD")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--anchor", default=".simplicio/orchestrator/loop/anchor.json")
    parser.add_argument("--journal", default=".simplicio/orchestrator/loop/journal.jsonl")
    parser.add_argument("--iteration", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        snapshot = read_git_snapshot(args.root, args.baseline)
        result = evaluate(
            args.mode,
            snapshot["changed_files"],
            snapshot["added_lines"],
            snapshot["deleted_lines"],
            snapshot["new_files"],
            snapshot["sensitive_files"],
            max_files=args.max_files,
            max_lines=args.max_lines,
        )
    except RuntimeError as exc:
        result = {
            "schema": SCHEMA,
            "measured": False,
            "mode": "converge",
            "promoted": True,
            "monotonic": True,
            "reason": "promotion required: %s" % exc,
            "fingerprint": _fingerprint({"error": str(exc)}),
            "violations": ["git measurement unavailable"],
            "measurements": {},
        }
    result["anchor_updated"] = record_anchor(Path(args.root) / args.anchor, result)
    result["journal_recorded"] = record_journal(Path(args.root) / args.journal, result, args.iteration)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

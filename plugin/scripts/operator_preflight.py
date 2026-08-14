#!/usr/bin/env python3
"""TTL-gated operator preflight and per-run version pinning."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


SCHEMA = "simplicio.operator-preflight/v1"
PIN_SCHEMA = "simplicio.operator-pin/v1"
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_BINARIES = ("simplicio-mapper", "simplicio-dev-cli")


def _timestamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def installed_versions(binaries: tuple[str, ...] = DEFAULT_BINARIES) -> dict[str, str]:
    versions: dict[str, str] = {}
    for binary in binaries:
        executable = shutil.which(binary)
        if not executable:
            versions[binary] = "missing"
            continue
        try:
            result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5)
            text = (result.stdout or result.stderr).strip().splitlines()
            versions[binary] = text[0][:200] if text else "available"
        except (OSError, subprocess.SubprocessError):
            versions[binary] = "available"
    return versions


def evaluate(
    state: Mapping[str, Any],
    *,
    now: float,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    versions: Mapping[str, str],
    run_pin: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    missing = sorted(name for name, version in versions.items() if version == "missing")
    checked_at = str(state.get("checked_at", ""))
    age = None
    if checked_at:
        try:
            age = max(0.0, now - _epoch(checked_at))
        except (TypeError, ValueError, OverflowError):
            age = None
    cached = not missing and age is not None and age <= ttl_seconds
    pin_versions = dict((run_pin or {}).get("versions", {}))
    mismatch = bool(pin_versions) and pin_versions != dict(versions)
    if missing:
        status, reason, refresh = "blocked", "missing_operator", False
    elif cached:
        status, reason, refresh = "cached", "within_ttl", False
    else:
        status, reason, refresh = "refresh_required", "missing_or_expired_check", True
    return {
        "schema": SCHEMA,
        "status": status,
        "reason": reason,
        "refresh_required": refresh,
        "network_upgrade_allowed": refresh,
        "missing": missing,
        "checked_at": checked_at or None,
        "age_seconds": age,
        "ttl_seconds": ttl_seconds,
        "versions": dict(versions),
        "run_version_mismatch": mismatch,
        "warning": "operator version changed during run; do not upgrade silently" if mismatch else "",
    }


def preflight(
    *,
    state_path: str | Path,
    run_pin_path: str | Path,
    run_id: str,
    now: float | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    record: bool = False,
    version_provider: Callable[[], dict[str, str]] = installed_versions,
) -> dict[str, Any]:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    current = time.time() if now is None else float(now)
    state_file, pin_file = Path(state_path), Path(run_pin_path)
    versions = version_provider()
    state, pin = _read(state_file), _read(pin_file)
    receipt = evaluate(state, now=current, ttl_seconds=ttl_seconds, versions=versions, run_pin=pin)
    receipt["run_id"] = run_id
    if record and receipt["status"] != "blocked":
        checked = _timestamp(current)
        state_payload = {"schema": SCHEMA, "checked_at": checked, "versions": versions}
        pin_payload = {"schema": PIN_SCHEMA, "run_id": run_id, "checked_at": checked, "versions": versions}
        _write(state_file, state_payload)
        _write(pin_file, pin_payload)
        receipt["checked_at"] = checked
        receipt["recorded"] = True
    else:
        receipt["recorded"] = False
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, default=Path.home() / ".simplicio" / "operator-check.json")
    parser.add_argument("--run-state", type=Path, default=Path(".simplicio/orchestrator/loop/operator-pin.json"))
    parser.add_argument("--run-id", default="unbound")
    parser.add_argument("--ttl-seconds", type=int, default=DEFAULT_TTL_SECONDS)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args(argv)
    receipt = preflight(state_path=args.state, run_pin_path=args.run_state, run_id=args.run_id,
                        ttl_seconds=args.ttl_seconds, record=args.record)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())

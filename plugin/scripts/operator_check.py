#!/usr/bin/env python3
"""TTL-gated operator preflight (issue #526 Etapa 6).

The old preflight contract ran `pip install -qU simplicio-cli` on every single armada — a
network round-trip the operator almost never needed, and one that could silently swap the
operator version out from under a run already in progress. This worker replaces "always
upgrade" with two independent, deterministic rules:

1. **TTL-gated upgrade.** An upgrade attempt is only warranted when the last successful check
   is older than ``ttl_days`` (default 7, configurable) OR a required binary is missing from
   PATH. The last-checked timestamp lives in ``~/.simplicio/operator-check.json`` (override the
   home directory with ``SIMPLICIO_HOME``, matching ``scripts/install_lib.py``). Within the TTL,
   `maybe_upgrade()` never invokes the upgrade command — no network call, no subprocess.
2. **Per-run version pin.** The operator version actually resolved at arming time is written
   once into the run's `.simplicio/orchestrator/loop/scratchpad.md` frontmatter
   (`operator_versions: {"simplicio-mapper": "0.0.0-test", ...}`) and never rewritten mid-run.
   A later iteration that observes a different version is a warning
   (`check_pin_mismatch()`), never a silent upgrade — the pin is deliberately one-way for the
   lifetime of a run.

Usage::

    python3 scripts/operator_check.py should-upgrade --json
    python3 scripts/operator_check.py record --versions '{"simplicio-mapper":"0.0.0-test"}'
    python3 scripts/operator_check.py pin --scratchpad <path> --versions '{"simplicio-mapper":"0.0.0-test"}'
    python3 scripts/operator_check.py check-pin --scratchpad <path> --versions '{"simplicio-mapper":"0.0.1-test"}'
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "simplicio.operator-check/v1"
# Explicit --ttl-days always wins. When omitted: always-latest (default) → 0;
# SIMPLICIO_OPERATOR_ALWAYS_LATEST=0 restores the classic 7-day window.
DEFAULT_TTL_DAYS = 0.0
LEGACY_TTL_DAYS = 7.0
DEFAULT_BINARIES = ("simplicio-mapper", "simplicio-dev-cli")
DEFAULT_PACKAGE = "simplicio-cli"
# Unpinned names: with `pip install -U` these always resolve to the latest PyPI release.
DEFAULT_PACKAGES = (
    "simplicio-loop",
    "simplicio-cli",
    "simplicio-mapper",
    "simplicio-fast",
)
ALWAYS_LATEST_ENV = "SIMPLICIO_OPERATOR_ALWAYS_LATEST"
_FALSE = frozenset({"0", "false", "no", "off", "disabled", "legacy"})

# These values are deliberately synthetic. Keeping self-tests independent from published
# operator trains prevents copied historical versions from looking like current composition
# claims (distribution issue #322).
SELFTEST_OPERATOR_VERSION = "0.0.0-test"
SELFTEST_OPERATOR_VERSION_MISMATCH = "0.0.1-test"

# Same override convention as scripts/install_lib.py: an explicit override keeps isolated
# tests (and portable profiles) honest; normal runs use the platform's real user home.
HOME = (os.environ.get("SIMPLICIO_HOME") or os.environ.get("HOME")
        or os.path.expanduser("~"))


def always_latest_enabled() -> bool:
    """When true (default), every preflight may run ``pip install -U`` for operators."""
    raw = str(os.environ.get(ALWAYS_LATEST_ENV, "1")).strip().lower()
    return raw not in _FALSE


def resolve_ttl_days(ttl_days: float | None = None) -> float:
    """Return effective TTL.

    - Explicit ``ttl_days`` (CLI/tests) always wins — including 7 for legacy tests.
    - Otherwise always-latest (default) → 0; opt-out → LEGACY_TTL_DAYS (7).
    """
    if ttl_days is not None:
        return float(ttl_days)
    if always_latest_enabled():
        return 0.0
    return float(LEGACY_TTL_DAYS)


def default_cache_path() -> Path:
    return Path(HOME) / ".simplicio" / "operator-check.json"


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def read_cache(path: str | Path) -> dict[str, Any]:
    """Return the persisted cache, or {} if missing/corrupt (fail-open on the READ side —
    a broken cache degrades to 'check again', never to a crash)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_cache(path: str | Path, data: Mapping[str, Any]) -> bool:
    cache_path = Path(path)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        tmp.write_text(json.dumps(dict(data), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        os.replace(tmp, cache_path)
        return True
    except OSError:
        return False


def missing_binaries(binaries: Sequence[str]) -> list[str]:
    return [name for name in binaries if shutil.which(name) is None]


def should_upgrade(cache_path: str | Path, *, ttl_days: float | None = None,
                   binaries: Sequence[str] = DEFAULT_BINARIES,
                   now: float | None = None) -> dict[str, Any]:
    """Pure decision: does THIS preflight warrant an upgrade attempt?

    Never touches the network itself — callers gate the actual upgrade command on the
    ``should_upgrade`` field so a fresh cache never triggers a subprocess.

    ``ttl_days <= 0`` (default under always-latest) means always upgrade.
    """
    now = _now() if now is None else now
    effective_ttl = resolve_ttl_days(ttl_days)
    absent = missing_binaries(binaries)
    if absent:
        return {
            "schema": SCHEMA,
            "should_upgrade": True,
            "reason": "binary missing: %s" % ", ".join(absent),
            "missing_binaries": absent,
            "last_checked_at": None,
            "age_days": None,
            "ttl_days": effective_ttl,
            "always_latest": always_latest_enabled(),
        }
    if effective_ttl <= 0:
        return {
            "schema": SCHEMA,
            "should_upgrade": True,
            "reason": "always-latest (ttl_days<=0): pull latest PyPI packages",
            "missing_binaries": [],
            "last_checked_at": None,
            "age_days": None,
            "ttl_days": effective_ttl,
            "always_latest": True,
        }
    cache = read_cache(cache_path)
    last_checked_at = cache.get("last_checked_at")
    last_checked_ts = cache.get("last_checked_ts")
    if not isinstance(last_checked_ts, (int, float)):
        return {
            "schema": SCHEMA,
            "should_upgrade": True,
            "reason": "no prior check recorded",
            "missing_binaries": [],
            "last_checked_at": last_checked_at if isinstance(last_checked_at, str) else None,
            "age_days": None,
            "ttl_days": effective_ttl,
            "always_latest": always_latest_enabled(),
        }
    age_days = max(0.0, (now - float(last_checked_ts)) / 86400.0)
    expired = age_days > effective_ttl
    return {
        "schema": SCHEMA,
        "should_upgrade": expired,
        "reason": ("ttl expired (%.2fd > %sd)" % (age_days, effective_ttl)) if expired
                  else ("within TTL (%.2fd <= %sd)" % (age_days, effective_ttl)),
        "missing_binaries": [],
        "last_checked_at": last_checked_at,
        "age_days": age_days,
        "ttl_days": effective_ttl,
        "always_latest": always_latest_enabled(),
    }


def record_check(cache_path: str | Path, versions: Mapping[str, str],
                 *, now: float | None = None) -> dict[str, Any]:
    """Persist a successful probe so the NEXT preflight sees a fresh TTL window."""
    now = _now() if now is None else now
    payload = {
        "schema": SCHEMA,
        "last_checked_ts": now,
        "last_checked_at": _iso(now),
        "versions": dict(versions),
    }
    write_cache(cache_path, payload)
    return payload


def run_pip_upgrade(
    packages: Sequence[str] | str = DEFAULT_PACKAGES,
) -> subprocess.CompletedProcess[str]:
    """The one function that actually touches the network. Kept separate from
    ``should_upgrade``/`maybe_upgrade`` so tests can monkeypatch/assert-not-called on this
    single seam instead of mocking the whole subprocess module."""
    requested = [packages] if isinstance(packages, str) else list(packages)
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "-qU"] + requested,
        capture_output=True, text=True, timeout=180,
    )


def maybe_upgrade(cache_path: str | Path, *, ttl_days: float | None = None,
                  binaries: Sequence[str] = DEFAULT_BINARIES,
                  versions: Mapping[str, str] | None = None,
                  upgrade_fn=run_pip_upgrade, now: float | None = None) -> dict[str, Any]:
    """Fail-open, best-effort upgrade — but ONLY when ``should_upgrade`` says the TTL
    expired, always-latest is on, or a binary is absent. A within-TTL call is a pure
    cache read: zero subprocess, zero network, by construction."""
    decision = should_upgrade(cache_path, ttl_days=ttl_days, binaries=binaries, now=now)
    if not decision["should_upgrade"]:
        decision["upgraded"] = False
        decision["upgrade_error"] = None
        return decision
    try:
        result = upgrade_fn()
        decision["upgraded"] = getattr(result, "returncode", 1) == 0
        decision["upgrade_error"] = None if decision["upgraded"] else (
            getattr(result, "stderr", "") or "upgrade command failed")
    except (OSError, subprocess.SubprocessError) as exc:
        decision["upgraded"] = False
        decision["upgrade_error"] = str(exc)
    # Record the check regardless of upgrade success — a failed/offline upgrade still means
    # "we looked"; it must not be retried on every single iteration until the TTL window
    # rolls forward again (best-effort, offline-safe, matching the old contract's fallback).
    record_check(cache_path, versions or {}, now=now)
    return decision


# --------------------------------------------------------------------------
# Per-run version pin (scratchpad frontmatter)
# --------------------------------------------------------------------------

def _read_scratchpad(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_pinned_versions(scratchpad_path: str | Path) -> dict[str, str] | None:
    """Return the operator_versions pinned at arming time, or None if never pinned/corrupt."""
    try:
        text = _read_scratchpad(scratchpad_path)
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    for line in parts[1].splitlines():
        if not line.startswith("operator_versions:"):
            continue
        _, _, raw = line.partition(":")
        try:
            value = json.loads(raw.strip())
        except ValueError:
            return None
        return value if isinstance(value, dict) else None
    return None


def pin_versions(scratchpad_path: str | Path, versions: Mapping[str, str]) -> bool:
    """Write the operator version pin into the scratchpad frontmatter, ONCE, at arming time.

    A run that already has a pin is left untouched — pinning happens only "na armada"
    (issue #526 Etapa 6 AC2); re-pinning mid-run would defeat the whole point.
    """
    path = Path(scratchpad_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    if read_pinned_versions(path) is not None:
        return False  # already pinned this run — never overwrite
    frontmatter = parts[1]
    line = "operator_versions: %s" % json.dumps(dict(versions), ensure_ascii=False,
                                                sort_keys=True)
    if not frontmatter.endswith("\n"):
        frontmatter += "\n"
    new_frontmatter = frontmatter + line + "\n"
    new_text = "---" + new_frontmatter + "---" + parts[2]
    try:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def check_pin_mismatch(scratchpad_path: str | Path,
                       current_versions: Mapping[str, str]) -> list[str]:
    """Compare the pinned-at-arming versions against what's on PATH right now. Returns a list
    of human-readable warnings — NEVER triggers an upgrade and never blocks the run. An empty
    list means "no pin recorded" (nothing to compare) or "everything still matches"."""
    pinned = read_pinned_versions(scratchpad_path)
    if not pinned:
        return []
    warnings: list[str] = []
    for name, pinned_version in sorted(pinned.items()):
        current = current_versions.get(name)
        if current is not None and current != pinned_version:
            warnings.append(
                "operator version mismatch: %s pinned %s, now %s (no silent upgrade — "
                "the pin holds for the rest of this run)" % (name, pinned_version, current)
            )
    return warnings


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_should = sub.add_parser("should-upgrade")
    p_should.add_argument("--cache", default=None)
    p_should.add_argument(
        "--ttl-days",
        type=float,
        default=None,
        help="override TTL (default: 0 always-latest; use 7 for classic weekly gate)",
    )
    p_should.add_argument("--binary", action="append", dest="binaries", default=None)
    p_should.add_argument("--json", action="store_true")

    p_maybe = sub.add_parser("maybe-upgrade")
    p_maybe.add_argument("--cache", default=None)
    p_maybe.add_argument(
        "--ttl-days",
        type=float,
        default=None,
        help="override TTL (default: 0 always-latest; use 7 for classic weekly gate)",
    )
    p_maybe.add_argument("--binary", action="append", dest="binaries", default=None)
    p_maybe.add_argument("--package", action="append", dest="packages", default=None)
    p_maybe.add_argument("--json", action="store_true")

    p_record = sub.add_parser("record")
    p_record.add_argument("--cache", default=None)
    p_record.add_argument("--versions", default="{}")

    p_pin = sub.add_parser("pin")
    p_pin.add_argument("--scratchpad", required=True)
    p_pin.add_argument("--versions", required=True)

    p_check_pin = sub.add_parser("check-pin")
    p_check_pin.add_argument("--scratchpad", required=True)
    p_check_pin.add_argument("--versions", required=True)
    p_check_pin.add_argument("--json", action="store_true")

    sub.add_parser("selftest")

    args = parser.parse_args(argv)
    cache_path = Path(args.cache) if getattr(args, "cache", None) else default_cache_path()

    if args.cmd == "should-upgrade":
        binaries = args.binaries or list(DEFAULT_BINARIES)
        decision = should_upgrade(cache_path, ttl_days=args.ttl_days, binaries=binaries)
        if args.json:
            print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        else:
            print("should_upgrade=%s (%s)" % (decision["should_upgrade"], decision["reason"]))
        return 0

    if args.cmd == "maybe-upgrade":
        binaries = args.binaries or list(DEFAULT_BINARIES)
        decision = maybe_upgrade(
            cache_path, ttl_days=args.ttl_days, binaries=binaries,
            upgrade_fn=lambda: run_pip_upgrade(args.packages or DEFAULT_PACKAGES),
        )
        if args.json:
            print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
        else:
            print("should_upgrade=%s upgraded=%s (%s)" % (
                decision["should_upgrade"], decision["upgraded"], decision["reason"]))
        return 0

    if args.cmd == "record":
        versions = json.loads(args.versions)
        payload = record_check(cache_path, versions)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.cmd == "pin":
        versions = json.loads(args.versions)
        pinned = pin_versions(args.scratchpad, versions)
        print(json.dumps({"pinned": pinned}, ensure_ascii=False))
        return 0 if pinned or read_pinned_versions(args.scratchpad) is not None else 1

    if args.cmd == "check-pin":
        versions = json.loads(args.versions)
        warnings = check_pin_mismatch(args.scratchpad, versions)
        if args.json:
            print(json.dumps({"warnings": warnings}, ensure_ascii=False))
        else:
            for warning in warnings:
                print("WARNING: %s" % warning)
            if not warnings:
                print("operator_check: no mismatch")
        return 0

    if args.cmd == "selftest":
        return _selftest()

    return 1


def _selftest() -> int:
    import tempfile

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "operator-check.json"
        decision = should_upgrade(cache, binaries=())
        ok = ok and decision["should_upgrade"] is True
        record_check(cache, {"simplicio-mapper": SELFTEST_OPERATOR_VERSION})
        # Explicit legacy TTL: within-window must NOT upgrade (always-latest default
        # would otherwise force True; TTL tests pin the classic gate).
        decision2 = should_upgrade(cache, ttl_days=7, binaries=())
        ok = ok and decision2["should_upgrade"] is False

        scratchpad = Path(tmp) / "scratchpad.md"
        scratchpad.write_text("---\niteration: 1\n---\ngoal\n", encoding="utf-8")
        ok = ok and pin_versions(scratchpad, {"simplicio-mapper": SELFTEST_OPERATOR_VERSION})
        ok = ok and not pin_versions(scratchpad, {"simplicio-mapper": SELFTEST_OPERATOR_VERSION_MISMATCH})
        ok = ok and read_pinned_versions(scratchpad) == {"simplicio-mapper": SELFTEST_OPERATOR_VERSION}
        warnings = check_pin_mismatch(
            scratchpad, {"simplicio-mapper": SELFTEST_OPERATOR_VERSION_MISMATCH}
        )
        ok = ok and len(warnings) == 1

    print("operator_check selftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

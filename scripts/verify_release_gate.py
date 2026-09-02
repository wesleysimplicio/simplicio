#!/usr/bin/env python3
"""Fail-closed verifier for the installed Desktop release gate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "simplicio.desktop.release-gate/v1"
REQUIRED_TRACKS = ("install", "oauth", "e2e", "usage", "cost", "privacy", "release")
REQUIRED_DEPENDENCIES = ("#282", "#283", "#286", "#287", "#288", "#289", "#301", "#302", "#303")
STATUSES = ("verified", "unavailable", "blocked")
SOURCES = ("installed", "runtime")
SAFE_ID = re.compile(r"^[A-Za-z0-9#][A-Za-z0-9_.:#-]{0,127}$")
SENSITIVE_KEY = re.compile(
    r"(^|_)(path|cwd|home|argv|prompt|secret|password|credential|"
    r"authorization|api_key|access_token|refresh_token|raw_payload|raw_output)(_|$)",
    re.IGNORECASE,
)


class GateInputError(ValueError):
    """The evidence document is not safe or not version-compatible."""


def _object(value: Any, code: str = "gate_invalid") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateInputError(code)
    return value


def _text(value: Any, code: str = "gate_invalid") -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 256
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or "/" in value
        or "\\" in value
    ):
        raise GateInputError(code)
    return value


def _safe_id(value: Any) -> str:
    text = _text(value, "gate_evidence_id_invalid")
    if SAFE_ID.fullmatch(text) is None:
        raise GateInputError("gate_evidence_id_invalid")
    return text


def _reject_unsafe(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise GateInputError("gate_key_invalid")
            if key.lower() == "preview" and child is not False:
                raise GateInputError("gate_preview_forbidden")
            if key not in {"paths_redacted", "argv_redacted", "clean_home"} and SENSITIVE_KEY.search(key):
                raise GateInputError("gate_sensitive_field")
            _reject_unsafe(child)
    elif isinstance(value, list):
        for child in value:
            _reject_unsafe(child)


def _status(value: Any) -> str:
    return _text(value, "gate_status_invalid") if value in STATUSES else (_ for _ in ()).throw(
        GateInputError("gate_status_invalid")
    )


def _source(value: Any) -> str:
    return _text(value, "gate_source_invalid") if value in SOURCES else (_ for _ in ()).throw(
        GateInputError("gate_source_invalid")
    )


def _evidence_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise GateInputError("gate_evidence_invalid")
    return [_safe_id(item) for item in value]


def _common_evidence(item: Mapping[str, Any], label: str) -> tuple[str, str, list[str]]:
    status = _status(item.get("status"))
    source = _source(item.get("source"))
    evidence_ids = _evidence_ids(item.get("evidence_ids"))
    if item.get("redacted") is not True:
        raise GateInputError(f"{label}_not_redacted")
    if item.get("preview", False) is not False:
        raise GateInputError("gate_preview_forbidden")
    return status, source, evidence_ids


def _require_true(item: Mapping[str, Any], key: str, reasons: list[str]) -> None:
    if item.get(key) is not True:
        reasons.append(f"{key}=true")


def _require_value(item: Mapping[str, Any], key: str, expected: Any, reasons: list[str]) -> None:
    if item.get(key) != expected:
        reasons.append(f"{key}={expected!r}")


def _require_nonnegative_int(item: Mapping[str, Any], key: str, reasons: list[str]) -> int | None:
    value = item.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        reasons.append(f"{key}=nonnegative_integer")
        return None
    return value


def _validate_track(track: Mapping[str, Any], reasons: list[str]) -> None:
    track_id = _safe_id(track.get("id"))
    local_reasons: list[str] = []
    status, _, evidence_ids = _common_evidence(track, track_id)
    if status == "verified" and not evidence_ids:
        local_reasons.append("evidence_ids=nonempty")
    if status != "verified":
        local_reasons.append("status=verified")
        reasons.extend(f"{track_id}:{reason}" for reason in local_reasons)
        return

    requirements: dict[str, dict[str, Any]] = {
        "install": {
            "all_platforms": True,
            "native_install": True,
            "runtime_digest": True,
            "signature": True,
            "sbom": True,
            "provenance": True,
            "runtime_healthy": True,
        },
        "oauth": {
            "all_platforms": True,
            "clean_home": True,
            "google_callback": True,
            "runtime_confirmed": True,
            "host_unchanged": True,
            "logout_relogin": True,
        },
        "e2e": {
            "all_platforms": True,
            "clean_home": True,
            "scenario_matrix": True,
            "secrets_redacted": True,
        },
        "privacy": {
            "paths_redacted": True,
            "argv_redacted": True,
            "prompts_absent": True,
            "secrets_redacted": True,
        },
        "release": {
            "all_platforms": True,
            "native_install": True,
            "login_real": True,
            "runtime_digest": True,
            "runtime_healthy": True,
        },
    }.get(track_id, {})
    for key, expected in requirements.items():
        if expected is True:
            _require_true(track, key, local_reasons)
        else:
            _require_value(track, key, expected, local_reasons)

    if track_id == "usage":
        _require_value(track, "coverage", "complete", local_reasons)
        _require_value(track, "unknown_providers", 0, local_reasons)
        _require_true(track, "usage_total_known", local_reasons)
        if track.get("renderer_recomputed") is not False:
            local_reasons.append("renderer_recomputed=false")
        usage_total = _require_nonnegative_int(track, "usage_total_tokens", local_reasons)
        if usage_total == 0:
            _require_true(track, "zero_usage_proven", local_reasons)
    if track_id == "cost":
        _require_value(track, "coverage", "complete", local_reasons)
        _require_value(track, "pricing_unknown", False, local_reasons)
        _require_true(track, "cost_total_known", local_reasons)
        if track.get("renderer_recomputed") is not False:
            local_reasons.append("renderer_recomputed=false")
        cost_total = track.get("cost_total_usd")
        if not isinstance(cost_total, (int, float)) or isinstance(cost_total, bool) or cost_total < 0:
            local_reasons.append("cost_total_usd=nonnegative_number")
        elif cost_total == 0:
            _require_true(track, "zero_cost_proven", local_reasons)

    reasons.extend(f"{track_id}:{reason}" for reason in local_reasons)


def _dependency_map(value: Any, reasons: list[str]) -> dict[str, Mapping[str, Any]]:
    dependencies = _object(value, "gate_dependencies_invalid")
    if set(dependencies) != set(REQUIRED_DEPENDENCIES):
        reasons.append("dependencies=exact_required_issues")
    result: dict[str, Mapping[str, Any]] = {}
    for issue in REQUIRED_DEPENDENCIES:
        raw = dependencies.get(issue)
        if raw is None:
            reasons.append(f"{issue}:present")
            continue
        item = _object(raw, "gate_dependency_invalid")
        status, _, evidence_ids = _common_evidence(item, issue)
        result[issue] = item
        if status != "verified":
            reasons.append(f"{issue}:status=verified")
        if not evidence_ids:
            reasons.append(f"{issue}:evidence_ids=nonempty")
    return result


def verify_gate(document: Any) -> dict[str, Any]:
    """Return a redacted gate result; every unknown/failed prerequisite blocks readiness."""
    _reject_unsafe(document)
    root = _object(document)
    if root.get("schema") != SCHEMA:
        raise GateInputError("gate_schema_invalid")
    if root.get("preview") is not False or root.get("redacted") is not True:
        raise GateInputError("gate_uninstalled_or_unredacted")
    _source(root.get("source"))

    reasons: list[str] = []
    raw_tracks = root.get("tracks")
    if not isinstance(raw_tracks, list):
        raise GateInputError("gate_tracks_invalid")
    tracks: dict[str, Mapping[str, Any]] = {}
    for raw_track in raw_tracks:
        track = _object(raw_track, "gate_track_invalid")
        track_id = _safe_id(track.get("id"))
        if track_id in tracks:
            reasons.append(f"{track_id}:unique")
        tracks[track_id] = track
    if set(tracks) != set(REQUIRED_TRACKS):
        reasons.append("tracks=exact_required_set")
    for track_id in REQUIRED_TRACKS:
        track = tracks.get(track_id)
        if track is None:
            reasons.append(f"{track_id}:present")
        else:
            _validate_track(track, reasons)

    dependencies = _dependency_map(root.get("dependencies"), reasons)
    status = "ready" if not reasons else "blocked"
    return {
        "schema": SCHEMA,
        "status": status,
        "verified_tracks": [track_id for track_id in REQUIRED_TRACKS if track_id in tracks
                            and tracks[track_id].get("status") == "verified"
                            and not any(reason.startswith(f"{track_id}:") for reason in reasons)],
        "dependency_status": {
            issue: item.get("status") for issue, item in dependencies.items()
        },
        "blocking_reasons": sorted(set(reasons)),
        "redacted": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify installed Desktop release evidence.")
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.evidence.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
        result = verify_gate(document)
    except (OSError, json.JSONDecodeError, GateInputError):
        result = {
            "schema": SCHEMA,
            "status": "blocked",
            "verified_tracks": [],
            "dependency_status": {},
            "blocking_reasons": ["evidence_unreadable_or_invalid"],
            "redacted": True,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Regression tests for the installed native validation matrix (#286)."""
from __future__ import annotations

from copy import deepcopy

from verify_installed_validation_matrix import PLATFORMS, SCENARIOS, SCHEMA, verify_matrix


def valid_matrix() -> dict:
    scenarios = []
    for scenario_id in SCENARIOS:
        record = {
            "id": scenario_id,
            "status": "verified",
            "source": "installed",
            "redacted": True,
            "evidence_id": f"evidence-{scenario_id}",
        }
        if scenario_id == "google_login":
            record["runtime_confirmed"] = True
        if scenario_id == "usage_absent":
            record.update(reported_state="unknown", not_zero=True)
        if scenario_id == "handshake_stale":
            record.update(reported_state="stale", connected=False)
        scenarios.append(record)
    return {
        "schema": SCHEMA,
        "installed_e2e": True,
        "preview": False,
        "source": "installed",
        "clean_home": True,
        "runtime": {"state": "healthy", "fresh_snapshot": True},
        "scenarios": scenarios,
        "platform_matrix": [{"id": platform, "status": "verified", "redacted": True} for platform in PLATFORMS],
    }


def test_complete_installed_matrix_is_ready() -> None:
    report = verify_matrix(valid_matrix())
    assert report["ready"] is True
    assert report["required_scenarios"] == len(SCENARIOS)


def test_missing_usage_cannot_be_reported_as_zero() -> None:
    document = valid_matrix()
    document["scenarios"][SCENARIOS.index("usage_absent")]["reported_state"] = "zero"
    document["scenarios"][SCENARIOS.index("usage_absent")]["not_zero"] = False
    report = verify_matrix(document)
    assert report["ready"] is False
    assert any(item["code"] == "usage_zero_inference" for item in report["errors"])


def test_stale_handshake_and_preview_are_not_connected_passes() -> None:
    document = valid_matrix()
    stale = document["scenarios"][SCENARIOS.index("handshake_stale")]
    stale["reported_state"] = "connected"
    stale["connected"] = True
    document["preview"] = True
    report = verify_matrix(document)
    codes = {item["code"] for item in report["errors"]}
    assert {"handshake_state_confused", "installed_source_required"} <= codes


def test_sensitive_receipts_and_unavailable_platforms_block() -> None:
    document = deepcopy(valid_matrix())
    document["runtime"]["home_path"] = "/Users/test"
    document["platform_matrix"][0] = {
        "id": PLATFORMS[0],
        "status": "unavailable",
        "reason_code": "host_unavailable",
    }
    report = verify_matrix(document)
    assert report["ready"] is False
    assert any(item["code"] == "personal_path" for item in report["errors"])
    assert PLATFORMS[0] in report["unavailable_platforms"]

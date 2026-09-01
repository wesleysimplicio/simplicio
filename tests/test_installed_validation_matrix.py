from __future__ import annotations

from scripts.verify_installed_validation_matrix import PLATFORMS, SCENARIOS, SCHEMA, verify_matrix


def valid_matrix() -> dict:
    return {
        "schema": SCHEMA,
        "installed_e2e": True,
        "preview": False,
        "source": "installed",
        "clean_home": True,
        "runtime": {"state": "healthy", "fresh_snapshot": True},
        "scenarios": [
            {
                "id": item,
                "status": "verified",
                "source": "installed",
                "redacted": True,
                "evidence_id": item,
                **({"runtime_confirmed": True} if item == "google_login" else {}),
                **({"reported_state": "unknown", "not_zero": True} if item == "usage_absent" else {}),
                **({"reported_state": "stale", "connected": False} if item == "handshake_stale" else {}),
            }
            for item in SCENARIOS
        ],
        "platform_matrix": [
            {"id": platform, "status": "verified", "redacted": True}
            for platform in PLATFORMS
        ],
    }


def test_complete_matrix_is_ready() -> None:
    report = verify_matrix(valid_matrix())
    assert report["ready"] is True
    assert len(report["verified_scenarios"]) == len(SCENARIOS)


def test_preview_and_missing_usage_zero_are_blocked() -> None:
    document = valid_matrix()
    document["preview"] = True
    document["scenarios"][13]["reported_state"] = "zero"
    document["scenarios"][13]["not_zero"] = False
    report = verify_matrix(document)
    codes = {item["code"] for item in report["errors"]}
    assert "installed_source_required" in codes
    assert "usage_zero_inference" in codes


def test_unavailable_platform_is_explicitly_reported_and_blocks_ready() -> None:
    document = valid_matrix()
    document["platform_matrix"][1] = {"id": PLATFORMS[1], "status": "unavailable", "reason_code": "host_unavailable"}
    report = verify_matrix(document)
    assert report["ready"] is False
    assert PLATFORMS[1] in report["unavailable_platforms"]


def test_sensitive_fields_are_rejected() -> None:
    document = valid_matrix()
    document["scenarios"][0]["prompt"] = "not allowed"
    report = verify_matrix(document)
    assert any(item["code"] == "sensitive_field" for item in report["errors"])

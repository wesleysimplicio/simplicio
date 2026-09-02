"""Regression tests for scripts/verify_clean_oauth_evidence.py (#283)."""
from __future__ import annotations

from copy import deepcopy

from verify_clean_oauth_evidence import PLATFORMS, SCHEMA, verify_evidence


def valid_evidence() -> dict:
    return {
        "schema": SCHEMA,
        "version": "3.8.41",
        "clean_home": True,
        "no_host_plugin_auto_mutation": True,
        "runtime": {
            "state": "healthy",
            "fresh_snapshot": True,
            "version": "3.8.40",
            "digest": "sha256:" + "a" * 64,
        },
        "oauth": {
            "browser_grant_completed": True,
            "callback_received": True,
            "final_access_active": True,
            "logout_completed": True,
            "relogin_completed": True,
            "logout_state": "signed_out",
            "relogin_state": "active",
            "redacted_receipt": True,
        },
        "platforms": [{
            "id": platform,
            "status": "verified",
            "native_install": True,
            "runtime_healthy": True,
            "oauth_receipt_redacted": True,
            "version_recorded": True,
            "digest_recorded": True,
        } for platform in PLATFORMS],
    }


def test_clean_oauth_matrix_is_ready() -> None:
    report = verify_evidence(valid_evidence())
    assert report["ready"] is True
    assert report["verified_platforms"] == list(PLATFORMS)


def test_clean_home_and_host_mutation_are_hard_gates() -> None:
    document = valid_evidence()
    document["clean_home"] = False
    document["no_host_plugin_auto_mutation"] = False
    report = verify_evidence(document)
    assert report["ready"] is False
    codes = {item["code"] for item in report["errors"]}
    assert {"clean_home_required", "host_mutation_policy"} <= codes


def test_oauth_secrets_and_raw_paths_are_rejected() -> None:
    document = valid_evidence()
    document["oauth"]["access_token"] = "must-not-be-recorded"
    document["runtime"]["home_path"] = "/Users/test"
    report = verify_evidence(document)
    assert report["ready"] is False
    assert {item["code"] for item in report["errors"]} >= {"sensitive_key", "personal_path"}


def test_unavailable_platform_is_not_a_pass() -> None:
    document = deepcopy(valid_evidence())
    document["platforms"][0] = {
        "id": PLATFORMS[0],
        "status": "unavailable",
        "reason_code": "host_unavailable",
    }
    report = verify_evidence(document)
    assert report["ready"] is False
    assert PLATFORMS[0] in report["unavailable_platforms"]

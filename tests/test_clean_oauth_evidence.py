from __future__ import annotations

from pathlib import Path

from scripts.verify_clean_oauth_evidence import PLATFORMS, SCHEMA, verify_evidence


def valid_document() -> dict:
    return {
        "schema": SCHEMA,
        "version": "3.8.40",
        "clean_home": True,
        "no_host_plugin_auto_mutation": True,
        "runtime": {"state": "healthy", "fresh_snapshot": True, "version": "3.8.40", "digest": "sha256:" + "a" * 64},
        "oauth": {
            "browser_grant_completed": True,
            "callback_received": True,
            "final_access_active": True,
            "logout_completed": True,
            "relogin_completed": True,
            "redacted_receipt": True,
            "logout_state": "signed_out",
            "relogin_state": "active",
        },
        "platforms": [
            {
                "id": platform,
                "status": "verified",
                "native_install": True,
                "runtime_healthy": True,
                "oauth_receipt_redacted": True,
                "version_recorded": True,
                "digest_recorded": True,
            }
            for platform in PLATFORMS
        ],
    }


def test_valid_clean_oauth_evidence_is_ready() -> None:
    report = verify_evidence(valid_document())
    assert report["ready"] is True
    assert report["verified_platforms"] == list(PLATFORMS)


def test_unavailable_platform_blocks_complete_gate() -> None:
    document = valid_document()
    document["platforms"][1] = {"id": PLATFORMS[1], "status": "unavailable", "reason_code": "host_unavailable"}
    report = verify_evidence(document)
    assert report["ready"] is False
    assert PLATFORMS[1] in report["unavailable_platforms"]


def test_sensitive_evidence_is_rejected() -> None:
    document = valid_document()
    document["oauth"]["access_token"] = "must-not-be-recorded"
    document["runtime"]["path"] = "/Users/example/.simplicio/bin/simplicio"
    report = verify_evidence(document)
    codes = {item["code"] for item in report["errors"]}
    assert "sensitive_key" in codes
    assert report["ready"] is False

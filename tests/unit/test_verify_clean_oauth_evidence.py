"""Unit tests for the clean native Google OAuth evidence verifier (#283)."""

from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json

from scripts.verify_clean_oauth_evidence import PLATFORMS, main, verify_evidence


def _digest(number: int) -> str:
    return f"sha256:{number:064x}"


def _bound_evidence(platform: str, number: int, *, redacted: bool = True) -> dict:
    evidence = {"target": platform, "digest": _digest(number)}
    if redacted:
        evidence["redacted"] = True
    return evidence


def _host_plugin_audit(platform: str) -> dict:
    content = {
        "apply_calls": 0,
        "plan_calls": 0,
        "redacted": True,
        "schema": "simplicio.host-plugin-audit/v1",
        "target": platform,
    }
    raw = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "target": platform,
        "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "redacted": True,
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }


def _valid_evidence() -> dict:
    desktop_artifacts = {
        platform: _digest(index + 1)
        for index, platform in enumerate(PLATFORMS)
    }
    runtime_artifacts = {
        platform: _digest(index + 10)
        for index, platform in enumerate(PLATFORMS)
    }

    def platform_evidence(platform: str, index: int) -> dict:
        evidence_base = 100 + index * 10
        audit_receipt = _host_plugin_audit(platform)
        receipts = {
            "install": _bound_evidence(platform, evidence_base + 2),
            "fresh_snapshot": _bound_evidence(platform, evidence_base + 3),
            "oauth": _bound_evidence(platform, evidence_base + 4),
            "logout": _bound_evidence(platform, evidence_base + 5),
        }
        screenshots = [
            _bound_evidence(platform, evidence_base + 6),
            _bound_evidence(platform, evidence_base + 7),
        ]
        covered_digests = [
            audit_receipt["digest"],
            *(receipt["digest"] for receipt in receipts.values()),
            *(screenshot["digest"] for screenshot in screenshots),
        ]
        manifest = _bound_evidence(
            platform,
            evidence_base,
            redacted=False,
        )
        manifest["covered_digests"] = covered_digests
        return {
            "id": platform,
            "status": "verified",
            "run": {
                "id": f"clean-oauth-{platform}-run-1",
                "manifest": manifest,
            },
            "desktop": {
                "version": "3.8.41",
                "digest": desktop_artifacts[platform],
            },
            "runtime": {
                "version": "3.8.40",
                "digest": runtime_artifacts[platform],
            },
            "clean_home": True,
            "install": {"completed": True, "atomic": True},
            "runtime_state": "healthy",
            "fresh_snapshot": True,
            "host_plugins": {
                "plan_calls": 0,
                "apply_calls": 0,
                "audit_receipt": audit_receipt,
            },
            "oauth": {
                "browser_grant_completed": True,
                "callback_received": True,
                "final_state": "active",
                "redacted": True,
            },
            "logout": {"completed": True, "final_state": "signed_out"},
            "receipts": receipts,
            "screenshots": screenshots,
        }

    return {
        "schema": "simplicio.clean-oauth-evidence/v2",
        "version": "3.8.41",
        "clean_home": True,
        "no_host_plugin_auto_mutation": True,
        "desktop": {
            "version": "3.8.41",
            "artifacts": desktop_artifacts,
        },
        "runtime": {
            "state": "healthy",
            "fresh_snapshot": True,
            "version": "3.8.40",
            "artifacts": runtime_artifacts,
        },
        "platforms": [
            platform_evidence(platform, index)
            for index, platform in enumerate(PLATFORMS)
        ],
    }


def error_codes(report: dict) -> set[str]:
    return {item["code"] for item in report["errors"]}


def rewrite_audit_calls(
    document: dict,
    platform_index: int,
    *,
    plan_calls: int,
    recompute_digest: bool,
) -> None:
    record = document["platforms"][platform_index]
    audit = record["host_plugins"]["audit_receipt"]
    content = json.loads(base64.b64decode(audit["content_base64"]))
    content["plan_calls"] = plan_calls
    raw = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    audit["content_base64"] = base64.b64encode(raw).decode("ascii")
    record["host_plugins"]["plan_calls"] = plan_calls
    if recompute_digest:
        previous = audit["digest"]
        audit["digest"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        covered = record["run"]["manifest"]["covered_digests"]
        covered[covered.index(previous)] = audit["digest"]


def noncanonical_base64_alias(encoded: str) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    padding = len(encoded) - len(encoded.rstrip("="))
    assert padding in (1, 2)
    index = len(encoded) - padding - 1
    value = alphabet.index(encoded[index])
    assert value & (3 if padding == 1 else 15) == 0
    return encoded[:index] + alphabet[value | 1] + encoded[index + 1 :]


def test_distinct_clean_oauth_matrix_is_ready() -> None:
    document = _valid_evidence()

    report = verify_evidence(document)

    assert report["ready"] is True
    assert report["verified_platforms"] == list(PLATFORMS)
    assert len({record["run"]["id"] for record in document["platforms"]}) == 4


def test_native_targets_accept_distinct_desktop_and_runtime_artifacts() -> None:
    document = _valid_evidence()

    report = verify_evidence(document)

    assert report["ready"] is True
    assert len(set(document["desktop"]["artifacts"].values())) == 4
    assert len(set(document["runtime"]["artifacts"].values())) == 4


def test_release_artifact_digest_reused_across_targets_is_rejected() -> None:
    document = _valid_evidence()
    reused = document["desktop"]["artifacts"][PLATFORMS[0]]
    document["desktop"]["artifacts"][PLATFORMS[1]] = reused
    document["platforms"][1]["desktop"]["digest"] = reused

    report = verify_evidence(document)

    assert report["ready"] is False
    assert "artifact_digest_reused" in error_codes(report)


def test_global_identity_cannot_cover_missing_platform_oauth() -> None:
    document = _valid_evidence()
    del document["platforms"][1]["oauth"]

    report = verify_evidence(document)

    assert report["ready"] is False
    assert PLATFORMS[1] not in report["verified_platforms"]
    assert "platform_oauth_missing" in error_codes(report)


def test_platform_identity_must_match_target_release_artifacts() -> None:
    document = _valid_evidence()
    document["platforms"][0]["desktop"]["digest"] = "sha256:" + "9" * 64
    document["platforms"][1]["runtime"]["version"] = "9.9.9"

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"desktop_identity_mismatch", "runtime_identity_mismatch"} <= error_codes(report)


def test_cross_platform_clone_is_rejected() -> None:
    document = _valid_evidence()
    clone = deepcopy(document["platforms"][0])
    clone["id"] = PLATFORMS[1]
    document["platforms"][1] = clone

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"run_identity_reused", "evidence_target_mismatch", "evidence_digest_reused"} <= error_codes(report)


def test_missing_host_plugin_audit_receipt_is_rejected() -> None:
    document = _valid_evidence()
    del document["platforms"][0]["host_plugins"]["audit_receipt"]

    report = verify_evidence(document)

    assert report["ready"] is False
    assert "host_plugin_audit_invalid" in error_codes(report)


def test_reused_host_plugin_audit_receipt_is_rejected() -> None:
    document = _valid_evidence()
    document["platforms"][1]["host_plugins"]["audit_receipt"] = deepcopy(
        document["platforms"][0]["host_plugins"]["audit_receipt"]
    )
    document["platforms"][1]["host_plugins"]["audit_receipt"]["target"] = PLATFORMS[1]

    report = verify_evidence(document)

    assert report["ready"] is False
    assert "evidence_digest_reused" in error_codes(report)


def test_nonzero_host_plugin_call_is_rejected() -> None:
    document = _valid_evidence()
    document["platforms"][0]["host_plugins"]["plan_calls"] = 1

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"host_plugin_auto_mutation", "host_plugin_audit_invalid"} <= error_codes(report)


def test_mutated_audit_bytes_without_new_digest_are_rejected() -> None:
    document = _valid_evidence()
    rewrite_audit_calls(
        document,
        0,
        plan_calls=1,
        recompute_digest=False,
    )

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"host_plugin_audit_digest_mismatch", "host_plugin_auto_mutation"} <= error_codes(report)


def test_rehashed_audit_with_nonzero_call_is_rejected() -> None:
    document = _valid_evidence()
    rewrite_audit_calls(
        document,
        0,
        plan_calls=1,
        recompute_digest=True,
    )

    report = verify_evidence(document)

    assert report["ready"] is False
    assert "host_plugin_auto_mutation" in error_codes(report)


def test_noncanonical_base64_padding_alias_is_rejected() -> None:
    document = _valid_evidence()
    audit = document["platforms"][0]["host_plugins"]["audit_receipt"]
    audit["content_base64"] = noncanonical_base64_alias(audit["content_base64"])

    report = verify_evidence(document)

    assert report["ready"] is False
    assert "host_plugin_audit_base64_noncanonical" in error_codes(report)


def test_run_manifest_must_cover_host_audit_and_receipts() -> None:
    document = _valid_evidence()
    document["platforms"][0]["run"]["manifest"]["covered_digests"].pop()

    report = verify_evidence(document)

    assert report["ready"] is False
    assert "run_manifest_coverage_invalid" in error_codes(report)


def test_missing_receipt_and_screenshot_evidence_is_rejected() -> None:
    document = _valid_evidence()
    del document["platforms"][1]["receipts"]["fresh_snapshot"]
    document["platforms"][2]["screenshots"] = []

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"receipt_digest_invalid", "screenshots_missing"} <= error_codes(report)


def test_unavailable_platform_blocks_complete_gate() -> None:
    document = _valid_evidence()
    document["platforms"][1] = {
        "id": PLATFORMS[1],
        "status": "unavailable",
        "reason_code": "host_unavailable",
        "reason": "No controlled native host was available for this target.",
    }

    report = verify_evidence(document)

    assert report["ready"] is False
    assert PLATFORMS[1] in report["unavailable_platforms"]


def test_unavailable_platform_cannot_smuggle_verified_evidence() -> None:
    document = _valid_evidence()
    unavailable = deepcopy(document["platforms"][0])
    unavailable.update(status="unavailable", reason_code="host_unavailable")
    document["platforms"][0] = unavailable

    report = verify_evidence(document)

    assert report["ready"] is False
    assert PLATFORMS[0] not in report["verified_platforms"]
    assert "unavailable_evidence_present" in error_codes(report)


def test_clean_home_and_host_mutation_are_global_hard_gates() -> None:
    document = _valid_evidence()
    document["clean_home"] = False
    document["no_host_plugin_auto_mutation"] = False

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"clean_home_required", "host_mutation_policy"} <= error_codes(report)


def test_sensitive_evidence_is_rejected() -> None:
    document = _valid_evidence()
    document["platforms"][0]["oauth"]["access_token"] = "must-not-be-recorded"
    document["runtime"]["path"] = "/Users/example/.simplicio/bin/simplicio"

    report = verify_evidence(document)

    assert report["ready"] is False
    assert {"sensitive_key", "personal_path"} <= error_codes(report)


def test_cli_read_failure_does_not_echo_personal_path(capsys) -> None:
    personal_path = "/Users/private-account/oauth-evidence.json"

    assert main(["--evidence", personal_path, "--json"]) == 1

    output = capsys.readouterr().out
    assert personal_path not in output
    assert "evidence_read_failed" in output

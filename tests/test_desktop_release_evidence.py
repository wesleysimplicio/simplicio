from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_desktop_release_evidence import PLATFORMS, SCHEMA, verify_evidence


def valid_document(root: Path) -> dict:
    records = []
    for platform in PLATFORMS:
        artifact = root / f"{platform}.installer"
        artifact.write_bytes(platform.encode("utf-8"))
        records.append({
            "id": platform,
            "status": "verified",
            "artifact": artifact.name,
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "size": artifact.stat().st_size,
            "runtime_digest": "a" * 64,
            "digest_rechecked": True,
            "signature_verified": True,
            "provenance_verified": True,
            "sbom_verified": True,
            "platform_signing_verified": True,
            "notarization_verified": True,
            "clean_install": True,
            "runtime_healthy": True,
            "installed_smoke": True,
        })
    return {
        "schema": SCHEMA,
        "version": "3.8.40",
        "release_tag": "v3.8.40",
        "immutable_tag": True,
        "source_commit": "b" * 40,
        "assets_redownloaded": True,
        "platforms": records,
    }


def test_valid_evidence_is_ready(tmp_path: Path) -> None:
    report = verify_evidence(valid_document(tmp_path), tmp_path)
    assert report["ready"] is True
    assert report["verified_platforms"] == list(PLATFORMS)


def test_unavailable_host_is_not_a_pass(tmp_path: Path) -> None:
    document = valid_document(tmp_path)
    document["platforms"][2] = {"id": PLATFORMS[2], "status": "unavailable", "reason_code": "host_unavailable"}
    report = verify_evidence(document, tmp_path)
    assert report["ready"] is False
    assert PLATFORMS[2] in report["unavailable_platforms"]


def test_digest_and_path_fail_closed(tmp_path: Path) -> None:
    document = valid_document(tmp_path)
    document["platforms"][0]["sha256"] = "0" * 64
    document["platforms"][1]["artifact"] = "../outside"
    report = verify_evidence(document, tmp_path)
    assert report["ready"] is False
    codes = {item["code"] for item in report["errors"]}
    assert "artifact_digest_mismatch" in codes
    assert "artifact_path_invalid" in codes

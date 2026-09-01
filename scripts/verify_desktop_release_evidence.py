#!/usr/bin/env python3
"""Fail-closed verifier for native Desktop release evidence (#282).

This tool validates evidence produced by the manual release process. It never
turns a missing host, a cross-compiled artifact, or a build-directory check into
a native install pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "simplicio.desktop-release-evidence/v1"
PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64", "linux-x64")
VERSION_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
REASON_CODES = {
    "host_unavailable",
    "signing_identity_unavailable",
    "notarization_unavailable",
    "native_smoke_unavailable",
    "artifact_not_built",
    "environment_blocked",
}


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _safe_path(root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_evidence(document: Any, staging_root: Path) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not isinstance(document, dict):
        return {"schema": SCHEMA, "ready": False, "errors": [_error("document_invalid", "evidence must be a JSON object")], "verified_platforms": []}
    if document.get("schema") != SCHEMA:
        errors.append(_error("schema_invalid", f"schema must be {SCHEMA}"))
    tag = document.get("release_tag")
    version = document.get("version")
    if not isinstance(tag, str) or not VERSION_RE.fullmatch(tag):
        errors.append(_error("release_tag_invalid", "release_tag must be an immutable vMAJOR.MINOR.PATCH tag"))
    if not isinstance(version, str) or not VERSION_RE.fullmatch("v" + version.lstrip("v")) or "v" + version.lstrip("v") != tag:
        errors.append(_error("version_mismatch", "version and release_tag must identify the same release"))
    if document.get("immutable_tag") is not True:
        errors.append(_error("immutable_tag_required", "evidence must confirm an immutable release tag"))
    if not isinstance(document.get("source_commit"), str) or not re.fullmatch(r"[0-9a-fA-F]{40}", document["source_commit"]):
        errors.append(_error("source_commit_invalid", "source_commit must be a full 40-character commit"))
    if document.get("assets_redownloaded") is not True:
        errors.append(_error("redownload_required", "final assets must be downloaded again from the published release"))

    records = document.get("platforms")
    if not isinstance(records, list):
        records = []
        errors.append(_error("platforms_missing", "platform evidence must be a list"))
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            errors.append(_error("platform_record_invalid", "each platform record needs an id"))
            continue
        platform = record["id"]
        if platform in by_id:
            errors.append(_error("platform_duplicate", f"duplicate platform evidence: {platform}"))
        by_id[platform] = record
    if set(by_id) != set(PLATFORMS):
        missing = sorted(set(PLATFORMS) - set(by_id))
        extra = sorted(set(by_id) - set(PLATFORMS))
        if missing:
            errors.append(_error("platform_missing", "missing platform evidence: " + ", ".join(missing)))
        if extra:
            errors.append(_error("platform_unknown", "unknown platform evidence: " + ", ".join(extra)))

    verified_platforms: list[str] = []
    unavailable_platforms: list[str] = []
    for platform in PLATFORMS:
        record = by_id.get(platform)
        if record is None:
            continue
        status = record.get("status")
        if status == "unavailable":
            reason = record.get("reason_code")
            if reason not in REASON_CODES:
                errors.append(_error("unavailable_reason_invalid", f"{platform} needs an explicit environment reason"))
            unavailable_platforms.append(platform)
            continue
        if status != "verified":
            errors.append(_error("platform_status_invalid", f"{platform} must be verified or unavailable"))
            continue

        required = (
            "digest_rechecked",
            "signature_verified",
            "provenance_verified",
            "sbom_verified",
            "platform_signing_verified",
            "clean_install",
            "runtime_healthy",
            "installed_smoke",
        )
        for field in required:
            if record.get(field) is not True:
                errors.append(_error("evidence_missing", f"{platform} is missing positive evidence: {field}"))
        if platform.startswith("macos-") and record.get("notarization_verified") is not True:
            errors.append(_error("notarization_required", f"{platform} needs notarization_verified=true"))
        artifact = record.get("artifact")
        path = _safe_path(staging_root, artifact)
        if path is None:
            errors.append(_error("artifact_path_invalid", f"{platform} artifact path is unsafe or missing"))
        elif not path.is_file():
            errors.append(_error("artifact_missing", f"{platform} artifact is not present in the evidence staging root"))
        else:
            actual = _sha256(path)
            expected = str(record.get("sha256", "")).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
                errors.append(_error("artifact_digest_mismatch", f"{platform} artifact SHA-256 does not match the downloaded bytes"))
            if record.get("size") != path.stat().st_size:
                errors.append(_error("artifact_size_mismatch", f"{platform} artifact size does not match the downloaded bytes"))
        if not isinstance(record.get("runtime_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["runtime_digest"]):
            errors.append(_error("runtime_digest_missing", f"{platform} must record the bundled Runtime digest"))
        if not any(error["message"].startswith(f"{platform} ") for error in errors):
            verified_platforms.append(platform)

    ready = not errors and len(verified_platforms) == len(PLATFORMS)
    return {
        "schema": SCHEMA,
        "release_tag": tag,
        "version": version,
        "ready": ready,
        "verified_platforms": verified_platforms,
        "unavailable_platforms": unavailable_platforms,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.evidence.read_text(encoding="utf-8"))
        report = verify_evidence(document, args.staging_root)
    except (OSError, json.JSONDecodeError) as exc:
        report = {"schema": SCHEMA, "ready": False, "errors": [_error("evidence_read_failed", str(exc))], "verified_platforms": []}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("desktop release evidence: " + ("READY" if report["ready"] else "BLOCKED"))
        for item in report.get("errors", []):
            print(f"  [{item['code']}] {item['message']}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

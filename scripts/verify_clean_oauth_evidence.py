#!/usr/bin/env python3
"""Validate redacted Google OAuth evidence from a clean native installation (#283)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "simplicio.clean-oauth-evidence/v1"
PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64", "linux-x64")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
UNAVAILABLE_REASONS = {
    "host_unavailable",
    "oauth_provider_unavailable",
    "native_package_unavailable",
    "environment_blocked",
}
SENSITIVE_KEY_RE = re.compile(
    r"(?:token|secret|password|cookie|authorization|credential|prompt|response|argv|"
    r"personal.?path|home.?path|access.?token|refresh.?token)",
    re.IGNORECASE,
)
PERSONAL_PATH_RE = re.compile(r"(?:^|[/\\])(?:Users|home|AppData|Library)[/\\]", re.IGNORECASE)


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def contains_sensitive_data(value: Any, location: str = "$") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                errors.append(failure("sensitive_key", f"{location}.{key} is not allowed in redacted OAuth evidence"))
            errors.extend(contains_sensitive_data(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(contains_sensitive_data(child, f"{location}[{index}]"))
    elif isinstance(value, str) and PERSONAL_PATH_RE.search(value):
        errors.append(failure("personal_path", f"{location} contains a personal filesystem path"))
    return errors


def verify_evidence(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        return {"schema": SCHEMA, "ready": False, "errors": [failure("document_invalid", "evidence must be a JSON object")]}
    errors = contains_sensitive_data(document)
    if document.get("schema") != SCHEMA:
        errors.append(failure("schema_invalid", f"schema must be {SCHEMA}"))
    version = document.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        errors.append(failure("version_invalid", "version must be semantic version text"))
    if document.get("clean_home") is not True:
        errors.append(failure("clean_home_required", "evidence must start from a clean HOME with no prior Runtime/auth state"))
    if document.get("no_host_plugin_auto_mutation") is not True:
        errors.append(failure("host_mutation_policy", "login/install evidence must prove that host plugins were not mutated automatically"))

    runtime = document.get("runtime")
    if not isinstance(runtime, dict):
        errors.append(failure("runtime_missing", "runtime identity evidence is required"))
        runtime = {}
    if runtime.get("state") != "healthy":
        errors.append(failure("runtime_not_healthy", "the installed Runtime must return a healthy snapshot"))
    if runtime.get("fresh_snapshot") is not True:
        errors.append(failure("fresh_snapshot_required", "the healthy snapshot must be new after installation"))
    if not isinstance(runtime.get("version"), str) or not VERSION_RE.fullmatch(runtime.get("version", "")):
        errors.append(failure("runtime_version_invalid", "runtime version evidence is invalid"))
    if not isinstance(runtime.get("digest"), str) or not DIGEST_RE.fullmatch(runtime.get("digest", "")):
        errors.append(failure("runtime_digest_invalid", "runtime digest evidence must be sha256:<64 lowercase hex>"))

    oauth = document.get("oauth")
    if not isinstance(oauth, dict):
        errors.append(failure("oauth_missing", "Google OAuth lifecycle evidence is required"))
        oauth = {}
    required_true = (
        "browser_grant_completed",
        "callback_received",
        "final_access_active",
        "logout_completed",
        "relogin_completed",
        "redacted_receipt",
    )
    for field in required_true:
        if oauth.get(field) is not True:
            errors.append(failure("oauth_step_missing", f"oauth.{field} must be true"))
    if oauth.get("logout_state") != "signed_out":
        errors.append(failure("logout_state_invalid", "logout must return to signed_out"))
    if oauth.get("relogin_state") != "active":
        errors.append(failure("relogin_state_invalid", "a second login must return to active"))

    records = document.get("platforms")
    if not isinstance(records, list):
        records = []
        errors.append(failure("platforms_missing", "all supported native platforms need a record"))
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            errors.append(failure("platform_record_invalid", "each platform record needs an id"))
            continue
        if record["id"] in by_id:
            errors.append(failure("platform_duplicate", f"duplicate platform: {record['id']}"))
        by_id[record["id"]] = record
    if set(by_id) != set(PLATFORMS):
        errors.append(failure("platform_set_invalid", "platform evidence must cover exactly " + ", ".join(PLATFORMS)))

    verified: list[str] = []
    unavailable: list[str] = []
    for platform in PLATFORMS:
        record = by_id.get(platform)
        if record is None:
            continue
        if record.get("status") == "unavailable":
            if record.get("reason_code") not in UNAVAILABLE_REASONS:
                errors.append(failure("unavailable_reason_invalid", f"{platform} needs a truthful unavailable reason"))
            unavailable.append(platform)
            continue
        if record.get("status") != "verified":
            errors.append(failure("platform_status_invalid", f"{platform} must be verified or unavailable"))
            continue
        for field in ("native_install", "runtime_healthy", "oauth_receipt_redacted", "version_recorded", "digest_recorded"):
            if record.get(field) is not True:
                errors.append(failure("platform_evidence_missing", f"{platform} is missing {field}"))
        if not any(item["message"].startswith(f"{platform} ") for item in errors):
            verified.append(platform)

    return {
        "schema": SCHEMA,
        "version": version,
        "ready": not errors and len(verified) == len(PLATFORMS),
        "verified_platforms": verified,
        "unavailable_platforms": unavailable,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = verify_evidence(json.loads(args.evidence.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        report = {"schema": SCHEMA, "ready": False, "errors": [failure("evidence_read_failed", str(exc))]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("clean OAuth evidence: " + ("READY" if report["ready"] else "BLOCKED"))
        for item in report.get("errors", []):
            print(f"  [{item['code']}] {item['message']}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

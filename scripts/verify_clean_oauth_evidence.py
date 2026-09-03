#!/usr/bin/env python3
"""Validate redacted Google OAuth evidence from a clean native installation (#283)."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "simplicio.clean-oauth-evidence/v2"
PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64", "linux-x64")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
UNAVAILABLE_REASONS = {
    "host_unavailable",
    "oauth_provider_unavailable",
    "native_package_unavailable",
    "environment_blocked",
}
AUDIT_RECEIPT_MAX_BYTES = 16 * 1024
AUDIT_RECEIPT_MAX_BASE64 = 4 * ((AUDIT_RECEIPT_MAX_BYTES + 2) // 3)
AUDIT_RECEIPT_SCHEMA = "simplicio.host-plugin-audit/v1"
SENSITIVE_KEY_RE = re.compile(
    r"(?:token|secret|password|cookie|authorization|credential|prompt|response|argv|"
    r"personal.?path|home.?path|access.?token|refresh.?token)",
    re.IGNORECASE,
)
PERSONAL_PATH_RE = re.compile(r"(?:^|[/\\])(?:Users|home|AppData|Library)[/\\]", re.IGNORECASE)


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def valid_version(value: Any) -> bool:
    return isinstance(value, str) and VERSION_RE.fullmatch(value) is not None


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


def platform_failure(code: str, platform: str, message: str) -> dict[str, str]:
    return failure(code, f"{platform} {message}")


def validate_bound_digest(
    value: Any,
    platform: str,
    label: str,
    errors: list[dict[str, str]],
    seen_digests: dict[str, str],
    *,
    invalid_code: str = "evidence_digest_invalid",
    require_redacted: bool = False,
) -> str | None:
    if not isinstance(value, dict) or not valid_digest(value.get("digest")):
        errors.append(
            platform_failure(
                invalid_code,
                platform,
                f"{label} must have a sha256 digest",
            )
        )
        return None
    if value.get("target") != platform:
        errors.append(
            platform_failure(
                "evidence_target_mismatch",
                platform,
                f"{label} must be bound to target {platform}",
            )
        )
    if require_redacted and value.get("redacted") is not True:
        errors.append(
            platform_failure(
                "evidence_not_redacted",
                platform,
                f"{label} must be marked redacted",
            )
        )
    digest = value["digest"]
    previous = seen_digests.get(digest)
    if previous is not None:
        errors.append(
            platform_failure(
                "evidence_digest_reused",
                platform,
                f"{label} reuses evidence digest from {previous}",
            )
        )
    else:
        seen_digests[digest] = f"{platform}:{label}"
    return digest


def validate_release_identity(
    name: str,
    identity: Any,
    errors: list[dict[str, str]],
    seen_artifacts: dict[str, str],
) -> dict[str, Any]:
    if not isinstance(identity, dict):
        errors.append(failure(f"{name}_missing", f"{name} release identity evidence is required"))
        return {}
    if not valid_version(identity.get("version")):
        errors.append(failure(f"{name}_version_invalid", f"{name} release version evidence is invalid"))
    artifacts = identity.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(PLATFORMS):
        errors.append(
            failure(
                f"{name}_artifacts_invalid",
                f"{name} release artifacts must cover exactly " + ", ".join(PLATFORMS),
            )
        )
    else:
        for platform, digest in artifacts.items():
            if not valid_digest(digest):
                errors.append(
                    failure(
                        f"{name}_artifact_digest_invalid",
                        f"{name} artifact {platform} must have a sha256 digest",
                    )
                )
                continue
            previous = seen_artifacts.get(digest)
            if previous is not None:
                errors.append(
                    failure(
                        "artifact_digest_reused",
                        f"{name} artifact {platform} reuses digest from {previous}",
                    )
                )
            else:
                seen_artifacts[digest] = f"{name}:{platform}"
    return identity


def validate_host_plugin_audit(
    value: Any,
    platform: str,
    host_plugins: dict[str, Any],
    errors: list[dict[str, str]],
    seen_digests: dict[str, str],
) -> str | None:
    digest = validate_bound_digest(
        value,
        platform,
        "host-plugin audit receipt",
        errors,
        seen_digests,
        invalid_code="host_plugin_audit_invalid",
        require_redacted=True,
    )
    if not isinstance(value, dict):
        return digest
    encoded = value.get("content_base64")
    if not isinstance(encoded, str) or len(encoded) > AUDIT_RECEIPT_MAX_BASE64:
        errors.append(
            platform_failure(
                "host_plugin_audit_content_invalid",
                platform,
                "audit receipt must contain bounded base64 JSON bytes",
            )
        )
        return digest
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        errors.append(
            platform_failure(
                "host_plugin_audit_content_invalid",
                platform,
                "audit receipt base64 is invalid",
            )
        )
        return digest
    if encoded != base64.b64encode(raw).decode("ascii"):
        errors.append(
            platform_failure(
                "host_plugin_audit_base64_noncanonical",
                platform,
                "audit receipt base64 must use canonical padding bits",
            )
        )
    if not raw or len(raw) > AUDIT_RECEIPT_MAX_BYTES:
        errors.append(
            platform_failure(
                "host_plugin_audit_content_invalid",
                platform,
                "audit receipt JSON bytes are empty or exceed the size limit",
            )
        )
        return digest
    computed_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if digest != computed_digest:
        errors.append(
            platform_failure(
                "host_plugin_audit_digest_mismatch",
                platform,
                "audit receipt digest does not match its JSON bytes",
            )
        )
    try:
        content = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(
            platform_failure(
                "host_plugin_audit_content_invalid",
                platform,
                "audit receipt bytes must be valid JSON",
            )
        )
        return digest
    if not isinstance(content, dict):
        errors.append(
            platform_failure(
                "host_plugin_audit_content_invalid",
                platform,
                "audit receipt JSON must be an object",
            )
        )
        return digest
    canonical = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if raw != canonical:
        errors.append(
            platform_failure(
                "host_plugin_audit_content_noncanonical",
                platform,
                "audit receipt JSON bytes must use canonical encoding",
            )
        )
    errors.extend(
        contains_sensitive_data(
            content,
            f"$.platforms.{platform}.host_plugins.audit_receipt.content",
        )
    )
    if (
        content.get("schema") != AUDIT_RECEIPT_SCHEMA
        or content.get("target") != platform
        or content.get("redacted") is not True
    ):
        errors.append(
            platform_failure(
                "host_plugin_audit_content_invalid",
                platform,
                "audit receipt must bind schema, target, and redaction",
            )
        )
    for operation in ("plan_calls", "apply_calls"):
        calls = content.get(operation)
        if type(calls) is not int or calls != 0:
            errors.append(
                platform_failure(
                    "host_plugin_auto_mutation",
                    platform,
                    f"audit receipt must prove {operation}=0",
                )
            )
        if host_plugins.get(operation) != calls:
            errors.append(
                platform_failure(
                    "host_plugin_audit_invalid",
                    platform,
                    f"audit receipt does not match {operation}",
                )
            )
    return digest


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
    if not valid_version(version):
        errors.append(failure("version_invalid", "version must be semantic version text"))
    if document.get("clean_home") is not True:
        errors.append(failure("clean_home_required", "evidence must start from a clean HOME with no prior Runtime/auth state"))
    if document.get("no_host_plugin_auto_mutation") is not True:
        errors.append(failure("host_mutation_policy", "login/install evidence must prove that host plugins were not mutated automatically"))

    seen_artifacts: dict[str, str] = {}
    desktop = validate_release_identity(
        "desktop",
        document.get("desktop"),
        errors,
        seen_artifacts,
    )
    if valid_version(version) and desktop.get("version") != version:
        errors.append(failure("desktop_version_mismatch", "desktop package version must match evidence version"))

    runtime = validate_release_identity(
        "runtime",
        document.get("runtime"),
        errors,
        seen_artifacts,
    )
    if runtime.get("state") != "healthy":
        errors.append(failure("runtime_not_healthy", "the installed Runtime must return a healthy snapshot"))
    if runtime.get("fresh_snapshot") is not True:
        errors.append(failure("fresh_snapshot_required", "the healthy snapshot must be new after installation"))

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
    seen_digests: dict[str, str] = {}
    seen_run_ids: dict[str, str] = {}
    for platform in PLATFORMS:
        record = by_id.get(platform)
        if record is None:
            continue
        if record.get("status") == "unavailable":
            if record.get("reason_code") not in UNAVAILABLE_REASONS:
                errors.append(failure("unavailable_reason_invalid", f"{platform} needs a truthful unavailable reason"))
            allowed = {"id", "status", "reason_code", "reason"}
            if set(record) - allowed:
                errors.append(
                    platform_failure(
                        "unavailable_evidence_present",
                        platform,
                        "unavailable record cannot contain verified evidence",
                    )
                )
            unavailable.append(platform)
            continue
        if record.get("status") != "verified":
            errors.append(failure("platform_status_invalid", f"{platform} must be verified or unavailable"))
            continue
        error_count = len(errors)
        if record.get("clean_home") is not True:
            errors.append(platform_failure("platform_clean_home_required", platform, "must start from a clean HOME"))

        install = record.get("install")
        if not isinstance(install, dict) or install.get("completed") is not True or install.get("atomic") is not True:
            errors.append(
                platform_failure(
                    "native_install_invalid",
                    platform,
                    "must prove a completed atomic native install",
                )
            )
        if record.get("runtime_state") != "healthy" or record.get("fresh_snapshot") is not True:
            errors.append(
                platform_failure(
                    "fresh_runtime_invalid",
                    platform,
                    "must prove a fresh healthy Runtime snapshot",
                )
            )

        run = record.get("run")
        manifest: Any = None
        if not isinstance(run, dict) or not isinstance(run.get("id"), str) or not run["id"].strip():
            errors.append(
                platform_failure(
                    "run_identity_invalid",
                    platform,
                    "must record a non-empty clean-run id",
                )
            )
        else:
            manifest = run.get("manifest")
            previous_platform = seen_run_ids.get(run["id"])
            if previous_platform is not None:
                errors.append(
                    platform_failure(
                        "run_identity_reused",
                        platform,
                        f"reuses clean-run id from {previous_platform}",
                    )
                )
            else:
                seen_run_ids[run["id"]] = platform
            validate_bound_digest(
                manifest,
                platform,
                "run manifest",
                errors,
                seen_digests,
                invalid_code="run_manifest_invalid",
            )

        for identity_name, expected in (("desktop", desktop), ("runtime", runtime)):
            identity = record.get(identity_name)
            if not isinstance(identity, dict):
                errors.append(
                    platform_failure(
                        f"{identity_name}_identity_missing",
                        platform,
                        f"is missing {identity_name} identity",
                    )
                )
                continue
            if not valid_version(identity.get("version")) or not valid_digest(identity.get("digest")):
                errors.append(
                    platform_failure(
                        f"{identity_name}_identity_invalid",
                        platform,
                        f"has invalid {identity_name} version or digest",
                    )
                )
                continue
            expected_artifacts = expected.get("artifacts")
            expected_digest = expected_artifacts.get(platform) if isinstance(expected_artifacts, dict) else None
            if identity.get("version") != expected.get("version") or identity.get("digest") != expected_digest:
                errors.append(
                    platform_failure(
                        f"{identity_name}_identity_mismatch",
                        platform,
                        f"does not match the release {identity_name} identity",
                    )
                )

        host_plugins = record.get("host_plugins")
        covered_digests: list[str] = []
        if not isinstance(host_plugins, dict):
            errors.append(
                platform_failure(
                    "host_plugin_evidence_missing",
                    platform,
                    "is missing host-plugin call evidence",
                )
            )
        else:
            audit_receipt = host_plugins.get("audit_receipt")
            for operation in ("plan_calls", "apply_calls"):
                calls = host_plugins.get(operation)
                if type(calls) is not int or calls != 0:
                    errors.append(
                        platform_failure(
                            "host_plugin_auto_mutation",
                            platform,
                            f"must record {operation}=0",
                        )
                    )
            audit_digest = validate_host_plugin_audit(
                audit_receipt,
                platform,
                host_plugins,
                errors,
                seen_digests,
            )
            if audit_digest is not None:
                covered_digests.append(audit_digest)

        oauth = record.get("oauth")
        if not isinstance(oauth, dict):
            errors.append(
                platform_failure(
                    "platform_oauth_missing",
                    platform,
                    "is missing Google OAuth lifecycle evidence",
                )
            )
        else:
            for field in ("browser_grant_completed", "callback_received", "redacted"):
                if oauth.get(field) is not True:
                    errors.append(
                        platform_failure(
                            "platform_oauth_step_missing",
                            platform,
                            f"oauth.{field} must be true",
                        )
                    )
            if oauth.get("final_state") != "active":
                errors.append(
                    platform_failure(
                        "platform_oauth_state_invalid",
                        platform,
                        "OAuth must end in active state",
                    )
                )

        logout = record.get("logout")
        if not isinstance(logout, dict) or logout.get("completed") is not True or logout.get("final_state") != "signed_out":
            errors.append(
                platform_failure(
                    "platform_logout_invalid",
                    platform,
                    "logout must complete and return to signed_out",
                )
            )

        receipts = record.get("receipts")
        if not isinstance(receipts, dict):
            errors.append(platform_failure("receipts_missing", platform, "is missing redacted receipt digests"))
        else:
            for receipt in ("install", "fresh_snapshot", "oauth", "logout"):
                receipt_digest = validate_bound_digest(
                    receipts.get(receipt),
                    platform,
                    f"{receipt} receipt",
                    errors,
                    seen_digests,
                    invalid_code="receipt_digest_invalid",
                    require_redacted=True,
                )
                if receipt_digest is not None:
                    covered_digests.append(receipt_digest)

        screenshots = record.get("screenshots")
        if not isinstance(screenshots, list) or not screenshots:
            errors.append(
                platform_failure(
                    "screenshots_missing",
                    platform,
                    "must include at least one redacted screenshot digest",
                )
            )
        else:
            for index, screenshot in enumerate(screenshots):
                screenshot_digest = validate_bound_digest(
                    screenshot,
                    platform,
                    f"screenshot {index}",
                    errors,
                    seen_digests,
                    invalid_code="screenshot_digest_invalid",
                    require_redacted=True,
                )
                if screenshot_digest is not None:
                    covered_digests.append(screenshot_digest)

        manifest_coverage = manifest.get("covered_digests") if isinstance(manifest, dict) else None
        if (
            not isinstance(manifest_coverage, list)
            or len(manifest_coverage) != len(covered_digests)
            or set(manifest_coverage) != set(covered_digests)
        ):
            errors.append(
                platform_failure(
                    "run_manifest_coverage_invalid",
                    platform,
                    "run manifest must cover every receipt and screenshot digest exactly once",
                )
            )

        if len(errors) == error_count:
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
    except (OSError, json.JSONDecodeError):
        report = {
            "schema": SCHEMA,
            "ready": False,
            "errors": [failure("evidence_read_failed", "unable to read or parse the redacted evidence file")],
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("clean OAuth evidence: " + ("READY" if report["ready"] else "BLOCKED"))
        for item in report.get("errors", []):
            print(f"  [{item['code']}] {item['message']}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

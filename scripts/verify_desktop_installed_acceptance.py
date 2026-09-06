#!/usr/bin/env python3
"""Verify redacted evidence from one installed Desktop acceptance run.

This verifier accepts only a report captured from the installed native app. It
does not turn preview tests, a build directory, or a missing platform into a
pass. Blocked and unexecuted checks are retained as honest evidence but keep
the report not ready.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "simplicio.desktop-installed-acceptance/v1"
PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64", "linux-x64")
CHECKS = (
    "bundle_identity",
    "runtime_snapshot",
    "provider_quotas_contract",
    "provider_quotas_current",
    "signed_update_download",
    "signed_update_install",
    "signed_update_relaunch",
    "signed_update_health",
    "signed_update_rollback",
    "logout_relogin",
    "permissions",
)
STATUSES = {"verified", "blocked", "unexecuted"}
REASONS = {
    "app_not_installed",
    "artifact_not_built",
    "authentication_not_authorized",
    "developer_id_unavailable",
    "environment_blocked",
    "host_unavailable",
    "notarization_unavailable",
    "provider_session_unavailable",
    "rust_toolchain_unavailable",
    "signed_sidecar_missing",
}
PROVIDER_CONTRACT = {
    "codex": ("codex_app_server", "local_authenticated_account"),
    "grok": ("grok_cli_billing", "local_cli_session"),
}
PROVIDER_STATUSES = {"fresh", "stale", "unavailable"}
ROOT_STATUSES = {"available", "stale", "unavailable", "busy"}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
UNSAFE_KEY = re.compile(
    r"(?:path|cwd|home|argv|secret|password|credential|authorization|"
    r"api[_-]?key|access[_-]?token|refresh[_-]?token|raw[_-]?(?:output|payload))",
    re.I,
)


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _contains_unsafe_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            not isinstance(key, str)
            or (key != "clean_home" and UNSAFE_KEY.search(key) is not None)
            or _contains_unsafe_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_unsafe_key(child) for child in value)
    return False


def _quota_errors(observation: Any) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not isinstance(observation, dict):
        return [_error("quota_observation_missing", "provider quota contract observation is required")]
    if observation.get("schema") != "simplicio.provider-quotas/v2":
        errors.append(_error("quota_schema_invalid", "provider quota observation must use v2"))
    root_status = observation.get("status")
    if root_status not in ROOT_STATUSES:
        errors.append(_error("quota_root_status_invalid", "provider quota root status is invalid"))
    providers = observation.get("providers")
    if not isinstance(providers, list) or len(providers) > 2:
        errors.append(_error("quota_providers_invalid", "provider quota observation must contain at most two records"))
        providers = []
    seen: set[str] = set()
    statuses: list[str] = []
    for provider in providers:
        if not isinstance(provider, dict):
            errors.append(_error("quota_provider_invalid", "each provider quota record must be an object"))
            continue
        provider_id = provider.get("id")
        source = provider.get("source")
        scope = provider.get("accountScope")
        expected = PROVIDER_CONTRACT.get(provider_id) if isinstance(provider_id, str) else None
        if (
            not isinstance(provider_id, str)
            or provider_id in seen
            or expected is None
            or source != expected[0]
            or scope != expected[1]
        ):
            errors.append(_error("quota_provider_identity_invalid", "provider id, source and account scope must agree"))
        else:
            seen.add(provider_id)
        if provider.get("redacted") is not True:
            errors.append(_error("quota_redaction_invalid", "provider quota evidence must be redacted"))
        status = provider.get("status")
        if status not in PROVIDER_STATUSES:
            errors.append(_error("quota_provider_status_invalid", "provider quota status is invalid"))
        else:
            statuses.append(status)
        window_count = provider.get("window_count")
        if not isinstance(window_count, int) or isinstance(window_count, bool) or not 0 <= window_count <= 32:
            errors.append(_error("quota_window_count_invalid", "provider quota window_count must be between 0 and 32"))
        elif status == "unavailable" and window_count != 0:
            errors.append(_error("quota_unavailable_has_windows", "unavailable provider quotas must have zero windows"))
        elif status in {"fresh", "stale"} and window_count == 0:
            errors.append(_error("quota_current_has_no_windows", "fresh or stale provider quotas need a window count"))
    if root_status == "busy" and providers:
        errors.append(_error("quota_busy_has_providers", "busy root status must have no provider records"))
    elif root_status != "busy":
        expected_root = "available" if "fresh" in statuses else "stale" if "stale" in statuses else "unavailable"
        if root_status != expected_root:
            errors.append(_error("quota_root_status_mismatch", "root status does not summarize provider states"))
    return errors


def verify_evidence(document: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not isinstance(document, dict):
        return {"schema": SCHEMA, "ready": False, "errors": [_error("document_invalid", "evidence must be an object")]}
    if _contains_unsafe_key(document):
        return {"schema": SCHEMA, "ready": False, "errors": [_error("sensitive_field", "installed evidence contains a forbidden field")]}
    if document.get("schema") != SCHEMA:
        errors.append(_error("schema_invalid", f"schema must be {SCHEMA}"))
    if document.get("source") != "installed" or document.get("preview") is not False:
        errors.append(_error("installed_source_required", "preview or mocked evidence cannot satisfy installed acceptance"))
    if document.get("clean_home") is not True:
        errors.append(_error("clean_home_required", "acceptance must use an isolated clean HOME"))
    if document.get("platform") not in PLATFORMS:
        errors.append(_error("platform_invalid", "acceptance must name a supported native platform"))
    app = document.get("installed_app")
    if not isinstance(app, dict) or not isinstance(app.get("version"), str) or not VERSION.fullmatch(app["version"]):
        errors.append(_error("installed_app_identity_missing", "installed_app.version must be a release version"))
    if not isinstance(app, dict) or not isinstance(app.get("runtime_version"), str) or not VERSION.fullmatch(app["runtime_version"]):
        errors.append(_error("runtime_identity_missing", "installed_app.runtime_version must be a release version"))
    if not isinstance(app, dict) or not isinstance(app.get("runtime_digest"), str) or not DIGEST.fullmatch(app["runtime_digest"]):
        errors.append(_error("runtime_digest_missing", "installed_app.runtime_digest must be a SHA-256 digest"))

    records = document.get("checks")
    if not isinstance(records, list):
        records = []
        errors.append(_error("checks_missing", "acceptance checks must be a list"))
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            errors.append(_error("check_invalid", "each acceptance check needs an id"))
            continue
        check_id = record["id"]
        if check_id in by_id:
            errors.append(_error("check_duplicate", f"duplicate acceptance check: {check_id}"))
        by_id[check_id] = record
    missing = sorted(set(CHECKS) - set(by_id))
    extra = sorted(set(by_id) - set(CHECKS))
    if missing:
        errors.append(_error("check_missing", "missing checks: " + ", ".join(missing)))
    if extra:
        errors.append(_error("check_unknown", "unknown checks: " + ", ".join(extra)))

    verified: list[str] = []
    blocked: list[str] = []
    unexecuted: list[str] = []
    for check_id in CHECKS:
        record = by_id.get(check_id)
        if record is None:
            continue
        if record.get("source") != "installed" or record.get("redacted") is not True:
            errors.append(_error("check_evidence_invalid", f"{check_id} must be installed redacted evidence"))
        evidence_id = record.get("evidence_id")
        if not isinstance(evidence_id, str) or not IDENTIFIER.fullmatch(evidence_id):
            errors.append(_error("evidence_id_invalid", f"{check_id} needs a safe evidence_id"))
        status = record.get("status")
        if status not in STATUSES:
            errors.append(_error("check_status_invalid", f"{check_id} has an invalid status"))
            continue
        if status == "verified":
            verified.append(check_id)
            if "reason_code" in record:
                errors.append(_error("verified_reason_invalid", f"verified {check_id} cannot carry a blocker reason"))
        else:
            (blocked if status == "blocked" else unexecuted).append(check_id)
            if record.get("reason_code") not in REASONS:
                errors.append(_error("reason_code_invalid", f"{check_id} needs an explicit environment reason"))
        if check_id == "provider_quotas_contract" and status == "verified":
            errors.extend(_quota_errors(record.get("observation")))
        if check_id == "provider_quotas_current" and status == "verified":
            fresh = record.get("fresh_provider_ids")
            if (
                not isinstance(fresh, list)
                or not fresh
                or any(not isinstance(item, str) or item not in PROVIDER_CONTRACT for item in fresh)
            ):
                errors.append(_error("quota_current_missing", "current quota evidence needs at least one fresh provider id"))

    ready = not errors and len(verified) == len(CHECKS)
    return {
        "schema": SCHEMA,
        "ready": ready,
        "platform": document.get("platform"),
        "verified_checks": verified,
        "blocked_checks": blocked,
        "unexecuted_checks": unexecuted,
        "required_checks": len(CHECKS),
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
        report = {"schema": SCHEMA, "ready": False, "errors": [_error("evidence_read_failed", str(exc))]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("desktop installed acceptance: " + ("READY" if report["ready"] else "BLOCKED"))
        for item in report.get("errors", []):
            print(f"  [{item['code']}] {item['message']}")
        for check_id in report.get("blocked_checks", []):
            print(f"  [blocked] {check_id}")
        for check_id in report.get("unexecuted_checks", []):
            print(f"  [unexecuted] {check_id}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

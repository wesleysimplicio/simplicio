#!/usr/bin/env python3
"""Validate the installed Desktop E2E matrix for login, MCP, and usage (#286)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "simplicio.installed-validation-matrix/v1"
PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64", "linux-x64")
SCENARIOS = (
    "clean_install",
    "runtime_healthy_snapshot",
    "google_login",
    "logout_relogin",
    "mcp_absent",
    "mcp_detected",
    "mcp_registered",
    "handshake_stale",
    "mcp_connected",
    "claude_fixture",
    "codex_fixture",
    "opencode_fixture",
    "usage_present",
    "usage_absent",
    "usage_corrupt",
    "fork_resume",
    "duplicate_event",
    "token_expired",
    "unknown_session",
    "timeout",
    "network_unavailable",
)
SENSITIVE_KEY = re.compile(r"(?:secret|token|password|cookie|prompt|response|argv|personal.?path|home.?path|credential)", re.I)
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


def failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def sensitive_errors(value: Any, location: str = "$") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if SENSITIVE_KEY.search(str(key)):
                errors.append(failure("sensitive_field", f"{location}.{key} is not allowed in installed evidence"))
            errors.extend(sensitive_errors(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(sensitive_errors(child, f"{location}[{index}]"))
    elif isinstance(value, str) and re.search(r"(?:^|[/\\])(?:Users|home|AppData|Library)[/\\]", value, re.I):
        errors.append(failure("personal_path", f"{location} contains a personal path"))
    return errors


def verify_matrix(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        return {"schema": SCHEMA, "ready": False, "errors": [failure("document_invalid", "matrix must be a JSON object")]}
    errors = sensitive_errors(document)
    if document.get("schema") != SCHEMA:
        errors.append(failure("schema_invalid", f"schema must be {SCHEMA}"))
    if document.get("installed_e2e") is not True or document.get("preview") is not False or document.get("source") != "installed":
        errors.append(failure("installed_source_required", "only a real installed native run can satisfy this matrix"))
    if document.get("clean_home") is not True:
        errors.append(failure("clean_home_required", "the matrix must start from an isolated clean HOME"))

    runtime = document.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("state") != "healthy" or runtime.get("fresh_snapshot") is not True:
        errors.append(failure("runtime_confirmation_missing", "each matrix run needs a fresh healthy Runtime snapshot"))

    scenarios = document.get("scenarios")
    if not isinstance(scenarios, list):
        scenarios = []
        errors.append(failure("scenarios_missing", "required E2E scenarios are missing"))
    by_id: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("id"), str):
            errors.append(failure("scenario_invalid", "each scenario needs an id"))
            continue
        if scenario["id"] in by_id:
            errors.append(failure("scenario_duplicate", f"duplicate scenario: {scenario['id']}"))
        by_id[scenario["id"]] = scenario
    missing = sorted(set(SCENARIOS) - set(by_id))
    extra = sorted(set(by_id) - set(SCENARIOS))
    if missing:
        errors.append(failure("scenario_missing", "missing scenarios: " + ", ".join(missing)))
    if extra:
        errors.append(failure("scenario_unknown", "unknown scenarios: " + ", ".join(extra)))

    verified: list[str] = []
    for scenario_id in SCENARIOS:
        scenario = by_id.get(scenario_id)
        if scenario is None:
            continue
        status = scenario.get("status")
        if status != "verified":
            errors.append(failure("scenario_not_verified", f"{scenario_id} is {status!r}, not verified"))
            continue
        if scenario.get("source") != "installed" or scenario.get("redacted") is not True:
            errors.append(failure("scenario_evidence_invalid", f"{scenario_id} needs installed redacted evidence"))
        evidence_id = scenario.get("evidence_id")
        if not isinstance(evidence_id, str) or not IDENTIFIER.fullmatch(evidence_id):
            errors.append(failure("evidence_id_invalid", f"{scenario_id} needs a safe evidence id"))
        if scenario_id == "google_login" and scenario.get("runtime_confirmed") is not True:
            errors.append(failure("login_confirmation_missing", "Google login is valid only after Runtime confirmation"))
        if scenario_id == "usage_absent" and (
            scenario.get("reported_state") not in {"unknown", "partial"} or scenario.get("not_zero") is not True
        ):
            errors.append(failure("usage_zero_inference", "missing usage must remain unknown/partial, never zero"))
        if scenario_id == "handshake_stale" and (
            scenario.get("reported_state") != "stale" or scenario.get("connected") is True
        ):
            errors.append(failure("handshake_state_confused", "stale handshake cannot be reported as connected"))
        verified.append(scenario_id)

    platform_matrix = document.get("platform_matrix")
    if not isinstance(platform_matrix, list):
        platform_matrix = []
        errors.append(failure("platform_matrix_missing", "native platform coverage is required"))
    platform_by_id: dict[str, dict[str, Any]] = {}
    for record in platform_matrix:
        if isinstance(record, dict) and isinstance(record.get("id"), str):
            platform_by_id[record["id"]] = record
    if set(platform_by_id) != set(PLATFORMS):
        errors.append(failure("platform_matrix_incomplete", "platform matrix must cover exactly " + ", ".join(PLATFORMS)))
    unavailable: list[str] = []
    for platform in PLATFORMS:
        record = platform_by_id.get(platform)
        if record is None:
            continue
        if record.get("status") == "unavailable":
            unavailable.append(platform)
        elif record.get("status") != "verified":
            errors.append(failure("platform_status_invalid", f"{platform} must be verified or unavailable"))
        elif record.get("redacted") is not True:
            errors.append(failure("platform_evidence_invalid", f"{platform} evidence must be redacted"))

    return {
        "schema": SCHEMA,
        "ready": not errors and len(verified) == len(SCENARIOS) and len(unavailable) == 0,
        "verified_scenarios": verified,
        "required_scenarios": len(SCENARIOS),
        "unavailable_platforms": unavailable,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = verify_matrix(json.loads(args.matrix.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        report = {"schema": SCHEMA, "ready": False, "errors": [failure("matrix_read_failed", str(exc))]}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print("installed E2E matrix: " + ("READY" if report["ready"] else "BLOCKED"))
        for item in report.get("errors", []):
            print(f"  [{item['code']}] {item['message']}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

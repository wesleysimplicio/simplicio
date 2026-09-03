#!/usr/bin/env python3
"""Fail-closed verifier for the Runtime-managed external operator bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from verify_ed25519 import verify_signature_for_digest

SCHEMA = "simplicio.operator-bundle-manifest/v1"
REPORT_SCHEMA = "simplicio.operator-bundle-verification/v1"
REQUIRED_COMPONENTS = {
    "simplicio-runtime",
    "simplicio-loop",
    "simplicio-mapper",
    "simplicio-dev-cli",
    "simplicio-fast",
    "simplicio-prompt",
}
REQUIRED_POLICIES = {
    "offline_install": True,
    "absolute_entrypoints": True,
    "native_loop_default": True,
    "external_loop_fallback_only": True,
    "hooks_provision_packages": False,
    "host_plugin_consent_required": True,
    "atomic_runtime_operator_activation": True,
    "active_run_slot_pinning": True,
}
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _failure(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail}


def _object(value: Any, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def _safe_filename(value: Any) -> bool:
    return isinstance(value, str) and SAFE_FILENAME.fullmatch(value) is not None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_component(raw: Any, failures: list[dict[str, str]]) -> str | None:
    try:
        component = _object(raw, "component_invalid")
    except ValueError:
        failures.append(_failure("component_invalid", "component must be an object"))
        return None
    name = component.get("name")
    if name not in REQUIRED_COMPONENTS:
        failures.append(_failure("component_unknown", f"unsupported component {name!r}"))
        return None
    if not isinstance(component.get("version"), str) or not SEMVER.fullmatch(component["version"]):
        failures.append(_failure("component_version_invalid", f"{name} needs an exact semantic version"))
    if component.get("tag") != f"v{component.get('version')}":
        failures.append(_failure("component_tag_invalid", f"{name} tag must match its exact version"))
    if not isinstance(component.get("source_commit"), str) or not COMMIT.fullmatch(component["source_commit"]):
        failures.append(_failure("component_commit_invalid", f"{name} needs a 40-character source commit"))
    repository = component.get("repository")
    if not isinstance(repository, str) or not repository.startswith("https://github.com/wesleysimplicio/"):
        failures.append(_failure("component_repository_invalid", f"{name} repository is not approved"))
    schemas = component.get("schemas")
    if not isinstance(schemas, list) or not schemas or any(not isinstance(item, str) or not item for item in schemas):
        failures.append(_failure("component_schemas_invalid", f"{name} needs explicit schema capabilities"))
    entrypoint = component.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint.startswith("/"):
        failures.append(_failure("component_entrypoint_invalid", f"{name} entrypoint must be absolute"))
    compatibility = component.get("compatible_runtime")
    if not isinstance(compatibility, str) or not compatibility:
        failures.append(_failure("component_compatibility_invalid", f"{name} needs an explicit Runtime compatibility range"))
    skill_digest = component.get("skill_bundle_sha256")
    if not isinstance(skill_digest, str) or not SHA256.fullmatch(skill_digest):
        failures.append(_failure("component_skill_digest_invalid", f"{name} needs a skill or script bundle digest"))
    if component.get("revoked") is not False:
        failures.append(_failure("component_revoked", f"{name} must not be revoked"))
    return name


def verify_manifest(document: Any, bundle_dir: Path | None = None) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    try:
        root = _object(document, "manifest_invalid")
    except ValueError:
        return {"schema": REPORT_SCHEMA, "ready": False, "failures": [_failure("manifest_invalid", "manifest must be an object")]}

    if root.get("schema") != SCHEMA:
        failures.append(_failure("schema_invalid", f"expected {SCHEMA}"))
    public_key = root.get("signing_pubkey")
    if not isinstance(public_key, str) or not public_key:
        failures.append(_failure("signing_key_missing", "signing_pubkey is required"))

    composition = root.get("composition")
    if not isinstance(composition, dict):
        failures.append(_failure("composition_invalid", "composition must be an object"))
    else:
        digest = composition.get("runtime_release_manifest_sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            failures.append(_failure("runtime_manifest_digest_invalid", "Runtime release manifest digest is required"))
        lock_digest = composition.get("composition_lock_sha256")
        if not isinstance(lock_digest, str) or not SHA256.fullmatch(lock_digest):
            failures.append(_failure("composition_lock_invalid", "promoted composition lock digest is required"))
        if composition.get("runtime_slot") == composition.get("operator_slot"):
            failures.append(_failure("slot_identity_invalid", "Runtime and operator slots must be distinct"))
        for field in ("runtime_slot", "operator_slot"):
            value = composition.get(field)
            if not isinstance(value, str) or not value:
                failures.append(_failure("composition_field_missing", f"{field} is required"))
        for field in (
            "operator_bundle_sha256",
            "host_plugin_bundle_sha256",
            "rollback_composition_sha256",
        ):
            value = composition.get(field)
            if not isinstance(value, str) or not SHA256.fullmatch(value):
                failures.append(_failure("composition_digest_invalid", f"{field} is required"))

    components = root.get("components")
    names: list[str] = []
    if not isinstance(components, list):
        failures.append(_failure("components_invalid", "components must be an array"))
    else:
        for component in components:
            name = _validate_component(component, failures)
            if name is not None:
                names.append(name)
        if len(names) != len(set(names)):
            failures.append(_failure("component_duplicate", "component names must be unique"))
        missing = sorted(REQUIRED_COMPONENTS - set(names))
        extra = sorted(set(names) - REQUIRED_COMPONENTS)
        if missing:
            failures.append(_failure("component_missing", ", ".join(missing)))
        if extra:
            failures.append(_failure("component_unknown", ", ".join(extra)))

    policies = root.get("policies")
    if not isinstance(policies, dict):
        failures.append(_failure("policies_invalid", "policies must be an object"))
    else:
        for field, expected in REQUIRED_POLICIES.items():
            if policies.get(field) is not expected:
                failures.append(_failure("policy_invalid", f"{field} must be {str(expected).lower()}"))

    artifacts = root.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        failures.append(_failure("artifacts_invalid", "at least one signed artifact is required"))
    else:
        seen: set[str] = set()
        for index, raw in enumerate(artifacts):
            if not isinstance(raw, dict):
                failures.append(_failure("artifact_invalid", f"artifact {index} must be an object"))
                continue
            component = raw.get("component")
            if component not in REQUIRED_COMPONENTS:
                failures.append(_failure("artifact_component_invalid", f"artifact {index} component is invalid"))
            platform = raw.get("platform")
            if not _safe_filename(platform):
                failures.append(_failure("artifact_platform_invalid", f"artifact {index} platform is invalid"))
            python_abi = raw.get("python_abi")
            if python_abi is not None and not _safe_filename(python_abi):
                failures.append(_failure("artifact_python_abi_invalid", f"artifact {index} Python ABI is invalid"))
            filename = raw.get("filename")
            signature_file = raw.get("signature_file")
            sbom_file = raw.get("sbom_file")
            provenance_file = raw.get("provenance_file")
            filenames = (filename, signature_file, sbom_file, provenance_file)
            if any(not _safe_filename(item) for item in filenames):
                failures.append(_failure("artifact_filename_invalid", f"artifact {index} has an unsafe filename"))
                continue
            if len(set(filenames)) != len(filenames) or any(item in seen for item in filenames):
                failures.append(_failure("artifact_filename_duplicate", f"artifact {index} reuses a filename"))
            seen.update(filenames)
            digest = raw.get("sha256")
            signature = raw.get("signature")
            if not isinstance(digest, str) or not SHA256.fullmatch(digest):
                failures.append(_failure("artifact_digest_invalid", f"artifact {index} digest is invalid"))
                continue
            if not isinstance(signature, str) or not signature.startswith("ed25519:"):
                failures.append(_failure("artifact_signature_invalid", f"artifact {index} signature is missing"))
            elif isinstance(public_key, str):
                try:
                    if not verify_signature_for_digest(public_key, signature, digest):
                        failures.append(_failure("artifact_signature_invalid", f"artifact {index} signature does not verify"))
                except ValueError:
                    failures.append(_failure("artifact_signature_invalid", f"artifact {index} signature encoding is invalid"))
            if bundle_dir is not None:
                for item in filenames:
                    path = bundle_dir / item
                    if path.is_symlink() or not path.is_file():
                        failures.append(_failure("artifact_file_missing", str(item)))
                payload = bundle_dir / filename
                if payload.is_file() and not payload.is_symlink() and _sha256_file(payload) != digest:
                    failures.append(_failure("artifact_digest_mismatch", str(filename)))
                signature_path = bundle_dir / signature_file
                if signature_path.is_file() and not signature_path.is_symlink():
                    try:
                        sidecar = signature_path.read_text(encoding="utf-8").strip()
                    except (OSError, UnicodeError):
                        sidecar = ""
                    if sidecar != signature:
                        failures.append(_failure("signature_sidecar_mismatch", str(signature_file)))

        missing_artifacts = sorted(REQUIRED_COMPONENTS - {item.get("component") for item in artifacts if isinstance(item, dict)})
        if missing_artifacts:
            failures.append(_failure("component_artifact_missing", ", ".join(missing_artifacts)))
        if bundle_dir is not None and bundle_dir.is_dir():
            actual = {item.name for item in bundle_dir.iterdir() if item.is_file() or item.is_symlink()}
            extra = sorted(actual - seen)
            if extra:
                failures.append(_failure("bundle_file_unexpected", ", ".join(extra)))

    return {
        "schema": REPORT_SCHEMA,
        "ready": not failures,
        "components_verified": sorted(set(names)),
        "artifacts_verified": len(artifacts) if isinstance(artifacts, list) and not failures else 0,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = verify_manifest(document, args.bundle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report = {"schema": REPORT_SCHEMA, "ready": False, "failures": [_failure("manifest_read_failed", str(exc))]}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

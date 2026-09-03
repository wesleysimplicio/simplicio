from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_operator_bundle_manifest as verifier

PUBLIC_KEY = "2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok="
SIGNATURE = "ed25519:/Tt+wpY4VedOmsOJRPAaAz470OfD4QprLGnTed7QGkkWgyqLoeg2U/dr6PD3EWl4rvHLiok2UWALeDBvG9KmCQ=="
DIGEST = "12681adb6fa49bc2a5d39f8feca42baabe5d97b61cfdf40a5d452d890a8be83a"


def valid_manifest() -> dict:
    components = []
    artifacts = []
    for index, name in enumerate(sorted(verifier.REQUIRED_COMPONENTS)):
        version = "3.8.41" if name == "simplicio-runtime" else "1.2.3"
        components.append({
            "name": name,
            "version": version,
            "tag": f"v{version}",
            "source_commit": f"{index + 1:040x}",
            "repository": f"https://github.com/wesleysimplicio/{name}",
            "schemas": [f"{name}.contract/v1"],
            "entrypoint": f"/managed/operators/slot-b/{name}",
            "compatible_runtime": ">=3.8.41,<3.9.0",
            "skill_bundle_sha256": f"{index + 10:064x}",
            "revoked": False,
        })
        artifacts.append({
            "component": name,
            "platform": "any",
            "python_abi": "cp311",
            "filename": f"{name}.bin",
            "sha256": DIGEST,
            "signature": SIGNATURE,
            "signature_file": f"{name}.bin.sig",
            "sbom_file": f"{name}.bin.spdx.json",
            "provenance_file": f"{name}.bin.provenance.json",
        })
    return {
        "schema": verifier.SCHEMA,
        "signing_pubkey": PUBLIC_KEY,
        "composition": {
            "runtime_release_manifest_sha256": "a" * 64,
            "composition_lock_sha256": "b" * 64,
            "runtime_slot": "runtime-slot-b",
            "operator_slot": "operator-slot-b",
            "operator_bundle_sha256": "c" * 64,
            "host_plugin_bundle_sha256": "d" * 64,
            "rollback_composition_sha256": "e" * 64,
        },
        "components": components,
        "artifacts": artifacts,
        "policies": dict(verifier.REQUIRED_POLICIES),
    }


def failure_codes(report: dict) -> set[str]:
    return {item["code"] for item in report["failures"]}


def test_valid_signed_manifest_is_ready() -> None:
    report = verifier.verify_manifest(valid_manifest())
    assert report["ready"] is True
    assert report["components_verified"] == sorted(verifier.REQUIRED_COMPONENTS)


def test_unsigned_or_incomplete_component_fails_closed() -> None:
    manifest = valid_manifest()
    manifest["components"].pop()
    manifest["artifacts"][0]["signature"] = "unsigned"
    report = verifier.verify_manifest(manifest)
    assert report["ready"] is False
    assert {"component_missing", "artifact_signature_invalid"} <= failure_codes(report)


def test_security_policies_cannot_be_relaxed() -> None:
    manifest = valid_manifest()
    manifest["policies"]["native_loop_default"] = False
    manifest["policies"]["host_plugin_consent_required"] = False
    manifest["policies"]["hooks_provision_packages"] = True
    report = verifier.verify_manifest(manifest)
    assert report["ready"] is False
    assert "policy_invalid" in failure_codes(report)


def test_bundle_rejects_missing_extra_and_symlink_files(tmp_path: Path) -> None:
    manifest = valid_manifest()
    first = manifest["artifacts"][0]
    (tmp_path / first["filename"]).symlink_to(tmp_path / "outside")
    (tmp_path / "unexpected.whl").write_bytes(b"extra")
    report = verifier.verify_manifest(copy.deepcopy(manifest), tmp_path)
    assert report["ready"] is False
    assert {"artifact_file_missing", "bundle_file_unexpected"} <= failure_codes(report)


def test_component_entrypoints_must_be_absolute() -> None:
    manifest = valid_manifest()
    manifest["components"][0]["entrypoint"] = "ambient/simplicio-loop"
    report = verifier.verify_manifest(manifest)
    assert report["ready"] is False
    assert "component_entrypoint_invalid" in failure_codes(report)

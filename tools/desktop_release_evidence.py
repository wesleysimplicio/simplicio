"""Fail-closed validation for manually published Desktop release evidence.

The validator accepts only redacted evidence metadata. It never signs, notarizes,
uploads, or treats a Runtime sidecar digest as proof for the Desktop container.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


SCHEMA = "simplicio.desktop-release-evidence/v1"
PLATFORMS = ("macos-arm64", "macos-x64", "windows-x64", "linux-x64")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
UNSAFE_KEY = re.compile(r"(?:path|cwd|home|argv|secret|password|credential|authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|raw[_-]?(?:output|payload))", re.I)


class ReleaseEvidenceError(ValueError):
    """Raised when a release manifest cannot prove every required gate."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReleaseEvidenceError(f"{label}_invalid")
    return value


def _text(value: Any, label: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise ReleaseEvidenceError(f"{label}_invalid")
    return value


def _flag(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        raise ReleaseEvidenceError(f"{label}_invalid")


def _digest(value: Any, label: str) -> str:
    value = _text(value, label, 71)
    if not SHA256.fullmatch(value):
        raise ReleaseEvidenceError(f"{label}_invalid")
    return value


def _reject_unsafe(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str) or UNSAFE_KEY.search(key):
                raise ReleaseEvidenceError("release_evidence_sensitive_field")
            _reject_unsafe(child)
    elif isinstance(value, list):
        for child in value:
            _reject_unsafe(child)


def sha256_file(path: Path) -> str:
    """Return a file digest without exposing the path in any receipt."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_artifact(platform: str, raw: Any, artifact_root: Path | None) -> dict[str, Any]:
    artifact = _mapping(raw, f"{platform}_artifact")
    installer = _text(artifact.get("installer"), f"{platform}_installer", 128)
    if "/" in installer or "\\" in installer or installer in {".", ".."}:
        raise ReleaseEvidenceError(f"{platform}_installer_invalid")
    digest = _text(artifact.get("sha256"), f"{platform}_sha256", 64)
    if not HEX64.fullmatch(digest):
        raise ReleaseEvidenceError(f"{platform}_sha256_invalid")
    if artifact_root is not None:
        candidate = (artifact_root / installer).resolve()
        root = artifact_root.resolve()
        if root not in candidate.parents or not candidate.is_file():
            raise ReleaseEvidenceError(f"{platform}_installer_missing")
        if sha256_file(candidate) != digest:
            raise ReleaseEvidenceError(f"{platform}_installer_digest_mismatch")

    signature = _mapping(artifact.get("signature"), f"{platform}_signature")
    if signature.get("status") != "verified" or signature.get("algorithm") != "ed25519":
        raise ReleaseEvidenceError(f"{platform}_signature_unverified")
    _text(signature.get("key_id"), f"{platform}_signature_key", 128)

    for name in ("sbom", "provenance"):
        record = _mapping(artifact.get(name), f"{platform}_{name}")
        if record.get("status") != "attached":
            raise ReleaseEvidenceError(f"{platform}_{name}_missing")
        _text(record.get("digest"), f"{platform}_{name}_digest", 71)

    _digest(artifact.get("sidecar_digest"), f"{platform}_sidecar_digest")
    _flag(artifact.get("install_smoke"), True, f"{platform}_install_smoke")
    _flag(artifact.get("runtime_flow"), True, f"{platform}_runtime_flow")
    _flag(artifact.get("redacted"), True, f"{platform}_redacted")
    return {
        "installer": installer,
        "sha256": digest,
        "signature": {"status": "verified", "algorithm": "ed25519", "key_id": signature["key_id"]},
        "sbom": {"status": "attached", "digest": artifact["sbom"]["digest"]},
        "provenance": {"status": "attached", "digest": artifact["provenance"]["digest"]},
        "sidecar_digest": artifact["sidecar_digest"],
        "install_smoke": True,
        "runtime_flow": True,
        "redacted": True,
    }


def validate_release_manifest(document: Any, artifact_root: Path | None = None) -> dict[str, Any]:
    """Validate and return a normalized release manifest, or raise."""
    _reject_unsafe(document)
    raw = _mapping(document, "release_evidence")
    if raw.get("schema") != SCHEMA:
        raise ReleaseEvidenceError("release_evidence_schema_invalid")
    version = _text(raw.get("version"), "release_version", 64)
    if not SEMVER.fullmatch(version):
        raise ReleaseEvidenceError("release_version_invalid")
    tag = _text(raw.get("immutable_tag"), "immutable_tag", 128)
    if tag != f"v{version}":
        raise ReleaseEvidenceError("immutable_tag_invalid")
    _flag(raw.get("manual_only"), True, "manual_only")
    _flag(raw.get("actions_used"), False, "actions_used")
    _flag(raw.get("redacted"), True, "redacted")
    platforms = _mapping(raw.get("platforms"), "platforms")
    if set(platforms) != set(PLATFORMS):
        raise ReleaseEvidenceError("platform_matrix_incomplete")
    normalized = {
        "schema": SCHEMA,
        "version": version,
        "immutable_tag": tag,
        "manual_only": True,
        "actions_used": False,
        "redacted": True,
        "platforms": {platform: _verify_artifact(platform, platforms[platform], artifact_root) for platform in PLATFORMS},
    }
    return normalized


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) not in (1, 2):
        print("usage: verify_desktop_release.py MANIFEST.json [ARTIFACT_ROOT]", file=sys.stderr)
        return 2
    try:
        document = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
        root = Path(arguments[1]) if len(arguments) == 2 else None
        normalized = validate_release_manifest(document, root)
    except (OSError, json.JSONDecodeError, ReleaseEvidenceError) as error:
        print(json.dumps({"schema": SCHEMA, "status": "blocked", "reason": str(error)}))
        return 1
    print(json.dumps({"schema": SCHEMA, "status": "verified", "version": normalized["version"], "platforms": list(PLATFORMS)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

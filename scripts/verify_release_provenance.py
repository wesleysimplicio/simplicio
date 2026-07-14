#!/usr/bin/env python3
"""Fail closed when a release would mutate tag-bound artifact provenance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROVENANCE_FIELDS = ("artifact", "url", "sha256", "signature")
GENERATED_RELEASE_ASSETS = {"simplicio-update-manifest.json", "SHA256SUMS"}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def provenance_snapshot(manifest: dict) -> tuple[str, tuple[tuple[str, str, str, str], ...]]:
    version = str(manifest.get("version") or "").strip()
    if not version:
        raise ValueError("manifest version is missing")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("manifest artifacts must be a non-empty list")

    records: list[tuple[str, str, str, str]] = []
    names: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ValueError(f"manifest artifact {index} is not an object")
        values = tuple(str(artifact.get(field) or "").strip() for field in PROVENANCE_FIELDS)
        missing = [field for field, value in zip(PROVENANCE_FIELDS, values) if not value]
        if missing:
            raise ValueError(f"manifest artifact {index} is missing: {', '.join(missing)}")
        if values[0] in names:
            raise ValueError(f"manifest contains duplicate artifact name: {values[0]}")
        names.add(values[0])
        records.append(values)
    return version, tuple(sorted(records))


def compare_tag_provenance(working: dict, tagged: dict) -> list[str]:
    working_version, working_artifacts = provenance_snapshot(working)
    tagged_version, tagged_artifacts = provenance_snapshot(tagged)
    errors: list[str] = []
    if tagged_version != working_version:
        errors.append(
            f"tag manifest version {tagged_version} does not equal working manifest version {working_version}"
        )
    if tagged_artifacts != working_artifacts:
        errors.append("tag manifest artifact name/url/sha256/signature provenance differs from working manifest")
    return errors


def existing_asset_conflicts(working: dict, remote_release: dict) -> list[str]:
    _, artifacts = provenance_snapshot(working)
    declared_names = {record[0] for record in artifacts} | GENERATED_RELEASE_ASSETS
    assets = remote_release.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("remote release assets must be a list")
    existing_names = {
        str(asset.get("name") or "")
        for asset in assets
        if isinstance(asset, dict) and asset.get("name")
    }
    return sorted(declared_names & existing_names)


def verify(working: dict, tagged: dict, remote_release: dict | None = None) -> list[str]:
    errors = compare_tag_provenance(working, tagged)
    if remote_release is not None:
        conflicts = existing_asset_conflicts(working, remote_release)
        if conflicts:
            errors.append("immutable release already contains assets: " + ", ".join(conflicts))
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--working-manifest", type=Path, required=True)
    parser.add_argument("--tag-manifest", type=Path, required=True)
    parser.add_argument("--remote-release", type=Path)
    args = parser.parse_args(argv)
    try:
        working = load_json(args.working_manifest)
        tagged = load_json(args.tag_manifest)
        remote = load_json(args.remote_release) if args.remote_release else None
        errors = verify(working, tagged, remote)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"invalid release provenance input: {exc}"]
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print("release-provenance: PASS (tag and remote assets are immutable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

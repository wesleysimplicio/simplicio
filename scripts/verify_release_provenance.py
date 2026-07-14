#!/usr/bin/env python3
"""Plan immutable releases and verify bytes from a distinct staging origin."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

PROVENANCE_FIELDS = ("artifact", "url", "sha256", "signature")


@dataclass(frozen=True)
class ReleasePlan:
    mode: str
    errors: tuple[str, ...] = ()


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
        if Path(values[0]).name != values[0] or "/" in values[0] or "\\" in values[0]:
            raise ValueError(f"manifest artifact name is not a safe filename: {values[0]}")
        if len(values[2]) != 64 or any(character not in "0123456789abcdefABCDEF" for character in values[2]):
            raise ValueError(f"manifest artifact {values[0]} has invalid SHA256")
        if not values[3].startswith("ed25519:"):
            raise ValueError(f"manifest artifact {values[0]} lacks Ed25519 signature metadata")
        names.add(values[0])
        records.append((values[0], values[1], values[2].lower(), values[3]))
    return version, tuple(sorted(records))


def validate_staging_base_url(base_url: str, version: str, repository: str) -> list[str]:
    parsed = urlparse(base_url)
    errors: list[str] = []
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append("artifact_base_url must be absolute HTTPS")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        errors.append("artifact_base_url must not contain credentials, query, or fragment")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if f"v{version}" not in segments:
        errors.append(f"artifact_base_url must contain immutable version segment v{version}")
    target = f"https://github.com/{repository}/releases/download/v{version}".rstrip("/").lower()
    normalized = base_url.rstrip("/").lower()
    if normalized == target or normalized.startswith(target + "/"):
        errors.append("artifact_base_url must be distinct from the target release URL")
    return errors


def target_url_errors(working: dict, repository: str) -> list[str]:
    version, artifacts = provenance_snapshot(working)
    errors: list[str] = []
    for name, url, _, _ in artifacts:
        expected = f"https://github.com/{repository}/releases/download/v{version}/{name}"
        if url != expected:
            errors.append(f"target release URL mismatch for {name}")
    return errors


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


def remote_exists(remote_release: dict) -> bool:
    explicit = remote_release.get("exists")
    if isinstance(explicit, bool):
        return explicit
    return bool(remote_release.get("id") or remote_release.get("tag_name"))


def remote_digest_errors(working: dict, remote_release: dict) -> list[str]:
    _, artifacts = provenance_snapshot(working)
    assets = remote_release.get("assets")
    if not isinstance(assets, list):
        return ["remote release assets must be a list"]
    by_name: dict[str, list[dict]] = {}
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name"):
            by_name.setdefault(str(asset["name"]), []).append(asset)
    errors: list[str] = []
    for name, _, sha256, _ in artifacts:
        matches = by_name.get(name, [])
        if len(matches) != 1:
            errors.append(f"remote release must contain exactly one {name} asset")
            continue
        digest = str(matches[0].get("digest") or "").lower()
        if digest != f"sha256:{sha256}":
            errors.append(f"remote asset digest mismatch for {name}")
    return errors


def plan_release(
    working: dict,
    *,
    tag_exists: bool,
    tagged: dict | None,
    remote_release: dict,
    artifact_base_url: str,
    repository: str,
) -> ReleasePlan:
    version, _ = provenance_snapshot(working)
    errors = validate_staging_base_url(artifact_base_url, version, repository)
    errors.extend(target_url_errors(working, repository))
    release_exists = remote_exists(remote_release)
    if tag_exists:
        if tagged is None:
            errors.append("existing tag is missing its manifest")
        else:
            errors.extend(compare_tag_provenance(working, tagged))
        if not release_exists:
            errors.append("existing tag has no corresponding release; refusing mutation")
        else:
            errors.extend(remote_digest_errors(working, remote_release))
        return ReleasePlan("blocked" if errors else "idempotent", tuple(errors))
    if tagged is not None:
        errors.append("tag manifest was supplied for a tag reported as absent")
    if release_exists:
        errors.append("remote release exists while target tag is absent")
    return ReleasePlan("blocked" if errors else "publish", tuple(errors))


def verify_staged_files(working: dict, staging_dir: Path) -> list[str]:
    _, artifacts = provenance_snapshot(working)
    errors: list[str] = []
    for name, _, expected_sha256, _ in artifacts:
        path = staging_dir / name
        if not path.is_file():
            errors.append(f"staged artifact is missing: {name}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_sha256:
            errors.append(f"staged artifact digest mismatch for {name}")
    return errors


def write_output(path: Path | None, mode: str) -> None:
    if path:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"mode={mode}\n")


def plan_command(args: argparse.Namespace) -> int:
    try:
        working = load_json(args.working_manifest)
        tagged = load_json(args.tag_manifest) if args.tag_exists else None
        remote = load_json(args.remote_release)
        plan = plan_release(
            working,
            tag_exists=args.tag_exists,
            tagged=tagged,
            remote_release=remote,
            artifact_base_url=args.artifact_base_url,
            repository=args.repository,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        plan = ReleasePlan("blocked", (f"invalid release provenance input: {exc}",))
    write_output(args.github_output, plan.mode)
    if plan.errors:
        for error in plan.errors:
            print(f"[ERROR] {error}")
        return 1
    print(f"release-provenance: PASS mode={plan.mode}")
    return 0


def staged_command(args: argparse.Namespace) -> int:
    try:
        errors = verify_staged_files(load_json(args.working_manifest), args.staging_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"invalid staged provenance input: {exc}"]
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1
    print("release-provenance: staged artifact digests PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--working-manifest", type=Path, required=True)
    plan.add_argument("--tag-exists", action="store_true")
    plan.add_argument("--tag-manifest", type=Path, required=True)
    plan.add_argument("--remote-release", type=Path, required=True)
    plan.add_argument("--artifact-base-url", required=True)
    plan.add_argument("--repository", required=True)
    plan.add_argument("--github-output", type=Path)
    plan.set_defaults(handler=plan_command)
    staged = subparsers.add_parser("verify-staged")
    staged.add_argument("--working-manifest", type=Path, required=True)
    staged.add_argument("--staging-dir", type=Path, required=True)
    staged.set_defaults(handler=staged_command)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Plan immutable releases and verify bytes from a distinct staging origin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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


def append_outputs(path: Path | None, values: dict[str, str]) -> None:
    if path:
        with path.open("a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def collect_release_state(
    working_manifest: Path,
    repository: str,
    token: str,
    state_dir: Path,
    github_output: Path | None,
    *,
    runner=subprocess.run,
    opener=urlopen,
) -> bool:
    if not repository or not token:
        raise ValueError("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    working = load_json(working_manifest)
    version, _ = provenance_snapshot(working)
    tag = f"v{version}"
    state_dir.mkdir(parents=True, exist_ok=True)
    tag_result = runner(["git", "tag", "--list", tag], check=True, capture_output=True, text=True)
    tag_exists = tag_result.stdout.strip() == tag
    tag_manifest_path = state_dir / "tag-manifest.json"
    if tag_exists:
        tagged = runner(
            ["git", "show", f"{tag}:simplicio-update-manifest.json"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        tag_manifest_path.write_text(tagged, encoding="utf-8")
    else:
        tag_manifest_path.write_text("{}\n", encoding="utf-8")
    request = Request(
        f"https://api.github.com/repos/{repository}/releases/tags/{tag}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request) as response:
            remote = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code != 404:
            raise
        exc.close()
        remote = {"exists": False, "assets": []}
    (state_dir / "remote-release.json").write_text(json.dumps(remote, indent=2) + "\n", encoding="utf-8")
    append_outputs(github_output, {"version": version, "tag_exists": str(tag_exists).lower()})
    return tag_exists


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


def exact_directory_errors(directory: Path, expected_names: set[str], label: str) -> list[str]:
    errors: list[str] = []
    if directory.is_symlink() or not directory.is_dir():
        return [f"{label} directory is missing or not a real directory"]
    entries = list(directory.iterdir())
    actual_names = {entry.name for entry in entries}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing:
        errors.append(f"{label} set is missing: {', '.join(missing)}")
    if extra:
        errors.append(f"{label} set has unmanifested entries: {', '.join(extra)}")
    for entry in entries:
        if entry.name in expected_names and (entry.is_symlink() or not entry.is_file()):
            errors.append(f"{label} entry is not a regular file: {entry.name}")
    return errors


def verify_staged_files(working: dict, staging_dir: Path) -> list[str]:
    _, artifacts = provenance_snapshot(working)
    expected_names = {record[0] for record in artifacts}
    errors = exact_directory_errors(staging_dir, expected_names, "staging")
    if errors:
        return errors
    for name, _, expected_sha256, _ in artifacts:
        path = staging_dir / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected_sha256:
            errors.append(f"staged artifact digest mismatch for {name}")
    return errors


def verify_publish_files(working: dict, staging_dir: Path) -> list[str]:
    _, artifacts = provenance_snapshot(working)
    expected_names = {record[0] for record in artifacts} | {
        "simplicio-update-manifest.json",
        "SHA256SUMS",
    }
    return exact_directory_errors(staging_dir, expected_names, "publish")


def download_staged_files(
    working: dict,
    artifact_base_url: str,
    repository: str,
    staging_dir: Path,
    *,
    opener=urlopen,
) -> None:
    version, artifacts = provenance_snapshot(working)
    errors = validate_staging_base_url(artifact_base_url, version, repository)
    errors.extend(target_url_errors(working, repository))
    if errors:
        raise ValueError("; ".join(errors))
    if staging_dir.exists():
        if staging_dir.is_symlink() or not staging_dir.is_dir():
            raise ValueError("staging destination must be a real directory")
        stale = sorted(entry.name for entry in staging_dir.iterdir())
        if stale:
            raise ValueError("staging destination is not empty: " + ", ".join(stale))
    else:
        staging_dir.mkdir(parents=True)
    base = artifact_base_url.rstrip("/")
    for name, _, _, _ in artifacts:
        with opener(Request(f"{base}/{name}")) as response:
            (staging_dir / name).write_bytes(response.read())


def generate_release_metadata(working_manifest: Path, staging_dir: Path) -> None:
    working = load_json(working_manifest)
    _, artifacts = provenance_snapshot(working)
    errors = verify_staged_files(working, staging_dir)
    if errors:
        raise ValueError("; ".join(errors))
    lines = [
        f"{hashlib.sha256((staging_dir / name).read_bytes()).hexdigest()} *{name}"
        for name, _, _, _ in artifacts
    ]
    shutil.copy2(working_manifest, staging_dir / "simplicio-update-manifest.json")
    manifest_path = staging_dir / "simplicio-update-manifest.json"
    lines.append(f"{hashlib.sha256(manifest_path.read_bytes()).hexdigest()} *{manifest_path.name}")
    (staging_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="ascii")
    final_errors = verify_publish_files(working, staging_dir)
    if final_errors:
        raise ValueError("; ".join(final_errors))


def write_output(path: Path | None, mode: str) -> None:
    append_outputs(path, {"mode": mode})


def state_command(args: argparse.Namespace) -> int:
    try:
        tag_exists = collect_release_state(
            args.working_manifest,
            args.repository,
            args.github_token,
            args.state_dir,
            args.github_output,
        )
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, HTTPError) as exc:
        print(f"[ERROR] release state collection failed: {exc}")
        return 1
    print(f"release-provenance: state PASS tag_exists={str(tag_exists).lower()}")
    return 0


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


def download_command(args: argparse.Namespace) -> int:
    try:
        download_staged_files(
            load_json(args.working_manifest),
            args.artifact_base_url,
            args.repository,
            args.staging_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError, HTTPError) as exc:
        print(f"[ERROR] staged artifact download failed: {exc}")
        return 1
    print("release-provenance: staging download PASS")
    return 0


def metadata_command(args: argparse.Namespace) -> int:
    try:
        generate_release_metadata(args.working_manifest, args.staging_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] release metadata generation failed: {exc}")
        return 1
    print("release-provenance: metadata PASS")
    return 0


def environment_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    state = subparsers.add_parser("state")
    state.add_argument("--working-manifest", type=Path, default=Path("simplicio-update-manifest.json"))
    state.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    state.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN", ""))
    state.add_argument("--state-dir", type=Path, default=Path(".release"))
    state.add_argument("--github-output", type=Path, default=environment_path("GITHUB_OUTPUT"))
    state.set_defaults(handler=state_command)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--working-manifest", type=Path, default=Path("simplicio-update-manifest.json"))
    plan.add_argument("--tag-exists", action="store_true", default=os.environ.get("TAG_EXISTS", "").lower() == "true")
    plan.add_argument("--tag-manifest", type=Path, default=Path(".release/tag-manifest.json"))
    plan.add_argument("--remote-release", type=Path, default=Path(".release/remote-release.json"))
    plan.add_argument("--artifact-base-url", default=os.environ.get("ARTIFACT_BASE_URL", ""))
    plan.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    plan.add_argument("--github-output", type=Path, default=environment_path("GITHUB_OUTPUT"))
    plan.set_defaults(handler=plan_command)
    download = subparsers.add_parser("download")
    download.add_argument("--working-manifest", type=Path, default=Path("simplicio-update-manifest.json"))
    download.add_argument("--artifact-base-url", default=os.environ.get("ARTIFACT_BASE_URL", ""))
    download.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    download.add_argument("--staging-dir", type=Path, default=Path("dist"))
    download.set_defaults(handler=download_command)
    staged = subparsers.add_parser("verify-staged")
    staged.add_argument("--working-manifest", type=Path, default=Path("simplicio-update-manifest.json"))
    staged.add_argument("--staging-dir", type=Path, default=Path("dist"))
    staged.set_defaults(handler=staged_command)
    metadata = subparsers.add_parser("metadata")
    metadata.add_argument("--working-manifest", type=Path, default=Path("simplicio-update-manifest.json"))
    metadata.add_argument("--staging-dir", type=Path, default=Path("dist"))
    metadata.set_defaults(handler=metadata_command)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

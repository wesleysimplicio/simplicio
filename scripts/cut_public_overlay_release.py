#!/usr/bin/env python3.11
"""Cut a public product release that reuses the last signed Runtime binary.

Use this when the product version moves (optional modules, docs, plugin pin)
but official-runtime cannot be rebuilt and Ed25519-signed on this host.

The installer keeps fail-closed verification: same signed bytes, same
checksums, same signatures. Only the GitHub tag / manifest URLs change.

  python3 scripts/cut_public_overlay_release.py \\
      --version 3.8.49 --runtime-from v3.8.47 \\
      --rewrite-manifest --apply-metadata

  python3 scripts/cut_public_overlay_release.py \\
      --version 3.8.49 --runtime-from v3.8.47 \\
      --bundle-dir /tmp/bundle-3.8.49 --download --upload \\
      --modules-dir /tmp/dist/modules-3.8.49

Does not invoke GitHub Actions. Does not overwrite signed Runtime bytes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import publish_release_local as pub  # noqa: E402

ASSETS = pub.ASSETS
META = pub.META_ASSETS
SIDECARS = (".sig", ".spdx.json", ".provenance.json")


def tag_for(version: str) -> str:
    return version if version.startswith("v") else "v" + version


def version_of(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def rewrite_manifest(
    manifest: dict,
    *,
    version: str,
    runtime_from: str,
    source_commit: str,
    generated_at: str | None = None,
) -> dict:
    """Retarget URLs/version; keep sha256 + Ed25519 signatures of signed bytes."""
    tag = tag_for(version)
    from_tag = tag_for(runtime_from)
    from_version = version_of(from_tag)
    out = json.loads(json.dumps(manifest))
    out["version"] = version
    out["release_tag"] = tag
    out["generated_at"] = generated_at or dt.datetime.now(dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    out["commit"] = source_commit
    source = dict(out.get("source") or {})
    source["version"] = "Cargo.toml"
    source["tag"] = tag
    source["commit"] = source_commit
    out["source"] = source
    out["runtime_binary"] = {
        "schema": "simplicio.runtime-binary-carry-forward/v1",
        "version": from_version,
        "tag": from_tag,
        "bytes": "unchanged-signed",
        "reason": "official-runtime not rebuilt; signed installer assets carried forward",
    }
    artifacts = []
    for artifact in out.get("artifacts") or []:
        item = dict(artifact)
        name = str(item.get("artifact") or "")
        item["url"] = (
            f"https://github.com/{pub.PUBLIC_REPOSITORY}/releases/download/{tag}/{name}"
        )
        artifacts.append(item)
    out["artifacts"] = artifacts
    return out


def download_signed_runtime(source_tag: str, bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    names = list(META)
    for asset in ASSETS:
        names.append(asset)
        for suffix in SIDECARS:
            names.append(asset + suffix)
    subprocess.run(
        [
            "gh",
            "release",
            "download",
            tag_for(source_tag),
            "--repo",
            pub.PUBLIC_REPOSITORY,
            "--dir",
            str(bundle),
            *[item for name in names for item in ("--pattern", name)],
        ],
        check=True,
        cwd=ROOT,
    )


def write_rewritten_manifest(bundle: Path, version: str, runtime_from: str, source_commit: str) -> Path:
    source = bundle / "simplicio-update-manifest.json"
    if not source.is_file():
        source = ROOT / "simplicio-update-manifest.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    rewritten = rewrite_manifest(
        manifest,
        version=version,
        runtime_from=runtime_from,
        source_commit=source_commit,
    )
    dest = bundle / "simplicio-update-manifest.json"
    dest.write_text(json.dumps(rewritten, indent=2) + "\n", encoding="utf-8")
    repo_manifest = ROOT / "simplicio-update-manifest.json"
    shutil.copy2(dest, repo_manifest)
    return dest


def apply_metadata(version: str, source_commit: str) -> list[Path]:
    tag = tag_for(version)
    changed = pub.update_public_metadata(tag, version, source_commit)
    changed.extend(pub.prepare_package(version))
    return changed


def upload_release(version: str, bundle: Path, modules_dir: Path | None, notes: str) -> None:
    tag = tag_for(version)
    files: list[str] = []
    for name in META:
        files.append(str(bundle / name))
    for asset in ASSETS:
        files.append(str(bundle / asset))
        for suffix in SIDECARS:
            files.append(str(bundle / (asset + suffix)))
    if modules_dir:
        for path in sorted(modules_dir.iterdir()):
            if path.is_file() and path.suffix != ".zip":
                files.append(str(path))
        zip_path = modules_dir / f"simplicio-modules-{version}.zip"
        if zip_path.is_file():
            files.append(str(zip_path))
    existing = subprocess.run(
        ["gh", "release", "view", tag, "--repo", pub.PUBLIC_REPOSITORY],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if existing.returncode != 0:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag,
                *files,
                "--repo",
                pub.PUBLIC_REPOSITORY,
                "--title",
                f"Simplicio v{version}",
                "--notes",
                notes,
            ],
            check=True,
            cwd=ROOT,
        )
    else:
        subprocess.run(
            [
                "gh",
                "release",
                "upload",
                tag,
                *files,
                "--repo",
                pub.PUBLIC_REPOSITORY,
                "--clobber",
            ],
            check=True,
            cwd=ROOT,
        )
        subprocess.run(
            [
                "gh",
                "release",
                "edit",
                tag,
                "--repo",
                pub.PUBLIC_REPOSITORY,
                "--prerelease=false",
                "--latest",
                "--title",
                f"Simplicio v{version}",
                "--notes",
                notes,
            ],
            check=True,
            cwd=ROOT,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--runtime-from", required=True, help="last signed Runtime tag, e.g. v3.8.47")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--bundle-dir", default="")
    parser.add_argument("--modules-dir", default="")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--rewrite-manifest", action="store_true")
    parser.add_argument("--apply-metadata", action="store_true")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--notes", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = version_of(args.version)
    runtime_from = args.runtime_from
    source_commit = args.source_commit.strip()
    if not source_commit:
        source_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    bundle = Path(args.bundle_dir) if args.bundle_dir else ROOT / "dist" / f"overlay-{version}"
    if args.download:
        download_signed_runtime(runtime_from, bundle)
    if args.rewrite_manifest:
        write_rewritten_manifest(bundle, version, runtime_from, source_commit)
    if args.apply_metadata:
        apply_metadata(version, source_commit)
    if args.upload:
        notes = args.notes or (
            f"Public v{version}. Signed Runtime bytes carried forward from "
            f"{tag_for(runtime_from)}. Optional modules attached when present. "
            "No GitHub Actions."
        )
        modules = Path(args.modules_dir) if args.modules_dir else None
        upload_release(version, bundle, modules, notes)
    print(f"overlay {version} runtime-from {tag_for(runtime_from)} commit {source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Publish one already-built Simplicio bundle from the public repository only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REPOSITORY = "wesleysimplicio/simplicio"
PACKAGE_ROOT = ROOT / "pypi/simplicio"
ASSETS = (
    "simplicio-macos-arm64",
    "simplicio-macos-x64",
    "simplicio-linux-x64",
    "simplicio-windows-x64.exe",
)
META_ASSETS = ("SHA256SUMS", "simplicio-update-manifest.json")


class PublishError(RuntimeError):
    pass


def run(command: list[str], *, cwd: Path = ROOT, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublishError("command could not complete: " + " ".join(command[:4])) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-1600:].strip()
        raise PublishError("%s failed: %s" % (" ".join(command[:4]), detail))
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_version(value: str) -> tuple[str, str]:
    tag = value.strip()
    if not tag.startswith("v"):
        tag = "v" + tag
    if re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) is None:
        raise PublishError("version must be vMAJOR.MINOR.PATCH")
    return tag, tag[1:]


def required_bundle_files() -> list[str]:
    files = list(META_ASSETS)
    for asset in ASSETS:
        files.extend((asset, asset + ".sig", asset + ".spdx.json", asset + ".provenance.json"))
    return files


def verify_bundle(bundle: Path, tag: str, version: str, source_commit: str) -> dict:
    if not bundle.is_dir():
        raise PublishError("release bundle does not exist: %s" % bundle)
    missing = [name for name in required_bundle_files() if not (bundle / name).is_file()]
    if missing:
        raise PublishError("release bundle is missing: " + ", ".join(missing))

    manifest = json.loads((bundle / "simplicio-update-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != version or manifest.get("release_tag") != tag:
        raise PublishError("manifest version/tag mismatch")
    if manifest.get("repository") != PUBLIC_REPOSITORY:
        raise PublishError("manifest repository mismatch")
    if manifest.get("commit") != source_commit:
        raise PublishError("manifest source commit mismatch")
    public_key = str(manifest.get("signing_pubkey") or "")
    if not public_key:
        raise PublishError("manifest signing key is missing")

    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from verify_ed25519 import verify_signature_for_digest

    records = manifest.get("artifacts")
    if not isinstance(records, list) or len(records) != 4:
        raise PublishError("manifest must contain exactly four artifacts")
    expected_targets = {"macos-arm64", "macos-x64", "linux-x64", "windows-x64"}
    if {str(item.get("target")) for item in records if isinstance(item, dict)} != expected_targets:
        raise PublishError("manifest target set mismatch")

    verified = []
    for record in records:
        asset = str(record.get("artifact") or "")
        if asset not in ASSETS:
            raise PublishError("unexpected manifest artifact: %s" % asset)
        path = bundle / asset
        digest = sha256(path)
        signature = (bundle / (asset + ".sig")).read_text(encoding="utf-8").strip()
        if record.get("sha256") != digest or record.get("size") != path.stat().st_size:
            raise PublishError("manifest identity mismatch: %s" % asset)
        if record.get("signature") != signature:
            raise PublishError("signature sidecar mismatch: %s" % asset)
        if not verify_signature_for_digest(public_key, signature, digest):
            raise PublishError("Ed25519 verification failed: %s" % asset)
        for suffix in (".spdx.json", ".provenance.json"):
            json.loads((bundle / (asset + suffix)).read_text(encoding="utf-8"))
        verified.append({"asset": asset, "sha256": digest, "size": path.stat().st_size})
    return {"version": version, "source_commit": source_commit, "artifacts": verified}


def public_preflight(tag: str, version: str, *, require_clean: bool) -> None:
    if run(["git", "branch", "--show-current"]).stdout.strip() != "master":
        raise PublishError("public repository must be on master")
    if "wesleysimplicio/simplicio" not in run(["git", "remote", "get-url", "origin"]).stdout.strip():
        raise PublishError("origin is not the public distribution repository")
    with (PACKAGE_ROOT / "pyproject.toml").open("rb") as handle:
        package = tomllib.load(handle)
    if package.get("project", {}).get("name") != "simplicio-installer":
        raise PublishError("public package identity mismatch")
    if require_clean and run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip():
        raise PublishError("public tracked worktree must be clean before publication")
    if run(["git", "ls-remote", "--tags", "origin", "refs/tags/" + tag]).stdout.strip():
        raise PublishError("public tag already exists: " + tag)
    run(["gh", "auth", "status"], timeout=60)
    existing = subprocess.run(
        ["gh", "release", "view", tag, "--repo", PUBLIC_REPOSITORY],
        cwd=ROOT, capture_output=True, text=True, timeout=60, check=False
    )
    if existing.returncode == 0:
        raise PublishError("public release already exists: " + tag)
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/simplicio-installer/json", timeout=30) as response:
            releases = json.load(response).get("releases", {})
    except Exception as exc:
        raise PublishError("could not verify current PyPI project state") from exc
    if version in releases:
        raise PublishError("PyPI version already exists: " + version)


def update_public_metadata(tag: str, version: str, source_commit: str) -> list[Path]:
    changed: list[Path] = []
    version_file = ROOT / "version.txt"
    version_file.write_text(version + "\n", encoding="utf-8")
    changed.append(version_file)

    version_doc = ROOT / "VERSION.md"
    text = version_doc.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^## Runtime snapshot: v[0-9]+\.[0-9]+\.[0-9]+$", "## Runtime snapshot: " + tag, text)
    text = re.sub(r"(?m)^## Current Version: v[0-9]+\.[0-9]+\.[0-9]+$", "## Current Version: " + tag, text)
    text = re.sub(
        r"(?m)^  " + chr(96) + r"[0-9a-f]{40}" + chr(96),
        "  " + chr(96) + source_commit + chr(96),
        text,
        count=1,
    )
    version_doc.write_text(text, encoding="utf-8")
    changed.append(version_doc)

    for relative in ("README.md", "MCP-CONNECT.md"):
        path = ROOT / relative
        body = path.read_text(encoding="utf-8")
        body = re.sub(
            r"SIMPLICIO_CODEX_HOOK_REF=v[0-9]+\.[0-9]+\.[0-9]+",
            "SIMPLICIO_CODEX_HOOK_REF=" + tag,
            body,
        )
        path.write_text(body, encoding="utf-8")
        changed.append(path)
    return changed


def stage_bundle(bundle: Path) -> list[Path]:
    staged = []
    for name in required_bundle_files():
        destination = ROOT / name
        shutil.copy2(bundle / name, destination)
        staged.append(destination)
    return staged


def prepare_package(version: str) -> list[Path]:
    run([
        sys.executable,
        str(ROOT / "scripts/prepare_pypi_release.py"),
        "--version", version,
        "--manifest", str(ROOT / "simplicio-update-manifest.json"),
        "--package-root", str(PACKAGE_ROOT),
    ])
    return [
        PACKAGE_ROOT / "pyproject.toml",
        PACKAGE_ROOT / "simplicio/__init__.py",
        PACKAGE_ROOT / "simplicio/__main__.py",
    ]


def build_wheel(output: Path, version: str) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "build", "--wheel", "--outdir", str(output), str(PACKAGE_ROOT)])
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise PublishError("expected exactly one wheel, found %d" % len(wheels))
    wheel = wheels[0]
    if version not in wheel.name:
        raise PublishError("wheel filename does not contain release version")
    run([sys.executable, "-m", "twine", "check", str(wheel)])
    return wheel


def wheel_help_smoke(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="simplicio-wheel-smoke-") as raw:
        environment = Path(raw) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        launcher = environment / ("Scripts/simplicio.exe" if os.name == "nt" else "bin/simplicio")
        run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
        run([str(launcher), "--help"])


def commit_public(paths: list[Path], tag: str, source_commit: str) -> str:
    relative = sorted({str(path.relative_to(ROOT)) for path in paths})
    run(["git", "add", "--", *relative])
    run(["git", "-c", "core.whitespace=cr-at-eol", "diff", "--cached", "--check"])
    run([
        "git", "commit", "-m", "release(public): publish signed Runtime %s" % tag,
        "-m", "Source commit: " + source_commit,
    ])
    commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    run(["git", "push", "origin", "master"])
    run(["git", "tag", tag])
    run(["git", "push", "origin", "refs/tags/" + tag])
    return commit


def create_public_release(tag: str, bundle: Path) -> None:
    run([
        "gh", "release", "create", tag,
        *[str(bundle / name) for name in required_bundle_files()],
        "--repo", PUBLIC_REPOSITORY,
        "--verify-tag",
        "--title", "Simplicio Runtime " + tag,
        "--notes", "Signed public Runtime release %s built and verified locally." % tag,
    ], timeout=3600)


def wait_for_pypi(version: str) -> dict:
    for _ in range(30):
        with urllib.request.urlopen("https://pypi.org/pypi/simplicio-installer/json", timeout=30) as response:
            payload = json.load(response)
        files = payload.get("releases", {}).get(version, [])
        if files:
            if len(files) != 1 or files[0].get("packagetype") != "bdist_wheel":
                raise PublishError("PyPI release is not exactly one wheel")
            return {
                "filename": files[0].get("filename"),
                "sha256": files[0].get("digests", {}).get("sha256"),
            }
        time.sleep(4)
    raise PublishError("PyPI version did not become visible: " + version)


def publish(bundle: Path, tag: str, version: str, source_commit: str) -> dict:
    public_preflight(tag, version, require_clean=True)
    bundle_receipt = verify_bundle(bundle, tag, version, source_commit)
    changed = stage_bundle(bundle)
    changed.extend(update_public_metadata(tag, version, source_commit))
    changed.extend(prepare_package(version))

    run([sys.executable, str(ROOT / "scripts/verify_distribution_consistency.py")])
    run([
        sys.executable, "-m", "pytest", "-q",
        "tests/test_codex_integration_cli.py",
        "tests/test_release_local_contract.py",
    ])
    run([str(bundle / "simplicio-macos-arm64"), "version", "--json"])
    if (ROOT / "scripts/verify_mcp_tools.py").is_file():
        run([
            sys.executable,
            str(ROOT / "scripts/verify_mcp_tools.py"),
            str(bundle / "simplicio-macos-arm64"),
        ])

    with tempfile.TemporaryDirectory(prefix="simplicio-public-wheel-") as raw:
        wheel = build_wheel(Path(raw), version)
        wheel_help_smoke(wheel)
        public_commit = commit_public(changed, tag, source_commit)
        create_public_release(tag, bundle)

        terminal = run([
            sys.executable,
            str(ROOT / "scripts/release_install_smoke.py"),
            "--version", version, "--terminal", "--json",
        ], timeout=900)
        run([sys.executable, "-m", "twine", "upload", "--non-interactive", str(wheel)], timeout=900)
        pypi = wait_for_pypi(version)
        package = run([
            sys.executable,
            str(ROOT / "scripts/release_install_smoke.py"),
            "--version", version, "--pypi", "--json",
        ], timeout=1200)
        remote = run([
            sys.executable,
            str(ROOT / "scripts/post_release_smoke.py"),
            "--repo", PUBLIC_REPOSITORY,
            "--version", tag,
            "--execute", "--json",
        ], timeout=1200)

    return {
        "schema": "simplicio.local-publication/v1",
        "status": "verified",
        "version": version,
        "tag": tag,
        "source_commit": source_commit,
        "public_commit": public_commit,
        "bundle": bundle_receipt,
        "terminal_install": json.loads(terminal.stdout),
        "pypi": pypi,
        "pypi_install": json.loads(package.stdout),
        "remote_release": json.loads(remote.stdout),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    tag, version = normalize_version(args.version)
    if re.fullmatch(r"[0-9a-f]{40}", args.source_commit) is None:
        raise PublishError("source commit must be a full SHA-1")
    public_preflight(tag, version, require_clean=args.publish)
    if args.check_only:
        receipt = {
            "schema": "simplicio.local-publication-preflight/v1",
            "status": "ready",
            "bundle": "ready" if args.bundle.is_dir() else "build-required",
            "version": version,
        }
    else:
        receipt = publish(args.bundle.resolve(), tag, version, args.source_commit)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublishError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)

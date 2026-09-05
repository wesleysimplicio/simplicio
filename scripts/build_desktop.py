#!/usr/bin/env python3
"""Build the native Simplicio Desktop package from one verified Runtime asset.

This is the manual, local release path for issue #345.  It deliberately does
not publish or mutate GitHub/PyPI.  The Runtime sidecar is staged into the
Tauri input directory, verified against the checked-in release manifest, and
then bundled by the local Tauri CLI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "apps" / "desktop"
TAURI = DESKTOP / "src-tauri"
VERSION_FILE = ROOT / "version.txt"
MANIFEST_FILE = ROOT / "simplicio-update-manifest.json"
PACKAGE_FILE = DESKTOP / "package.json"
TAURI_CONFIG = TAURI / "tauri.conf.json"
CARGO_MANIFEST = TAURI / "Cargo.toml"
SIDECAR_NAME = "simplicio"


class BuildError(RuntimeError):
    """A fail-closed local package error."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildError(f"cannot read JSON contract: {path}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"JSON contract must be an object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_output(command: list[str], *, cwd: Path | None = None, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError("command could not complete: " + " ".join(command)) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-800:].strip()
        raise BuildError(f"command failed ({result.returncode}): {' '.join(command)}: {detail}")
    return result


def native_target() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    if system != "Darwin":
        raise BuildError(f"issue #345 is a native macOS build; host is {system}/{machine}")
    if machine in {"arm64", "aarch64"}:
        return "macos-arm64", "aarch64-apple-darwin"
    if machine in {"x86_64", "amd64"}:
        return "macos-x64", "x86_64-apple-darwin"
    raise BuildError(f"unsupported native macOS architecture: {machine}")


def source_versions() -> tuple[str, dict[str, Any], str, str]:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    package = load_json(PACKAGE_FILE)
    tauri = load_json(TAURI_CONFIG)
    cargo = CARGO_MANIFEST.read_text(encoding="utf-8")
    cargo_version = next(
        (line.split("=", 1)[1].strip().strip('"') for line in cargo.splitlines() if line.startswith("version =")),
        "",
    )
    versions = {
        "version.txt": version,
        "apps/desktop/package.json": str(package.get("version", "")),
        "apps/desktop/src-tauri/tauri.conf.json": str(tauri.get("version", "")),
        "apps/desktop/src-tauri/Cargo.toml": cargo_version,
    }
    if not version or any(value != version for value in versions.values()):
        raise BuildError("Desktop version sources disagree: " + json.dumps(versions, sort_keys=True))
    return version, package, tauri, cargo_version


def manifest_record(version: str, target_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_json(MANIFEST_FILE)
    if str(manifest.get("version")) != version or str(manifest.get("release_tag")) != "v" + version:
        raise BuildError("release manifest is not bound to Desktop version " + version)
    records = manifest.get("artifacts")
    if not isinstance(records, list):
        raise BuildError("release manifest has no artifact records")
    record = next((item for item in records if isinstance(item, dict) and item.get("target") == target_id), None)
    if record is None:
        raise BuildError(f"release manifest has no Runtime asset for {target_id}")
    digest = str(record.get("sha256", "")).lower()
    signature = str(record.get("signature", ""))
    if len(digest) != 64 or not all(char in "0123456789abcdef" for char in digest):
        raise BuildError(f"manifest digest is invalid for {target_id}")
    if not signature.startswith("ed25519:"):
        raise BuildError(f"manifest signature is missing for {target_id}")
    return manifest, record


def runtime_version(binary: Path) -> str:
    result = command_output([str(binary), "version", "--json"], timeout=60)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BuildError("Runtime sidecar version --json is invalid") from exc
    candidates: list[Any] = [payload.get("version")] if isinstance(payload, dict) else []
    if isinstance(payload, dict):
        for key in ("runtime", "executable"):
            value = payload.get(key)
            if isinstance(value, dict):
                candidates.append(value.get("version"))
    for value in candidates:
        if value:
            return str(value).lstrip("v")
    raise BuildError("Runtime sidecar version --json has no version")


def verify_manifest_signature(manifest: dict[str, Any], record: dict[str, Any]) -> None:
    public_key = str(manifest.get("signing_pubkey", "")).strip()
    signature = str(record.get("signature", "")).strip()
    digest = str(record.get("sha256", "")).strip().lower()
    helper = ROOT / "scripts" / "verify_ed25519.py"
    if not public_key or not helper.is_file():
        raise BuildError("manifest signature verification helper/key is unavailable")
    command_output(
        [
            sys.executable,
            str(helper),
            "--public-key",
            public_key,
            "--signature",
            signature,
            "--sha256",
            digest,
        ],
        timeout=60,
    )


def resolve_runtime(path_arg: str | None, version: str, target_id: str, manifest: dict[str, Any], record: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    candidate = Path(path_arg).expanduser() if path_arg else Path(
        os.environ.get("SIMPLICIO_DESKTOP_RUNTIME", str(Path.home() / ".simplicio" / "bin" / SIDECAR_NAME))
    )
    if candidate.is_symlink():
        raise BuildError("Runtime sidecar must be a regular file: " + str(candidate))
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise BuildError("Runtime sidecar must be a regular file: " + str(candidate))
    if os.name != "nt" and not (candidate.stat().st_mode & stat.S_IXUSR):
        raise BuildError("Runtime sidecar is not executable: " + str(candidate))
    actual_version = runtime_version(candidate)
    if actual_version != version:
        raise BuildError(f"Runtime sidecar version {actual_version} does not match {version}")
    actual_digest = sha256(candidate)
    expected_digest = str(record["sha256"]).lower()
    if actual_digest != expected_digest:
        raise BuildError(
            f"Runtime sidecar SHA-256 {actual_digest} does not match manifest {expected_digest} for {target_id}"
        )
    verify_manifest_signature(manifest, record)
    return candidate, {
        "source": str(candidate),
        "version": actual_version,
        "sha256": actual_digest,
        "manifest_sha256": expected_digest,
        "signature": {"algorithm": "ed25519", "status": "verified"},
    }


def stage_sidecar(source: Path, triple: str) -> Path:
    directory = TAURI / "binaries"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{SIDECAR_NAME}-{triple}"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".simplicio-", dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            with source.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(temporary, 0o755)
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    if not destination.is_file() or sha256(destination) != sha256(source):
        raise BuildError("staged Runtime sidecar does not match source bytes")
    return destination


def artifact_record(path: Path, bundle_root: Path) -> dict[str, Any]:
    relative = path.relative_to(bundle_root)
    return {"path": str(relative), "size": path.stat().st_size, "sha256": sha256(path)}


def inspect_bundle(bundle_root: Path, triple: str, expected_sidecar_sha256: str) -> dict[str, Any]:
    apps = sorted(path for path in bundle_root.rglob("*.app") if path.is_dir())
    if not apps:
        raise BuildError("Tauri build produced no .app bundle")
    app = apps[0]
    macos_dir = app / "Contents" / "MacOS"
    sidecars = [macos_dir / SIDECAR_NAME, macos_dir / f"{SIDECAR_NAME}-{triple}"]
    sidecar = next((path for path in sidecars if path.is_file()), None)
    if sidecar is None:
        raise BuildError("Tauri .app does not contain the target-specific Runtime sidecar")
    if os.name != "nt" and not (sidecar.stat().st_mode & stat.S_IXUSR):
        raise BuildError("bundled Runtime sidecar is not executable")
    sidecar_digest = sha256(sidecar)
    if sidecar_digest != expected_sidecar_sha256:
        raise BuildError(
            f"bundled Runtime sidecar SHA-256 {sidecar_digest} does not match verified source {expected_sidecar_sha256}"
        )
    signing: dict[str, Any] = {"status": "not_checked", "notarization": "not_performed"}
    codesign = shutil.which("codesign")
    if codesign:
        result = subprocess.run([codesign, "--verify", "--strict", str(app)], capture_output=True, text=True)
        signing["status"] = "verified" if result.returncode == 0 else "failed"
        if result.returncode != 0:
            signing["reason"] = (result.stderr or result.stdout)[-500:].strip()
    else:
        signing["status"] = "unavailable"
        signing["reason"] = "codesign is unavailable on this host"
    if shutil.which("xcrun"):
        notarization = subprocess.run(
            ["xcrun", "stapler", "validate", str(app)], capture_output=True, text=True
        )
        signing["notarization"] = "verified" if notarization.returncode == 0 else "not_performed"
    return {
        "app": artifact_record(app / "Contents" / "Info.plist", bundle_root) if (app / "Contents" / "Info.plist").is_file() else {"path": str(app.relative_to(bundle_root))},
        "app_path": str(app.relative_to(bundle_root)),
        "sidecar_path": str(sidecar.relative_to(bundle_root)),
        "sidecar_sha256": sidecar_digest,
        "signing": signing,
    }


def git_commit() -> str:
    result = command_output(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=30)
    return result.stdout.strip()


def create_dmg(app: Path, bundle_root: Path, version: str, target_id: str) -> Path:
    hdiutil = shutil.which("hdiutil")
    if not hdiutil:
        raise BuildError("hdiutil is unavailable; cannot create the macOS installer")
    output = bundle_root / "macos" / f"Simplicio_{version}_{target_id}.dmg"
    output.parent.mkdir(parents=True, exist_ok=True)
    command_output(
        [
            hdiutil,
            "create",
            "-ov",
            "-format",
            "UDZO",
            "-volname",
            f"Simplicio {version}",
            "-srcfolder",
            str(app),
            str(output),
        ],
        cwd=ROOT,
        timeout=300,
    )
    return output


def sign_app_ad_hoc(app: Path) -> None:
    codesign = shutil.which("codesign")
    if not codesign:
        return
    # No Apple credentials are required for a local package. Re-sign the
    # complete bundle after Tauri copies the external sidecar, then verify it.
    command_output([codesign, "--force", "--sign", "-", str(app)], cwd=ROOT, timeout=120)


def build_local(bundle_mode: str, version: str, target_id: str) -> Path:
    npm = shutil.which("npm")
    if not npm:
        raise BuildError("npm is required for the Desktop package build")
    # Build only the .app through Tauri. Its create-dmg helper requires a GUI
    # Finder session and is not deterministic on a headless/locked Mac.
    command_output(
        [npm, "--prefix", str(DESKTOP), "run", "tauri", "--", "build", "--bundles", "app"],
        cwd=ROOT,
        timeout=1_800,
    )
    bundle_root = TAURI / "target" / "release" / "bundle"
    if not bundle_root.is_dir():
        raise BuildError("Tauri build did not create target/release/bundle")
    apps = sorted(path for path in bundle_root.rglob("*.app") if path.is_dir())
    if not apps:
        raise BuildError("Tauri build produced no .app bundle")
    sign_app_ad_hoc(apps[0])
    if bundle_mode not in {"app", "dmg", "app,dmg"}:
        raise BuildError("bundle mode must be app, dmg or app,dmg")
    if "dmg" in bundle_mode:
        create_dmg(apps[0], bundle_root, version, target_id)
    return bundle_root


def make_report(
    version: str,
    target_id: str,
    triple: str,
    runtime: dict[str, Any],
    bundle_root: Path | None,
    bundle_mode: str,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "simplicio.desktop-build/v1",
        "issue": 345,
        "version": version,
        "target": target_id,
        "target_triple": triple,
        "source_commit": git_commit(),
        "runtime": runtime,
        "build": {
            "status": "staged",
            "publication": "not_requested",
            "bundles": bundle_mode,
        },
    }
    if bundle_root is None:
        return report
    files = [
        path
        for path in bundle_root.rglob("*")
        if path.is_file()
        and not path.name.startswith(".")
        and not path.name.startswith("rw.")
        and (any(part.endswith(".app") for part in path.parts) or (("dmg" in bundle_mode) and path.suffix == ".dmg"))
    ]
    report["build"] = {
        "status": "built",
        "publication": "not_requested",
        "bundles": bundle_mode,
        "artifacts": [artifact_record(path, bundle_root) for path in sorted(files)],
        "desktop": inspect_bundle(bundle_root, triple, str(runtime["sha256"])),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", help="verified Runtime executable (defaults to ~/.simplicio/bin/simplicio)")
    parser.add_argument("--stage-only", action="store_true", help="verify and stage the sidecar without running Tauri")
    parser.add_argument("--report", type=Path, help="write the JSON evidence report to this path")
    parser.add_argument(
        "--bundles",
        choices=("app", "dmg", "app,dmg"),
        default="app,dmg",
        help="local package outputs (default: app,dmg; DMG uses hdiutil without Finder)",
    )
    args = parser.parse_args(argv)
    try:
        version, _package, _tauri, _cargo = source_versions()
        target_id, triple = native_target()
        manifest, record = manifest_record(version, target_id)
        source, runtime = resolve_runtime(args.runtime, version, target_id, manifest, record)
        staged = stage_sidecar(source, triple)
        report = make_report(
            version,
            target_id,
            triple,
            runtime,
            None if args.stage_only else build_local(args.bundles, version, target_id),
            args.bundles,
        )
        report["staged_sidecar"] = {
            "path": str(staged.relative_to(ROOT)),
            "sha256": sha256(staged),
            "executable": bool(staged.stat().st_mode & stat.S_IXUSR),
        }
        report_path = args.report or ROOT / "reports" / f"desktop-build-{version}-{target_id}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except BuildError as exc:
        print(f"desktop build blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""The small PyPI launcher for the Simplicio runtime.

The launcher deliberately does not execute a remote shell script. It obtains
the immutable GitHub Release for its own version, verifies the pinned manifest
digest and asset checksum, and only then atomically installs the runtime.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

from . import __version__

INSTALL_DIR = os.path.expanduser("~/.local/bin")
BINARY_NAME = "simplicio" + (".exe" if platform.system() == "Windows" else "")
BINARY_PATH = os.path.join(INSTALL_DIR, BINARY_NAME)
RELEASE_API_BASE = "https://api.github.com/repos/wesleysimplicio/simplicio/releases/tags"
MANIFEST_ASSET = "simplicio-update-manifest.json"
# The wheel anchors each release manifest before trusting its artifact hashes.
TRUSTED_MANIFEST_SHA256 = {
    "3.5.2": "85a486b1210d3610365ce78279f3b964c5713ab311407efa8812cd6eeda4fc1f",
    "3.8.11": "22e535fb3875bad6af98af1b156975b25f2a4a5b0cbd32462ca2d9d0f2c3a9f0",
    "3.8.17": "9c0b753a874ee1e6543bcb0df1c59732233ea7ef706d8dc549fc5da4ba5728b9",    "3.8.24": "508177cc8a90670a77e1c6c95f0fa9cc1c3ad4a5365d17691e69af8b2e80cdb5",
    "3.8.25": "c526055fccb869abbea98a15a322f6774b18410efe1bc6c07c7b9112889237b7",
    "3.8.30": "9edb13dd5041d02ac4770407eee15e8ca9ae498104e359ee36bb0bd0dcb0031b",
}

# Kept in lockstep with distribution/targets.json.  The PyPI wheel must retain
# this table because it is also used outside a checkout of the repository.
TARGETS = {
    ("Windows", "amd64"): ("windows-x64", "simplicio-windows-x64.exe"),
    ("Windows", "x86_64"): ("windows-x64", "simplicio-windows-x64.exe"),
    ("Darwin", "arm64"): ("macos-arm64", "simplicio-macos-arm64"),
    ("Darwin", "aarch64"): ("macos-arm64", "simplicio-macos-arm64"),
    ("Darwin", "x86_64"): ("macos-x64", "simplicio-macos-x64"),
    ("Linux", "x86_64"): ("linux-x64", "simplicio-linux-x64"),
    ("Linux", "amd64"): ("linux-x64", "simplicio-linux-x64"),
}


class InstallError(RuntimeError):
    """An expected installation failure which should not show a traceback."""


class ReleaseClient:
    """Fetch one immutable GitHub Release; injectable for offline tests."""

    def __init__(self, api_base: str = RELEASE_API_BASE, opener=urlopen):
        self.api_base = api_base.rstrip("/")
        self.opener = opener

    def release(self, version: str) -> dict:
        with self.opener(self.api_base + "/v" + version.lstrip("v")) as response:
            return json.loads(response.read().decode("utf-8"))

    def download_asset(self, asset: dict) -> bytes:
        url = asset.get("browser_download_url")
        if not isinstance(url, str) or not url.startswith("https://github.com/"):
            raise InstallError("Release asset has no valid GitHub download URL.")
        with self.opener(url) as response:
            return response.read()


def _resolve_binary():
    """Find the installed real binary: canonical dir first, then PATH."""
    if os.path.exists(BINARY_PATH) and os.path.realpath(BINARY_PATH) != os.path.realpath(
        sys.argv[0]
    ):
        return BINARY_PATH
    found = shutil.which("simplicio")
    if found and os.path.realpath(found) != os.path.realpath(sys.argv[0]):
        return found
    return None


def _target(system=None, machine=None):
    key = (system or platform.system(), (machine or platform.machine()).lower())
    try:
        return TARGETS[key]
    except KeyError:
        raise InstallError("Unsupported platform: %s/%s" % key) from None


def _artifact(manifest: dict, target: str, asset: str, expected_version: str) -> dict:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), list):
        raise InstallError("Release manifest has an invalid structure.")
    if not isinstance(manifest.get("version"), str):
        raise InstallError("Release manifest has an invalid structure.")
    for item in manifest["artifacts"]:
        if not isinstance(item, dict):
            raise InstallError("Release manifest has an invalid artifact entry.")
    version = manifest["version"].lstrip("v")
    if version != expected_version.lstrip("v"):
        raise InstallError(
            "Release/runtime version mismatch (expected %s, manifest has %s). "
            "Install a matching simplicio-installer version."
            % (expected_version, version or "none")
        )
    for item in manifest["artifacts"]:
        if item.get("target") == target:
            if item.get("artifact") != asset:
                raise InstallError("Release manifest asset mismatch for %s." % target)
            digest = item.get("sha256", "")
            if (
                isinstance(digest, str)
                and len(digest) == 64
                and all(c in "0123456789abcdefABCDEF" for c in digest)
            ):
                return item
            raise InstallError("Release manifest has no valid SHA-256 for %s." % target)
    raise InstallError(
        "No release asset for %s. This release cannot be installed on this platform." % target
    )


def _release_asset(release: dict, name: str) -> dict:
    assets = release.get("assets") if isinstance(release, dict) else None
    if not isinstance(assets, list):
        raise InstallError("GitHub Release has an invalid assets list.")
    for asset in assets:
        if not isinstance(asset, dict):
            raise InstallError("GitHub Release has an invalid asset entry.")
        if asset.get("name") == name:
            return asset
    raise InstallError("Release is missing required asset %s." % name)


def _release_for_version(client, expected_version: str) -> dict:
    try:
        release = client.release(expected_version)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise InstallError(
            "Could not fetch GitHub Release v%s; try again later." % expected_version
        ) from exc
    if not isinstance(release, dict) or release.get("tag_name") != "v" + expected_version.lstrip(
        "v"
    ):
        raise InstallError(
            "GitHub Release v%s was not found or does not match this installer." % expected_version
        )
    return release


def _verified_manifest(payload: bytes, expected_version: str, trust_store: dict) -> dict:
    version = expected_version.lstrip("v")
    expected_digest = trust_store.get(version)
    if not isinstance(expected_digest, str):
        raise InstallError("No trusted manifest digest is available for version %s." % version)
    actual_digest = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual_digest, expected_digest.lower()):
        raise InstallError("Release manifest digest mismatch; installation aborted.")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise InstallError("Could not read the release manifest; installation aborted.") from exc


def _validate_runtime(path: Path, expected_version: str, runner=subprocess.run) -> None:
    try:
        result = runner(
            [str(path), "version", "--json"], check=True, capture_output=True, text=True
        )
        runtime = json.loads(result.stdout).get("runtime")
        actual = str(runtime.get("version", "")).lstrip("v")
    except (
        OSError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        TypeError,
        AttributeError,
    ) as exc:
        raise InstallError("Downloaded runtime did not return a valid version JSON.") from exc
    if actual != expected_version.lstrip("v"):
        raise InstallError(
            "Release/runtime version mismatch (expected %s, runtime has %s)."
            % (expected_version, actual or "none")
        )


def do_install(
    client=None,
    install_dir=None,
    expected_version=__version__,
    runner=subprocess.run,
    trusted_manifest_sha256=None,
) -> None:
    """Download a verified release asset, validate it, then atomically install it."""
    target, asset = _target()
    client = client or ReleaseClient()
    trust_store = (
        TRUSTED_MANIFEST_SHA256
        if trusted_manifest_sha256 is None
        else trusted_manifest_sha256
    )
    release = _release_for_version(client, expected_version)
    try:
        manifest_payload = client.download_asset(_release_asset(release, MANIFEST_ASSET))
    except OSError as exc:
        raise InstallError("Could not read the release manifest; installation aborted.") from exc
    manifest = _verified_manifest(manifest_payload, expected_version, trust_store)
    info = _artifact(manifest, target, asset, expected_version)
    try:
        payload = client.download_asset(_release_asset(release, asset))
    except OSError as exc:
        raise InstallError("Could not download release asset %s." % asset) from exc
    actual_digest = hashlib.sha256(payload).hexdigest()
    if actual_digest.lower() != info["sha256"].lower():
        raise InstallError("Downloaded asset checksum mismatch; installation aborted.")

    destination_dir = Path(install_dir or INSTALL_DIR)
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise InstallError("Could not create the installation directory.") from exc
    destination = destination_dir / BINARY_NAME
    staged_path = None
    try:
        suffix = Path(asset).suffix
        with tempfile.NamedTemporaryFile(
            dir=str(destination_dir), prefix=".simplicio-", suffix=suffix, delete=False
        ) as staged:
            staged.write(payload)
            staged_path = Path(staged.name)
        staged_path.chmod(0o755)
        _validate_runtime(staged_path, expected_version, runner)
        os.replace(str(staged_path), str(destination))
    except InstallError:
        raise
    except OSError as exc:
        raise InstallError("Could not stage or install the verified runtime.") from exc
    finally:
        install_error_in_flight = sys.exc_info()[0] is not None
        if staged_path is not None and staged_path.exists():
            try:
                staged_path.unlink()
            except OSError as exc:
                # Do not replace the actionable install error already in flight.
                if not install_error_in_flight:
                    raise InstallError("Could not clean up the staged runtime.") from exc
    print("Installed Simplicio %s to %s" % (expected_version, destination))


def main():
    args = sys.argv[1:]
    if not args or args[0] == "install":
        try:
            do_install()
        except InstallError as exc:
            print("Simplicio install failed: %s" % exc, file=sys.stderr)
            sys.exit(1)
        return
    binary = _resolve_binary()
    if binary:
        try:
            subprocess.run([binary] + args, check=True)
        except subprocess.CalledProcessError as exc:
            sys.exit(exc.returncode)
        except OSError as exc:
            print("Could not run installed Simplicio: %s" % exc, file=sys.stderr)
            sys.exit(1)
    else:
        print("Simplicio is not installed. Run 'simplicio install' first.")
        sys.exit(1)


if __name__ == "__main__":
    main()

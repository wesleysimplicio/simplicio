#!/usr/bin/env python3
"""Fail-closed smoke test for an already-published Simplicio release.

This command validates the bytes served by GitHub Release, not the local
staging directory. It verifies the immutable manifest, every target artifact,
SHA-256, Ed25519 sidecars, SBOMs, provenance records, and (with ``--execute``)
the native artifact for the current host.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping, Sequence

try:
    from scripts.verify_ed25519 import verify_signature_for_digest
except ModuleNotFoundError:  # direct execution: python scripts/post_release_smoke.py
    from verify_ed25519 import verify_signature_for_digest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY = "wesleysimplicio/simplicio"
MANIFEST_ASSET = "simplicio-update-manifest.json"
CHECKSUMS_ASSET = "SHA256SUMS"
VERSION_RE = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")


def load_target_table(path: Path = ROOT / "distribution/targets.json") -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    targets = document.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("distribution target table is empty")
    return [target for target in targets if isinstance(target, dict)]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_checksums(value: bytes) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in value.decode("utf-8").splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) != 2:
            continue
        digest, filename = fields
        checksums[filename.lstrip("*")] = digest.lower()
    return checksums


def expected_asset_names(manifest: Mapping[str, object], targets: Sequence[dict]) -> set[str]:
    names = {MANIFEST_ASSET, CHECKSUMS_ASSET}
    artifacts = manifest.get("artifacts", [])
    for target in targets:
        record = next(
            (item for item in artifacts if isinstance(item, dict) and item.get("target") == target.get("id")),
            {},
        )
        artifact = str(record.get("artifact") or target.get("asset") or "")
        if not artifact:
            continue
        names.add(artifact)
        names.add(str(record.get("signature_file") or f"{artifact}.sig"))
        sbom = record.get("sbom")
        provenance = record.get("provenance")
        if isinstance(sbom, dict) and sbom.get("file"):
            names.add(str(sbom["file"]))
        if isinstance(provenance, dict) and provenance.get("file"):
            names.add(str(provenance["file"]))
        # Older Windows releases may carry this compatibility sidecar.
        names.add(f"{artifact}.sha256")
    return names


def verify_release_payload(
    release: Mapping[str, object],
    manifest: Mapping[str, object],
    assets: Mapping[str, bytes],
    *,
    repository: str,
    tag: str,
    targets: Sequence[dict],
) -> dict:
    """Verify downloaded release payloads and return a machine-readable report."""
    errors: list[str] = []
    release_tag = str(release.get("tag_name") or "")
    if release_tag != tag:
        errors.append(f"release tag mismatch: {release_tag!r} != {tag!r}")
    if release.get("draft") is True or release.get("prerelease") is True:
        errors.append("release is draft or prerelease")

    version = str(manifest.get("version") or "")
    if manifest.get("release_tag") != tag:
        errors.append("manifest release_tag does not match the requested immutable tag")
    if manifest.get("repository") != repository:
        errors.append("manifest repository does not match the requested repository")
    if not version or f"v{version}" != tag:
        errors.append("manifest version does not match the requested release tag")

    security = manifest.get("security")
    if not isinstance(security, dict):
        errors.append("manifest security contract is missing")
        security = {}
    if security.get("signature_required") is not True or security.get("refuse_unsigned") is not True:
        errors.append("manifest does not require fail-closed signatures")
    if security.get("signature_algorithm") != "ed25519":
        errors.append("manifest signature algorithm is not ed25519")
    signing_pubkey = str(manifest.get("signing_pubkey") or "").strip()
    if not signing_pubkey:
        errors.append("manifest signing_pubkey is missing")

    release_assets = release.get("assets")
    release_names = {
        str(item.get("name"))
        for item in release_assets
        if isinstance(item, dict) and item.get("name")
    } if isinstance(release_assets, list) else set()
    if MANIFEST_ASSET not in release_names or CHECKSUMS_ASSET not in release_names:
        errors.append("release is missing the manifest or SHA256SUMS asset")
    expected_names = expected_asset_names(manifest, targets)
    unexpected = sorted(release_names - expected_names)
    if unexpected:
        errors.append("release contains unexpected assets: " + ", ".join(unexpected))
    missing_payloads = sorted(release_names - set(assets))
    if missing_payloads:
        errors.append("release assets were not downloaded: " + ", ".join(missing_payloads))

    checksums = parse_checksums(assets[CHECKSUMS_ASSET]) if CHECKSUMS_ASSET in assets else {}
    artifact_records = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    records_by_target = {str(item.get("target")): item for item in artifact_records}
    target_ids = {str(target.get("id")) for target in targets}
    if set(records_by_target) != target_ids:
        errors.append("manifest artifact targets do not match distribution/targets.json")

    verified_artifacts: list[str] = []
    base_url = f"https://github.com/{repository}/releases/download/{tag}/"
    for target in targets:
        target_id = str(target.get("id"))
        record = records_by_target.get(target_id)
        if record is None:
            continue
        artifact = str(record.get("artifact") or "")
        expected_artifact = str(target.get("asset") or "")
        if artifact != expected_artifact:
            errors.append(f"{target_id}: artifact name mismatch: {artifact!r} != {expected_artifact!r}")
            continue
        digest = str(record.get("sha256") or "").lower()
        signature = str(record.get("signature") or "").strip()
        signature_file = str(record.get("signature_file") or f"{artifact}.sig")
        if record.get("url") != base_url + artifact:
            errors.append(f"{artifact}: URL is not immutable for tag {tag}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"{artifact}: invalid SHA-256 in manifest")
            continue
        binary = assets.get(artifact)
        sidecar = assets.get(signature_file)
        if binary is None or sidecar is None:
            continue
        actual_digest = sha256_bytes(binary)
        if actual_digest != digest:
            errors.append(f"{artifact}: downloaded SHA-256 mismatch")
        if checksums.get(artifact) != digest:
            errors.append(f"{artifact}: SHA256SUMS mismatch")
        if sidecar.decode("utf-8").strip() != signature:
            errors.append(f"{artifact}: signature sidecar differs from manifest")
        try:
            valid_signature = verify_signature_for_digest(signing_pubkey, signature, digest)
        except (ValueError, TypeError, binascii.Error) as exc:
            valid_signature = False
            errors.append(f"{artifact}: invalid Ed25519 input: {exc}")
        if not valid_signature:
            errors.append(f"{artifact}: Ed25519 signature verification failed")
        if record.get("size") is not None and int(record["size"]) != len(binary):
            errors.append(f"{artifact}: manifest size mismatch")

        sbom = record.get("sbom")
        if security.get("sbom_required") is True:
            sbom_file = str(sbom.get("file")) if isinstance(sbom, dict) else ""
            if not sbom_file or sbom_file not in assets:
                errors.append(f"{artifact}: required SBOM is missing")
            else:
                try:
                    sbom_data = json.loads(assets[sbom_file])
                    file_entries = sbom_data.get("files", [])
                    matching = [entry for entry in file_entries if entry.get("fileName") == artifact]
                    sbom_hashes = {
                        str(checksum.get("checksumValue", "")).lower()
                        for entry in matching
                        for checksum in entry.get("checksums", [])
                        if checksum.get("algorithm") == "SHA256"
                    }
                    if sbom_data.get("spdxVersion") != "SPDX-2.3" or digest not in sbom_hashes:
                        errors.append(f"{artifact}: SBOM does not describe the verified bytes")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{artifact}: invalid SBOM JSON: {exc}")

        provenance = record.get("provenance")
        if security.get("provenance_required") is True:
            provenance_file = str(provenance.get("file")) if isinstance(provenance, dict) else ""
            if not provenance_file or provenance_file not in assets:
                errors.append(f"{artifact}: required provenance is missing")
            else:
                try:
                    provenance_data = json.loads(assets[provenance_file])
                    subject = provenance_data.get("subject", {})
                    build = provenance_data.get("build", {})
                    if (
                        subject.get("name") != artifact
                        or str(subject.get("sha256", "")).lower() != digest
                        or int(subject.get("size", -1)) != len(binary)
                        or str(build.get("version")) != version
                        or str(build.get("target")) not in {
                            target_id,
                            str(target.get("rust_triple") or ""),
                            *(str(alias) for alias in target.get("provenance_target_aliases", [])),
                        }
                    ):
                        errors.append(f"{artifact}: provenance does not describe the verified bytes")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{artifact}: invalid provenance JSON: {exc}")
        if not any(error.startswith(f"{artifact}:") for error in errors):
            verified_artifacts.append(artifact)

    return {
        "repository": repository,
        "tag": tag,
        "version": version,
        "verified_artifacts": verified_artifacts,
        "artifact_count": len(artifact_records),
        "errors": errors,
    }


def github_request(url: str, token: str = "") -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "simplicio-post-release-smoke"},
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def download_release(repository: str, tag: str, token: str) -> tuple[dict, dict[str, bytes]]:
    api_url = f"https://api.github.com/repos/{repository}/releases/tags/{tag}"
    release = json.loads(github_request(api_url, token))
    payloads: dict[str, bytes] = {}
    for item in release.get("assets", []):
        if not isinstance(item, dict) or not item.get("name") or not item.get("browser_download_url"):
            continue
        payloads[str(item["name"])] = github_request(str(item["browser_download_url"]), token)
    return release, payloads


def host_target() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows-x64"
    if system == "linux":
        return "linux-x64"
    if system == "darwin":
        return "macos-arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "macos-x64"
    raise RuntimeError(f"unsupported host platform: {platform.system()} {platform.machine()}")


def reported_runtime_version(version_json: Mapping[str, object]) -> str:
    """Read the Runtime version from its canonical version JSON envelope."""
    runtime = version_json.get("runtime")
    executable = version_json.get("executable")
    candidates = [
        runtime.get("version") if isinstance(runtime, dict) else None,
        executable.get("version") if isinstance(executable, dict) else None,
        version_json.get("version"),  # compatibility with older Runtime envelopes
    ]
    return next((str(value) for value in candidates if value), "")


def run_native_smoke(target: str, manifest: Mapping[str, object], binary: bytes) -> dict:
    record = next(item for item in manifest.get("artifacts", []) if item.get("target") == target)
    artifact = str(record["artifact"])
    with tempfile.TemporaryDirectory(prefix="simplicio-post-release-") as directory:
        binary_path = Path(directory) / artifact
        binary_path.write_bytes(binary)
        if os.name != "nt":
            binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR)
        command = [str(binary_path)]
        version_proc = subprocess.run(command + ["version", "--json"], capture_output=True, text=True, timeout=90)
        if version_proc.returncode != 0:
            raise RuntimeError(f"version --json failed: {version_proc.stderr[-500:]}")
        version_json = json.loads(version_proc.stdout)
        binary_version = reported_runtime_version(version_json)
        if binary_version != str(manifest.get("version")):
            raise RuntimeError("binary version does not match manifest")

        with tempfile.TemporaryDirectory(prefix="simplicio-clean-home-") as home:
            clean_env = dict(os.environ)
            clean_env.update({
                "HOME": home,
                "USERPROFILE": home,
                "XDG_CONFIG_HOME": str(Path(home) / ".config"),
                "SIMPLICIO_E2E_EXPECT_LOGIN_REQUIRED": "1",
            })
            auth = subprocess.run(command + ["auth", "status", "--json"], env=clean_env, capture_output=True, text=True, timeout=90)
            auth_text = (auth.stdout + auth.stderr).lower()
            if "login" not in auth_text and "unauthenticated" not in auth_text and "not authenticated" not in auth_text:
                raise RuntimeError("clean-home auth status did not enforce login")
            handshake = "".join(json.dumps(item) + "\n" for item in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "simplicio_map",
                        "arguments": {"repo": home, "task": "post-release login gate"},
                    },
                },
            ))
            mcp = subprocess.run(command + ["serve", "--mcp", "--stdio", "--json"], input=handshake, env=clean_env, capture_output=True, text=True, timeout=90)
            responses = {}
            for line in mcp.stdout.splitlines():
                try:
                    response = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if response.get("id") is not None:
                    responses[response["id"]] = response
            listed_tools = {
                str(tool.get("name"))
                for tool in responses.get(2, {}).get("result", {}).get("tools", [])
                if isinstance(tool, dict) and tool.get("name")
            }
            required_tools = {"simplicio_map", "simplicio_memory", "simplicio_gate", "simplicio_edit", "simplicio_validate"}
            missing_tools = sorted(required_tools - listed_tools)
            if missing_tools:
                raise RuntimeError("MCP tools/list is missing required tools: " + ", ".join(missing_tools))
            call_error = responses.get(3, {}).get("error", {})
            call_data = call_error.get("data", {}) if isinstance(call_error, dict) else {}
            if call_error.get("code") != -32001 or call_data.get("login_required") is not True:
                raise RuntimeError("MCP tools/call did not return structured login_required gate")
        return {
            "target": target,
            "binary_version": binary_version,
            "login_gate": True,
            "mcp_login_gate": True,
            "mcp_tools": len(listed_tools),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="immutable release tag, for example v3.8.17")
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY)
    parser.add_argument("--execute", action="store_true", help="execute the release artifact for this native host")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not VERSION_RE.fullmatch(args.version):
        parser.error("--version must be a semantic version tag such as v3.8.17")
    tag = args.version if args.version.startswith("v") else f"v{args.version}"
    try:
        release, payloads = download_release(args.repo, tag, os.environ.get("GITHUB_TOKEN", ""))
        manifest = json.loads(payloads[MANIFEST_ASSET])
        report = verify_release_payload(
            release,
            manifest,
            payloads,
            repository=args.repo,
            tag=tag,
            targets=load_target_table(),
        )
        if not report["errors"] and args.execute:
            target = host_target()
            artifact = next(item for item in manifest["artifacts"] if item.get("target") == target)["artifact"]
            report["native_smoke"] = run_native_smoke(target, manifest, payloads[artifact])
    except (KeyError, OSError, RuntimeError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        report = {"tag": tag, "errors": [str(exc)]}
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not report.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())

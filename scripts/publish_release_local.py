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
import zipfile
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
CODEX_HOOK_FILES = (
    "codex/mcp-route.sh",
    "codex/mcp-route.ps1",
)
LOCAL_STATE_PREFIXES = (".simplicio/", "pypi/simplicio/build/")
FORCE_TRACKED_RELEASE_PREFIXES = (
    "npm/simplicio/",
    "npm/simplicio-installer/",
    "npm/simplicio-unscoped/",
    "pypi/simplicio/",
)


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


def required_release_assets() -> list[str]:
    files = list(META_ASSETS)
    for asset in ASSETS:
        files.extend((asset, asset + ".sig", asset + ".spdx.json", asset + ".provenance.json"))
    return files


def verify_bundle(bundle: Path, tag: str, version: str, source_commit: str) -> dict:
    if not bundle.is_dir():
        raise PublishError("release bundle does not exist: %s" % bundle)
    required_public_files = (*required_release_assets(), *CODEX_HOOK_FILES)
    missing = [name for name in required_public_files if not (bundle / name).is_file()]
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
    hooks = [
        {"path": relative, "sha256": sha256(bundle / relative)}
        for relative in CODEX_HOOK_FILES
    ]
    return {
        "version": version,
        "source_commit": source_commit,
        "artifacts": verified,
        "codex_hooks": hooks,
    }


def is_ignored_local_state(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(LOCAL_STATE_PREFIXES)

def requires_forced_release_staging(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith(FORCE_TRACKED_RELEASE_PREFIXES)


def blocking_tracked_changes() -> list[str]:
    changed: set[str] = set()
    for command in (
        ["git", "diff", "--name-only"],
        ["git", "diff", "--cached", "--name-only"],
    ):
        changed.update(line.strip() for line in run(command).stdout.splitlines() if line.strip())
    return sorted(path for path in changed if not is_ignored_local_state(path))


def pypi_release_files(version: str) -> list[dict]:
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/simplicio-installer/json", timeout=30) as response:
            releases = json.load(response).get("releases", {})
    except Exception as exc:
        raise PublishError("could not verify current PyPI project state") from exc
    files = releases.get(version, [])
    if not isinstance(files, list):
        raise PublishError("PyPI release metadata is malformed")
    if files and (len(files) != 1 or files[0].get("packagetype") != "bdist_wheel"):
        raise PublishError("PyPI release is not exactly one wheel")
    return files


def resume_public_preflight(tag: str, version: str, source_commit: str) -> dict:
    if run(["git", "branch", "--show-current"]).stdout.strip() != "master":
        raise PublishError("public repository must be on master")
    if "wesleysimplicio/simplicio" not in run(["git", "remote", "get-url", "origin"]).stdout.strip():
        raise PublishError("origin is not the public distribution repository")
    blocking = blocking_tracked_changes()
    if blocking:
        raise PublishError(
            "public tracked worktree has distribution changes: " + ", ".join(blocking)
        )

    run(["git", "fetch", "--quiet", "origin", "master", "--tags"], timeout=120)
    remote_tag = run(
        ["git", "ls-remote", "--tags", "origin", "refs/tags/" + tag]
    ).stdout.strip()
    if not remote_tag:
        raise PublishError("cannot resume before the public tag exists: " + tag)
    remote_tag_object = remote_tag.split()[0]
    local_tag_object = run(["git", "rev-parse", "refs/tags/" + tag]).stdout.strip()
    if remote_tag_object != local_tag_object:
        raise PublishError("local and remote public tag identities differ")
    public_commit = run(["git", "rev-list", "-n", "1", tag]).stdout.strip()
    remote_master = run(["git", "ls-remote", "origin", "refs/heads/master"]).stdout.split()[0]
    run(["git", "merge-base", "--is-ancestor", public_commit, remote_master])

    manifest = json.loads((ROOT / "simplicio-update-manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("version") != version
        or manifest.get("release_tag") != tag
        or manifest.get("commit") != source_commit
    ):
        raise PublishError("public checkout does not match the release identity being resumed")
    if (ROOT / "version.txt").read_text(encoding="utf-8").strip() != version:
        raise PublishError("public version.txt does not match the release being resumed")
    if source_commit not in (ROOT / "VERSION.md").read_text(encoding="utf-8"):
        raise PublishError("public VERSION.md does not name the Runtime source commit")

    release = json.loads(run([
        "gh", "release", "view", tag,
        "--repo", PUBLIC_REPOSITORY,
        "--json", "tagName,isDraft,isPrerelease,assets",
    ]).stdout)
    if (
        release.get("tagName") != tag
        or release.get("isDraft") is True
        or release.get("isPrerelease") is True
    ):
        raise PublishError("existing GitHub release is not the expected final release")
    release_assets = {
        str(item.get("name"))
        for item in release.get("assets", [])
        if isinstance(item, dict) and item.get("name")
    }
    if release_assets != set(required_release_assets()):
        raise PublishError("existing GitHub release asset set is incomplete or unexpected")

    existing_pypi = pypi_release_files(version)
    return {
        "public_commit": public_commit,
        "already_published_to_pypi": bool(existing_pypi),
    }


def public_preflight(tag: str, version: str, *, require_clean: bool) -> None:
    if run(["git", "branch", "--show-current"]).stdout.strip() != "master":
        raise PublishError("public repository must be on master")
    if "wesleysimplicio/simplicio" not in run(["git", "remote", "get-url", "origin"]).stdout.strip():
        raise PublishError("origin is not the public distribution repository")
    with (PACKAGE_ROOT / "pyproject.toml").open("rb") as handle:
        package = tomllib.load(handle)
    if package.get("project", {}).get("name") != "simplicio-installer":
        raise PublishError("public package identity mismatch")
    if require_clean:
        blocking = blocking_tracked_changes()
        if blocking:
            raise PublishError(
                "public tracked worktree has distribution changes: " + ", ".join(blocking)
            )
    if run(["git", "ls-remote", "--tags", "origin", "refs/tags/" + tag]).stdout.strip():
        raise PublishError("public tag already exists: " + tag)
    run(["gh", "auth", "status"], timeout=60)
    existing = subprocess.run(
        ["gh", "release", "view", tag, "--repo", PUBLIC_REPOSITORY],
        cwd=ROOT, capture_output=True, text=True, timeout=60, check=False
    )
    if existing.returncode == 0:
        raise PublishError("public release already exists: " + tag)
    if pypi_release_files(version):
        raise PublishError("PyPI version already exists: " + version)


PLUGIN_BOOTSTRAP = "plugins/simplicio/bin/simplicio-mcp-bootstrap.js"
PLUGIN_MANIFESTS = (
    "plugins/simplicio/plugin.json",
    "plugins/simplicio/.codex-plugin/plugin.json",
    "plugins/simplicio/.claude-plugin/plugin.json",
)
PERSISTENT_LOGIN_MINIMUM = "3.8.40"


def version_parts(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in normalize_version(value)[1].split("."))


def read_plugin_policy() -> dict:
    # Requiring the module does not start its installer or MCP server.
    probe = (
        "const b=require(process.argv[1]);"
        "process.stdout.write(JSON.stringify({policy:b.POLICY,"
        "acceptsTarget:b.supportedRuntimeVersion(b.POLICY.runtimeVersion),"
        "acceptsMinimum:b.supportedRuntimeVersion(b.POLICY.minimumRuntimeVersion),"
        "acceptsLegacy:b.supportedRuntimeVersion('3.8.39')}));"
    )
    return json.loads(run(
        ["node", "-e", probe, str(ROOT / PLUGIN_BOOTSTRAP)],
        cwd=ROOT, timeout=30,
    ).stdout)


def plugin_manifests() -> list[tuple[Path, dict]]:
    manifests = []
    for relative in PLUGIN_MANIFESTS:
        path = ROOT / relative
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("name") != "simplicio":
            raise PublishError("plugin manifest identity mismatch: " + relative)
        version_parts(document["version"])
        manifests.append((path, document))
    if len({document["version"] for _, document in manifests}) != 1:
        raise PublishError("plugin manifest versions differ")
    return manifests


def prepare_plugin_release_policy(version: str) -> list[Path]:
    """Pin installation bytes only when the signed bundle is being published."""
    policy = read_plugin_policy()["policy"]
    minimum = max(
        (policy["minimumRuntimeVersion"], PERSISTENT_LOGIN_MINIMUM),
        key=version_parts,
    )
    if version_parts(version) < version_parts(minimum):
        raise PublishError("release predates the plugin's required Runtime capabilities")
    commit = run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    remote = run(
        ["git", "ls-remote", "origin", "refs/heads/master"], cwd=ROOT, timeout=60
    ).stdout.split()
    if not remote or remote[0] != commit:
        raise PublishError("plugin installer pin requires the current published master commit")
    path = ROOT / PLUGIN_BOOTSTRAP
    original = path.read_text(encoding="utf-8")
    body = original

    def replace_once(pattern: str, value: str) -> None:
        nonlocal body
        body, count = re.subn(pattern, lambda match: match[1] + value + match[2], body)
        if count != 1:
            raise PublishError("plugin bootstrap policy field is missing or ambiguous")

    for field, value in (
        ("runtimeVersion", version),
        ("minimumRuntimeVersion", minimum),
        ("installerCommit", commit),
    ):
        replace_once(r'(?m)^(  ' + field + r': ")[^"]+(",?)$', value)
    for platform, filename in (("posix", "install.sh"), ("win32", "install.ps1")):
        if policy["installers"][platform]["filename"] != filename:
            raise PublishError("plugin installer filename mismatch")
        # Hash Git blob bytes, never text-mode output or checkout EOL conversion.
        result = subprocess.run(
            ["git", "show", commit + ":" + filename], cwd=ROOT,
            capture_output=True, timeout=60, check=False,
        )
        if result.returncode != 0 or not result.stdout:
            raise PublishError("published installer blob is unavailable: " + filename)
        replace_once(
            r'(filename: "' + re.escape(filename) + r'",\s+sha256: ")[0-9a-f]{64}(")',
            hashlib.sha256(result.stdout).hexdigest(),
        )
    manifests = plugin_manifests()
    if body == original:
        return []
    major, minor, patch = version_parts(manifests[0][1]["version"])
    plugin_version = f"{major}.{minor}.{patch + 1}"
    # Validate the entire update before touching any release metadata.
    path.write_text(body, encoding="utf-8")
    changed = [path]
    for manifest, document in manifests:
        document["version"] = plugin_version
        manifest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        changed.append(manifest)
    return changed


def verify_plugin_release_policy(version: str) -> None:
    # Historical releases can still finish an interrupted publication.
    if version_parts(version) < version_parts(PERSISTENT_LOGIN_MINIMUM):
        return
    result = read_plugin_policy()
    policy = result["policy"]
    if (
        policy["runtimeVersion"] != version
        or not version_parts(PERSISTENT_LOGIN_MINIMUM)
        <= version_parts(policy["minimumRuntimeVersion"]) <= version_parts(version)
        or not result["acceptsTarget"] or not result["acceptsMinimum"]
        or result["acceptsLegacy"]
    ):
        raise PublishError("plugin policy does not enforce persistent-login compatibility")
    plugin_manifests()
    commit = policy["installerCommit"]
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise PublishError("plugin installer commit is not immutable")
    for platform, filename in (("posix", "install.sh"), ("win32", "install.ps1")):
        installer = policy["installers"][platform]
        if installer["filename"] != filename:
            raise PublishError("plugin installer filename mismatch")
        url = f"https://raw.githubusercontent.com/{PUBLIC_REPOSITORY}/{commit}/{filename}"
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read(1024 * 1024 + 1)
        if not content or len(content) > 1024 * 1024:
            raise PublishError("plugin installer response has an invalid size")
        if hashlib.sha256(content).hexdigest() != installer["sha256"]:
            raise PublishError("published plugin installer digest mismatch: " + filename)
    run(
        ["node", "--test", "plugins/simplicio/tests/bootstrap.test.js"],
        cwd=ROOT, timeout=120,
    )


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

    for relative in (
        "npm/simplicio/package.json",
        "npm/simplicio-installer/package.json",
        "npm/simplicio-unscoped/package.json",
    ):
        path = ROOT / relative
        body = path.read_text(encoding="utf-8")
        body, replacements = re.subn(
            r'(?m)^  "version": "[0-9]+\.[0-9]+\.[0-9]+",$',
            '  "version": "' + version + '",',
            body,
            count=1,
        )
        if replacements != 1:
            raise PublishError("could not update wrapper version: " + relative)
        path.write_text(body, encoding="utf-8")
        changed.append(path)

    ecosystem = ROOT / "SIMPLICIO_ECOSYSTEM.md"
    body = ecosystem.read_text(encoding="utf-8")
    body, current_replacements = re.subn(
        r"(?m)^[0-9]+\.[0-9]+\.[0-9]+ \(release pública;",
        version + " (release pública;",
        body,
        count=1,
    )
    body, manifest_replacements = re.subn(
        r"(?m)^O manifest atualmente publicado neste repositório é o `[0-9]+\.[0-9]+\.[0-9]+`\.",
        "O manifest atualmente publicado neste repositório é o `" + version + "`.",
        body,
        count=1,
    )
    if current_replacements != 1 or manifest_replacements != 1:
        raise PublishError("could not update SIMPLICIO_ECOSYSTEM.md version")
    ecosystem.write_text(body, encoding="utf-8")
    changed.append(ecosystem)
    return changed


def stage_bundle(bundle: Path) -> list[Path]:
    staged = []
    for name in required_release_assets():
        destination = ROOT / name
        shutil.copy2(bundle / name, destination)
        # Executables are immutable GitHub Release assets, not source-tree
        # files. The repository policy intentionally rejects tracked binaries.
        if name not in ASSETS:
            staged.append(destination)
    return staged


def stage_codex_hooks(bundle: Path) -> list[Path]:
    staged = []
    for relative in CODEX_HOOK_FILES:
        source = bundle / relative
        destination = ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged.append(destination)
    return staged


def verify_public_codex_hooks(bundle: Path) -> None:
    mismatched = [
        relative
        for relative in CODEX_HOOK_FILES
        if not (ROOT / relative).is_file()
        or sha256(ROOT / relative) != sha256(bundle / relative)
    ]
    if mismatched:
        raise PublishError("public Codex hooks differ from release bundle: " + ", ".join(mismatched))


def verify_codex_hook_contract() -> None:
    if shutil.which("pwsh") is None:
        raise PublishError("PowerShell is required to validate the Windows Codex hook")
    run(["bash", str(ROOT / "tests/test_codex_hooks.sh")], timeout=60)


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
    with tempfile.TemporaryDirectory(prefix="simplicio-wheel-source-") as raw:
        clean_package = Path(raw) / "simplicio"
        shutil.copytree(
            PACKAGE_ROOT,
            clean_package,
            ignore=shutil.ignore_patterns(
                "build",
                "dist",
                "*.egg-info",
                "__pycache__",
                "*.pyc",
            ),
        )
        run([
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(output),
            str(clean_package),
        ])
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise PublishError("expected exactly one wheel, found %d" % len(wheels))
    wheel = wheels[0]
    if version not in wheel.name:
        raise PublishError("wheel filename does not contain release version")
    try:
        with zipfile.ZipFile(wheel) as archive:
            cached = [
                name
                for name in archive.namelist()
                if "__pycache__" in name or name.endswith(".pyc")
            ]
    except (OSError, zipfile.BadZipFile) as exc:
        raise PublishError("wheel is not a valid ZIP archive") from exc
    if cached:
        raise PublishError("wheel contains cached bytecode: " + ", ".join(cached))
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
    branch = "release/" + tag
    run(["git", "switch", "-c", branch])
    forced = [path for path in relative if requires_forced_release_staging(path)]
    normal = [path for path in relative if not requires_forced_release_staging(path)]
    if normal:
        run(["git", "add", "--", *normal])
    if forced:
        # The broad binary-name ignore rules also match these known installer
        # source directories. Force only this explicit source allowlist.
        run(["git", "add", "-f", "--", *forced])
    run(["git", "-c", "core.whitespace=cr-at-eol", "diff", "--cached", "--check"])
    run([
        "git", "commit", "-m", "release(public): publish signed Runtime %s" % tag,
        "-m", "Source commit: " + source_commit,
    ])
    release_commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    run(["git", "push", "-u", "origin", branch])
    run([
        "gh", "pr", "create",
        "--repo", PUBLIC_REPOSITORY,
        "--base", "master",
        "--head", branch,
        "--title", "release(public): publish signed Runtime " + tag,
        "--body", "Source Runtime commit: " + source_commit,
    ])
    pull_number = run([
        "gh", "pr", "view", branch,
        "--repo", PUBLIC_REPOSITORY,
        "--json", "number",
        "--jq", ".number",
    ]).stdout.strip()
    run([
        "gh", "pr", "merge", pull_number,
        "--repo", PUBLIC_REPOSITORY,
        "--squash",
        "--subject", "release(public): publish signed Runtime %s (#%s)" % (tag, pull_number),
        "--body", "Source Runtime commit: " + source_commit,
    ], timeout=600)

    run(["git", "fetch", "--quiet", "origin", "master"])
    run(["git", "switch", "master"])
    run(["git", "merge", "--ff-only", "origin/master"])
    public_commit = run(["git", "rev-parse", "HEAD"]).stdout.strip()
    run(["git", "diff", "--exit-code", release_commit, public_commit, "--", *relative])
    run(["git", "tag", tag, public_commit])
    run(["git", "push", "origin", "refs/tags/" + tag])
    return public_commit


def create_public_release(tag: str, bundle: Path) -> None:
    run([
        "gh", "release", "create", tag,
        *[str(bundle / name) for name in required_release_assets()],
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
    changed.extend(stage_codex_hooks(bundle))
    changed.extend(update_public_metadata(tag, version, source_commit))
    changed.extend(prepare_package(version))
    changed.extend(prepare_plugin_release_policy(version))
    verify_plugin_release_policy(version)

    verify_codex_hook_contract()
    run([sys.executable, str(ROOT / "scripts/verify_distribution_consistency.py")])
    run([
        sys.executable, "-m", "pytest", "-q",
        "tests/test_codex_integration_cli.py",
        "tests/test_release_local_contract.py",
        "tests/test_plugin_release_policy.py",
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


def resume_publish(bundle: Path, tag: str, version: str, source_commit: str) -> dict:
    resume_state = resume_public_preflight(tag, version, source_commit)
    bundle_receipt = verify_bundle(bundle, tag, version, source_commit)
    verify_public_codex_hooks(bundle)
    verify_plugin_release_policy(version)

    verify_codex_hook_contract()
    run([sys.executable, str(ROOT / "scripts/verify_distribution_consistency.py")])
    run([
        sys.executable, "-m", "pytest", "-q",
        "tests/test_codex_integration_cli.py",
        "tests/test_release_local_contract.py",
        "tests/test_plugin_release_policy.py",
    ])
    run([str(bundle / "simplicio-macos-arm64"), "version", "--json"])
    if (ROOT / "scripts/verify_mcp_tools.py").is_file():
        run([
            sys.executable,
            str(ROOT / "scripts/verify_mcp_tools.py"),
            str(bundle / "simplicio-macos-arm64"),
        ])

    with tempfile.TemporaryDirectory(prefix="simplicio-public-resume-wheel-") as raw:
        wheel = build_wheel(Path(raw), version)
        wheel_help_smoke(wheel)
        terminal = run([
            sys.executable,
            str(ROOT / "scripts/release_install_smoke.py"),
            "--version", version, "--terminal", "--json",
        ], timeout=900)
        if not resume_state["already_published_to_pypi"]:
            run(
                [sys.executable, "-m", "twine", "upload", "--non-interactive", str(wheel)],
                timeout=900,
            )
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
        "schema": "simplicio.local-publication-resume/v1",
        "status": "verified",
        "resumed": True,
        "version": version,
        "tag": tag,
        "source_commit": source_commit,
        "public_commit": resume_state["public_commit"],
        "already_published_to_pypi": resume_state["already_published_to_pypi"],
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
    mode.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    tag, version = normalize_version(args.version)
    if re.fullmatch(r"[0-9a-f]{40}", args.source_commit) is None:
        raise PublishError("source commit must be a full SHA-1")
    if args.resume:
        receipt = resume_publish(args.bundle.resolve(), tag, version, args.source_commit)
    elif args.check_only:
        public_preflight(tag, version, require_clean=True)
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

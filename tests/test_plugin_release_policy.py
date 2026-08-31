"""Exercise release policy migration through real Git blobs and the JS consumer."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def release_policy(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "plugin_release_policy_fixture", ROOT / "scripts/publish_release_local.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public = tmp_path / "public"
    public.mkdir()
    monkeypatch.setattr(module, "ROOT", public)
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    source = (ROOT / module.PLUGIN_BOOTSTRAP).read_text(encoding="utf-8")
    for key in ("runtimeVersion", "minimumRuntimeVersion"):
        source = re.sub(
            r'(?m)^(  ' + key + r': ")[^"]+(",?)$',
            lambda match: match[1] + "3.8.35" + match[2],
            source,
        )
    bootstrap = public / module.PLUGIN_BOOTSTRAP
    bootstrap.parent.mkdir(parents=True)
    bootstrap.write_text(source, encoding="utf-8")
    test_path = public / "plugins/simplicio/tests/bootstrap.test.js"
    test_path.parent.mkdir(parents=True)
    test_path.write_bytes((ROOT / test_path.relative_to(public)).read_bytes())
    for relative in module.PLUGIN_MANIFESTS:
        path = public / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": "simplicio", "version": "0.2.4"}))
    blobs = {
        "install.sh": b"#!/bin/sh\nprintf 'fixture-only\\n'\n",
        "install.ps1": b"Write-Output 'fixture-only'\r\n# Preserve CRLF bytes.\r\n",
    }
    for name, content in blobs.items():
        (public / name).write_bytes(content)
    (public / ".gitattributes").write_text("install.* -text\n")

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=public, capture_output=True, text=True,
            timeout=30, check=True,
        ).stdout.strip()

    git("init", "-q", "--initial-branch=master")
    git("config", "user.name", "Release Fixture")
    git("config", "user.email", "release@example.test")
    git("config", "commit.gpgsign", "false")
    git("add", ".")
    git("commit", "-qm", "Fixture installers and bootstrap")
    remote = tmp_path / "origin.git"
    git("clone", "--bare", str(public), str(remote))
    git("remote", "add", "origin", str(remote))
    return module, public, blobs, git


def test_policy_moves_to_persistent_login_and_hashes_immutable_installer_bytes(release_policy):
    module, public, blobs, git = release_policy
    assert module.read_plugin_policy()["acceptsLegacy"] is True
    changed = module.prepare_plugin_release_policy("3.8.40")
    assert {path.relative_to(public).as_posix() for path in changed} == {
        module.PLUGIN_BOOTSTRAP, *module.PLUGIN_MANIFESTS
    }
    result = module.read_plugin_policy()
    policy = result["policy"]
    assert policy["runtimeVersion"] == "3.8.40"
    assert policy["minimumRuntimeVersion"] == "3.8.40"
    assert policy["installerCommit"] == git("rev-parse", "HEAD")
    assert result["acceptsLegacy"] is False
    assert result["acceptsTarget"] is True
    assert result["acceptsMinimum"] is True
    for installer in policy["installers"].values():
        assert installer["sha256"] == hashlib.sha256(blobs[installer["filename"]]).hexdigest()
    assert {body["version"] for _, body in module.plugin_manifests()} == {"0.2.5"}
    assert module.prepare_plugin_release_policy("3.8.40") == []
    assert {body["version"] for _, body in module.plugin_manifests()} == {"0.2.5"}

    module.prepare_plugin_release_policy("3.8.41")
    next_policy = module.read_plugin_policy()["policy"]
    assert next_policy["runtimeVersion"] == "3.8.41"
    assert next_policy["minimumRuntimeVersion"] == "3.8.40"


def test_unpublished_installer_commit_cannot_be_pinned(release_policy):
    module, public, _, git = release_policy
    before = (public / module.PLUGIN_BOOTSTRAP).read_bytes()
    git("commit", "--allow-empty", "-qm", "Unpublished local change")
    with pytest.raises(module.PublishError, match="published master"):
        module.prepare_plugin_release_policy("3.8.40")
    assert (public / module.PLUGIN_BOOTSTRAP).read_bytes() == before
    assert {body["version"] for _, body in module.plugin_manifests()} == {"0.2.4"}


@pytest.mark.parametrize("failure", ["old_release", "duplicate_field", "manifest_drift"])
def test_invalid_policy_inputs_fail_before_any_metadata_write(release_policy, failure):
    module, public, _, _ = release_policy
    bootstrap = public / module.PLUGIN_BOOTSTRAP
    if failure == "duplicate_field":
        body = bootstrap.read_text()
        body = body.replace('  runtimeVersion: "3.8.35",', '  runtimeVersion: "3.8.35",\n  runtimeVersion: "3.8.35",')
        bootstrap.write_text(body)
    elif failure == "manifest_drift":
        manifest = public / module.PLUGIN_MANIFESTS[0]
        document = json.loads(manifest.read_text())
        document["version"] = "0.2.9"
        manifest.write_text(json.dumps(document))
    paths = [bootstrap, *(public / relative for relative in module.PLUGIN_MANIFESTS)]
    before = {str(path): path.read_bytes() for path in paths}
    with pytest.raises(module.PublishError):
        module.prepare_plugin_release_policy("3.8.39" if failure == "old_release" else "3.8.40")
    assert {str(path): path.read_bytes() for path in paths} == before


def test_verifier_checks_published_bytes_and_runs_real_bootstrap_tests(release_policy, monkeypatch):
    module, _, blobs, _ = release_policy
    module.prepare_plugin_release_policy("3.8.40")
    commit = module.read_plugin_policy()["policy"]["installerCommit"]
    requested = []

    def read_installer(url, timeout):
        assert timeout == 30
        assert url.startswith(f"https://raw.githubusercontent.com/{module.PUBLIC_REPOSITORY}/{commit}/")
        filename = url.rsplit("/", 1)[1]
        requested.append(filename)
        return io.BytesIO(blobs[filename])

    monkeypatch.setattr(module.urllib.request, "urlopen", read_installer)
    module.verify_plugin_release_policy("3.8.40")
    assert requested == ["install.sh", "install.ps1"]

    monkeypatch.setattr(
        module.urllib.request, "urlopen",
        lambda *_args, **_kwargs: io.BytesIO(b"unexpected proxy response"),
    )
    with pytest.raises(module.PublishError, match="digest mismatch"):
        module.verify_plugin_release_policy("3.8.40")

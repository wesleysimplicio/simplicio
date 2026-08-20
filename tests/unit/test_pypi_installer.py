from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).parents[2] / "pypi" / "simplicio"
REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(PACKAGE_ROOT))
import simplicio  # noqa: E402
from simplicio import __main__ as installer  # noqa: E402

CURRENT_VERSION = "3.8.17"
TEST_TRUST = {CURRENT_VERSION: "fixture-digest"}


@pytest.fixture(autouse=True)
def fixture_manifest_trust(monkeypatch, request):
    if request.node.name != "test_default_manifest_pin_matches_versioned_checkout":
        monkeypatch.setattr(installer, "TRUSTED_MANIFEST_SHA256", TEST_TRUST)


def trusted_digest(payload):
    TEST_TRUST[CURRENT_VERSION] = hashlib.sha256(payload).hexdigest()
    return TEST_TRUST


class FakeReleaseClient:
    def __init__(self, manifest, payload=b"runtime", release=True):
        self.manifest = manifest
        self.payload = payload
        trusted_digest(manifest)
        self.release_data = (
            {
                "tag_name": "v3.8.17",
                "assets": [
                    {"name": installer.MANIFEST_ASSET},
                    {"name": "simplicio-linux-x64"},
                ],
            }
            if release
            else None
        )
        self.downloaded = []

    def release(self, version):
        return self.release_data

    def download_asset(self, asset):
        self.downloaded.append(asset["name"])
        if asset["name"] == installer.MANIFEST_ASSET:
            return self.manifest
        return self.payload


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def manifest_for(payload, version=CURRENT_VERSION, target="linux-x64", asset="simplicio-linux-x64"):
    return json_bytes(
        {
            "version": version,
            "artifacts": [
                {"target": target, "artifact": asset, "sha256": hashlib.sha256(payload).hexdigest()}
            ],
        }
    )


def json_bytes(value):
    return json.dumps(value).encode("utf-8")


def valid_runner(command, **kwargs):
    assert command[1:] == ["version", "--json"]
    assert kwargs["check"] and kwargs["capture_output"] and kwargs["text"]
    return subprocess.CompletedProcess(command, 0, '{"runtime":{"version":"3.8.17"}}', "")


def test_install_verifies_then_atomically_replaces_binary(tmp_path, monkeypatch):
    payload = b"verified runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    destination = tmp_path / "simplicio"
    destination.write_bytes(b"old")

    installer.do_install(
        client=client,
        install_dir=tmp_path,
        runner=valid_runner,
        trusted_manifest_sha256=trusted_digest(client.manifest),
    )

    assert destination.read_bytes() == payload
    assert client.downloaded == [installer.MANIFEST_ASSET, "simplicio-linux-x64"]
    assert not list(tmp_path.glob(".simplicio-*"))


def test_install_rejects_missing_target_without_downloading(tmp_path, monkeypatch):
    client = FakeReleaseClient(
        manifest_for(b"x", target="macos-arm64", asset="simplicio-macos-arm64")
    )
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))

    with pytest.raises(installer.InstallError, match="No release asset for linux-x64"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)

    assert client.downloaded == [installer.MANIFEST_ASSET]


def test_install_rejects_checksum_before_writing(tmp_path, monkeypatch):
    client = FakeReleaseClient(manifest_for(b"expected"), b"tampered")
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    destination = tmp_path / "simplicio"
    destination.write_bytes(b"old")

    with pytest.raises(installer.InstallError, match="checksum mismatch"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)

    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob(".simplicio-*"))


def test_install_rejects_manifest_version_mismatch(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload, version="3.5.3"), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))

    with pytest.raises(installer.InstallError, match="version mismatch"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)

    assert client.downloaded == [installer.MANIFEST_ASSET]


def test_install_rejects_runtime_version_and_preserves_existing_binary(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    (tmp_path / "simplicio").write_bytes(b"old")

    def wrong_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, '{"runtime":{"version":"3.5.3"}}', "")

    with pytest.raises(installer.InstallError, match="runtime has 3.5.3"):
        installer.do_install(client=client, install_dir=tmp_path, runner=wrong_runner)

    assert (tmp_path / "simplicio").read_bytes() == b"old"
    assert not list(tmp_path.glob(".simplicio-*"))


def test_target_uses_canonical_distribution_asset_names():
    assert installer._target("Linux", "x86_64") == ("linux-x64", "simplicio-linux-x64")
    assert installer._target("Darwin", "arm64") == ("macos-arm64", "simplicio-macos-arm64")
    assert installer._target("Windows", "AMD64") == ("windows-x64", "simplicio-windows-x64.exe")


def test_install_rejects_missing_release_before_any_download(tmp_path, monkeypatch):
    client = FakeReleaseClient(manifest_for(b"runtime"), release=False)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    with pytest.raises(installer.InstallError, match=f"GitHub Release v{CURRENT_VERSION}"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)
    assert client.downloaded == []


def test_install_rejects_missing_manifest_asset(tmp_path, monkeypatch):
    client = FakeReleaseClient(manifest_for(b"runtime"))
    client.release_data["assets"] = [{"name": "simplicio-linux-x64"}]
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    with pytest.raises(
        installer.InstallError,
        match="missing required asset simplicio-update-manifest.json",
    ):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)
    assert client.downloaded == []


def test_install_rejects_missing_runtime_asset_and_preserves_existing(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    client.release_data["assets"] = [{"name": installer.MANIFEST_ASSET}]
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    destination = tmp_path / "simplicio"
    destination.write_bytes(b"old")
    with pytest.raises(installer.InstallError, match="missing required asset simplicio-linux-x64"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)
    assert destination.read_bytes() == b"old"
    assert client.downloaded == [installer.MANIFEST_ASSET]


def test_install_rejects_invalid_runtime_json_and_cleans_staging(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    (tmp_path / "simplicio").write_bytes(b"old")

    def invalid_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "not-json", "")

    with pytest.raises(installer.InstallError, match="valid version JSON"):
        installer.do_install(client=client, install_dir=tmp_path, runner=invalid_runner)
    assert (tmp_path / "simplicio").read_bytes() == b"old"
    assert not list(tmp_path.glob(".simplicio-*"))


def test_console_entry_point_propagates_install_failure(monkeypatch):
    def failed_install():
        raise installer.InstallError("checksum mismatch")

    monkeypatch.setattr(installer, "do_install", failed_install)
    monkeypatch.setattr(sys, "argv", ["simplicio", "install"])
    with pytest.raises(SystemExit) as exc:
        simplicio.main()
    assert exc.value.code == 1


def test_resolve_binary_rejects_wrapper_at_canonical_path(monkeypatch):
    monkeypatch.setattr(installer.os.path, "exists", lambda path: path == installer.BINARY_PATH)
    monkeypatch.setattr(installer.sys, "argv", [installer.BINARY_PATH])
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    assert installer._resolve_binary() is None


def test_resolve_binary_prefers_real_canonical_binary(monkeypatch):
    monkeypatch.setattr(installer.os.path, "exists", lambda path: path == installer.BINARY_PATH)
    monkeypatch.setattr(installer.sys, "argv", ["/tmp/wrapper"])
    assert installer._resolve_binary() == installer.BINARY_PATH


def test_resolve_binary_uses_path_when_canonical_is_absent(monkeypatch):
    monkeypatch.setattr(installer.os.path, "exists", lambda path: False)
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/opt/bin/simplicio")
    monkeypatch.setattr(installer.sys, "argv", ["/tmp/wrapper"])
    assert installer._resolve_binary() == "/opt/bin/simplicio"


def test_release_client_fetches_versioned_release_and_asset():
    calls = []

    def opener(url):
        calls.append(url)
        return (
            Response(b'{"tag_name":"v3.8.11"}')
            if url.endswith("/v3.8.11")
            else Response(b"binary")
        )

    client = installer.ReleaseClient("https://api.example/releases", opener)
    assert client.release("v3.8.11")["tag_name"] == "v3.8.11"
    assert client.download_asset(
        {"browser_download_url": "https://github.com/org/repo/releases/download/v3/a"}
    ) == b"binary"
    assert calls == [
        "https://api.example/releases/v3.8.11",
        "https://github.com/org/repo/releases/download/v3/a",
    ]


def test_release_client_rejects_non_github_asset_url():
    with pytest.raises(installer.InstallError, match="valid GitHub download URL"):
        installer.ReleaseClient(opener=lambda url: None).download_asset(
            {"browser_download_url": "https://example.com/a"}
        )


def test_default_manifest_pin_matches_versioned_checkout():
    payload = (REPO_ROOT / "simplicio-update-manifest.json").read_bytes()
    assert installer.TRUSTED_MANIFEST_SHA256[CURRENT_VERSION] == hashlib.sha256(payload).hexdigest()


def test_install_rejects_substituted_or_unpinned_manifest_before_runtime_download(
    tmp_path, monkeypatch
):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    with pytest.raises(installer.InstallError, match="manifest digest mismatch"):
        installer.do_install(
            client=client,
            install_dir=tmp_path,
            runner=valid_runner,
            trusted_manifest_sha256={CURRENT_VERSION: "0" * 64},
        )
    assert client.downloaded == [installer.MANIFEST_ASSET]

    client = FakeReleaseClient(manifest_for(payload), payload)
    with pytest.raises(installer.InstallError, match="No trusted manifest digest"):
        installer.do_install(
            client=client, install_dir=tmp_path, runner=valid_runner, trusted_manifest_sha256={}
        )
    assert client.downloaded == [installer.MANIFEST_ASSET]


def test_target_rejects_unsupported_platform():
    with pytest.raises(installer.InstallError, match="Unsupported platform"):
        installer._target("Plan9", "mips")


def test_artifact_rejects_wrong_name_and_invalid_digest():
    with pytest.raises(installer.InstallError, match="asset mismatch"):
        installer._artifact(json.loads(manifest_for(b"x")), "linux-x64", "other", CURRENT_VERSION)
    manifest = json.loads(manifest_for(b"x"))
    manifest["artifacts"][0]["sha256"] = "not-a-digest"
    with pytest.raises(installer.InstallError, match="valid SHA-256"):
        installer._artifact(manifest, "linux-x64", "simplicio-linux-x64", CURRENT_VERSION)


@pytest.mark.parametrize(
    "manifest",
    [[], {"version": "3.8.11", "artifacts": {}}, {"artifacts": ["bad"]}],
)
def test_install_rejects_invalid_manifest_structure(tmp_path, monkeypatch, manifest):
    client = FakeReleaseClient(json_bytes(manifest))
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    with pytest.raises(installer.InstallError, match="invalid"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)


def test_install_rejects_invalid_release_assets_structure(tmp_path, monkeypatch):
    client = FakeReleaseClient(manifest_for(b"runtime"))
    client.release_data["assets"] = {}
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    with pytest.raises(installer.InstallError, match="invalid assets list"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)


def test_windows_staging_uses_exe_suffix(tmp_path, monkeypatch):
    payload = b"windows runtime"
    asset = "simplicio-windows-x64.exe"
    client = FakeReleaseClient(manifest_for(payload, target="windows-x64", asset=asset), payload)
    client.release_data["assets"].append({"name": asset})
    monkeypatch.setattr(installer, "_target", lambda: ("windows-x64", asset))
    monkeypatch.setattr(installer, "BINARY_NAME", "simplicio.exe")
    staged_paths = []

    def runner(command, **kwargs):
        staged_paths.append(command[0])
        return subprocess.CompletedProcess(command, 0, '{"runtime":{"version":"3.8.17"}}', "")

    installer.do_install(client=client, install_dir=tmp_path, runner=runner)
    assert staged_paths[0].endswith(".exe")
    assert (tmp_path / "simplicio.exe").read_bytes() == payload


def test_replace_failure_rolls_back_and_cleans_staging(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    destination = tmp_path / "simplicio"
    destination.write_bytes(b"old")

    def fail_replace(source, target):
        raise OSError("replace failed")

    monkeypatch.setattr(installer.os, "replace", fail_replace)
    with pytest.raises(installer.InstallError, match="stage or install"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)
    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob(".simplicio-*"))


def test_cleanup_failure_without_install_error_is_short_install_error(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    monkeypatch.setattr(installer.os, "replace", lambda source, target: None)

    def fail_unlink(path):
        raise OSError("cleanup failed")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(installer.InstallError, match="clean up the staged runtime"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)


def test_cleanup_failure_preserves_original_install_error(tmp_path, monkeypatch):
    payload = b"runtime"
    client = FakeReleaseClient(manifest_for(payload), payload)
    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))

    def invalid_runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "not-json", "")

    def fail_unlink(path):
        raise OSError("cleanup failed")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(installer.InstallError, match="valid version JSON"):
        installer.do_install(client=client, install_dir=tmp_path, runner=invalid_runner)


def test_install_reports_release_fetch_and_manifest_download_failures(tmp_path, monkeypatch):
    class FailingRelease:
        def release(self, version):
            raise OSError("offline")

    monkeypatch.setattr(installer, "_target", lambda: ("linux-x64", "simplicio-linux-x64"))
    with pytest.raises(installer.InstallError, match="Could not fetch GitHub Release"):
        installer.do_install(client=FailingRelease(), install_dir=tmp_path, runner=valid_runner)

    client = FakeReleaseClient(b"not-json")
    with pytest.raises(installer.InstallError, match="Could not read the release manifest"):
        installer.do_install(client=client, install_dir=tmp_path, runner=valid_runner)


def test_main_delegates_and_reports_missing_binary(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(installer.sys, "argv", ["simplicio", "chat", "hello"])
    monkeypatch.setattr(installer, "_resolve_binary", lambda: "/opt/simplicio")
    monkeypatch.setattr(
        installer.subprocess, "run", lambda command, check: calls.append((command, check))
    )
    installer.main()
    assert calls == [(["/opt/simplicio", "chat", "hello"], True)]

    monkeypatch.setattr(installer, "_resolve_binary", lambda: None)
    with pytest.raises(SystemExit) as exc:
        installer.main()
    assert exc.value.code == 1
    assert "not installed" in capsys.readouterr().out


def test_main_preserves_delegated_binary_exit_code(monkeypatch):
    monkeypatch.setattr(installer.sys, "argv", ["simplicio", "chat"])
    monkeypatch.setattr(installer, "_resolve_binary", lambda: "/opt/simplicio")

    def failing_run(command, check):
        raise subprocess.CalledProcessError(7, command)

    monkeypatch.setattr(installer.subprocess, "run", failing_run)
    with pytest.raises(SystemExit) as exc:
        installer.main()
    assert exc.value.code == 7


def test_main_reports_oserror_from_delegated_binary(monkeypatch, capsys):
    monkeypatch.setattr(installer.sys, "argv", ["simplicio", "chat"])
    monkeypatch.setattr(installer, "_resolve_binary", lambda: "/opt/simplicio")
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda command, check: (_ for _ in ()).throw(OSError("denied")),
    )
    with pytest.raises(SystemExit) as exc:
        installer.main()
    assert exc.value.code == 1
    assert "Could not run installed Simplicio" in capsys.readouterr().err

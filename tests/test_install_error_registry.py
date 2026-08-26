from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
REGISTRY = ROOT / "tests" / "install_error_registry.json"


def load_registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_registry_is_versioned_and_covers_all_installers():
    registry = load_registry()
    assert registry["schema"] == "simplicio.install-error-registry/v1"
    assert registry["version"] == 1
    entries = registry["entries"]
    assert len({entry["id"] for entry in entries}) == len(entries)
    platforms = {entry["platform"] for entry in entries}
    assert {"windows", "macos-linux", "windows-macos-linux"} <= platforms
    assert any(entry["platform"] == "macos" for entry in entries)
    assert any(entry["status"] in {"fixed", "guarded"} for entry in entries)


def test_every_registry_entry_links_to_existing_regression_tests():
    for entry in load_registry()["entries"]:
        assert entry["regression_tests"], entry["id"]
        for reference in entry["regression_tests"]:
            parts = reference.split("::")
            test_path = ROOT / parts[0]
            assert test_path.exists(), reference
            source = test_path.read_text(encoding="utf-8")
            for symbol in parts[1:]:
                assert symbol in source, reference


def test_unix_asset_fetch_failure_is_caught_and_cleaned():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")
    start = text.index('STAGING_PATH="$DEST_PATH.download-$$.tmp"')
    end = text.index('if [ ! -s "$STAGING_PATH" ]', start)
    block = text[start:end]
    assert 'if ! fetch "$DOWNLOAD_URL" "$STAGING_PATH"; then' in block
    assert 'rm -f "$STAGING_PATH"' in block
    assert "download falhou ao buscar $DOWNLOAD_URL" in block


def test_windows_fetch_failures_are_caught_and_cleaned():
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    assert "could not download Ed25519 verification helper" in powershell
    assert "Download failed for $Asset from $DownloadUrl" in powershell
    assert "if (Test-Path $StagingPath) { Remove-Item -Force $StagingPath" in powershell


def test_install_docs_use_pypi_bootstrap():
    for relative in ("README.md", "INSTALL.md", "READMEs/README.pt-BR.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "python3 -m pip install --upgrade simplicio-installer" in text
        assert "simplicio install" in text
        assert "raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh" not in text
    for relative in ("README.md", "INSTALL.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "py -m pip install --upgrade simplicio-installer" in text


def test_supported_unix_manifest_targets_are_present():
    targets = json.loads((ROOT / "distribution/targets.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "simplicio-update-manifest.json").read_text(encoding="utf-8"))
    target_ids = {item["id"] for item in targets["targets"] if item["installer"] == "install.sh"}
    manifest_targets = {item["target"] for item in manifest["artifacts"]}
    assert target_ids <= manifest_targets
    assert {"macos-arm64", "macos-x64", "linux-x64"} <= target_ids


def test_validation_sentinels_are_recorded_as_fixed():
    entries = {entry["id"]: entry for entry in load_registry()["entries"]}
    expected = {
        "MCP-BOOT-006",
        "CODEX-HOOK-007",
        "UNINSTALL-008",
        "MACOS-X64-009",
        "BENCH-010",
        "PYPI-MANIFEST-011",
    }
    assert expected <= entries.keys()
    assert all(entries[key]["status"] == "fixed" for key in expected)

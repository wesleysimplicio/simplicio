import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "prepare_pypi_release.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_pypi_release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "package"
    package = root / "simplicio"
    package.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "simplicio-installer"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (package / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    (package / "__main__.py").write_text(
        'TRUSTED_MANIFEST_SHA256 = {\n    "1.0.0": "' + "0" * 64 + '",\n}\n',
        encoding="utf-8",
    )
    return root


def manifest_fixture(tmp_path: Path, version: str = "2.0.0") -> Path:
    path = tmp_path / "simplicio-update-manifest.json"
    path.write_text(json.dumps({"version": version, "artifacts": []}) + "\n", encoding="utf-8")
    return path


def test_prepare_updates_versions_and_pins_exact_manifest_digest(tmp_path):
    module = load_module()
    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path)

    receipt = module.prepare(package_root, manifest, "v2.0.0")

    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert receipt["version"] == "2.0.0"
    assert receipt["manifest_sha256"] == digest
    assert 'version = "2.0.0"' in (package_root / "pyproject.toml").read_text()
    assert '__version__ = "2.0.0"' in (package_root / "simplicio/__init__.py").read_text()
    assert f'"2.0.0": "{digest}"' in (package_root / "simplicio/__main__.py").read_text()


def test_prepare_rejects_manifest_version_mismatch(tmp_path):
    module = load_module()
    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path, "2.0.1")

    with pytest.raises(module.PreparationError, match="does not match"):
        module.prepare(package_root, manifest, "2.0.0")


def test_check_mode_detects_drift_without_writing(tmp_path):
    module = load_module()
    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path)
    before = (package_root / "pyproject.toml").read_bytes()

    with pytest.raises(module.PreparationError, match="not prepared"):
        module.prepare(package_root, manifest, "2.0.0", check=True)

    assert (package_root / "pyproject.toml").read_bytes() == before


def test_preparation_is_idempotent_and_check_passes(tmp_path):
    module = load_module()
    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path)

    module.prepare(package_root, manifest, "2.0.0")
    receipt = module.prepare(package_root, manifest, "v2.0.0", check=True)

    assert receipt["ok"] is True
    assert receipt["changed_files"] == []


def test_invalid_version_and_malformed_manifest_fail_closed(tmp_path):
    module = load_module()
    with pytest.raises(module.PreparationError, match="invalid release version"):
        module.normalize_version("release-latest")

    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path)
    manifest.write_text("{not-json", encoding="utf-8")
    with pytest.raises(module.PreparationError, match="could not read release manifest"):
        module.prepare(package_root, manifest, "2.0.0")


def test_wrong_package_and_missing_trust_store_fail_closed(tmp_path):
    module = load_module()
    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path)
    pyproject = package_root / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace("simplicio-installer", "other"))
    with pytest.raises(module.PreparationError, match="not simplicio-installer"):
        module.prepare(package_root, manifest, "2.0.0")

    pyproject.write_text(pyproject.read_text().replace("other", "simplicio-installer"))
    (package_root / "simplicio/__main__.py").write_text("TRUST = {}\n", encoding="utf-8")
    with pytest.raises(module.PreparationError, match="mapping was not found"):
        module.prepare(package_root, manifest, "2.0.0")


def test_cli_json_receipts_cover_prepare_check_and_error(tmp_path, capsys):
    module = load_module()
    package_root = package_fixture(tmp_path)
    manifest = manifest_fixture(tmp_path)
    common = [
        "--version",
        "2.0.0",
        "--package-root",
        str(package_root),
        "--manifest",
        str(manifest),
        "--json",
    ]

    assert module.main(common) == 0
    prepared = json.loads(capsys.readouterr().out)
    assert prepared["ok"] is True
    assert module.main(common + ["--check"]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["mode"] == "check"

    assert module.main(["--version", "latest", "--json"]) == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["ok"] is False

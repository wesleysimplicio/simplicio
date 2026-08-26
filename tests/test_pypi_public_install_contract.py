from pathlib import Path

import hashlib
import json
import re


ROOT = Path(__file__).parents[1]


def test_pypi_package_is_the_current_verified_bootstrap():
    pyproject = (ROOT / "pypi/simplicio/pyproject.toml").read_text(encoding="utf-8")
    init = (ROOT / "pypi/simplicio/simplicio/__init__.py").read_text(encoding="utf-8")
    main = (ROOT / "pypi/simplicio/simplicio/__main__.py").read_text(encoding="utf-8")
    readme = (ROOT / "pypi/simplicio/README.md").read_text(encoding="utf-8")

    manifest_bytes = (ROOT / "simplicio-update-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert match is not None
    version = match.group(1)
    assert 'name = "simplicio-installer"' in pyproject
    assert version == str(manifest["version"]).lstrip("v")
    assert f'__version__ = "{version}"' in init
    assert f'"{version}": "{hashlib.sha256(manifest_bytes).hexdigest()}"' in main
    assert "python3 -m pip install --upgrade simplicio-installer" in readme
    assert "simplicio install" in readme


def test_primary_install_docs_use_pypi_on_all_supported_hosts():
    for relative in ("README.md", "INSTALL.md", "READMEs/README.pt-BR.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "python3 -m pip install --upgrade simplicio-installer" in text
        assert "simplicio install" in text
        assert "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh" in text
        assert "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex" in text

    for relative in ("README.md", "INSTALL.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "py -m pip install --upgrade simplicio-installer" in text


def test_translated_install_docs_use_the_pypi_bootstrap():
    translated = (
        "ar-SA",
        "es-ES",
        "fr-FR",
        "he-IL",
        "hi-IN",
        "id-ID",
        "it-IT",
        "ja-JP",
        "ko-KR",
        "ms-MY",
        "pl-PL",
        "ru-RU",
        "zh-CN",
    )
    for language in translated:
        text = (ROOT / f"READMEs/README.{language}.md").read_text(encoding="utf-8")
        assert "python3 -m pip install --upgrade simplicio-installer" in text
        assert "simplicio install" in text
        assert "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh" in text
        assert "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex" in text


def test_pypi_publication_is_local_manual_and_fail_closed():
    publisher = (ROOT / "scripts/publish_release_local.py").read_text(encoding="utf-8")
    assert not (ROOT / ".github/workflows/publish-pypi.yml").exists()
    for required in (
        "prepare_pypi_release.py",
        "release_install_smoke.py",
        "post_release_smoke.py",
        '"-m", "twine", "check"',
        '"-m", "twine", "upload"',
        '"--non-interactive"',
        '"--publish"',
        '"--resume"',
    ):
        assert required in publisher
    assert re.search(r"pypi-[A-Za-z0-9_-]{20,}", publisher) is None

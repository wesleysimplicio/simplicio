from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_pypi_package_is_the_current_verified_bootstrap():
    pyproject = (ROOT / "pypi/simplicio/pyproject.toml").read_text(encoding="utf-8")
    init = (ROOT / "pypi/simplicio/simplicio/__init__.py").read_text(encoding="utf-8")
    main = (ROOT / "pypi/simplicio/simplicio/__main__.py").read_text(encoding="utf-8")
    readme = (ROOT / "pypi/simplicio/README.md").read_text(encoding="utf-8")

    assert 'name = "simplicio-installer"' in pyproject
    assert 'version = "3.8.25"' in pyproject
    assert '__version__ = "3.8.25"' in init
    assert '"3.8.25": "c526055fccb869abbea98a15a322f6774b18410efe1bc6c07c7b9112889237b7"' in main
    assert "python3 -m pip install --upgrade simplicio-installer" in readme
    assert "simplicio install" in readme


def test_primary_install_docs_use_pypi_on_all_supported_hosts():
    for relative in ("README.md", "INSTALL.md", "READMEs/README.pt-BR.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "python3 -m pip install --upgrade simplicio-installer" in text
        assert "simplicio install" in text
        assert "raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh" not in text

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
        assert "raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh" not in text


def test_pypi_publish_workflow_builds_and_publishes_without_embedded_tokens():
    workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
    assert "pypi/simplicio" in workflow
    assert "PYPI_API_TOKEN" in workflow
    assert "python -m build" in workflow
    assert "python -m twine check" in workflow
    assert "simplicio-installer" in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "pypi-" not in workflow.replace("pypi-API-TOKEN-PLACEHOLDER", "")

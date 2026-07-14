"""Shared fixtures for the `simplicio` distribution-repo unit test suite.

These tests are fully isolated: every test builds its own throwaway repo
tree under ``tmp_path`` (pytest's built-in fixture), so nothing here reads
or writes real repository files, touches the network, or depends on wall
clock time unless a test explicitly freezes it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DEFAULT_VERSION = "3.5.2"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    _write(path, json.dumps(data))


class RepoBuilder:
    """Builds a minimal, valid fake copy of the distribution repo layout.

    Call the individual `with_*` helpers to mutate a single file away from
    the "everything consistent" baseline for a given test scenario, then
    call `root` (or just use the returned Path) to point the module at it.
    """

    def __init__(self, root: Path):
        self.root = root
        self.version = DEFAULT_VERSION

    def build(self) -> "RepoBuilder":
        root = self.root
        v = self.version

        _write(root / "VERSION.md", "# Version policy\n\nUse `master` branch only for installs.\n")
        _write(root / "version.txt", v)
        _write_json(
            root / "simplicio-update-manifest.json",
            {
                "version": v,
                "entitlement": {"beta_until": "2099-01-01"},
            },
        )

        install_body = (
            "Install:\n"
            "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh\n"
        )
        _write(root / "README.md", install_body)
        _write(root / "INSTALL.md", install_body)
        _write(root / "install.sh", install_body)
        _write(root / "install.ps1", install_body.replace("install.sh", "install.ps1"))
        _write(root / ".github/workflows/release.yml", "name: release\n")
        _write(root / "pypi/simplicio/simplicio/__main__.py", "# entrypoint\n")
        (root / "READMEs").mkdir(parents=True, exist_ok=True)

        _write(root / "Formula/simplicio.rb", f'class Simplicio < Formula\n  version "{v}"\nend\n')
        _write_json(root / "npm/simplicio/package.json", {"version": v})
        _write_json(root / "npm/simplicio-installer/package.json", {"version": v})
        _write_json(root / "npm/simplicio-unscoped/package.json", {"version": v})
        _write(root / "pypi/simplicio/pyproject.toml", f'[project]\nname = "simplicio"\nversion = "{v}"\n')

        _write(root / "SIMPLICIO_ECOSYSTEM.md", f"## Versão atual\n{v}\n")

        return self

    # -- scenario mutators -------------------------------------------------

    def with_version_txt(self, value: str) -> "RepoBuilder":
        _write(self.root / "version.txt", value)
        return self

    def with_manifest(self, **overrides: Any) -> "RepoBuilder":
        path = self.root / "simplicio-update-manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(overrides)
        _write_json(path, data)
        return self

    def with_beta_until(self, value) -> "RepoBuilder":
        path = self.root / "simplicio-update-manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("entitlement", {})["beta_until"] = value
        _write_json(path, data)
        return self

    def with_version_md_missing_master_clause(self) -> "RepoBuilder":
        _write(self.root / "VERSION.md", "# Version policy\n\nNo canonical branch declared.\n")
        return self

    def with_main_branch_reference(self, filename: str = "README.md") -> "RepoBuilder":
        _write(
            self.root / filename,
            "Install:\ncurl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh\n",
        )
        return self

    def with_formula_version(self, value: str) -> "RepoBuilder":
        _write(self.root / "Formula/simplicio.rb", f'class Simplicio < Formula\n  version "{value}"\nend\n')
        return self

    def with_formula_unparseable(self) -> "RepoBuilder":
        _write(self.root / "Formula/simplicio.rb", "class Simplicio < Formula\nend\n")
        return self

    def with_npm_version(self, package: str, value: str) -> "RepoBuilder":
        _write_json(self.root / f"npm/{package}/package.json", {"version": value})
        return self

    def with_pyproject_version(self, value: str) -> "RepoBuilder":
        _write(self.root / "pypi/simplicio/pyproject.toml", f'[project]\nname = "simplicio"\nversion = "{value}"\n')
        return self

    def with_pyproject_unparseable(self) -> "RepoBuilder":
        _write(self.root / "pypi/simplicio/pyproject.toml", '[project]\nname = "simplicio"\n')
        return self

    def with_ecosystem_version(self, value: str) -> "RepoBuilder":
        _write(self.root / "SIMPLICIO_ECOSYSTEM.md", f"## Versão atual\n{value}\n")
        return self

    def with_readme_beta_no_end_date(self) -> "RepoBuilder":
        path = self.root / "README.md"
        text = path.read_text(encoding="utf-8")
        _write(path, text + "\nWe are in public beta with no end date.\n")
        return self


@pytest.fixture
def repo(tmp_path: Path) -> RepoBuilder:
    """A consistent, passing fake repo tree ready for scenario mutation."""
    return RepoBuilder(tmp_path).build()


@pytest.fixture
def verify_module():
    """Import (or reuse) the module under test, isolated from sys.path pollution."""
    import verify_distribution_consistency as module

    return module

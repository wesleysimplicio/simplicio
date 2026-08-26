from __future__ import annotations

import re
import importlib.util
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "install.ps1"


def test_powershell_variables_followed_by_colon_are_braced():
    source = INSTALLER.read_text(encoding="utf-8")
    invalid = re.findall(
        r"\$(?!(?:env|global|script|local|private|using):)([A-Za-z_][A-Za-z0-9_]*):",
        source,
    )
    assert invalid == []
    assert "${LASTEXITCODE}: $detail" in source


def test_powershell_install_paths_use_windows_separators_and_join_path():
    source = INSTALLER.read_text(encoding="utf-8")
    assert '$InstallDir = Join-Path $env:USERPROFILE ".simplicio\\bin"' in source
    assert '$InstallDir = "$env:USERPROFILE\\.simplicio\\bin"' not in source
    assert "Join-Path $InstallDir" in source
    assert '$InstallDir = "$env:USERPROFILE/.simplicio/bin"' not in source


def test_mcp_docs_use_copy_safe_absolute_paths_for_every_platform():
    for relative in ("README.md", "MCP-CONNECT.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert 'command = "C:/Users/YourName/.simplicio/bin/simplicio.exe"' in source
        assert 'command = "/Users/your-name/.simplicio/bin/simplicio"' in source
        assert 'command = "/home/your-name/.simplicio/bin/simplicio"' in source
        assert 'command = "~/.simplicio/bin/simplicio"' not in source
        assert not re.search(r'command\s*=\s*"[A-Za-z]:\\(?!\\)', source)


def test_powershell_parser_accepts_the_public_installer():
    pwsh = shutil.which("pwsh")
    assert pwsh is not None, "pwsh is a required local release-test dependency"
    path = str(INSTALLER).replace("'", "''")
    script = (
        f"$path='{path}'; $tokens=$null; $errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$path,[ref]$tokens,[ref]$errors) > $null; "
        "if ($errors.Count -ne 0) { "
        "$errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
    )
    result = subprocess.run(
        [pwsh, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_public_repository_owns_local_pypi_and_release_publication():
    publisher = ROOT / "scripts/publish_release_local.py"
    assert publisher.is_file()
    source = publisher.read_text(encoding="utf-8")
    assert "pypi/simplicio" in source
    assert "twine" in source
    assert "wesleysimplicio/simplicio" in source
    assert "workflow" not in source.lower()
    assert "simplicio-runtime" not in source


def test_public_publisher_uses_post_release_smoke_cli_contract():
    publisher = (ROOT / "scripts/publish_release_local.py").read_text(encoding="utf-8")
    assert '"--repo", PUBLIC_REPOSITORY' in publisher
    assert '"--repository"' not in publisher
    assert '"core.whitespace=cr-at-eol"' in publisher


def test_public_publisher_requires_pr_merge_before_tagging():
    publisher = (ROOT / "scripts/publish_release_local.py").read_text(encoding="utf-8")
    assert '"gh", "pr", "create"' in publisher
    assert '"gh", "pr", "merge"' in publisher
    assert '["git", "push", "origin", "master"]' not in publisher
    assert '["git", "merge", "--ff-only", "origin/master"]' in publisher


def test_public_publisher_can_resume_after_an_external_partial_failure():
    source = (ROOT / "scripts/publish_release_local.py").read_text(encoding="utf-8")
    assert 'mode.add_argument("--resume"' in source
    assert "def resume_public_preflight(" in source
    assert "def resume_publish(" in source
    assert "already_published_to_pypi" in source


def test_publication_cleanliness_ignores_only_protected_local_state():
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.is_ignored_local_state(".simplicio/runtime-resource-map.json")
    assert module.is_ignored_local_state("pypi/simplicio/build/generated.whl")
    assert module.is_ignored_local_state(r".simplicio\\ledger\\events.jsonl")
    assert not module.is_ignored_local_state("README.md")
    assert not module.is_ignored_local_state("pypi/simplicio/pyproject.toml")
    source = script.read_text(encoding="utf-8")
    assert "public_preflight(tag, version, require_clean=True)" in source

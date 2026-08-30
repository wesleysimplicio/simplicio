from __future__ import annotations

import json
import re
import importlib.util
import shutil
import subprocess
import zipfile
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


def test_all_readmes_document_pypi_and_direct_installer_paths():
    readmes = [ROOT / "README.md", *sorted((ROOT / "READMEs").glob("README.*.md"))]
    assert len(readmes) == 15
    for path in readmes:
        source = path.read_text(encoding="utf-8")
        assert "simplicio-installer" in source, path
        assert "pip install" in source, path
        assert "install.sh" in source, path
        assert "install.ps1" in source, path


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


def test_public_publisher_stages_versioned_codex_hooks(tmp_path, monkeypatch):
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local_hooks", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    bundle = tmp_path / "bundle"
    public = tmp_path / "public"
    for relative in module.CODEX_HOOK_FILES:
        source = bundle / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("fixture " + relative + "\n", encoding="utf-8")
    (bundle / "codex/mcp-route.sh").chmod(0o755)

    monkeypatch.setattr(module, "ROOT", public)
    changed = module.stage_codex_hooks(bundle)

    assert {path.relative_to(public).as_posix() for path in changed} == set(
        module.CODEX_HOOK_FILES
    )
    for relative in module.CODEX_HOOK_FILES:
        assert (public / relative).read_bytes() == (bundle / relative).read_bytes()
    assert (public / "codex/mcp-route.sh").stat().st_mode & 0o111



def test_public_publisher_keeps_executables_out_of_the_source_commit(tmp_path, monkeypatch):
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local_assets", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    bundle = tmp_path / "bundle"
    public = tmp_path / "public"
    bundle.mkdir()
    public.mkdir()
    for name in module.required_release_assets():
        (bundle / name).write_bytes(("fixture:" + name).encode("utf-8"))

    monkeypatch.setattr(module, "ROOT", public)
    changed = module.stage_bundle(bundle)
    changed_names = {path.relative_to(public).as_posix() for path in changed}

    assert changed_names == set(module.required_release_assets()) - set(module.ASSETS)
    assert not (changed_names & set(module.ASSETS))
    for name in module.required_release_assets():
        assert (public / name).read_bytes() == (bundle / name).read_bytes()


def test_publication_paths_gate_the_executable_codex_hook_contract():
    publisher = (ROOT / "scripts/publish_release_local.py").read_text(encoding="utf-8")
    assert 'shutil.which("pwsh")' in publisher
    assert 'run(["bash", str(ROOT / "tests/test_codex_hooks.sh")], timeout=60)' in publisher
    assert publisher.count("verify_codex_hook_contract()") == 3


def test_publication_fails_closed_when_powershell_is_unavailable(monkeypatch):
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local_pwsh", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)

    try:
        module.verify_codex_hook_contract()
    except module.PublishError as exc:
        assert "PowerShell is required" in str(exc)
    else:
        raise AssertionError("publication accepted a skipped Windows hook contract")


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



def test_publication_force_stages_only_known_installer_source_wrappers():
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local_force_paths", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    for path in (
        "npm/simplicio/package.json",
        "npm/simplicio-installer/package.json",
        "npm/simplicio-unscoped/package.json",
        "pypi/simplicio/pyproject.toml",
        r"pypi\simplicio\simplicio\__main__.py",
    ):
        assert module.requires_forced_release_staging(path)

    for path in (
        "simplicio-macos-arm64",
        "simplicio-windows-x64.exe",
        "simplicio-macos-arm64.sig",
        "SHA256SUMS",
        "codex/mcp-route.sh",
        "scripts/publish_release_local.py",
    ):
        assert not module.requires_forced_release_staging(path)


def test_public_publisher_builds_wheel_from_clean_source(tmp_path, monkeypatch):
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local_clean_wheel", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    package = tmp_path / "package"
    source = package / "simplicio"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "stale.pyc").write_bytes(b"stale")
    build = package / "build"
    build.mkdir()
    (build / "stale.txt").write_text("stale", encoding="utf-8")
    monkeypatch.setattr(module, "PACKAGE_ROOT", package)

    def fake_run(command, **_kwargs):
        if command[1:3] == ["-m", "build"]:
            clean_source = Path(command[-1])
            assert not (clean_source / "build").exists()
            assert not any(
                "__pycache__" in path.parts or path.suffix == ".pyc"
                for path in clean_source.rglob("*")
            )
            output = Path(command[command.index("--outdir") + 1])
            output.mkdir(parents=True, exist_ok=True)
            wheel = output / "simplicio_installer-3.8.31-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("simplicio/__init__.py", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module, "run", fake_run)
    wheel = module.build_wheel(tmp_path / "output", "3.8.31")
    with zipfile.ZipFile(wheel) as archive:
        assert archive.namelist() == ["simplicio/__init__.py"]


def test_public_publisher_updates_all_release_version_consumers(tmp_path, monkeypatch):
    script = ROOT / "scripts/publish_release_local.py"
    spec = importlib.util.spec_from_file_location("publish_release_local_versions", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)

    (tmp_path / "VERSION.md").write_text(
        "## Runtime snapshot: v3.8.30\n"
        "## Current Version: v3.8.30\n"
        "  `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb`\n",
        encoding="utf-8",
    )
    for relative in ("README.md", "MCP-CONNECT.md"):
        (tmp_path / relative).write_text(
            "SIMPLICIO_CODEX_HOOK_REF=v3.8.30\n",
            encoding="utf-8",
        )
    wrappers = (
        "npm/simplicio/package.json",
        "npm/simplicio-installer/package.json",
        "npm/simplicio-unscoped/package.json",
    )
    for relative in wrappers:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"name": relative, "version": "3.8.30", "description": "fixture"},
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
    (tmp_path / "SIMPLICIO_ECOSYSTEM.md").write_text(
        "3.8.30 (release pública; quatro alvos)\n"
        "O manifest atualmente publicado neste repositório é o `3.8.30`.\n",
        encoding="utf-8",
    )

    changed = module.update_public_metadata(
        "v3.8.31",
        "3.8.31",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    assert (tmp_path / "version.txt").read_text(encoding="utf-8") == "3.8.31\n"
    assert all(json.loads((tmp_path / path).read_text())["version"] == "3.8.31" for path in wrappers)
    ecosystem = (tmp_path / "SIMPLICIO_ECOSYSTEM.md").read_text(encoding="utf-8")
    assert "3.8.30" not in ecosystem
    assert ecosystem.count("3.8.31") == 2
    assert tmp_path / "SIMPLICIO_ECOSYSTEM.md" in changed


def test_public_runbook_requires_manual_publication_without_actions():
    source = (ROOT / "docs/RELEASE_RUNBOOK.md").read_text(encoding="utf-8")
    assert "publish-pypi.yml" not in source
    assert "GitHub Actions" not in source
    assert "publicador local/manual" in source


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

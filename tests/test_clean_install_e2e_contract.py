import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / 'scripts' / 'e2e_clean_install.py'


def test_clean_install_harness_covers_all_release_targets():
    spec = importlib.util.spec_from_file_location('e2e_clean_install', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for target in ('linux-x64', 'windows-x64', 'macos-x64', 'macos-arm64'):
        report = module.static_contract(target)
        assert report['signature'] is True


def test_workflow_has_four_platform_matrix_entries():
    workflow = (ROOT / '.github/workflows/e2e.yml').read_text(encoding='utf-8')
    for value in ('ubuntu-latest', 'windows-latest', 'macos-13', 'macos-14'):
        assert value in workflow
    assert '--download --json' in workflow


def test_release_install_smoke_covers_terminal_and_pypi_paths():
    script = (ROOT / 'scripts/release_install_smoke.py').read_text(encoding='utf-8')
    workflow = (ROOT / '.github/workflows/publish-pypi.yml').read_text(encoding='utf-8')
    assert 'install.sh' in script
    assert 'install.ps1' in script
    assert 'simplicio-installer==' in script
    assert '"-m",' in script
    assert '"venv",' in script
    assert 'release_install_smoke.py' in workflow
    assert 'needs: publish' in workflow

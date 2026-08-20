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

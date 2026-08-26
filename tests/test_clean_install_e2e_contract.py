import importlib.util
import json
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


def test_public_target_table_has_exactly_four_release_entries():
    payload = json.loads((ROOT / 'distribution/targets.json').read_text(encoding='utf-8'))
    target_ids = {item['id'] for item in payload['targets']}
    assert target_ids == {'linux-x64', 'windows-x64', 'macos-x64', 'macos-arm64'}


def test_release_smokes_enable_the_canonical_optional_login_gate():
    for relative in ('scripts/e2e_clean_install.py', 'scripts/post_release_smoke.py'):
        source = (ROOT / relative).read_text(encoding='utf-8')
        assert 'SIMPLICIO_LOGIN_REQUIRED' in source
        assert 'SIMPLICIO_E2E_EXPECT_LOGIN_REQUIRED' not in source


def test_local_publisher_covers_terminal_pypi_and_post_release_smokes():
    script = (ROOT / 'scripts/release_install_smoke.py').read_text(encoding='utf-8')
    publisher = (ROOT / 'scripts/publish_release_local.py').read_text(encoding='utf-8')
    assert 'install.sh' in script
    assert 'install.ps1' in script
    assert 'simplicio-installer==' in script
    assert '"-m",' in script
    assert '"venv",' in script
    assert publisher.count('scripts/release_install_smoke.py') >= 2
    assert '"--terminal"' in publisher
    assert '"--pypi"' in publisher
    assert '"twine", "upload"' in publisher
    assert 'scripts/post_release_smoke.py' in publisher
    assert '"--repo", PUBLIC_REPOSITORY' in publisher


def test_shell_installer_uses_safe_printf_without_losing_ansi_rendering():
    installer = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert "printf '%b' \"${GREEN}\"" in installer
    assert "printf '%b\\n' \"${GREEN}" in installer
    assert 'printf "${GREEN}"' not in installer
    assert "printf '%s' \"${GREEN}\"" not in installer

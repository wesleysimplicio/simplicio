import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_macos_x64_maps_to_signed_release_asset_and_installer():
    targets = json.loads((ROOT / 'distribution/targets.json').read_text(encoding='utf-8'))
    target = next(item for item in targets['targets'] if item['id'] == 'macos-x64')
    manifest = json.loads((ROOT / 'simplicio-update-manifest.json').read_text(encoding='utf-8'))
    artifact = next(item for item in manifest['artifacts'] if item['target'] == target['manifest_target'])
    assert target['asset'] == 'simplicio-macos-x64'
    assert target['installer'] == 'install.sh'
    assert artifact['artifact'] == target['asset']
    assert artifact['sha256']
    assert artifact['signature'].startswith('ed25519:')


def test_shell_installer_does_not_reject_macos_x64():
    text = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert 'TARGET_ID="$OS-$ARCH"' in text
    assert 'simplicio-$OS-$ARCH' in text
    assert 'macos-x86_64' not in text

#!/usr/bin/env python3
"""Cross-platform clean-install release smoke with an isolated HOME."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / 'distribution' / 'targets.json'
MANIFEST = ROOT / 'simplicio-update-manifest.json'

def load_target(target_id: str) -> tuple[dict, dict, dict]:
    target = next((item for item in json.loads(TARGETS.read_text()).get('targets', []) if item.get('id') == target_id), None)
    if not target:
        raise SystemExit(f'unknown target: {target_id}')
    manifest = json.loads(MANIFEST.read_text())
    artifact = next((item for item in manifest.get('artifacts', []) if item.get('target') == target.get('manifest_target', target_id)), None)
    if not artifact:
        raise SystemExit(f'manifest is missing target: {target_id}')
    return target, artifact, manifest

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def run_checked(command: list[str], env: dict[str, str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, env=env, input=input_text, capture_output=True, text=True, timeout=90)

def static_contract(target_id: str) -> dict:
    target, artifact, manifest = load_target(target_id)
    asset = ROOT / str(target['asset'])
    if not asset.is_file() or asset.stat().st_size == 0:
        raise SystemExit(f'asset missing or empty: {asset.name}')
    if sha256(asset).lower() != str(artifact.get('sha256', '')).lower():
        raise SystemExit(f'asset checksum mismatch: {asset.name}')
    if not str(artifact.get('signature', '')).startswith('ed25519:'):
        raise SystemExit(f'asset has no Ed25519 signature metadata: {target_id}')
    installer = ROOT / str(target['installer'])
    if not installer.is_file():
        raise SystemExit(f'installer missing: {installer}')
    return {'target': target_id, 'asset': target['asset'], 'version': manifest.get('version'), 'checksum': artifact.get('sha256'), 'signature': True}

def download_check(target_id: str, artifact: dict, manifest: dict) -> dict:
    url = str(artifact.get('url') or '')
    if not url:
        raise SystemExit(f'manifest has no download URL: {target_id}')
    with tempfile.NamedTemporaryFile(prefix='simplicio-e2e-', delete=False) as handle:
        path = Path(handle.name)
    try:
        urllib.request.urlretrieve(url, path)
        actual = sha256(path)
        expected = str(artifact.get('sha256', '')).lower()
        if actual.lower() != expected:
            raise SystemExit(f'download checksum mismatch for {target_id}: {actual} != {expected}')
        return {'download_url': url, 'download_checksum': actual}
    finally:
        path.unlink(missing_ok=True)

def runtime_check(target_id: str, target: dict, env: dict[str, str]) -> dict:
    binary = ROOT / str(target['asset'])
    if os.name == 'nt':
        command = [str(binary)]
    else:
        command = [str(binary)]
    if not os.access(binary, os.X_OK):
        raise SystemExit(f'fixture is not executable on this runner: {binary.name}')
    version = run_checked(command + ['version', '--json'], env)
    if version.returncode != 0:
        raise SystemExit(f'version --json failed: {version.stderr[-500:]}')
    payload = json.loads(version.stdout)
    if not (payload.get('identity') or {}).get('login_enabled'):
        raise SystemExit('Runtime does not advertise login_enabled')
    with tempfile.TemporaryDirectory(prefix='simplicio-clean-home-') as home:
        clean_env = dict(env)
        clean_env.update({'HOME': home, 'USERPROFILE': home, 'XDG_CONFIG_HOME': str(Path(home) / '.config'), 'SIMPLICIO_LOGIN_REQUIRED': '1'})
        status = run_checked(command + ['auth', 'status', '--json'], clean_env)
        status_output = (status.stdout + status.stderr).lower()
        if status.returncode != 0 and 'login' not in status_output and 'authenticated' not in status_output:
            raise SystemExit(f'clean-home auth status failed: {status.stderr[-500:]}')
        if status.returncode == 0:
            json.loads(status.stdout)
        requests = ''.join(json.dumps(item) + '\n' for item in ({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}))
        mcp = run_checked(command + ['serve', '--mcp', '--stdio', '--json'], clean_env, input_text=requests)
        combined = (mcp.stdout + mcp.stderr).lower()
        if 'login' not in combined and 'authenticated' not in combined and mcp.returncode == 0:
            raise SystemExit('clean-home MCP handshake did not report login-required state')
    return {'version_json': True, 'clean_home': True, 'mcp_login_gate': True}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', required=True)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--static-only', action='store_true')
    args = parser.parse_args(argv)
    target, artifact, manifest = load_target(args.target)
    report = static_contract(args.target)
    if args.download:
        report.update(download_check(args.target, artifact, manifest))
    if not args.static_only:
        report.update(runtime_check(args.target, target, dict(os.environ)))
        node = run_checked(['node', '--test', 'tests/node/installer-e2e.test.cjs'], dict(os.environ))
        if node.returncode != 0:
            raise SystemExit(node.stdout + node.stderr)
        report['npm_wrapper_smoke'] = True
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print('E2E PASS ' + json.dumps(report, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

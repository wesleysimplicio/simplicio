#!/usr/bin/env python3
"""Transactional, opt-in Codex MCP/hook integration manager."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

MARKER = '# BEGIN SIMPLICIO CODEX INTEGRATION v1'
END_MARKER = '# END SIMPLICIO CODEX INTEGRATION v1'

def paths(home: Path) -> tuple[Path, Path, Path, Path]:
    # --home is an explicit isolation boundary for installers, tests, and repair.
    # Do not let a process-wide CODEX_HOME redirect writes outside that boundary.
    codex = home / '.codex'
    return codex / 'config.toml', codex / 'hooks.json', home / '.simplicio' / 'hooks', home / '.simplicio' / 'codex-integration.json'

def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def backup_once(path: Path) -> None:
    backup = Path(str(path) + '.simplicio.bak')
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)

def hook_source(root: Path, platform: str) -> Path:
    return root / 'codex' / ('mcp-route.ps1' if platform == 'windows' else 'mcp-route.sh')

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'{path} must contain an object')
    return value

def install(args: argparse.Namespace) -> dict:
    config_path, hooks_path, hook_dir, state_path = paths(args.home)
    source = hook_source(args.source_root, args.platform)
    if not source.is_file():
        raise SystemExit(f'hook source not found: {source}')
    backup_once(config_path); backup_once(hooks_path)
    hook_path = hook_dir / source.name
    hook_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, hook_path)
    if hook_path.suffix == '.sh':
        hook_path.chmod(0o755)
    config = config_path.read_text(encoding='utf-8') if config_path.exists() else ''
    while MARKER in config and END_MARKER in config:
        start = config.index(MARKER); end = config.index(END_MARKER, start) + len(END_MARKER)
        config = config[:start] + config[end:]
    binary = args.binary or 'simplicio'
    if args.platform == 'windows':
        # Forward slashes are accepted by Windows and remain literal inside a
        # TOML basic string; an unescaped C:\\Users path would make \\U invalid.
        binary = binary.replace('\\', '/')
    block = f'{MARKER}\n[mcp_servers.simplicio]\ncommand = {json.dumps(binary)}\nargs = ["serve", "--mcp", "--stdio"]\n{END_MARKER}\n'
    config = config.rstrip() + ('\n\n' if config.strip() else '') + block
    atomic_write(config_path, config)
    root = load_json(hooks_path)
    hook_root = root.setdefault('hooks', {})
    if not isinstance(hook_root, dict):
        raise SystemExit('hooks.json has an invalid hooks object')
    entries = hook_root.setdefault('PreToolUse', [])
    if isinstance(entries, dict): entries = [entries]
    entries = [item for item in entries if not (isinstance(item, dict) and any('mcp-route' in str(h.get('command', '')) for h in item.get('hooks', []) if isinstance(h, dict)))]
    command = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{hook_path}"' if args.platform == 'windows' else f'bash "{hook_path}"'
    entries.append({'matcher': 'Bash|apply_patch|Edit|Write', 'hooks': [{'type': 'command', 'command': command, 'timeout': 8, 'statusMessage': 'Routing through Simplicio MCP'}]})
    hook_root['PreToolUse'] = entries
    root['simplicio'] = {'managed': True, 'version': args.version, 'hook_ref': args.hook_ref, 'mcp_separate_from_hooks': True}
    atomic_write(hooks_path, json.dumps(root, indent=2) + '\n')
    atomic_write(state_path, json.dumps(root['simplicio'], indent=2) + '\n')
    return {'status': 'installed', 'version': args.version, 'hook_ref': args.hook_ref, 'config': str(config_path), 'hooks': str(hooks_path)}

def uninstall(args: argparse.Namespace) -> dict:
    config_path, hooks_path, hook_dir, state_path = paths(args.home)
    for path in (config_path, hooks_path):
        backup = Path(str(path) + '.simplicio.bak')
        if backup.exists():
            shutil.copy2(backup, path)
    for hook in (hook_dir / 'mcp-route.sh', hook_dir / 'mcp-route.ps1'):
        hook.unlink(missing_ok=True)
    if state_path.exists(): state_path.unlink()
    return {'status': 'uninstalled', 'preserved_data': True}

def status(args: argparse.Namespace) -> dict:
    _, _, _, state_path = paths(args.home)
    state = load_json(state_path) if state_path.exists() else {}
    return {'status': 'installed' if state.get('managed') else 'absent', 'state': state}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('status', 'install', 'uninstall', 'repair'))
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--binary', default='simplicio')
    parser.add_argument('--version', default=os.environ.get('SIMPLICIO_VERSION', 'unknown'))
    parser.add_argument('--hook-ref', default='')
    parser.add_argument('--platform', choices=('unix', 'windows'), default='windows' if os.name == 'nt' else 'unix')
    args = parser.parse_args(argv)
    if args.command == 'status': result = status(args)
    elif args.command == 'uninstall': result = uninstall(args)
    else:
        if not args.hook_ref: raise SystemExit('hook ref is required; use --hook-ref vX.Y.Z')
        result = install(args)
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_install_docs_match_opt_in_transactional_contract():
    readme = read('README.md')
    install = read('INSTALL.md')
    assert 'SIMPLICIO_INSTALL_CODEX=1' in readme
    assert 'SIMPLICIO_INSTALL_CODEX=1' in install
    assert '--uninstall --keep-data' in readme
    assert '--uninstall --purge' in install
    assert 'SIMPLICIO_CONFIRM_PURGE=1' in readme
    assert 'rm -rf ~/.simplicio' not in install


def test_mcp_docs_match_local_authentication_contract():
    mcp = read('MCP-CONNECT.md')
    assert 'local STDIO' in mcp
    assert 'Google login' in mcp
    assert 'SIMPLICIO_INSTALL_CODEX=1' in mcp
    assert 'Ed25519' in mcp


def test_public_docs_point_to_canonical_distribution_contract():
    version = read('VERSION.md')
    asolaria = read('docs/asolaria-integration.md')
    assert 'macOS x64' in version
    assert 'distribution/targets.json' in asolaria
    assert 'histórico' in asolaria
    assert 'simplicio-update-manifest.json' in asolaria

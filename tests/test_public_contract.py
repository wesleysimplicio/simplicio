from pathlib import Path


ROOT = Path(__file__).parents[1]


def read(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_install_docs_match_automatic_transactional_contract():
    readme = read('README.md')
    install = read('INSTALL.md')
    assert 'SIMPLICIO_INSTALL_CODEX' not in readme
    assert 'SIMPLICIO_INSTALL_CODEX' not in install
    assert 'automatically' in readme
    assert '--uninstall --keep-data' in readme
    assert '--uninstall --purge' in install
    assert 'SIMPLICIO_CONFIRM_PURGE=1' in readme
    assert 'rm -rf ~/.simplicio' not in install


def test_mcp_docs_match_local_authentication_contract():
    mcp = read('MCP-CONNECT.md')
    assert 'local STDIO' in mcp
    assert 'Google login' in mcp
    assert 'SIMPLICIO_INSTALL_CODEX' not in mcp
    assert 'automatically' in mcp
    assert 'Ed25519' in mcp
    assert 'simplicio map' in mcp
    assert 'simplicio context' in mcp
    assert 'simplicio_context' in mcp


def test_public_docs_use_unified_mapper_vocabulary():
    readme = read('README.md')
    assert '`simplicio map --repo . --for-llm markdown`' in readme
    assert '`simplicio context --repo .`' in readme
    assert '`simplicio memory query "query" --json`' in readme
    assert '`simplicio edit --plan plan.json --repo .`' in readme
    assert '`simplicio run "task" --repo . --agents N`' in readme
    assert 'simplicio_context' in readme
    assert 'Mapper observes' in readme


def test_public_docs_point_to_canonical_distribution_contract():
    version = read('VERSION.md')
    asolaria = read('docs/asolaria-integration.md')
    assert 'macOS x64' in version
    assert 'distribution/targets.json' in asolaria
    assert 'histórico' in asolaria
    assert 'simplicio-update-manifest.json' in asolaria

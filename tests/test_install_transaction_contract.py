from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shell_uninstall_policy_and_rollback_are_explicit():
    text = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert '--keep-data' in text and '--purge' in text
    assert 'SIMPLICIO_CONFIRM_PURGE' in text
    assert 'INSTALL_TRANSACTION_ACTIVE' in text
    assert 'PREVIOUS_PATH' in text
    assert 'rollback_install' in text
    assert 'rm -rf "$PURGE_DIR"' in text


def test_powershell_uninstall_policy_and_rollback_are_explicit():
    text = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert '[switch]$KeepData' in text and '[switch]$Purge' in text
    assert 'SIMPLICIO_CONFIRM_PURGE' in text
    assert '$InstallTransactionActive' in text
    assert '$PreviousPath' in text
    assert 'Invoke-Rollback' in text
    assert 'Remove-Item -Recurse -Force $bundleDir' in text

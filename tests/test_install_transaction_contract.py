from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_shell_uninstall_policy_and_rollback_are_explicit():
    text = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert '--keep-data' in text and '--purge' in text
    assert 'SIMPLICIO_CONFIRM_PURGE' in text
    assert 'INSTALL_TRANSACTION_ACTIVE' in text
    assert 'PREVIOUS_PATH' in text
    assert 'rollback_install' in text
    assert 'for _entry in "$PURGE_DIR"/*' in text
    assert 'basename "$_entry"' in text
    assert 'dados do Simplicio removidos' in text
    assert 'AUTH_FILE' in text
    assert 'AUTH_FILE_WAS_PRESENT' in text
    assert 'estado de login desapareceu' in text


def test_shell_swap_has_one_activation_message_after_atomic_move():
    text = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert text.count('mv -f \"$STAGING_PATH\" \"$DEST_PATH\"') == 1
    assert text.count('ok \"Simplicio Runtime instalado em $DEST_PATH\"') == 1


def test_powershell_uninstall_policy_and_rollback_are_explicit():
    text = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert '[switch]$KeepData' in text and '[switch]$Purge' in text
    assert 'SIMPLICIO_CONFIRM_PURGE' in text
    assert '$InstallTransactionActive' in text
    assert '$PreviousPath' in text
    assert 'Invoke-Rollback' in text
    assert 'Where-Object { $_.Name -ne ".env" }' in text
    assert 'Simpli' in text and '.env and login state removed by explicit purge' in text
    assert '$AuthFile' in text
    assert '$AuthFileWasPresent' in text
    assert 'Login state disappeared during the upgrade' in text


def test_shell_purge_removes_simplicio_state_but_preserves_provider_env(tmp_path):
    import os
    import subprocess

    bundle = tmp_path / '.simplicio'
    bundle.mkdir()
    dotenv = bundle / '.env'
    dotenv.write_text('XAI_API_KEY=redacted-test-value\n', encoding='utf-8')
    (bundle / 'runtime-state.json').write_text('{}\n', encoding='utf-8')
    binary = tmp_path / '.local' / 'bin' / 'simplicio'
    binary.parent.mkdir(parents=True)
    binary.write_text('binary\n', encoding='utf-8')

    env = os.environ.copy()
    env.update({
        'HOME': str(tmp_path),
        'SIMPLICIO_BIN_DIR': str(binary.parent),
        'SIMPLICIO_BUNDLE_DIR': str(bundle),
        'SIMPLICIO_CONFIRM_PURGE': '1',
    })
    result = subprocess.run(
        ['sh', str(ROOT / 'install.sh'), '--uninstall', '--purge'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert dotenv.exists()
    assert not (bundle / 'runtime-state.json').exists()
    assert not binary.exists()
def test_powershell_signature_verifier_probes_all_python3_command_names():
    script = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert '@{ Name = "py"; Args = @(' in script
    assert '@{ Name = "python3"; Args = @() }' in script
    assert '@{ Name = "python"; Args = @() }' in script
    assert 'sys.version_info[0] == 3' in script
    assert '([string]$Signature).Trim()' in script
    assert 'ToLowerInvariant()' in script

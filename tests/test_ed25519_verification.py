import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
HELPER = ROOT / 'scripts' / 'verify_ed25519.py'
RUNTIME_PUBLIC_KEY = '2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok='
RUNTIME_SIGNATURE = '/Tt+wpY4VedOmsOJRPAaAz470OfD4QprLGnTed7QGkkWgyqLoeg2U/dr6PD3EWl4rvHLiok2UWALeDBvG9KmCQ=='
RUNTIME_DIGEST = '12681adb6fa49bc2a5d39f8feca42baabe5d97b61cfdf40a5d452d890a8be83a'


def run(signature=RUNTIME_SIGNATURE, digest=RUNTIME_DIGEST):
    return subprocess.run([
        sys.executable, str(HELPER), '--public-key', RUNTIME_PUBLIC_KEY,
        '--signature', 'ed25519:' + signature, '--sha256', digest,
    ], capture_output=True, text=True)


def test_runtime_domain_separated_signature_is_accepted():
    result = run()
    assert result.returncode == 0, result.stderr


def test_tampered_signature_is_rejected():
    tampered = ('A' if RUNTIME_SIGNATURE[0] != 'A' else 'B') + RUNTIME_SIGNATURE[1:]
    assert run(tampered).returncode != 0


def test_installers_pin_and_invoke_crypto_verification():
    shell = (ROOT / 'install.sh').read_text(encoding='utf-8')
    powershell = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert 'ED25519_PUBLIC_KEY' in shell and 'verify_ed25519_signature' in shell
    assert '$Ed25519PublicKey' in powershell and 'Test-Ed25519Signature' in powershell
    assert 'SIMPLICIO_ALLOW_UNVERIFIED' in shell and 'SIMPLICIO_ALLOW_UNVERIFIED' in powershell

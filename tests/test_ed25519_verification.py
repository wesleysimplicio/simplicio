import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
HELPER = ROOT / 'scripts' / 'verify_ed25519.py'
RUNTIME_PUBLIC_KEY = 'A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg='
RUNTIME_SIGNATURE = 'UKIyIZkSH3nmk+E1LybN3bjQlPpiumLoLIu+bdQUC/j4/6nQkNX3MBhU7kZv+OZ6S9iLYVGwwzPZD5n//MGGAQ=='
RUNTIME_DIGEST = '3ba84e1d362618f0e9f45064634a1594485bca3298b8182b5a7eaa3fded4688f'


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

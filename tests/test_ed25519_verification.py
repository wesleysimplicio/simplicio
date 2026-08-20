import base64
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
HELPER = ROOT / 'scripts' / 'verify_ed25519.py'
# RFC 8032 public key, with a deterministic 32-byte zero digest payload.
RFC_PUBLIC_KEY = base64.b64encode(bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')).decode()
RFC_SIGNATURE = 'NVx0BTo4CrWLKY3iOtzKSfObfKUKLOxbhh9sf934fIpTt4x7s5WSaMDbHt6wRAeGg5713vqtYjKQB2GYVgs8Ag=='


def run(signature=RFC_SIGNATURE, digest='00' * 32):
    return subprocess.run([
        sys.executable, str(HELPER), '--public-key', RFC_PUBLIC_KEY,
        '--signature', 'ed25519:' + signature, '--sha256', digest,
    ], capture_output=True, text=True)


def test_rfc8032_signature_is_accepted():
    result = run()
    assert result.returncode == 0, result.stderr


def test_tampered_signature_is_rejected():
    tampered = ('A' if RFC_SIGNATURE[0] != 'A' else 'B') + RFC_SIGNATURE[1:]
    assert run(tampered).returncode != 0


def test_installers_pin_and_invoke_crypto_verification():
    shell = (ROOT / 'install.sh').read_text(encoding='utf-8')
    powershell = (ROOT / 'install.ps1').read_text(encoding='utf-8')
    assert 'ED25519_PUBLIC_KEY' in shell and 'verify_ed25519_signature' in shell
    assert '$Ed25519PublicKey' in powershell and 'Test-Ed25519Signature' in powershell
    assert 'SIMPLICIO_ALLOW_UNVERIFIED' in shell and 'SIMPLICIO_ALLOW_UNVERIFIED' in powershell

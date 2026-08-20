# Update signature contract

This document records the trust contract shared by the compiled Runtime and
the public bootstrap installers. It exists to prevent a future release from
being published with a signature that the installer cannot validate.

## Canonical payload

For an artifact digest `D`, where `D` is the lowercase 64-character SHA-256
hex string, Runtime `simplicio update sign D` signs the UTF-8 bytes of:

```text
simplicio-release-v1:D
```

The signature is published as `ed25519:<base64-signature>` in both the artifact
sidecar (`<artifact>.sig`) and the corresponding manifest entry. The manifest
public key must match the key compiled into the Runtime and pinned by the
installers.

## Verification order

Every installer must:

1. download the immutable release manifest and artifact;
2. compare the artifact SHA-256 with the manifest;
3. verify the Ed25519 signature over the canonical payload above;
4. verify the Runtime distribution contract;
5. only then replace the installed binary.

An invalid or missing signature is a hard failure. `SIMPLICIO_ALLOW_UNVERIFIED=1`
is only an explicit checksum-only emergency override and must not be used for
official releases.

## Regression protection

The public repository keeps the verifier in `scripts/verify_ed25519.py`. The
following tests must remain green before publishing:

```bash
python3 -m unittest discover -s tests -p 'test_verify_ed25519.py'
python3 -m unittest discover -s tests -p 'test_release_provenance.py'
```

The fixture covers the real Runtime domain-separated payload and deliberately
rejects a raw digest signature. The release provenance gate also verifies the
cryptographic signature for every staged artifact whenever the manifest marks
signatures as required.

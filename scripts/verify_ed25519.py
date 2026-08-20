#!/usr/bin/env python3
"""Minimal RFC 8032 Ed25519 verifier for installer bootstrap trust.

The Runtime signs a domain-separated UTF-8 payload, not the raw 32-byte
SHA-256 digest.  Keeping this contract here prevents the Windows and
macOS/Linux bootstrap installers from drifting from the compiled Runtime:

    simplicio-release-v1:<lowercase sha256>

The sidecar and manifest carry the resulting ``ed25519:<base64>`` signature.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import sys

Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, Q - 2, Q)) % Q
I = pow(2, (Q - 1) // 4, Q)
B_Y = 4 * pow(5, Q - 2, Q) % Q
SIGNATURE_DOMAIN = "simplicio-release-v1:"

def inv(x: int) -> int:
    return pow(x, Q - 2, Q)

def x_recover(y: int) -> int:
    xx = (y * y - 1) * inv(D * y * y + 1) % Q
    x = pow(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q:
        x = x * I % Q
    if (x * x - xx) % Q:
        raise ValueError("invalid Ed25519 point")
    return x

def decode_point(raw: bytes) -> tuple[int, int]:
    if len(raw) != 32:
        raise ValueError("Ed25519 point must be 32 bytes")
    value = int.from_bytes(raw, "little")
    sign = value >> 255
    y = value & ((1 << 255) - 1)
    if y >= Q:
        raise ValueError("invalid Ed25519 y coordinate")
    x = x_recover(y)
    if (x & 1) != sign:
        x = Q - x
    return x, y

def encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    return ((y | ((x & 1) << 255))).to_bytes(32, "little")

def add(P: tuple[int, int], R: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = P
    x2, y2 = R
    denominator_x = inv(1 + D * x1 * x2 * y1 * y2)
    denominator_y = inv(1 - D * x1 * x2 * y1 * y2)
    return ((x1 * y2 + x2 * y1) * denominator_x % Q,
            (y1 * y2 + x1 * x2) * denominator_y % Q)

def scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    current = point
    while scalar:
        if scalar & 1:
            result = add(result, current)
        current = add(current, current)
        scalar >>= 1
    return result

B = (x_recover(B_Y), B_Y)
if B[0] & 1:
    B = (Q - B[0], B[1])

def verify(public_key: bytes, signature: bytes, message: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        A = decode_point(public_key)
        R = decode_point(signature[:32])
    except ValueError:
        return False
    S = int.from_bytes(signature[32:], "little")
    if S >= L:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % L
    return encode_point(scalar_mult(B, S)) == encode_point(add(R, scalar_mult(A, h)))

def parse_signature(value: str) -> bytes:
    if not value.startswith("ed25519:"):
        raise ValueError("signature must use ed25519:<base64> format")
    return base64.b64decode(value[8:], validate=True)


def canonical_sha256(value: str) -> str:
    """Return the canonical lowercase SHA-256 text accepted by the Runtime."""
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("SHA-256 digest must be exactly 64 hexadecimal characters")
    return digest


def signature_payload(sha256_hex: str) -> bytes:
    """Build the exact domain-separated payload signed by Runtime ``update sign``."""
    digest = canonical_sha256(sha256_hex)
    return f"{SIGNATURE_DOMAIN}{digest}".encode("ascii")


def verify_signature_for_digest(public_key_value: str, signature_value: str, sha256_hex: str) -> bool:
    """Verify a Runtime release signature for a hexadecimal artifact digest."""
    public_key = base64.b64decode(public_key_value.strip(), validate=True)
    signature = parse_signature(signature_value.strip())
    return verify(public_key, signature, signature_payload(sha256_hex))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-key", required=True, help="base64 raw Ed25519 public key")
    parser.add_argument("--signature", required=True, help="ed25519:<base64> manifest signature")
    parser.add_argument(
        "--sha256",
        required=True,
        help="lowercase hex SHA-256 digest; Runtime signs simplicio-release-v1:<digest>",
    )
    args = parser.parse_args(argv)
    try:
        digest = canonical_sha256(args.sha256)
        verified = verify_signature_for_digest(args.public_key, args.signature, digest)
    except (ValueError, base64.binascii.Error) as exc:
        print(f"invalid Ed25519 verification input: {exc}", file=sys.stderr)
        return 2
    if not verified:
        print("Ed25519 signature verification failed", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

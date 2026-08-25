from __future__ import annotations

import base64
import unittest

from scripts import verify_ed25519


PUBLIC_KEY = "2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok="
SIGNATURE = "ed25519:/Tt+wpY4VedOmsOJRPAaAz470OfD4QprLGnTed7QGkkWgyqLoeg2U/dr6PD3EWl4rvHLiok2UWALeDBvG9KmCQ=="
DIGEST = "12681adb6fa49bc2a5d39f8feca42baabe5d97b61cfdf40a5d452d890a8be83a"


class Ed25519ReleaseContractTests(unittest.TestCase):
    def test_runtime_domain_separated_payload_verifies(self):
        self.assertTrue(verify_ed25519.verify_signature_for_digest(PUBLIC_KEY, SIGNATURE, DIGEST))
        self.assertEqual(
            verify_ed25519.signature_payload(DIGEST),
            f"simplicio-release-v1:{DIGEST}".encode("ascii"),
        )

    def test_raw_digest_is_not_the_release_payload(self):
        self.assertFalse(
            verify_ed25519.verify(
                base64.b64decode(PUBLIC_KEY),
                verify_ed25519.parse_signature(SIGNATURE),
                bytes.fromhex(DIGEST),
            )
        )

    def test_invalid_digest_is_rejected(self):
        with self.assertRaises(ValueError):
            verify_ed25519.signature_payload("not-a-sha256")


if __name__ == "__main__":
    unittest.main()

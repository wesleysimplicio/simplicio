from __future__ import annotations

import base64
import unittest

from scripts import verify_ed25519


PUBLIC_KEY = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
SIGNATURE = "ed25519:UKIyIZkSH3nmk+E1LybN3bjQlPpiumLoLIu+bdQUC/j4/6nQkNX3MBhU7kZv+OZ6S9iLYVGwwzPZD5n//MGGAQ=="
DIGEST = "3ba84e1d362618f0e9f45064634a1594485bca3298b8182b5a7eaa3fded4688f"


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

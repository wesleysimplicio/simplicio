from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_KEY = "2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok="
HELPER_SHA256 = "f03a0719dd557ddea27dc4cf1456d6f06a47b9056505e4d4b8453090697600d0"
DIGEST = "12681adb6fa49bc2a5d39f8feca42baabe5d97b61cfdf40a5d452d890a8be83a"
SIGNATURE = (
    "ed25519:/Tt+wpY4VedOmsOJRPAaAz470OfD4QprLGnTed7QGkkWgyqLoeg2U/"
    "dr6PD3EWl4rvHLiok2UWALeDBvG9KmCQ=="
)


def _load_helper():
    path = ROOT / "scripts" / "verify_ed25519.py"
    spec = importlib.util.spec_from_file_location("verify_ed25519_public", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublicManifestSigningKeyTests(unittest.TestCase):
    def test_public_manifest_contains_official_key(self):
        manifest = json.loads((ROOT / "simplicio-update-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["signing_pubkey"], OFFICIAL_KEY)
        self.assertTrue(manifest["security"]["signature_required"])

    def test_helper_hash_and_canonical_signature_contract(self):
        helper = ROOT / "scripts" / "verify_ed25519.py"
        self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(), HELPER_SHA256)
        verifier = _load_helper()
        self.assertTrue(verifier.verify_signature_for_digest(OFFICIAL_KEY, SIGNATURE, DIGEST))
        self.assertEqual(
            verifier.signature_payload(DIGEST),
            ("simplicio-release-v1:" + DIGEST).encode("ascii"),
        )

    def test_missing_empty_whitespace_and_divergent_keys_fail_schema_contract(self):
        schema = json.loads(
            (ROOT / "schemas/update-manifest.schema.json").read_text(encoding="utf-8")
        )["oneOf"][0]
        self.assertIn("signing_pubkey", schema["required"])
        key_schema = schema["properties"]["signing_pubkey"]
        self.assertEqual(key_schema, {"type": "string", "const": OFFICIAL_KEY})
        for value in (None, "", "   ", "A" * 44, 123):
            self.assertFalse(isinstance(value, str) and value == OFFICIAL_KEY)

    def test_invalid_signature_and_checksum_are_rejected(self):
        verifier = _load_helper()
        bad_signature = "ed25519:" + ("A" if SIGNATURE[8] != "A" else "B") + SIGNATURE[9:]
        self.assertFalse(verifier.verify_signature_for_digest(OFFICIAL_KEY, bad_signature, DIGEST))
        self.assertNotEqual(
            hashlib.sha256(b"published").hexdigest(),
            hashlib.sha256(b"tampered").hexdigest(),
        )


    def test_v3_8_24_incident_fixture_keeps_missing_key_fatal(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/v3.8.24-manifest-missing-signing-pubkey.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = fixture["manifest"]
        evidence = fixture["evidence"]
        self.assertNotIn("signing_pubkey", manifest)
        self.assertTrue(manifest["security"]["signature_required"])
        self.assertIn("does not match the pinned installer key", evidence["observed_error"])
        powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
        shell = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn(evidence["expected_powershell_error"], powershell)
        self.assertIn(evidence["expected_shell_error"], shell)

    def test_both_installers_keep_key_errors_distinct_and_fail_closed(self):
        powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
        shell = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("signing_pubkey is missing", powershell)
        self.assertIn("does not match the pinned installer key", powershell)
        self.assertIn("manifest signing_pubkey is missing", shell)
        self.assertIn("manifest signing_pubkey does not match the pinned installer key", shell)
        self.assertIn("-cne $PinnedPublicKey", powershell)
        self.assertIn('SIGNING_PUBKEY" != "$ED25519_PUBLIC_KEY', shell)
        self.assertIn("SIMPLICIO_ALLOW_UNVERIFIED", powershell)
        self.assertIn("SIMPLICIO_ALLOW_UNVERIFIED", shell)
        self.assertIn("SIMPLICIO_CHANNEL", powershell)
        self.assertIn("SIMPLICIO_CHANNEL", shell)
        self.assertLess(powershell.index("if ($ExpectedSha256)"), powershell.rindex("Move-Item -Force"))
        self.assertLess(shell.index('if [ -n "$EXPECTED_SHA256" ]'), shell.rindex('mv -f "$STAGING_PATH" "$DEST_PATH"'))


if __name__ == "__main__":
    unittest.main()

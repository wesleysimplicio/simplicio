from __future__ import annotations

import hashlib
import json
import unittest

from scripts import post_release_smoke as smoke


PUBLIC_KEY = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
SIGNATURE = "ed25519:UKIyIZkSH3nmk+E1LybN3bjQlPpiumLoLIu+bdQUC/j4/6nQkNX3MBhU7kZv+OZ6S9iLYVGwwzPZD5n//MGGAQ=="
PAYLOAD = b"signed release bytes"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def fixture() -> tuple[dict, dict, dict[str, bytes], list[dict]]:
    target = {
        "id": "macos-arm64",
        "asset": "simplicio-macos-arm64",
        "rust_triple": "aarch64-apple-darwin",
        "provenance_target_aliases": ["macos-aarch64"],
    }
    artifact = target["asset"]
    signature_file = f"{artifact}.sig"
    sbom_file = f"{artifact}.spdx.json"
    provenance_file = f"{artifact}.provenance.json"
    manifest = {
        "schema": "simplicio.update-manifest/v1",
        "version": "3.8.17",
        "release_tag": "v3.8.17",
        "repository": "wesleysimplicio/simplicio",
        "security": {
            "signature_algorithm": "ed25519",
            "signature_required": True,
            "refuse_unsigned": True,
            "sbom_required": True,
            "provenance_required": True,
        },
        "signing_pubkey": PUBLIC_KEY,
        "artifacts": [{
            "target": target["id"],
            "artifact": artifact,
            "url": f"https://github.com/wesleysimplicio/simplicio/releases/download/v3.8.17/{artifact}",
            "size": len(PAYLOAD),
            "sha256": DIGEST,
            "signature": SIGNATURE,
            "signature_file": signature_file,
            "sbom": {"file": sbom_file, "format": "SPDX-2.3"},
            "provenance": {"file": provenance_file, "format": "simplicio.provenance/v1"},
        }],
    }
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "files": [{"fileName": artifact, "checksums": [{"algorithm": "SHA256", "checksumValue": DIGEST}]}],
    }
    provenance = {
        "schema": "simplicio.provenance/v1",
        "subject": {"name": artifact, "sha256": DIGEST, "size": len(PAYLOAD)},
        "build": {"version": "3.8.17", "target": "macos-aarch64"},
    }
    payloads = {
        smoke.MANIFEST_ASSET: json.dumps(manifest).encode(),
        smoke.CHECKSUMS_ASSET: f"{DIGEST} *{artifact}\n".encode(),
        artifact: PAYLOAD,
        signature_file: f"{SIGNATURE}\n".encode(),
        sbom_file: json.dumps(sbom).encode(),
        provenance_file: json.dumps(provenance).encode(),
    }
    release = {"tag_name": "v3.8.17", "draft": False, "prerelease": False, "assets": [{"name": name} for name in payloads]}
    return release, manifest, payloads, [target]


class PostReleaseSmokeTests(unittest.TestCase):
    def test_runtime_version_uses_canonical_json_envelope(self):
        self.assertEqual(
            smoke.reported_runtime_version({"runtime": {"version": "3.8.17"}, "version": "wrong"}),
            "3.8.17",
        )

    def test_published_payload_verifies_all_integrity_records(self):
        release, manifest, payloads, targets = fixture()
        report = smoke.verify_release_payload(
            release, manifest, payloads, repository="wesleysimplicio/simplicio", tag="v3.8.17", targets=targets
        )
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["verified_artifacts"], ["simplicio-macos-arm64"])

    def test_tampered_sidecar_is_rejected(self):
        release, manifest, payloads, targets = fixture()
        payloads["simplicio-macos-arm64.sig"] = b"ed25519:tampered\n"
        report = smoke.verify_release_payload(
            release, manifest, payloads, repository="wesleysimplicio/simplicio", tag="v3.8.17", targets=targets
        )
        self.assertTrue(any("signature" in error for error in report["errors"]))

    def test_latest_url_is_rejected_as_non_immutable(self):
        release, manifest, payloads, targets = fixture()
        manifest["artifacts"][0]["url"] = "https://github.com/wesleysimplicio/simplicio/releases/latest/download/simplicio-macos-arm64"
        report = smoke.verify_release_payload(
            release, manifest, payloads, repository="wesleysimplicio/simplicio", tag="v3.8.17", targets=targets
        )
        self.assertTrue(any("immutable" in error for error in report["errors"]))

    def test_missing_provenance_is_rejected(self):
        release, manifest, payloads, targets = fixture()
        payloads.pop("simplicio-macos-arm64.provenance.json")
        release["assets"] = [{"name": name} for name in payloads]
        report = smoke.verify_release_payload(
            release, manifest, payloads, repository="wesleysimplicio/simplicio", tag="v3.8.17", targets=targets
        )
        self.assertTrue(any("provenance" in error for error in report["errors"]))

    def test_unapproved_provenance_target_alias_is_rejected(self):
        release, manifest, payloads, targets = fixture()
        targets[0]["provenance_target_aliases"] = []
        report = smoke.verify_release_payload(
            release, manifest, payloads, repository="wesleysimplicio/simplicio", tag="v3.8.17", targets=targets
        )
        self.assertTrue(any("provenance" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()

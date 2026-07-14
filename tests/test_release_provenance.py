from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import verify_release_provenance as provenance


def manifest(version: str = "3.5.2") -> dict:
    name = "simplicio-macos-arm64"
    return {
        "version": version,
        "artifacts": [
            {
                "artifact": name,
                "url": f"https://github.com/wesleysimplicio/simplicio/releases/download/v{version}/{name}",
                "sha256": "9" * 64,
                "signature": "ed25519:fixture",
            }
        ],
    }


class ReleaseProvenanceTests(unittest.TestCase):
    def test_equal_tag_provenance_and_new_assets_pass(self):
        working = manifest()
        self.assertEqual(provenance.verify(working, manifest(), {"assets": []}), [])

    def test_known_tag_version_and_artifact_drift_fail_closed(self):
        errors = provenance.verify(manifest("3.5.2"), manifest("3.5.1"), {"assets": []})
        self.assertEqual(len(errors), 2)
        self.assertIn("tag manifest version 3.5.1 does not equal working manifest version 3.5.2", errors)
        self.assertTrue(any("artifact name/url/sha256/signature" in error for error in errors))

    def test_any_existing_declared_or_generated_asset_blocks_upload(self):
        working = manifest()
        for name in ("simplicio-macos-arm64", "simplicio-update-manifest.json", "SHA256SUMS"):
            with self.subTest(name=name):
                errors = provenance.verify(working, manifest(), {"assets": [{"name": name}]})
                self.assertEqual(errors, [f"immutable release already contains assets: {name}"])

    def test_invalid_or_duplicate_provenance_is_rejected(self):
        broken = manifest()
        del broken["artifacts"][0]["signature"]
        with self.assertRaisesRegex(ValueError, "missing: signature"):
            provenance.provenance_snapshot(broken)
        duplicate = manifest()
        duplicate["artifacts"].append(dict(duplicate["artifacts"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate artifact name"):
            provenance.provenance_snapshot(duplicate)

    def test_malformed_manifest_and_remote_shapes_are_rejected(self):
        for broken, message in (
            ({"artifacts": []}, "version is missing"),
            ({"version": "3.5.2", "artifacts": []}, "non-empty list"),
            ({"version": "3.5.2", "artifacts": ["not-an-object"]}, "not an object"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                provenance.provenance_snapshot(broken)
        with self.assertRaisesRegex(ValueError, "remote release assets must be a list"):
            provenance.existing_asset_conflicts(manifest(), {"assets": "unknown"})

    def test_cli_reports_tag_mismatch_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "working.json"
            tagged = root / "tagged.json"
            remote = root / "remote.json"
            working.write_text(json.dumps(manifest("3.5.2")), encoding="utf-8")
            tagged.write_text(json.dumps(manifest("3.5.1")), encoding="utf-8")
            remote.write_text(json.dumps({"assets": []}), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = provenance.main(
                    [
                        "--working-manifest",
                        str(working),
                        "--tag-manifest",
                        str(tagged),
                        "--remote-release",
                        str(remote),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertIn("3.5.1", output.getvalue())

    def test_cli_passes_equal_inputs_and_fails_non_object_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "working.json"
            tagged = root / "tagged.json"
            remote = root / "remote.json"
            working.write_text(json.dumps(manifest()), encoding="utf-8")
            tagged.write_text(json.dumps(manifest()), encoding="utf-8")
            remote.write_text(json.dumps({"assets": []}), encoding="utf-8")
            output = io.StringIO()
            args = ["--working-manifest", str(working), "--tag-manifest", str(tagged)]
            with contextlib.redirect_stdout(output):
                self.assertEqual(provenance.main(args), 0)
            self.assertIn("release-provenance: PASS", output.getvalue())
            working.write_text("[]", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(provenance.main(args), 1)
            self.assertIn("expected a JSON object", output.getvalue())


if __name__ == "__main__":
    unittest.main()

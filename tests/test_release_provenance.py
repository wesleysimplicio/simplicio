from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import verify_release_provenance as provenance

REPOSITORY = "wesleysimplicio/simplicio"
STAGING = "https://artifacts.example/simplicio/v3.5.2"


def manifest(version: str = "3.5.2", *, payload: bytes | None = None) -> dict:
    name = "simplicio-macos-arm64"
    sha256 = hashlib.sha256(payload).hexdigest() if payload is not None else "9" * 64
    return {
        "version": version,
        "artifacts": [
            {
                "artifact": name,
                "url": f"https://github.com/{REPOSITORY}/releases/download/v{version}/{name}",
                "sha256": sha256,
                "signature": "ed25519:fixture",
            }
        ],
    }


def remote_release(value: dict, *, digest: str | None = None) -> dict:
    artifact = value["artifacts"][0]
    return {
        "id": 123,
        "tag_name": f"v{value['version']}",
        "assets": [
            {
                "name": artifact["artifact"],
                "digest": digest or f"sha256:{artifact['sha256']}",
            }
        ],
    }


class ReleaseProvenanceTests(unittest.TestCase):
    def test_existing_coherent_tag_is_idempotent_no_publish(self):
        working = manifest()
        plan = provenance.plan_release(
            working,
            tag_exists=True,
            tagged=manifest(),
            remote_release=remote_release(working),
            artifact_base_url=STAGING,
            repository=REPOSITORY,
        )
        self.assertEqual(plan, provenance.ReleasePlan("idempotent"))

    def test_existing_mismatched_tag_blocks_without_mutation(self):
        working = manifest("3.5.2")
        plan = provenance.plan_release(
            working,
            tag_exists=True,
            tagged=manifest("3.5.1"),
            remote_release=remote_release(working),
            artifact_base_url=STAGING,
            repository=REPOSITORY,
        )
        self.assertEqual(plan.mode, "blocked")
        self.assertTrue(any("3.5.1" in error and "3.5.2" in error for error in plan.errors))
        self.assertTrue(any("artifact name/url/sha256/signature" in error for error in plan.errors))

    def test_new_tag_with_distinct_versioned_staging_is_publish_ready(self):
        plan = provenance.plan_release(
            manifest(),
            tag_exists=False,
            tagged=None,
            remote_release={"exists": False, "assets": []},
            artifact_base_url=STAGING,
            repository=REPOSITORY,
        )
        self.assertEqual(plan, provenance.ReleasePlan("publish"))

    def test_missing_or_unsafe_staging_blocks(self):
        for base, message in (
            ("", "absolute HTTPS"),
            ("http://artifacts.example/v3.5.2", "absolute HTTPS"),
            ("https://artifacts.example/latest", "immutable version segment"),
            (
                "https://github.com/wesleysimplicio/simplicio/releases/download/v3.5.2",
                "distinct from the target release",
            ),
            (
                "https://github.com/wesleysimplicio/simplicio/releases/download/v3.5.2/staging",
                "distinct from the target release",
            ),
            ("https://user:secret@artifacts.example/v3.5.2?token=x", "credentials, query, or fragment"),
        ):
            with self.subTest(base=base):
                plan = provenance.plan_release(
                    manifest(),
                    tag_exists=False,
                    tagged=None,
                    remote_release={"exists": False, "assets": []},
                    artifact_base_url=base,
                    repository=REPOSITORY,
                )
                self.assertEqual(plan.mode, "blocked")
                self.assertTrue(any(message in error for error in plan.errors))

    def test_existing_release_requires_exact_remote_digest(self):
        working = manifest()
        for remote, message in (
            ({"exists": False, "assets": []}, "no corresponding release"),
            ({"id": 123, "assets": []}, "exactly one"),
            (remote_release(working, digest="sha256:" + "8" * 64), "digest mismatch"),
        ):
            with self.subTest(message=message):
                plan = provenance.plan_release(
                    working,
                    tag_exists=True,
                    tagged=manifest(),
                    remote_release=remote,
                    artifact_base_url=STAGING,
                    repository=REPOSITORY,
                )
                self.assertEqual(plan.mode, "blocked")
                self.assertTrue(any(message in error for error in plan.errors))

    def test_new_tag_rejects_existing_release_or_supplied_tag_manifest(self):
        working = manifest()
        plan = provenance.plan_release(
            working,
            tag_exists=False,
            tagged=manifest(),
            remote_release=remote_release(working),
            artifact_base_url=STAGING,
            repository=REPOSITORY,
        )
        self.assertEqual(plan.mode, "blocked")
        self.assertEqual(len(plan.errors), 2)

    def test_staged_artifact_must_exist_and_match_digest(self):
        payload = b"signed release bytes"
        working = manifest(payload=payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(provenance.verify_staged_files(working, root), ["staged artifact is missing: simplicio-macos-arm64"])
            artifact = root / "simplicio-macos-arm64"
            artifact.write_bytes(b"wrong")
            self.assertEqual(provenance.verify_staged_files(working, root), ["staged artifact digest mismatch for simplicio-macos-arm64"])
            artifact.write_bytes(payload)
            self.assertEqual(provenance.verify_staged_files(working, root), [])

    def test_invalid_manifest_shapes_and_signature_are_rejected(self):
        for broken, message in (
            ({"artifacts": []}, "version is missing"),
            ({"version": "3.5.2", "artifacts": []}, "non-empty list"),
            ({"version": "3.5.2", "artifacts": ["bad"]}, "not an object"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                provenance.provenance_snapshot(broken)
        broken = manifest()
        broken["artifacts"][0]["signature"] = "unsigned"
        with self.assertRaisesRegex(ValueError, "Ed25519"):
            provenance.provenance_snapshot(broken)
        broken = manifest()
        broken["artifacts"][0]["sha256"] = "z" * 64
        with self.assertRaisesRegex(ValueError, "invalid SHA256"):
            provenance.provenance_snapshot(broken)
        broken = manifest()
        del broken["artifacts"][0]["url"]
        with self.assertRaisesRegex(ValueError, "missing: url"):
            provenance.provenance_snapshot(broken)
        duplicate = manifest()
        duplicate["artifacts"].append(dict(duplicate["artifacts"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate artifact"):
            provenance.provenance_snapshot(duplicate)
        unsafe = manifest()
        unsafe["artifacts"][0]["artifact"] = "../escape"
        with self.assertRaisesRegex(ValueError, "safe filename"):
            provenance.provenance_snapshot(unsafe)

    def test_plan_rejects_target_url_and_malformed_existing_state(self):
        wrong_target = manifest()
        wrong_target["artifacts"][0]["url"] = "https://example.test/wrong"
        plan = provenance.plan_release(
            wrong_target,
            tag_exists=False,
            tagged=None,
            remote_release={"exists": False, "assets": []},
            artifact_base_url=STAGING,
            repository=REPOSITORY,
        )
        self.assertTrue(any("target release URL mismatch" in error for error in plan.errors))
        no_manifest = provenance.plan_release(
            manifest(),
            tag_exists=True,
            tagged=None,
            remote_release={"id": 1, "assets": "invalid"},
            artifact_base_url=STAGING,
            repository=REPOSITORY,
        )
        self.assertTrue(any("missing its manifest" in error for error in no_manifest.errors))
        self.assertTrue(any("assets must be a list" in error for error in no_manifest.errors))

    def test_plan_cli_writes_idempotent_mode_and_staged_cli_passes(self):
        payload = b"release"
        working_value = manifest(payload=payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "working.json"
            tagged = root / "tagged.json"
            remote = root / "remote.json"
            output = root / "github-output.txt"
            working.write_text(json.dumps(working_value), encoding="utf-8")
            tagged.write_text(json.dumps(working_value), encoding="utf-8")
            remote.write_text(json.dumps(remote_release(working_value)), encoding="utf-8")
            args = [
                "plan",
                "--working-manifest", str(working),
                "--tag-exists",
                "--tag-manifest", str(tagged),
                "--remote-release", str(remote),
                "--artifact-base-url", STAGING,
                "--repository", REPOSITORY,
                "--github-output", str(output),
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(provenance.main(args), 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "mode=idempotent\n")
            artifact = root / "simplicio-macos-arm64"
            artifact.write_bytes(payload)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    provenance.main(["verify-staged", "--working-manifest", str(working), "--staging-dir", str(root)]),
                    0,
                )

    def test_cli_failures_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "working.json"
            tagged = root / "tagged.json"
            remote = root / "remote.json"
            working.write_text("[]", encoding="utf-8")
            tagged.write_text(json.dumps(manifest()), encoding="utf-8")
            remote.write_text(json.dumps({"exists": False, "assets": []}), encoding="utf-8")
            plan_args = [
                "plan", "--working-manifest", str(working), "--tag-manifest", str(tagged),
                "--remote-release", str(remote), "--artifact-base-url", STAGING,
                "--repository", REPOSITORY,
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(provenance.main(plan_args), 1)
            working.write_text(json.dumps(manifest(payload=b"expected")), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    provenance.main(["verify-staged", "--working-manifest", str(working), "--staging-dir", str(root)]),
                    1,
                )


if __name__ == "__main__":
    unittest.main()

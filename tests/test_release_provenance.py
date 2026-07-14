from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from scripts import verify_release_provenance as provenance

REPOSITORY = "wesleysimplicio/simplicio"
STAGING = "https://artifacts.example/simplicio/v3.5.2"


class FakeResponse:
    def __init__(self, value: bytes):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.value


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
    def test_state_collection_writes_existing_and_absent_tag_receipts(self):
        working_value = manifest()
        remote_value = remote_release(working_value)

        class Result:
            def __init__(self, stdout: str):
                self.stdout = stdout

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "working.json"
            working.write_text(json.dumps(working_value), encoding="utf-8")
            output = root / "output.txt"

            def existing_runner(command, **_kwargs):
                return Result("v3.5.2\n" if command[1] == "tag" else json.dumps(working_value))

            exists = provenance.collect_release_state(
                working,
                REPOSITORY,
                "token",
                root / "existing",
                output,
                runner=existing_runner,
                opener=lambda _request: FakeResponse(json.dumps(remote_value).encode()),
            )
            self.assertTrue(exists)
            self.assertEqual(json.loads((root / "existing/tag-manifest.json").read_text()), working_value)
            self.assertIn("tag_exists=true", output.read_text(encoding="utf-8"))

            def absent_runner(_command, **_kwargs):
                return Result("")

            def missing_release(request):
                raise HTTPError(request.full_url, 404, "missing", {}, None)

            exists = provenance.collect_release_state(
                working,
                REPOSITORY,
                "token",
                root / "absent",
                None,
                runner=absent_runner,
                opener=missing_release,
            )
            self.assertFalse(exists)
            self.assertEqual(json.loads((root / "absent/remote-release.json").read_text()), {"exists": False, "assets": []})

    def test_state_collection_requires_repository_and_token(self):
        with self.assertRaisesRegex(ValueError, "required"):
            provenance.collect_release_state(Path("missing"), "", "", Path("state"), None)

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
            self.assertEqual(provenance.verify_staged_files(working, root), ["staging set is missing: simplicio-macos-arm64"])
            artifact = root / "simplicio-macos-arm64"
            artifact.write_bytes(b"wrong")
            self.assertEqual(provenance.verify_staged_files(working, root), ["staged artifact digest mismatch for simplicio-macos-arm64"])
            artifact.write_bytes(payload)
            self.assertEqual(provenance.verify_staged_files(working, root), [])

    def test_download_and_metadata_use_verified_staging(self):
        payload = b"immutable staged bytes"
        working_value = manifest(payload=payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            working = root / "manifest.json"
            working.write_text(json.dumps(working_value), encoding="utf-8")
            dist = root / "dist"
            provenance.download_staged_files(
                working_value,
                STAGING,
                REPOSITORY,
                dist,
                opener=lambda _request: FakeResponse(payload),
            )
            self.assertEqual((dist / "simplicio-macos-arm64").read_bytes(), payload)
            provenance.generate_release_metadata(working, dist)
            self.assertTrue((dist / "simplicio-update-manifest.json").is_file())
            self.assertEqual(
                {path.name for path in dist.iterdir()},
                {"simplicio-macos-arm64", "simplicio-update-manifest.json", "SHA256SUMS"},
            )
            self.assertEqual(provenance.verify_publish_files(working_value, dist), [])
            sums = (dist / "SHA256SUMS").read_text(encoding="ascii")
            self.assertIn("simplicio-macos-arm64", sums)
            self.assertIn("simplicio-update-manifest.json", sums)

    def test_unmanifested_stale_directory_and_symlink_entries_are_rejected(self):
        payload = b"release"
        working = manifest(payload=payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            dist.mkdir()
            (dist / "simplicio-macos-arm64").write_bytes(payload)
            (dist / "unmanifested.exe").write_bytes(b"attack")
            self.assertTrue(any("unmanifested.exe" in error for error in provenance.verify_staged_files(working, dist)))
            with self.assertRaisesRegex(ValueError, "not empty"):
                provenance.download_staged_files(
                    working,
                    STAGING,
                    REPOSITORY,
                    dist,
                    opener=lambda _request: FakeResponse(payload),
                )

            (dist / "unmanifested.exe").unlink()
            artifact = dist / "simplicio-macos-arm64"
            original_is_symlink = Path.is_symlink

            def simulated_symlink(path):
                return path == artifact or original_is_symlink(path)

            with mock.patch.object(Path, "is_symlink", simulated_symlink):
                self.assertEqual(
                    provenance.verify_staged_files(working, dist),
                    ["staging entry is not a regular file: simplicio-macos-arm64"],
                )

            artifact.unlink()
            artifact.mkdir()
            self.assertEqual(
                provenance.verify_staged_files(working, dist),
                ["staging entry is not a regular file: simplicio-macos-arm64"],
            )

    def test_final_publish_set_rejects_any_extra_file(self):
        payload = b"release"
        working_value = manifest(payload=payload)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(working_value), encoding="utf-8")
            dist = root / "dist"
            dist.mkdir()
            (dist / "simplicio-macos-arm64").write_bytes(payload)
            provenance.generate_release_metadata(manifest_path, dist)
            (dist / "stale.bin").write_bytes(b"stale")
            self.assertEqual(
                provenance.verify_publish_files(working_value, dist),
                ["publish set has unmanifested entries: stale.bin"],
            )

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
            dist = root / "dist"
            dist.mkdir()
            artifact = dist / "simplicio-macos-arm64"
            artifact.write_bytes(payload)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    provenance.main(["verify-staged", "--working-manifest", str(working), "--staging-dir", str(dist)]),
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

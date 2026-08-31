from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts import verify_distribution_consistency as audit

ARTIFACTS = {
    "macos-arm64": "simplicio-macos-arm64",
    "macos-x64": "simplicio-macos-x64",
    "linux-x64": "simplicio-linux-x64",
    "windows-x64": "simplicio-windows-x64.exe",
}


class DistributionFixture:
    def __init__(self, root: Path):
        self.root = root
        self.version = "3.5.2"
        self.write()

    def put(self, relative: str, value: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def write(self) -> None:
        self.put("VERSION.md", f"## Current Version: v{self.version}\nUse `master` branch only\n")
        for relative in (
            "README.md",
            "INSTALL.md",
            "install.sh",
            "install.ps1",
            "pypi/simplicio/simplicio/__main__.py",
            "READMEs/README.pt-BR.md",
        ):
            self.put(relative, "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh\n")
        self.put(audit.LOCAL_PUBLISHER, (audit.ROOT / audit.LOCAL_PUBLISHER).read_text(encoding="utf-8"))
        self.put("version.txt", self.version + "\n")
        artifact_url = (
            "https://github.com/wesleysimplicio/simplicio/releases/download/"
            f"v{self.version}/simplicio-macos-arm64"
        )
        artifact_sha = "9" * 64
        self.put(
            "simplicio-update-manifest.json",
            json.dumps(
                {
                    "version": self.version,
                    "security": {"signature_required": True},
                    "entitlement": {"beta_until": None},
                    "artifacts": [
                        {
                            "target": target,
                            "artifact": asset,
                            "url": f"https://github.com/wesleysimplicio/simplicio/releases/download/v{self.version}/{asset}",
                            "sha256": artifact_sha,
                            "signature": "ed25519:fixture",
                            "signed": True,
                        }
                        for target, asset in ARTIFACTS.items()
                    ],
                }
            ),
        )
        for relative in (
            "npm/simplicio/package.json",
            "npm/simplicio-installer/package.json",
            "npm/simplicio-unscoped/package.json",
        ):
            self.put(relative, json.dumps({"version": self.version}))
        self.put("pypi/simplicio/pyproject.toml", f'version = "{self.version}"\n')
        self.put("SIMPLICIO_ECOSYSTEM.md", f"## Versão atual\n{self.version} (manifest)\n")
        self.put(
            "distribution/targets.json",
            json.dumps(
                {
                    "targets": [
                        {
                            "id": target,
                            "asset": asset,
                            "installer": None,
                            "manifest_target": target,
                        }
                        for target, asset in ARTIFACTS.items()
                    ]
                }
            ),
        )


class DistributionConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = DistributionFixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def levels(self):
        return [item.level for item in audit.run_audit(self.root, today=date(2026, 7, 14))]

    def test_clean_distribution_has_no_blocking_findings(self):
        self.assertEqual(self.levels(), ["OK"] * 8)

    def test_regression_wrong_branch_and_version_fail(self):
        self.fixture.put("README.md", "https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh\n")
        self.fixture.put("version.txt", "3.0.2\n")
        findings = audit.run_audit(self.root, today=date(2026, 7, 14))
        self.assertEqual(sum(item.level == "ERROR" for item in findings), 2)
        self.assertTrue(any("/main/" in item.message for item in findings))
        self.assertTrue(any("version mismatch" in item.message for item in findings))

    def test_regression_wrapper_and_ecosystem_drift_warn(self):
        self.fixture.put("npm/simplicio/package.json", json.dumps({"version": "3.0.2"}))
        self.fixture.put("SIMPLICIO_ECOSYSTEM.md", "## Versão atual\n1.2.0\n")
        warnings = [item.message for item in audit.run_audit(self.root) if item.level == "WARN"]
        self.assertEqual(len(warnings), 2)
        self.assertTrue(any("wrapper versions" in message for message in warnings))
        self.assertTrue(any("ECOSYSTEM" in message for message in warnings))

    def test_regression_version_document_drift_warns(self):
        self.fixture.put("VERSION.md", "## Current Version: v3.0.2\nUse `master` branch only\n")
        warnings = [item.message for item in audit.run_audit(self.root) if item.level == "WARN"]
        self.assertEqual(warnings, ["VERSION.md advertises 3.0.2 while manifest is 3.5.2."])

    def test_regression_expired_beta_and_contradictory_readme_warn(self):
        manifest = {"version": "3.5.2", "entitlement": {"beta_until": "2026-06-30"}}
        self.fixture.put("simplicio-update-manifest.json", json.dumps(manifest))
        self.fixture.put("README.md", "Public beta with no end date\n")
        warnings = [item.message for item in audit.run_audit(self.root, today=date(2026, 7, 14)) if item.level == "WARN"]
        self.assertEqual(len(warnings), 2)

    def test_invalid_beta_date_is_visible(self):
        manifest = {"version": "3.5.2", "entitlement": {"beta_until": "not-a-date"}}
        self.fixture.put("simplicio-update-manifest.json", json.dumps(manifest))
        warnings = [item.message for item in audit.run_audit(self.root) if item.level == "WARN"]
        self.assertEqual(warnings, ["could not parse beta_until date: not-a-date"])

    def test_parser_helpers_reject_missing_versions(self):
        broken = self.root / "broken.txt"
        broken.write_text("missing", encoding="utf-8")
        with self.assertRaises(ValueError):
            audit.version_from_pyproject(broken)

    def publisher_source(self):
        return (self.root / audit.LOCAL_PUBLISHER).read_text(encoding="utf-8")

    def test_release_requires_real_local_publisher(self):
        (self.root / audit.LOCAL_PUBLISHER).unlink()
        errors = audit.manual_release_errors(self.root)
        self.assertTrue(any("regular local file" in error for error in errors))

    def test_any_remote_workflow_is_rejected_even_manual_dispatch(self):
        for filename in ("release.yml", "repository-quality.yml", "other.yaml"):
            with self.subTest(filename=filename):
                self.fixture.put(".github/workflows/" + filename, '"on": workflow_dispatch\n')
                errors = audit.manual_release_errors(self.root)
                self.assertTrue(any("not workflow files" in error for error in errors))

    def test_publisher_comments_cannot_replace_executable_gates(self):
        source = self.publisher_source()
        for replacement in (
            "    # bundle_receipt = verify_bundle(bundle, tag, version, source_commit)",
            "    bundle_receipt = {}",
            "    if False:\n        bundle_receipt = verify_bundle(bundle, tag, version, source_commit)",
        ):
            with self.subTest(replacement=replacement):
                self.fixture.put(
                    audit.LOCAL_PUBLISHER,
                    source.replace("    bundle_receipt = verify_bundle(bundle, tag, version, source_commit)", replacement),
                )
                self.assertTrue(any("ordered local" in error for error in audit.manual_release_errors(self.root)))

    def test_publication_step_order_is_semantic(self):
        source = self.publisher_source()
        source = source.replace(
            "    bundle_receipt = verify_bundle(bundle, tag, version, source_commit)\n    changed = stage_bundle(bundle)",
            "    changed = stage_bundle(bundle)\n    bundle_receipt = verify_bundle(bundle, tag, version, source_commit)",
        )
        self.fixture.put(audit.LOCAL_PUBLISHER, source)
        self.assertTrue(any("publish must match" in error for error in audit.manual_release_errors(self.root)))

    def test_malicious_extra_command_and_overwrite_are_rejected(self):
        source = self.publisher_source()
        for command in (
            'run(["gh", "release", "upload", tag, "--clobber", "unverified.exe"])',
            'run(["git", "tag", "-f", tag])',
            'run(["git", "push", "--force", "origin", tag])',
            'run(["gh", "workflow", "run", "release.yml"])',
        ):
            with self.subTest(command=command):
                self.fixture.put(audit.LOCAL_PUBLISHER, source + "\ndef extra_effect():\n    " + command + "\n")
                self.assertTrue(audit.manual_release_errors(self.root))

    def test_bundle_upload_is_explicit_and_cannot_use_a_glob(self):
        source = self.publisher_source()
        for old, new in (
            ("*[str(bundle / name) for name in required_release_assets()]", '"dist/*"'),
            ('"--verify-tag",', '"--clobber",'),
            ('"--repo", PUBLIC_REPOSITORY,', '"--repo", "someone/else",'),
        ):
            with self.subTest(replacement=new):
                self.fixture.put(audit.LOCAL_PUBLISHER, source.replace(old, new))
                self.assertTrue(audit.manual_release_errors(self.root))

    def test_local_asset_contract_requires_signatures_sbom_and_provenance(self):
        source = self.publisher_source()
        for suffix in (".sig", ".spdx.json", ".provenance.json"):
            with self.subTest(suffix=suffix):
                self.fixture.put(audit.LOCAL_PUBLISHER, source.replace('asset + "' + suffix + '"', '"unchecked"'))
                self.assertTrue(any("required_release_assets" in error for error in audit.manual_release_errors(self.root)))

    def test_resume_cannot_create_another_release_or_skip_verification(self):
        source = self.publisher_source()
        self.fixture.put(
            audit.LOCAL_PUBLISHER,
            source.replace("    verify_public_codex_hooks(bundle)", "    create_public_release(tag, bundle)"),
        )
        self.assertTrue(any("resume_publish must match" in error for error in audit.manual_release_errors(self.root)))

    def test_duplicate_missing_and_invalid_python_publishers_fail_closed(self):
        source = self.publisher_source()
        for value in (
            "def invalid(",
            "# publish verify_bundle create_public_release",
            source + "\ndef publish():\n    pass\n",
            source.replace("def publish(", "def unrelated("),
            source.replace('META_ASSETS = ("SHA256SUMS", "simplicio-update-manifest.json")', 'META_ASSETS = ("SHA256SUMS",)'),
        ):
            with self.subTest(value=value[:40]):
                self.fixture.put(audit.LOCAL_PUBLISHER, value)
                self.assertTrue(audit.manual_release_errors(self.root))

    def test_publisher_asset_names_must_agree_with_canonical_targets(self):
        source = self.publisher_source().replace('"simplicio-macos-arm64",', '"simplicio-darwin-arm64",', 1)
        self.fixture.put(audit.LOCAL_PUBLISHER, source)
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertTrue(any("ASSETS differs" in message for message in errors))

    def test_manifest_requires_every_target_exactly_once(self):
        path = self.root / "simplicio-update-manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for artifacts in (original["artifacts"][:-1], original["artifacts"] + original["artifacts"][:1]):
            with self.subTest(count=len(artifacts)):
                value = {**original, "artifacts": artifacts}
                path.write_text(json.dumps(value), encoding="utf-8")
                errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
                self.assertTrue(any("each canonical target exactly once" in message for message in errors))

    def test_regression_manifest_url_must_be_version_bound(self):
        manifest_path = self.root / "simplicio-update-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"][0]["url"] = manifest["artifacts"][0]["url"].replace("v3.5.2", "latest")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertTrue(any("not version-bound" in message for message in errors))

    def test_signature_requirement_cannot_be_disabled_or_string_coerced(self):
        path = self.root / "simplicio-update-manifest.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for value in (False, None, "true", "false"):
            with self.subTest(value=value):
                manifest = {**original, "security": {"signature_required": value}}
                path.write_text(json.dumps(manifest), encoding="utf-8")
                errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
                self.assertTrue(any("must require Ed25519" in message for message in errors))

    def test_signature_requirement_cannot_hide_unsigned_artifacts(self):
        path = self.root / "simplicio-update-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["security"]["signature_required"] = False
        del manifest["artifacts"][0]["signature"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertTrue(any("lacks required Ed25519 signature" in message for message in errors))

    def test_junit_and_json_cli_are_machine_readable(self):
        junit = self.root / "artifacts/junit.xml"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = audit.main(["--root", str(self.root), "--strict", "--junit", str(junit), "--json"])
        self.assertEqual(result, 0)
        self.assertTrue(junit.exists())
        self.assertEqual(len(json.loads(output.getvalue())), 8)

    def test_strict_mode_fails_warning_while_default_does_not(self):
        self.fixture.put("npm/simplicio/package.json", json.dumps({"version": "3.0.2"}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--root", str(self.root)]), 0)
            self.assertEqual(audit.main(["--root", str(self.root), "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()

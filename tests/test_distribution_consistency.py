from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts import verify_distribution_consistency as audit


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
        self.put(
            ".github/workflows/release.yml",
            "git show-ref --verify --quiet refs/tags/v3.5.2\n"
            "foreach ($artifact in $manifest.artifacts) {\n"
            "  Invoke-WebRequest -Uri $artifact.url -OutFile $destination\n"
            "  $actualHash = (Get-FileHash $destination -Algorithm SHA256).Hash.ToLower()\n"
            "  if ($actualHash -ne $artifact.sha256.ToLower()) { throw 'mismatch' }\n"
            "}\n"
            "fail_on_unmatched_files: true\n"
            "files: dist/*\n",
        )
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
                            "target": "macos-arm64",
                            "artifact": "simplicio-macos-arm64",
                            "url": artifact_url,
                            "sha256": artifact_sha,
                            "signature": "ed25519:fixture",
                        }
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
        self.put(
            "Formula/simplicio.rb",
            f'version "{self.version}"\nurl "{artifact_url}"\nsha256 "{artifact_sha}"\n'
            'bin.install "simplicio-macos-arm64" => "simplicio"\n',
        )
        self.put("pypi/simplicio/pyproject.toml", f'version = "{self.version}"\n')
        self.put("SIMPLICIO_ECOSYSTEM.md", f"## Versão atual\n{self.version} (manifest)\n")


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
            audit.version_from_formula(broken)
        with self.assertRaises(ValueError):
            audit.version_from_pyproject(broken)
        with self.assertRaises(ValueError):
            audit.formula_provenance(broken)

    def test_regression_formula_must_match_signed_manifest_artifact(self):
        formula = self.root / "Formula/simplicio.rb"
        formula.write_text(formula.read_text(encoding="utf-8").replace("9" * 64, "8" * 64), encoding="utf-8")
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertIn("Formula URL/SHA256/install does not match the signed macos-arm64 manifest artifact.", errors)

    def test_regression_formula_must_install_versioned_asset(self):
        formula = self.root / "Formula/simplicio.rb"
        formula.write_text(
            formula.read_text(encoding="utf-8").replace(
                'bin.install "simplicio-macos-arm64" => "simplicio"',
                'bin.install "simplicio-wrapper" => "simplicio"',
            ),
            encoding="utf-8",
        )
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertIn("Formula URL/SHA256/install does not match the signed macos-arm64 manifest artifact.", errors)

    def test_regression_release_must_not_stage_repo_wrapper_binary(self):
        workflow = self.root / ".github/workflows/release.yml"
        workflow.write_text(workflow.read_text(encoding="utf-8") + "Copy-Item simplicio dist/simplicio-macos-arm64\n", encoding="utf-8")
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertTrue(any("release workflow provenance" in message and "unsafe" in message for message in errors))

    def test_regression_manifest_url_must_be_version_bound(self):
        manifest_path = self.root / "simplicio-update-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"][0]["url"] = manifest["artifacts"][0]["url"].replace("v3.5.2", "latest")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertTrue(any("not version-bound" in message for message in errors))

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

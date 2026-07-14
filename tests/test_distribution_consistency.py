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
            ".github/workflows/release.yml",
            "pypi/simplicio/simplicio/__main__.py",
            "READMEs/README.pt-BR.md",
        ):
            self.put(relative, "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh\n")
        self.put("version.txt", self.version + "\n")
        self.put(
            "simplicio-update-manifest.json",
            json.dumps({"version": self.version, "entitlement": {"beta_until": None}}),
        )
        for relative in (
            "npm/simplicio/package.json",
            "npm/simplicio-installer/package.json",
            "npm/simplicio-unscoped/package.json",
        ):
            self.put(relative, json.dumps({"version": self.version}))
        self.put("Formula/simplicio.rb", f'version "{self.version}"\n')
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
        self.assertEqual(self.levels(), ["OK", "OK", "OK", "OK", "OK"])

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

    def test_junit_and_json_cli_are_machine_readable(self):
        junit = self.root / "artifacts/junit.xml"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = audit.main(["--root", str(self.root), "--strict", "--junit", str(junit), "--json"])
        self.assertEqual(result, 0)
        self.assertTrue(junit.exists())
        self.assertEqual(len(json.loads(output.getvalue())), 5)

    def test_strict_mode_fails_warning_while_default_does_not(self):
        self.fixture.put("npm/simplicio/package.json", json.dumps({"version": "3.0.2"}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["--root", str(self.root)]), 0)
            self.assertEqual(audit.main(["--root", str(self.root), "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()

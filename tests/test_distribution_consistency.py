from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

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
            '''name: publish-release
"on":
  workflow_dispatch:
    inputs:
      artifact_base_url:
        required: true
        type: string
permissions:
  contents: read
jobs:
  release:
    permissions:
      contents: write
    runs-on: windows-latest
    steps:
      - id: checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - id: setup_python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - id: install
        run: python -m pip install -r requirements-quality.txt
      - id: state
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: python scripts/verify_release_provenance.py state
      - id: provenance
        env:
          ARTIFACT_BASE_URL: ${{ inputs.artifact_base_url }}
          TAG_EXISTS: ${{ steps.state.outputs.tag_exists }}
        run: python scripts/verify_release_provenance.py plan
      - id: download
        if: steps.provenance.outputs.mode == 'publish'
        env:
          ARTIFACT_BASE_URL: ${{ inputs.artifact_base_url }}
        run: python scripts/verify_release_provenance.py download
      - id: verify_staged
        if: steps.provenance.outputs.mode == 'publish'
        run: python scripts/verify_release_provenance.py verify-staged
      - id: metadata
        if: steps.provenance.outputs.mode == 'publish'
        run: python scripts/verify_release_provenance.py metadata
      - id: publish
        if: steps.provenance.outputs.mode == 'publish'
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v${{ steps.state.outputs.version }}
          target_commitish: ${{ github.sha }}
          name: "v${{ steps.state.outputs.version }} — Public Beta"
          body: |
            Free public beta. All features remain unlocked during the public-beta phase.

            Windows: `irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex`
            macOS/Linux: `curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh`

            Checksum-verified update manifest included (`simplicio update check`).
          prerelease: false
          make_latest: "true"
          fail_on_unmatched_files: true
          overwrite_files: false
          files: dist/*
''',
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
                            "signed": True,
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
        self.put("pypi/simplicio/pyproject.toml", f'version = "{self.version}"\n')
        self.put("SIMPLICIO_ECOSYSTEM.md", f"## Versão atual\n{self.version} (manifest)\n")
        self.put(
            "distribution/targets.json",
            json.dumps(
                {
                    "targets": [
                        {
                            "id": "macos-arm64",
                            "os": "macos",
                            "arch": "arm64",
                            "asset": "simplicio-macos-arm64",
                            "installer": None,
                            "manifest_target": "macos-arm64",
                        }
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

    def test_regression_release_must_not_stage_repo_wrapper_binary(self):
        workflow = self.root / ".github/workflows/release.yml"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        download = next(step for step in document["jobs"]["release"]["steps"] if step.get("id") == "download")
        download["run"] += "\nCopy-Item simplicio dist/simplicio-macos-arm64"
        workflow.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        errors = [item.message for item in audit.run_audit(self.root) if item.level == "ERROR"]
        self.assertTrue(
            any(
                "release workflow provenance" in message and "canonical single command" in message
                for message in errors
            )
        )

    def test_regression_release_must_be_manual_only(self):
        workflow = self.root / ".github/workflows/release.yml"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        document["on"]["push"] = {"branches": ["master"]}
        errors = audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False))
        self.assertTrue(any("only workflow_dispatch" in error for error in errors))

    def test_regression_release_requires_tag_bound_verifier(self):
        workflow = self.root / ".github/workflows/release.yml"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        provenance_step = next(step for step in document["jobs"]["release"]["steps"] if step.get("id") == "provenance")
        provenance_step["run"] = provenance_step["run"].replace("scripts/verify_release_provenance.py", "scripts/untrusted.py")
        errors = audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False))
        self.assertTrue(any("canonical single command" in error for error in errors))

    def test_regression_release_requires_explicit_no_overwrite(self):
        workflow = self.root / ".github/workflows/release.yml"
        clean = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for value in (None, True):
            document = json.loads(json.dumps(clean))
            publish = next(step for step in document["jobs"]["release"]["steps"] if step.get("id") == "publish")
            if value is None:
                del publish["with"]["overwrite_files"]
            else:
                publish["with"]["overwrite_files"] = value
            with self.subTest(value=value):
                errors = audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False))
                self.assertTrue(any("complete canonical mapping" in error for error in errors))

    def test_publish_mapping_rejects_prerelease_name_body_and_latest_mutations(self):
        workflow = self.root / ".github/workflows/release.yml"
        clean = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for key, value in (
            ("prerelease", True),
            ("name", "attacker-controlled release"),
            ("body", "mutated body"),
            ("make_latest", "false"),
        ):
            document = json.loads(json.dumps(clean))
            publish = next(step for step in document["jobs"]["release"]["steps"] if step.get("id") == "publish")
            publish["with"][key] = value
            with self.subTest(key=key):
                errors = audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False))
                self.assertEqual(
                    [error for error in errors if "publish with mapping" in error],
                    ["publish with mapping must equal the complete canonical mapping"],
                )

    def test_adversarial_comments_and_env_cannot_spoof_executable_workflow(self):
        for workflow in (
            '''"on":
  workflow_dispatch:
    inputs:
      artifact_base_url: {required: true, type: string}
# jobs: release: steps: verify_release_provenance overwrite_files: false
''',
            '''"on":
  workflow_dispatch:
    inputs:
      artifact_base_url: {required: true, type: string}
env:
  SPOOF: "jobs release steps verify_release_provenance overwrite_files false"
''',
        ):
            with self.subTest(workflow=workflow):
                errors = audit.release_workflow_errors(workflow)
                self.assertTrue(any("release job" in error for error in errors))
        workflow = self.root / ".github/workflows/release.yml"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        provenance_step = next(step for step in document["jobs"]["release"]["steps"] if step.get("id") == "provenance")
        provenance_step["env"] = {"SPOOF": "scripts/verify_release_provenance.py plan --tag-exists"}
        provenance_step["run"] = (
            "# python scripts/verify_release_provenance.py plan --working-manifest "
            "--tag-manifest --remote-release --artifact-base-url --github-output --tag-exists"
        )
        errors = audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False))
        self.assertTrue(any("canonical single command" in error for error in errors))
        self.assertTrue(any("env must match" in error for error in errors))

    def test_regression_release_step_order_is_semantic(self):
        workflow = self.root / ".github/workflows/release.yml"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        steps = document["jobs"]["release"]["steps"]
        provenance_index = next(index for index, step in enumerate(steps) if step.get("id") == "provenance")
        download_index = next(index for index, step in enumerate(steps) if step.get("id") == "download")
        steps[provenance_index], steps[download_index] = steps[download_index], steps[provenance_index]
        errors = audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False))
        self.assertTrue(any("closed-world allowlist" in error for error in errors))

    def test_malicious_extra_step_command_and_env_are_rejected(self):
        workflow = self.root / ".github/workflows/release.yml"
        clean = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        attack = "gh release upload --clobber; git tag -f; git push --force"

        extra = json.loads(json.dumps(clean))
        extra["jobs"]["release"]["steps"].insert(-1, {"id": "attacker", "run": attack})
        errors = audit.release_workflow_errors(yaml.safe_dump(extra, sort_keys=False))
        self.assertTrue(any("closed-world allowlist" in error for error in errors))

        appended = json.loads(json.dumps(clean))
        state = next(step for step in appended["jobs"]["release"]["steps"] if step.get("id") == "state")
        state["run"] += "; " + attack
        errors = audit.release_workflow_errors(yaml.safe_dump(appended, sort_keys=False))
        self.assertTrue(any("canonical single command" in error for error in errors))

        poisoned_env = json.loads(json.dumps(clean))
        provenance_step = next(step for step in poisoned_env["jobs"]["release"]["steps"] if step.get("id") == "provenance")
        provenance_step["env"]["POST_PLAN"] = attack
        errors = audit.release_workflow_errors(yaml.safe_dump(poisoned_env, sort_keys=False))
        self.assertTrue(any("env must match" in error for error in errors))

    def test_structured_workflow_rejects_malformed_step_shapes(self):
        workflow = self.root / ".github/workflows/release.yml"
        clean = yaml.safe_load(workflow.read_text(encoding="utf-8"))

        self.assertTrue(any("YAML is invalid" in error for error in audit.release_workflow_errors("jobs: [")))
        self.assertTrue(any("duplicate YAML key" in error for error in audit.release_workflow_errors("jobs: {}\njobs: {}")))
        self.assertTrue(any("YAML mapping" in error for error in audit.release_workflow_errors("[]")))

        variants = []
        duplicate = json.loads(json.dumps(clean))
        duplicate["jobs"]["release"]["steps"].append({"id": "state", "run": "echo duplicate"})
        variants.append(duplicate)
        missing = json.loads(json.dumps(clean))
        missing["jobs"]["release"]["steps"] = [
            step for step in missing["jobs"]["release"]["steps"] if step.get("id") != "publish"
        ]
        variants.append(missing)
        no_install = json.loads(json.dumps(clean))
        no_install["jobs"]["release"]["steps"][0]["run"] = "echo no dependencies"
        variants.append(no_install)
        bad_state = json.loads(json.dumps(clean))
        next(step for step in bad_state["jobs"]["release"]["steps"] if step.get("id") == "state")["run"] = (
            "echo remote-release.json"
        )
        variants.append(bad_state)
        bad_guard = json.loads(json.dumps(clean))
        next(step for step in bad_guard["jobs"]["release"]["steps"] if step.get("id") == "download")["if"] = "always()"
        variants.append(bad_guard)
        bad_download = json.loads(json.dumps(clean))
        next(step for step in bad_download["jobs"]["release"]["steps"] if step.get("id") == "download")["run"] = (
            "Invoke-WebRequest -Uri $artifact.url # releases/download"
        )
        variants.append(bad_download)
        bad_staged = json.loads(json.dumps(clean))
        next(step for step in bad_staged["jobs"]["release"]["steps"] if step.get("id") == "verify_staged")["run"] = (
            "echo unchecked"
        )
        variants.append(bad_staged)
        bad_action = json.loads(json.dumps(clean))
        next(step for step in bad_action["jobs"]["release"]["steps"] if step.get("id") == "publish")["uses"] = "example/unsafe@v1"
        variants.append(bad_action)
        bad_with = json.loads(json.dumps(clean))
        next(step for step in bad_with["jobs"]["release"]["steps"] if step.get("id") == "publish")["with"] = "spoof"
        variants.append(bad_with)
        bad_inputs = json.loads(json.dumps(clean))
        publish = next(step for step in bad_inputs["jobs"]["release"]["steps"] if step.get("id") == "publish")
        publish["with"]["fail_on_unmatched_files"] = False
        publish["with"]["files"] = "**/*"
        bad_inputs["jobs"]["release"]["steps"].append({"uses": "softprops/action-gh-release@v2"})
        variants.append(bad_inputs)
        for document in variants:
            with self.subTest(document=document):
                self.assertTrue(audit.release_workflow_errors(yaml.safe_dump(document, sort_keys=False)))

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

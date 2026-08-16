from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts import benchmark_distribution as benchmark
from scripts import flaky_check, quality_policy, security_scan


class QualityPolicyTests(unittest.TestCase):
    def test_missing_tests_directory_is_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(list(quality_policy.test_files(Path(directory))), [])

    def test_skip_without_issue_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tests/example.test.cjs"
            path.parent.mkdir(parents=True)
            path.write_text("test" + ".skip('later', () => {});\n", encoding="utf-8")
            violations = quality_policy.find_violations(root, today=date(2026, 7, 14))
            self.assertEqual([(item.path, item.line) for item in violations], [("tests/example.test.cjs", 1)])

    def test_skip_with_adjacent_issue_justification_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tests/example.py"
            path.parent.mkdir(parents=True)
            marker = "@unittest." + "skip('external')"
            path.write_text(
                "# JUSTIFICATION: tracked at https://github.com/wesleysimplicio/simplicio/issues/10\n"
                "# OWNER: @release-maintainer\n"
                "# REMOVE-BY: 2026-07-30\n"
                + marker
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(quality_policy.find_violations(root, today=date(2026, 7, 14)), [])

    def test_all_supported_skip_forms_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tests/skip_forms.py"
            path.parent.mkdir(parents=True)
            path.write_text(
                "self." + "skipTest('later')\n"
                "raise unittest." + "SkipTest('later')\n"
                "raise " + "SkipTest('later')\n"
                "options = { " + "sk" + "ip: true }\n",
                encoding="utf-8",
            )
            violations = quality_policy.find_violations(root, today=date(2026, 7, 14))
            self.assertEqual(len(violations), 4)
            self.assertTrue(all(item.reason == "missing JUSTIFICATION" for item in violations))

    def test_exception_requires_owner_and_near_term_removal(self):
        base = (
            "# JUSTIFICATION: external service\n"
            "# https://github.com/wesleysimplicio/simplicio/issues/10\n"
        )
        self.assertEqual(
            quality_policy.justification_error(base + "# REMOVE-BY: 2026-07-20", date(2026, 7, 14)),
            "missing OWNER",
        )
        complete = base + "# OWNER: @maintainer\n"
        self.assertEqual(
            quality_policy.justification_error(complete + "# REMOVE-BY: 2026-07-01", date(2026, 7, 14)),
            "REMOVE-BY is expired",
        )
        self.assertEqual(
            quality_policy.justification_error(complete + "# REMOVE-BY: 2026-09-01", date(2026, 7, 14)),
            "REMOVE-BY exceeds 30 days",
        )

    def test_policy_junit_records_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "policy.xml"
            violation = quality_policy.Violation("tests/a.py", 3, "skip", "missing OWNER")
            quality_policy.write_junit(target, [violation])
            self.assertIn("unjustified ignored tests", target.read_text(encoding="utf-8"))

    def test_policy_cli_reports_clean_and_blocked_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            junit = root / "clean.xml"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(quality_policy.main(["--root", str(root), "--junit", str(junit)]), 0)
            path = root / "tests/example.py"
            path.parent.mkdir(parents=True)
            path.write_text("@unittest." + "skip('later')\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(quality_policy.main(["--root", str(root)]), 1)


class BenchmarkTests(unittest.TestCase):
    def test_budget_evaluation_passes_and_fails_deterministically(self):
        contract = {"size": {"baseline": 100, "max_regression_percent": 10}}
        self.assertTrue(benchmark.evaluate({"size": 110}, contract)[0].passed)
        self.assertFalse(benchmark.evaluate({"size": 111}, contract)[0].passed)
        self.assertTrue(benchmark.evaluate({"size": 150}, contract, override=50)[0].passed)

    def test_payload_metric_covers_all_installer_surfaces(self):
        expected = sum((benchmark.ROOT / relative).stat().st_size for relative in benchmark.PAYLOAD_FILES)
        self.assertEqual(benchmark.payload_bytes(), expected)

    def test_benchmark_junit_exposes_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "benchmark.xml"
            result = benchmark.MetricResult("size", 120, 110, False)
            benchmark.write_junit(target, [result])
            self.assertIn("regression budget exceeded", target.read_text(encoding="utf-8"))

    def test_audit_timing_and_cli_emit_reports(self):
        self.assertGreaterEqual(benchmark.audit_median_ms(repetitions=2), 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "metrics": {
                            "installer_payload_bytes": {"baseline": 1_000_000, "max_regression_percent": 0},
                            "audit_median_ms": {"baseline": 10_000, "max_regression_percent": 0},
                        }
                    }
                ),
                encoding="utf-8",
            )
            junit = root / "benchmark.xml"
            output = root / "result.json"
            with contextlib.redirect_stdout(io.StringIO()):
                result = benchmark.main(
                    [
                        "--baseline",
                        str(baseline),
                        "--repetitions",
                        "2",
                        "--junit",
                        str(junit),
                        "--json",
                        str(output),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertTrue(junit.exists())
            self.assertEqual(len(json.loads(output.read_text(encoding="utf-8"))), 2)


class FlakyTests(unittest.TestCase):
    def test_classification_distinguishes_pass_fail_and_flaky(self):
        passed = flaky_check.Attempt(1, 0, 0.1, "ok")
        failed = flaky_check.Attempt(2, 1, 0.1, "bad")
        self.assertEqual(flaky_check.classification([passed]), "PASS")
        self.assertEqual(flaky_check.classification([failed]), "FAIL")
        self.assertEqual(flaky_check.classification([passed, failed]), "FLAKY")

    def test_attempt_runner_captures_output_and_exit(self):
        results = flaky_check.run_attempts([sys.executable, "-c", "print('ok')"], 2)
        self.assertEqual([item.returncode for item in results], [0, 0])
        self.assertTrue(all("ok" in item.output for item in results))

    def test_flaky_cli_writes_attempt_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            junit = Path(directory) / "flaky.xml"
            with contextlib.redirect_stdout(io.StringIO()):
                result = flaky_check.main(
                    [
                        "--attempts",
                        "2",
                        "--junit",
                        str(junit),
                        "--",
                        sys.executable,
                        "-c",
                        "print('stable')",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertIn("attempt-2", junit.read_text(encoding="utf-8"))


class SecurityScanTests(unittest.TestCase):
    def init_repo(self, root: Path, content: str) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / "sample.txt").write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "sample.txt"], cwd=root, check=True)

    def test_scanner_accepts_clean_tracked_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_repo(root, "placeholder only\n")
            self.assertEqual(security_scan.scan(root), [])

    def test_scanner_reports_high_confidence_token_without_echoing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token = "ghp_" + "A" * 40
            self.init_repo(root, token + "\n")
            findings = security_scan.scan(root)
            self.assertEqual([(item.kind, item.line) for item in findings], [("github-token", 1)])

    def test_security_cli_emits_junit_for_clean_and_dirty_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_repo(root, "clean\n")
            junit = root / "security.xml"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(security_scan.main(["--root", str(root), "--junit", str(junit)]), 0)
            (root / "sample.txt").write_text("AKIA" + "A" * 16 + "\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(security_scan.main(["--root", str(root)]), 1)
            self.assertTrue(junit.exists())

    def test_scanner_rejects_dynamic_eval_and_shell_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            source = root / "unsafe.py"
            source.write_text(
                "import subprocess\n"
                "command = input()\n"
                + "e" + "val(command)\n"
                + "subprocess.run(command, shell=True)\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "unsafe.py"], cwd=root, check=True)
            kinds = {item.kind for item in security_scan.scan(root)}
            self.assertEqual(kinds, {"dynamic-code-execution", "dynamic-shell-command"})


if __name__ == "__main__":
    unittest.main()

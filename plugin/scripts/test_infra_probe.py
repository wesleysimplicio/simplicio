#!/usr/bin/env python3
"""simplicio-loop — test infra probe (#526 Etapa 3: "DoD adaptativo a infra real do repositorio").

The 7-dimension DoD (`scripts/pr_dod_review.py` DOD_DIMENSIONS / CLAUDE.md) stays the target, but a
repository without a test project, coverage tooling, or a CI that runs tests cannot produce
`unit`/`min_coverage`/`perf_benchmark` evidence no matter how hard the loop tries — that is not a
quality failure, it is a fact about the repository. This worker answers that fact deterministically
(glob + grep, NEVER an LLM guess) so the gate can size itself to what the repo actually HAS:

  - is there a unit-test project/runner for this ecosystem?
  - is there coverage tooling wired up?
  - does a CI config actually invoke the ecosystem's test command?

Six ecosystems detected: .NET, Node, Python, Go, Rust, Java (table: `references/test-infra-probe.md`
in the simplicio-loop skill). Output is a MEASURED dict (`schema`, `measured: true`, per-ecosystem
markers, and the compact `test_infra: {unit, coverage, ci}` summary) — never hand-typed, never
LLM-asserted. `record_anchor` writes that summary onto the task anchor (`scripts/task_anchor.py`)
under the `test_infra` key, the same "record onto anchor.json" convention as `scripts/route_mode.py`
and `scripts/diff_escalation.py`.

Downstream, `task_anchor.py mark --id ACk --status waived:no-infra --reason "..."` uses this
MEASURED fact to excuse a structurally-impossible dimension (coverage without tooling, benchmark
without a perf harness) instead of leaving it silently pending or falsely marked done. See
`references/test-infra-probe.md` for the full detection table and the "external harness" evidence
form used when `unit: absent` and the delivery contract forbids new files in the target repo.

Usage:
    python3 scripts/test_infra_probe.py probe --root .
    python3 scripts/test_infra_probe.py probe --root . --anchor .simplicio/orchestrator/loop/anchor.json
    python3 scripts/test_infra_probe.py selftest
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "simplicio.test-infra-probe/v1"

# Directories never worth walking into: dependency caches, build output, VCS internals. ".git"
# itself is pruned explicitly below (NOT here) so ".github" (CI config) is never accidentally
# caught by a "starts with .git" shortcut.
PRUNE_DIRS = {
    "node_modules", "vendor", "target", "bin", "obj", "dist", "build", "out",
    ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox",
    "packages", ".idea", ".vs", ".gradle", ".cargo",
}

CI_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "azure-pipelines.yml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
)

# Per-ecosystem detection spec. See references/test-infra-probe.md for the human-readable table
# this mirrors — keep both in sync when adding a marker.
ECOSYSTEMS: Mapping[str, Mapping[str, Any]] = {
    "dotnet": {
        "unit_globs": ("*Tests.csproj", "*.Tests.csproj", "*Test.csproj", "*.Test.csproj"),
        "unit_content": ((("*.csproj",), re.compile(r"Microsoft\.NET\.Test\.Sdk", re.I)),),
        "coverage_globs": ("coverlet.runsettings", "*.coverage", "coverage.cobertura.xml"),
        "coverage_content": ((("*.csproj",), re.compile(r"coverlet", re.I)),),
        "ci_patterns": (re.compile(r"dotnet\s+test", re.I),),
    },
    "node": {
        "unit_globs": ("jest.config.*", "vitest.config.*", ".mocharc*", "karma.conf.*", "ava.config.*"),
        "unit_content": ((("package.json",),
                          re.compile(r'"(jest|mocha|vitest|ava|tape)"\s*:', re.I)),),
        "coverage_globs": (".nycrc*", ".c8rc*"),
        "coverage_content": (
            (("package.json",),
             re.compile(r'"(nyc|c8|@vitest/coverage-v8|@vitest/coverage-istanbul|istanbul)"', re.I)),
            (("jest.config.*",), re.compile(r"collectCoverage", re.I)),
        ),
        "ci_patterns": (
            re.compile(r"\b(npm|yarn|pnpm)\s+(run\s+)?test\b", re.I),
            re.compile(r"npx\s+(jest|vitest|mocha|ava)\b", re.I),
        ),
    },
    "python": {
        "unit_globs": ("pytest.ini", "conftest.py", "test_*.py", "*_test.py"),
        "unit_content": (
            (("pyproject.toml",), re.compile(r"\[tool\.pytest", re.I)),
            (("setup.cfg",), re.compile(r"\[tool:pytest\]", re.I)),
        ),
        "coverage_globs": (".coveragerc",),
        "coverage_content": (
            (("pyproject.toml",), re.compile(r"\[tool\.coverage", re.I)),
            (("setup.cfg",), re.compile(r"\[coverage:", re.I)),
        ),
        "ci_patterns": (
            re.compile(r"\bpytest\b", re.I),
            re.compile(r"python\d?\s+-m\s+pytest", re.I),
            re.compile(r"\btox\b", re.I),
        ),
    },
    "go": {
        "unit_globs": ("*_test.go",),
        "coverage_globs": (".codecov.yml", "codecov.yml"),
        "coverage_content": ((("Makefile",), re.compile(r"-cover\b")),),
        "ci_patterns": (re.compile(r"\bgo\s+test\b", re.I),),
    },
    "rust": {
        "unit_globs": ("tests/*.rs",),
        "unit_content": ((("src/*.rs", "src/**/*.rs"), re.compile(r"#\[test\]")),),
        "coverage_globs": ("tarpaulin.toml",),
        "coverage_content": ((("Cargo.toml",), re.compile(r"tarpaulin", re.I)),),
        "ci_patterns": (re.compile(r"\bcargo\s+test\b", re.I),),
    },
    "java": {
        "unit_globs": ("src/test/java/*.java",),
        "unit_content": ((("pom.xml",), re.compile(r"maven-surefire-plugin", re.I)),),
        "coverage_content": (
            (("pom.xml",), re.compile(r"jacoco", re.I)),
            (("build.gradle*",), re.compile(r"jacoco", re.I)),
        ),
        "ci_patterns": (
            re.compile(r"\bmvn\b[^\n]*\btest\b", re.I),
            re.compile(r"\.\/gradlew\s+test", re.I),
            re.compile(r"\bgradle\s+test\b", re.I),
        ),
    },
}


def _matches(relpath: str, pattern: str) -> bool:
    """`*` matches any character INCLUDING `/` (fnmatch is not path-segment aware), so a pattern
    with a `/` is checked against the full relpath and a bare pattern against just the basename —
    that keeps `pytest.ini` from requiring it to sit at the repo root while still letting
    `src/test/java/*.java` reach into nested packages."""
    if "/" in pattern:
        return fnmatch.fnmatch(relpath, pattern)
    return fnmatch.fnmatch(relpath.rsplit("/", 1)[-1], pattern)


def _relpaths(root: "str | Path") -> list:
    root = Path(root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS and d != ".git"]
        for name in filenames:
            full = Path(dirpath) / name
            try:
                out.append(full.relative_to(root).as_posix())
            except ValueError:
                continue
    return out


def _find(all_paths: Sequence[str], patterns: Sequence[str]) -> list:
    hits = set()
    for p in all_paths:
        for pat in patterns:
            if _matches(p, pat):
                hits.add(p)
                break
    return sorted(hits)


def _read(root: "str | Path", relpath: str) -> "str | None":
    try:
        with open(Path(root) / relpath, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _content_hits(root: "str | Path", all_paths: Sequence[str], content_spec) -> list:
    hits = []
    for patterns, rx in content_spec or ():
        for hit in _find(all_paths, patterns):
            text = _read(root, hit)
            if text is not None and rx.search(text):
                hits.append(hit)
    return hits


def _ecosystem_signal(root: "str | Path", all_paths: Sequence[str], spec: Mapping[str, Any]) -> dict:
    unit_hits = sorted(set(_find(all_paths, spec.get("unit_globs", ()))
                            + _content_hits(root, all_paths, spec.get("unit_content"))))
    coverage_hits = sorted(set(_find(all_paths, spec.get("coverage_globs", ()))
                                + _content_hits(root, all_paths, spec.get("coverage_content"))))
    ci_files = _find(all_paths, CI_GLOBS)
    ci_hits = []
    for f in ci_files:
        text = _read(root, f)
        if text is None:
            continue
        if any(pat.search(text) for pat in spec.get("ci_patterns", ())):
            ci_hits.append(f)
    return {
        "unit": bool(unit_hits),
        "unit_markers": unit_hits,
        "coverage": bool(coverage_hits),
        "coverage_markers": coverage_hits,
        "ci": bool(ci_hits),
        "ci_markers": sorted(set(ci_hits)),
    }


def probe(root: "str | Path") -> dict:
    """MEASURED: walk `root` once, run every ecosystem's detection spec, and aggregate.

    Never LLM-asserted — deterministic glob + grep only, same-input-same-output every run."""
    root = Path(root)
    all_paths = _relpaths(root)
    ecosystems = {name: _ecosystem_signal(root, all_paths, spec) for name, spec in ECOSYSTEMS.items()}
    unit_present = any(e["unit"] for e in ecosystems.values())
    coverage_present = any(e["coverage"] for e in ecosystems.values())
    ci_present = any(e["ci"] for e in ecosystems.values())
    detected = sorted(name for name, e in ecosystems.items() if e["unit"])
    return {
        "schema": SCHEMA,
        "measured": True,
        "root": str(root),
        "ecosystems": ecosystems,
        "detected_ecosystems": detected,
        "test_infra": {
            "unit": "present" if unit_present else "absent",
            "coverage": "present" if coverage_present else "absent",
            "ci": "present" if ci_present else "absent",
        },
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def record_anchor(anchor_path: "str | Path", result: Mapping[str, Any]) -> bool:
    """Write the compact `test_infra` MEASURED summary onto anchor.json — same convention as
    `route_mode.record_anchor` / `diff_escalation.record_anchor` (#526 Etapa 3 point 1)."""
    path = Path(anchor_path)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        data["test_infra"] = {
            "schema": result.get("schema", SCHEMA),
            "measured": True,
            "unit": result["test_infra"]["unit"],
            "coverage": result["test_infra"]["coverage"],
            "ci": result["test_infra"]["ci"],
            "detected_ecosystems": result.get("detected_ecosystems", []),
            "probed_at": _now(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        return False


def cmd_probe(args: argparse.Namespace) -> int:
    result = probe(args.root)
    if args.anchor:
        result["anchor_updated"] = record_anchor(args.anchor, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_selftest() -> int:
    import tempfile

    checks = []

    def chk(name, got, want):
        ok = got == want
        checks.append(ok)
        print("  [%s] %-32s got=%r want=%r" % ("ok" if ok else "XX", name, got, want))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        result = probe(root)
        chk("python.unit_present", result["ecosystems"]["python"]["unit"], True)
        chk("dotnet.unit_absent", result["ecosystems"]["dotnet"]["unit"], False)
        chk("overall.unit_present", result["test_infra"]["unit"], "present")
        chk("overall.coverage_absent", result["test_infra"]["coverage"], "absent")
        chk("overall.ci_absent", result["test_infra"]["ci"], "absent")
        chk("schema", result["schema"], SCHEMA)
        chk("measured", result["measured"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Foo.Tests.csproj").write_text("<Project></Project>", encoding="utf-8")
        chk("dotnet.unit_present_by_name", probe(root)["ecosystems"]["dotnet"]["unit"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Foo.csproj").write_text(
            "<Project><ItemGroup><PackageReference Include=\"Microsoft.NET.Test.Sdk\" "
            "Version=\"17.0.0\" /></ItemGroup></Project>", encoding="utf-8")
        chk("dotnet.unit_present_by_content", probe(root)["ecosystems"]["dotnet"]["unit"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "jest.config.js").write_text("module.exports = {}", encoding="utf-8")
        chk("node.unit_present", probe(root)["ecosystems"]["node"]["unit"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "main_test.go").write_text("package main\n", encoding="utf-8")
        chk("go.unit_present", probe(root)["ecosystems"]["go"]["unit"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "tests").mkdir()
        (root / "tests" / "it.rs").write_text("#[test]\nfn it_works() {}\n", encoding="utf-8")
        chk("rust.unit_present", probe(root)["ecosystems"]["rust"]["unit"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        d = root / "src" / "test" / "java"
        d.mkdir(parents=True)
        (d / "FooTest.java").write_text("class FooTest {}", encoding="utf-8")
        chk("java.unit_present", probe(root)["ecosystems"]["java"]["unit"], True)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("steps:\n  - run: dotnet test\n", encoding="utf-8")
        result = probe(root)
        chk("dotnet.ci_present", result["ecosystems"]["dotnet"]["ci"], True)
        chk("overall.ci_present", result["test_infra"]["ci"], "present")
        chk("node.ci_absent_when_unrelated", result["ecosystems"]["node"]["ci"], False)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        anchor = root / "anchor.json"
        anchor.write_text(json.dumps({"criteria": []}), encoding="utf-8")
        result = probe(root)
        chk("record_anchor.ok", record_anchor(anchor, result), True)
        saved = json.loads(anchor.read_text(encoding="utf-8"))
        chk("record_anchor.unit", saved["test_infra"]["unit"], "present")
        chk("record_anchor.missing_anchor_fails", record_anchor(root / "missing.json", result), False)

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    return 0 if ok else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--describe-cli":
        print(json.dumps({"verbs": ["probe", "selftest"], "flags": ["--root", "--anchor"]}))
        return 0
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    p_probe = sub.add_parser("probe", help="probe the repo for test/coverage/CI infra")
    p_probe.add_argument("--root", default=".")
    p_probe.add_argument("--anchor", default=None,
                         help="anchor.json path to record the MEASURED test_infra summary onto")
    sub.add_parser("selftest", help="run the deterministic in-memory selftest")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return cmd_selftest()
    if args.cmd != "probe":
        parser.print_help()
        return 2
    return cmd_probe(args)


if __name__ == "__main__":
    sys.exit(main())

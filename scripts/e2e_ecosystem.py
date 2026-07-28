#!/usr/bin/env python3
"""Real end-to-end integration tests for the Simplicio ecosystem (issue #9).

This repo ships the compiled `simplicio` runtime binary plus the npm/PyPI
wrappers around it. The actual mapper/dev-cli/prompt/sprint/agent components
live in sibling repos and are consumed here only as optional PATH adapters
(see `simplicio version --json` -> `components`). This script therefore
exercises the *real*, already-built binary end-to-end against an ephemeral,
disposable repo — no `cargo build`/`cargo test` is invoked (compiling the
runtime is out of scope for this packaging repo and explicitly disallowed by
its contribution workflow).

Scenarios covered (see issue #9 "Cenarios minimos"):
  1. Clean install & initialization         -> `simplicio setup`
  2. Valid vs. invalid configuration loading -> `simplicio doctor`
  3. Project discovery / mapping             -> `simplicio runtime map`
  4. A complete task end to end (input->result) -> `simplicio edit`
  5. Error / retry-exhaustion propagation    -> `simplicio edit` + `simplicio recover`
  6. Persistence & resume across process runs -> `.simplicio/` state directory
  7. Compatibility with published dependencies -> `simplicio version` + the
     existing `verify_distribution_consistency.py` packaging contract check

Every check runs against a throwaway temp directory (tempfile.mkdtemp),
never against the developer's real ~/.simplicio state for the *repo-scoped*
assertions. Nothing here talks to the network or requires credentials.

Usage:
    python scripts/e2e_ecosystem.py [--binary PATH] [--json]

Exit code:
    0 - all scenarios passed
    1 - at least one scenario failed (diagnostics printed for each)
    2 - no usable simplicio binary found for this platform (environment gap,
        not a test failure)
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.results.append(Result(name, passed, detail))
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))

    @property
    def ok(self) -> bool:
        return all(r.passed for r in self.results)


def pick_binary(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None

    system = platform.system().lower()
    candidates: list[str]
    if system == "windows":
        candidates = ["simplicio-windows-x64.exe", "simplicio.exe"]
    elif system == "darwin":
        machine = platform.machine().lower()
        if "arm" in machine or "aarch64" in machine:
            candidates = ["simplicio-macos-arm64", "simplicio"]
        else:
            candidates = ["simplicio-darwin-x64", "simplicio"]
    else:
        candidates = ["simplicio-linux-x64", "simplicio"]

    for name in candidates:
        p = ROOT / name
        if p.exists():
            return p
    return None


def run(binary: Path, args: list[str], cwd: Path, input_text: str | None = None,
        timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(binary), *args],
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def scenario_clean_install(binary: Path, report: Report) -> Path:
    """1. Clean install & initialization in a brand-new ephemeral repo."""
    tmp = Path(tempfile.mkdtemp(prefix="simplicio-e2e-init-"))
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=False)
    (tmp / "main.js").write_text("console.log('hi')\n", encoding="utf-8")

    proc = run(binary, ["setup", "--repo", "."], cwd=tmp, input_text="")
    config_path = tmp / ".simplicio" / "config.json"
    ok = proc.returncode == 0 and config_path.exists()
    detail = f"exit={proc.returncode}, config.json exists={config_path.exists()}"
    if ok:
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            ok = data.get("schema") == "simplicio.config/v1"
            detail += f", schema={data.get('schema')}"
        except json.JSONDecodeError as exc:
            ok = False
            detail += f", config.json unparsable: {exc}"
    report.add("1. clean install & initialization (simplicio setup)", ok, detail)
    return tmp


def scenario_config_loading(binary: Path, repo: Path, report: Report) -> None:
    """2. Valid config loads cleanly; corrupted config degrades, doesn't crash."""
    config_path = repo / ".simplicio" / "config.json"
    good_backup = config_path.read_text(encoding="utf-8")

    proc_valid = run(binary, ["doctor", "--repo", ".", "--json"], cwd=repo)
    valid_ok = proc_valid.returncode == 0 and '"overall_status"' in proc_valid.stdout
    report.add(
        "2a. doctor loads a valid repo config",
        valid_ok,
        f"exit={proc_valid.returncode}",
    )

    config_path.write_text("{ this is not valid json ####", encoding="utf-8")
    proc_invalid = run(binary, ["doctor", "--repo", ".", "--json"], cwd=repo)
    # A corrupted config must not crash the runtime (no panic/traceback) and
    # must still produce a diagnostic the caller can act on.
    crashed = proc_invalid.returncode not in (0, 1) or "panic" in proc_invalid.stderr.lower()
    invalid_ok = not crashed and (proc_invalid.stdout.strip() or proc_invalid.stderr.strip())
    report.add(
        "2b. doctor handles a corrupted config without crashing",
        invalid_ok,
        f"exit={proc_invalid.returncode}, crashed={crashed}",
    )

    config_path.write_text(good_backup, encoding="utf-8")


def scenario_project_mapping(binary: Path, repo: Path, report: Report) -> None:
    """3. Project discovery / mapping of the ephemeral repo."""
    proc = run(binary, ["runtime", "map", "--repo", ".", "--json"], cwd=repo, timeout=90)
    ok = proc.returncode == 0 and "simplicio.map-result/v1" in proc.stdout
    report.add(
        "3. project discovery/mapping (simplicio runtime map)",
        ok,
        f"exit={proc.returncode}",
    )


def scenario_full_task(binary: Path, repo: Path, report: Report) -> None:
    """4. A complete task, input to final result: a real mechanical edit."""
    target = repo / "main.js"
    before = target.read_text(encoding="utf-8")
    plan = json.dumps({
        "file": "main.js",
        "operations": [{"op": "replace", "find": "hi", "with": "bye"}],
    })
    proc = run(binary, ["edit", plan, "--json"], cwd=repo)
    after = target.read_text(encoding="utf-8") if target.exists() else ""
    ok = (
        proc.returncode == 0
        and '"status":"ok"' in proc.stdout
        and before != after
        and "bye" in after
    )
    report.add(
        "4. end-to-end task execution (simplicio edit, input->result)",
        ok,
        f"exit={proc.returncode}, before={before.strip()!r}, after={after.strip()!r}",
    )


def scenario_error_propagation(binary: Path, repo: Path, report: Report) -> None:
    """5. Errors and retry-exhaustion propagate with a clear diagnostic."""
    bad_plan = json.dumps({
        "file": "main.js",
        "operations": [{"op": "replace", "find": "DOES_NOT_EXIST_IN_FILE", "with": "x"}],
    })
    proc = run(binary, ["edit", bad_plan, "--json"], cwd=repo)
    edit_ok = proc.returncode != 0 and "pattern not found" in (proc.stdout + proc.stderr)
    report.add(
        "5a. edit failure propagates non-zero exit + clear diagnostic",
        edit_ok,
        f"exit={proc.returncode}, message={(proc.stdout + proc.stderr).strip()[:120]!r}",
    )

    proc_recover = run(binary, ["recover", "exit 3", "--attempts", "2", "--json"], cwd=repo)
    recover_ok = (
        proc_recover.returncode != 0
        and "exhausted 2 attempts" in (proc_recover.stdout + proc_recover.stderr)
    )
    report.add(
        "5b. retry exhaustion (simplicio recover) reports cancellation clearly",
        recover_ok,
        f"exit={proc_recover.returncode}",
    )


def scenario_persistence(binary: Path, repo: Path, report: Report) -> None:
    """6. State persists in .simplicio/ and is resumed by a fresh process."""
    state_dir = repo / ".simplicio"
    before_files = sorted(p.name for p in state_dir.iterdir()) if state_dir.exists() else []

    # A brand-new, independent process invocation must see the same state
    # (not re-run first-run setup) — this is the "resume after failure" bar.
    proc = run(binary, ["doctor", "--repo", ".", "--json"], cwd=repo)
    after_files = sorted(p.name for p in state_dir.iterdir()) if state_dir.exists() else []

    ok = (
        proc.returncode == 0
        and state_dir.exists()
        and "config.json" in after_files
        and before_files == after_files
    )
    report.add(
        "6. state persists across independent process runs (.simplicio/)",
        ok,
        f"state_dir_entries={after_files}",
    )


def scenario_compat(binary: Path, repo: Path, report: Report) -> None:
    """7. Compatibility matrix + published-package version consistency."""
    proc = run(binary, ["version", "--json"], cwd=repo)
    ok = proc.returncode == 0
    components: dict = {}
    if ok:
        try:
            data = json.loads(proc.stdout)
            components = data.get("components", {})
            ok = data.get("schema") == "simplicio.release-manifest/v1" and bool(components)
        except json.JSONDecodeError as exc:
            ok = False
            proc_detail = f"unparsable JSON: {exc}"
        else:
            proc_detail = f"components={sorted(components)}"
    else:
        proc_detail = f"exit={proc.returncode}"
    report.add("7a. release manifest declares component compatibility matrix", ok, proc_detail)

    # Reuse the existing packaging-consistency contract check: if published
    # wrapper/package versions drift from the signed manifest, this must fail.
    consistency_script = ROOT / "scripts" / "verify_distribution_consistency.py"
    proc2 = subprocess.run(
        [sys.executable, str(consistency_script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report.add(
        "7b. published package/manifest versions agree (verify_distribution_consistency.py)",
        proc2.returncode == 0,
        proc2.stdout.strip().splitlines()[-1] if proc2.stdout.strip() else f"exit={proc2.returncode}",
    )


SCENARIOS: list[Callable[[Path, Path, Report], None]] = [
    scenario_config_loading,
    scenario_project_mapping,
    scenario_full_task,
    scenario_error_propagation,
    scenario_persistence,
    scenario_compat,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", help="explicit path to a simplicio binary to test")
    parser.add_argument("--json", action="store_true", help="emit a JSON summary on stdout")
    args = parser.parse_args()

    binary = pick_binary(args.binary)
    if binary is None:
        print(
            "No usable simplicio binary found for this platform in the repo root "
            f"({platform.system()}/{platform.machine()}). This is an environment "
            "gap, not a test failure — skipping.",
            file=sys.stderr,
        )
        return 2

    print(f"Using binary: {binary}")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print()

    report = Report()
    repo = scenario_clean_install(binary, report)
    try:
        for scenario in SCENARIOS:
            try:
                scenario(binary, repo, report)
            except subprocess.TimeoutExpired as exc:
                report.add(f"{scenario.__name__} (timeout)", False, str(exc))
            except Exception as exc:  # noqa: BLE001 - surface any unexpected failure as a finding
                report.add(f"{scenario.__name__} (unexpected error)", False, repr(exc))
    finally:
        shutil.rmtree(repo, ignore_errors=True)

    print()
    passed = sum(1 for r in report.results if r.passed)
    total = len(report.results)
    print(f"summary: {passed}/{total} scenarios passed")

    if args.json:
        print(json.dumps({
            "binary": str(binary),
            "results": [r.__dict__ for r in report.results],
        }))

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed integrity audit for the public Simplicio distribution."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_BRANCH = "master"
MAIN_INSTALL_RE = re.compile(
    r"https://raw\.githubusercontent\.com/wesleysimplicio/simplicio/main/install\.(?:sh|ps1)"
)
FORMULA_VERSION_RE = re.compile(r'version\s+"([^"]+)"')
BETA_NO_END_RE = re.compile(r"public beta with no end date", re.IGNORECASE)
ECOSYSTEM_VERSION_RE = re.compile(r"## Versão atual\s+([^\n]+)", re.MULTILINE)
CURRENT_VERSION_RE = re.compile(r"## Current Version:\s*v([^\s]+)")


@dataclass(frozen=True)
class Finding:
    level: str
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(read_text(path))


def version_from_package_json(path: Path) -> str:
    return str(load_json(path)["version"])


def version_from_formula(path: Path) -> str:
    match = FORMULA_VERSION_RE.search(read_text(path))
    if not match:
        raise ValueError(f"could not parse formula version from {path}")
    return match.group(1)


def version_from_pyproject(path: Path) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', read_text(path), re.MULTILINE)
    if not match:
        raise ValueError(f"could not parse pyproject version from {path}")
    return match.group(1)


def iter_install_reference_files(root: Path) -> Iterable[Path]:
    fixed = (
        "README.md",
        "INSTALL.md",
        "install.sh",
        "install.ps1",
        ".github/workflows/release.yml",
        "pypi/simplicio/simplicio/__main__.py",
    )
    yield from (root / relative for relative in fixed)
    yield from sorted((root / "READMEs").glob("README*.md"))


def run_audit(root: Path = ROOT, *, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    findings: list[Finding] = []

    version_document = read_text(root / "VERSION.md")
    if "Use `master` branch only" not in version_document:
        findings.append(Finding("ERROR", "VERSION.md no longer declares `master` as canonical branch."))

    offenders = [
        str(path.relative_to(root))
        for path in iter_install_reference_files(root)
        if MAIN_INSTALL_RE.search(read_text(path))
    ]
    if offenders:
        findings.append(
            Finding(
                "ERROR",
                "install references point at `/main/` instead of `/master/`: " + ", ".join(offenders),
            )
        )
    else:
        findings.append(Finding("OK", "all public install references use the canonical `master` branch."))

    version_txt = read_text(root / "version.txt").strip()
    manifest = load_json(root / "simplicio-update-manifest.json")
    manifest_version = str(manifest["version"])
    if manifest_version != version_txt:
        findings.append(
            Finding("ERROR", f"version mismatch: version.txt={version_txt} but manifest={manifest_version}")
        )
    else:
        findings.append(Finding("OK", f"release version sources agree on {version_txt}."))

    documented = CURRENT_VERSION_RE.search(version_document)
    if not documented or documented.group(1) != manifest_version:
        value = documented.group(1) if documented else "missing"
        findings.append(Finding("WARN", f"VERSION.md advertises {value} while manifest is {manifest_version}."))
    else:
        findings.append(Finding("OK", "VERSION.md matches the release manifest."))

    wrappers = {
        "Formula/simplicio.rb": version_from_formula(root / "Formula/simplicio.rb"),
        "npm/simplicio/package.json": version_from_package_json(root / "npm/simplicio/package.json"),
        "npm/simplicio-installer/package.json": version_from_package_json(
            root / "npm/simplicio-installer/package.json"
        ),
        "npm/simplicio-unscoped/package.json": version_from_package_json(
            root / "npm/simplicio-unscoped/package.json"
        ),
        "pypi/simplicio/pyproject.toml": version_from_pyproject(root / "pypi/simplicio/pyproject.toml"),
    }
    drift = {path: version for path, version in wrappers.items() if version != manifest_version}
    if drift:
        details = ", ".join(f"{path}={version}" for path, version in drift.items())
        findings.append(Finding("WARN", f"wrapper versions lag manifest {manifest_version}: {details}"))
    else:
        findings.append(Finding("OK", "wrapper/package versions match the release manifest."))

    ecosystem = read_text(root / "SIMPLICIO_ECOSYSTEM.md")
    ecosystem_match = ECOSYSTEM_VERSION_RE.search(ecosystem)
    if not ecosystem_match or manifest_version not in ecosystem_match.group(1):
        advertised = ecosystem_match.group(1).strip() if ecosystem_match else "missing"
        findings.append(
            Finding("WARN", f"SIMPLICIO_ECOSYSTEM.md advertises `{advertised}` while manifest is `{manifest_version}`.")
        )
    else:
        findings.append(Finding("OK", "ecosystem documentation matches the release manifest."))

    beta_until = manifest.get("entitlement", {}).get("beta_until")
    if beta_until:
        try:
            beta_date = date.fromisoformat(str(beta_until))
            if beta_date < today:
                findings.append(Finding("WARN", f"public-beta date {beta_until} is before {today.isoformat()}."))
        except ValueError:
            findings.append(Finding("WARN", f"could not parse beta_until date: {beta_until}"))
        if BETA_NO_END_RE.search(read_text(root / "README.md")):
            findings.append(
                Finding("WARN", f"README has no-end-date claim but manifest carries beta_until={beta_until}.")
            )

    return findings


def write_junit(path: Path, findings: Sequence[Finding]) -> None:
    failures = [item for item in findings if item.level in {"ERROR", "WARN"}]
    suite = ET.Element(
        "testsuite",
        name="distribution-consistency",
        tests=str(len(findings)),
        failures=str(len(failures)),
    )
    for index, finding in enumerate(findings, 1):
        case = ET.SubElement(suite, "testcase", name=f"finding-{index}-{finding.level.lower()}")
        if finding.level in {"ERROR", "WARN"}:
            ET.SubElement(case, "failure", message=finding.message).text = finding.message
        else:
            ET.SubElement(case, "system-out").text = finding.message
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def print_human(root: Path, findings: Sequence[Finding]) -> None:
    print("Simplicio distribution consistency audit")
    print(f"repo: {root}")
    for finding in sorted(findings, key=lambda item: {"ERROR": 0, "WARN": 1, "OK": 2}[item.level]):
        print(f"[{finding.level}] {finding.message}")
    counts = {level: sum(item.level == level for item in findings) for level in ("ERROR", "WARN", "OK")}
    print(f"summary: {counts['ERROR']} error(s), {counts['WARN']} warning(s), {counts['OK']} ok")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    findings = run_audit(args.root)
    if args.junit:
        write_junit(args.junit, findings)
    if args.json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
    else:
        print_human(args.root, findings)
    blocked_levels = {"ERROR", "WARN"} if args.strict else {"ERROR"}
    return int(any(item.level in blocked_levels for item in findings))


if __name__ == "__main__":
    sys.exit(main())

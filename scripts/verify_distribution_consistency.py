#!/usr/bin/env python3
"""Low-risk integrity checks for the public Simplicio distribution repo.

Focuses on verifiable packaging/distribution drift:
- canonical branch install URLs (`master` in this repo)
- release/version source-of-truth mismatches
- stale or contradictory public-beta claims

Exit code:
- 0: no hard failures (warnings may still be printed)
- 1: at least one hard failure
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_BRANCH = "master"
MAIN_INSTALL_RE = re.compile(
    r"https://raw\.githubusercontent\.com/wesleysimplicio/simplicio/main/install\.(?:sh|ps1)"
)
VERSION_RE = re.compile(r'"version"\s*:\s*"([^"]+)"')
FORMULA_VERSION_RE = re.compile(r'version\s+"([^"]+)"')
BETA_NO_END_RE = re.compile(r"public beta with no end date", re.IGNORECASE)
ECOSYSTEM_VERSION_RE = re.compile(r"## Versão atual\s+([^\n]+)", re.MULTILINE)


@dataclass
class Finding:
    level: str  # ERROR | WARN | OK
    message: str


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(read_text(path))


def version_from_package_json(path: Path) -> str:
    return load_json(path)["version"]


def version_from_formula(path: Path) -> str:
    match = FORMULA_VERSION_RE.search(read_text(path))
    if not match:
        raise ValueError(f"could not parse formula version from {path}")
    return match.group(1)


def version_from_pyproject(path: Path) -> str:
    text = read_text(path)
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError(f"could not parse pyproject version from {path}")
    return match.group(1)


def iter_install_reference_files() -> Iterable[Path]:
    yield ROOT / "README.md"
    yield ROOT / "INSTALL.md"
    yield ROOT / "install.sh"
    yield ROOT / "install.ps1"
    yield ROOT / ".github/workflows/release.yml"
    yield ROOT / "pypi/simplicio/simplicio/__main__.py"
    for path in sorted((ROOT / "READMEs").glob("README*.md")):
        yield path


def main() -> int:
    findings: list[Finding] = []

    version_md = read_text(ROOT / "VERSION.md")
    if "Use `master` branch only" not in version_md:
        findings.append(Finding("ERROR", "VERSION.md no longer declares `master` as canonical branch."))

    offenders = []
    for path in iter_install_reference_files():
        text = read_text(path)
        if MAIN_INSTALL_RE.search(text):
            offenders.append(rel(path))
    if offenders:
        findings.append(
            Finding(
                "ERROR",
                "install references still point at `/main/` instead of canonical `/master/`: " + ", ".join(offenders),
            )
        )
    else:
        findings.append(Finding("OK", "all public install references use the canonical `master` branch."))

    version_txt = read_text(ROOT / "version.txt").strip()
    manifest = load_json(ROOT / "simplicio-update-manifest.json")
    manifest_version = manifest["version"]
    if manifest_version != version_txt:
        findings.append(
            Finding(
                "ERROR",
                f"version mismatch: version.txt={version_txt} but simplicio-update-manifest.json={manifest_version}",
            )
        )
    else:
        findings.append(Finding("OK", f"release version sources agree on {version_txt}."))

    wrapper_versions = {
        "Formula/simplicio.rb": version_from_formula(ROOT / "Formula/simplicio.rb"),
        "npm/simplicio/package.json": version_from_package_json(ROOT / "npm/simplicio/package.json"),
        "npm/simplicio-installer/package.json": version_from_package_json(ROOT / "npm/simplicio-installer/package.json"),
        "npm/simplicio-unscoped/package.json": version_from_package_json(ROOT / "npm/simplicio-unscoped/package.json"),
        "pypi/simplicio/pyproject.toml": version_from_pyproject(ROOT / "pypi/simplicio/pyproject.toml"),
    }
    drift = {path: version for path, version in wrapper_versions.items() if version != manifest_version}
    if drift:
        joined = ", ".join(f"{path}={version}" for path, version in drift.items())
        findings.append(
            Finding(
                "WARN",
                f"wrapper/package versions lag manifest {manifest_version}: {joined}",
            )
        )
    else:
        findings.append(Finding("OK", "wrapper/package versions match the release manifest."))

    ecosystem_text = read_text(ROOT / "SIMPLICIO_ECOSYSTEM.md")
    eco_match = ECOSYSTEM_VERSION_RE.search(ecosystem_text)
    if eco_match and manifest_version not in eco_match.group(1):
        findings.append(
            Finding(
                "WARN",
                f"SIMPLICIO_ECOSYSTEM.md advertises `{eco_match.group(1).strip()}` while manifest is `{manifest_version}`.",
            )
        )

    beta_until = manifest.get("entitlement", {}).get("beta_until")
    if beta_until:
        try:
            beta_until_date = date.fromisoformat(beta_until)
            if beta_until_date < date.today():
                findings.append(
                    Finding(
                        "WARN",
                        f"public-beta date is stale: beta_until={beta_until} is before today ({date.today().isoformat()}).",
                    )
                )
        except ValueError:
            findings.append(Finding("WARN", f"could not parse beta_until date: {beta_until}"))

    readme_text = read_text(ROOT / "README.md")
    if beta_until and BETA_NO_END_RE.search(readme_text):
        findings.append(
            Finding(
                "WARN",
                f"README says 'public beta with no end date' but manifest still carries beta_until={beta_until}.",
            )
        )

    errors = [f for f in findings if f.level == "ERROR"]
    warnings = [f for f in findings if f.level == "WARN"]
    oks = [f for f in findings if f.level == "OK"]

    print("Simplicio distribution consistency audit")
    print(f"repo: {ROOT}")
    print("")
    for bucket in (errors, warnings, oks):
        for finding in bucket:
            prefix = {"ERROR": "[ERROR]", "WARN": "[WARN]", "OK": "[OK]"}[finding.level]
            print(f"{prefix} {finding.message}")

    print("")
    print(f"summary: {len(errors)} error(s), {len(warnings)} warning(s), {len(oks)} ok")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

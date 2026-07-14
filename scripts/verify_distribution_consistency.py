#!/usr/bin/env python3
"""Low-risk integrity checks for the public Simplicio distribution repo.

Focuses on verifiable packaging/distribution drift:
- canonical branch install URLs (`master` in this repo)
- release/version source-of-truth mismatches
- stale or contradictory public-beta claims
- target-triplet naming drift between distribution/targets.json (the
  canonical table), the release workflow, the update manifest and the
  installers (issue #5)

Exit code:
- 0: no hard failures (warnings may still be printed)
- 1: at least one hard failure
"""

from __future__ import annotations

import json
import re
import sys
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


def check_target_triplet_consistency(findings: list[Finding]) -> None:
    """Enforce that distribution/targets.json is the single source of truth
    for asset naming across release.yml, the update manifest and both
    installers. This is the concrete regression guard for issue #5's
    "tabela canonica de target triplets" acceptance criterion.
    """
    targets_path = ROOT / "distribution/targets.json"
    if not targets_path.exists():
        findings.append(Finding("ERROR", "distribution/targets.json (canonical target-triplet table) is missing."))
        return

    table = load_json(targets_path)
    targets = table.get("targets", [])
    if not targets:
        findings.append(Finding("ERROR", "distribution/targets.json has no targets defined."))
        return

    release_yml = read_text(ROOT / ".github/workflows/release.yml")
    install_ps1 = read_text(ROOT / "install.ps1")
    install_sh = read_text(ROOT / "install.sh")
    manifest = load_json(ROOT / "simplicio-update-manifest.json")
    manifest_by_target = {a.get("target"): a for a in manifest.get("artifacts", [])}

    offenders: list[str] = []

    for t in targets:
        target_id = t["id"]
        asset = t["asset"]
        installer = t.get("installer")
        manifest_target = t.get("manifest_target", target_id)

        # release.yml must reference the canonical asset name for anything it stages.
        if f"dist/{asset}" not in release_yml:
            offenders.append(f"release.yml does not stage dist/{asset} (target {target_id})")

        # The installer responsible for this target must use the canonical asset name.
        if installer == "install.ps1" and asset not in install_ps1:
            offenders.append(f"install.ps1 does not reference canonical asset {asset} (target {target_id})")
        if installer == "install.sh":
            if t["os"] not in install_sh or t["arch"] not in install_sh:
                offenders.append(
                    f"install.sh does not map os={t['os']!r}/arch={t['arch']!r} to canonical asset {asset} (target {target_id})"
                )

        # If the manifest already publishes this target, its artifact name must match.
        artifact = manifest_by_target.get(manifest_target)
        if artifact and artifact.get("artifact") != asset:
            offenders.append(
                f"manifest artifact for target {manifest_target!r} is {artifact.get('artifact')!r}, expected canonical {asset!r}"
            )

    if offenders:
        findings.append(Finding("ERROR", "target-triplet drift detected: " + "; ".join(offenders)))
    else:
        findings.append(
            Finding("OK", f"release.yml, installers and manifest all agree with distribution/targets.json ({len(targets)} targets).")
        )

    # Unsigned-but-checksummed artifacts are allowed as an interim step, but
    # must say so explicitly rather than silently claiming full verification.
    unsigned = [
        a["target"]
        for a in manifest.get("artifacts", [])
        if a.get("sha256") and not a.get("signed", False)
    ]
    if unsigned:
        findings.append(
            Finding(
                "WARN",
                "artifacts published with checksum but no signature yet (interim, see issue #5): " + ", ".join(unsigned),
            )
        )


def main() -> int:
    findings: list[Finding] = []

    check_target_triplet_consistency(findings)

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

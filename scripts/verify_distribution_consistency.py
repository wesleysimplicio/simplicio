#!/usr/bin/env python3
"""Fail-closed integrity audit for the public Simplicio distribution.

Covers verifiable packaging/distribution drift:
- canonical branch install URLs (`master` in this repo)
- release/version source-of-truth mismatches
- stale or contradictory public-beta claims
- the release workflow's closed-world, provenance-driven publish contract
- target-triplet naming drift between distribution/targets.json (the
  canonical table), the release workflow, the update manifest and the
  installers (issue #5)

Exit code:
- 0: no hard failures (warnings may still be printed, unless --strict)
- 1: at least one hard failure
"""

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

import yaml

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_BRANCH = "master"
MAIN_INSTALL_RE = re.compile(
    r"https://raw\.githubusercontent\.com/wesleysimplicio/simplicio/main/install\.(?:sh|ps1)"
)
BETA_NO_END_RE = re.compile(r"public beta with no end date", re.IGNORECASE)
ECOSYSTEM_VERSION_RE = re.compile(r"## Versão atual\s+([^\n]+)", re.MULTILINE)
CURRENT_VERSION_RE = re.compile(r"## Current Version:\s*v([^\s]+)")
PUBLISH_BODY = (
    "Free public beta. All features remain unlocked during the public-beta phase.\n\n"
    "Windows: `irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex`\n"
    "macOS/Linux: `curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh`\n\n"
    "Checksum-verified update manifest included (`simplicio update check`).\n"
)
CANONICAL_PUBLISH_WITH = {
    "tag_name": "v${{ steps.state.outputs.version }}",
    "target_commitish": "${{ github.sha }}",
    "name": "v${{ steps.state.outputs.version }} — Public Beta",
    "body": PUBLISH_BODY,
    "prerelease": False,
    "make_latest": "true",
    "fail_on_unmatched_files": True,
    "overwrite_files": False,
    "files": "dist/*",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def construct_unique_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate YAML key: {key}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping)


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


def release_workflow_errors(workflow: str) -> list[str]:
    try:
        document = yaml.load(workflow, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        return [f"release workflow YAML is invalid: {exc}"]
    if not isinstance(document, dict):
        return ["release workflow must be a YAML mapping"]
    errors: list[str] = []
    if set(document) != {"name", "on", "permissions", "jobs"}:
        errors.append("release workflow has unexpected or missing top-level keys")
    triggers = document.get("on")
    if not isinstance(triggers, dict) or set(triggers) != {"workflow_dispatch"}:
        errors.append("release workflow must have only workflow_dispatch trigger")
        dispatch = {}
    else:
        dispatch = triggers.get("workflow_dispatch") or {}
    inputs = dispatch.get("inputs") if isinstance(dispatch, dict) else None
    base_input = inputs.get("artifact_base_url") if isinstance(inputs, dict) else None
    if not isinstance(base_input, dict) or base_input.get("required") is not True or base_input.get("type") != "string":
        errors.append("workflow_dispatch must require string input artifact_base_url")
    if document.get("permissions") != {"contents": "read"}:
        errors.append("workflow permissions must default to contents: read")
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {"release"}:
        errors.append("release workflow must contain exactly one release job")
        return errors
    release = jobs.get("release")
    if not isinstance(release, dict) or set(release) != {"permissions", "runs-on", "steps"}:
        errors.append("release job has unexpected or missing keys")
        return errors
    if release.get("permissions") != {"contents": "write"}:
        errors.append("only the release job may elevate contents: write")
    if release.get("runs-on") != "windows-latest":
        errors.append("release job must run on windows-latest")
    steps = release.get("steps") if isinstance(release, dict) else None
    expected_ids = (
        "checkout",
        "setup_python",
        "install",
        "state",
        "provenance",
        "download",
        "verify_staged",
        "metadata",
        "publish",
    )
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        errors.append("jobs.release.steps must be a list of mappings")
        return errors
    actual_ids = tuple(step.get("id") for step in steps)
    if actual_ids != expected_ids or len(set(actual_ids)) != len(actual_ids):
        errors.append("release step IDs must match the exact ordered closed-world allowlist")
        return errors
    indexed = {step["id"]: step for step in steps}
    expected_keys = {
        "checkout": {"id", "uses", "with"},
        "setup_python": {"id", "uses", "with"},
        "install": {"id", "run"},
        "state": {"id", "env", "run"},
        "provenance": {"id", "env", "run"},
        "download": {"id", "if", "env", "run"},
        "verify_staged": {"id", "if", "run"},
        "metadata": {"id", "if", "run"},
        "publish": {"id", "if", "uses", "with"},
    }
    expected_uses = {
        "checkout": "actions/checkout@v4",
        "setup_python": "actions/setup-python@v5",
        "publish": "softprops/action-gh-release@v2",
    }
    expected_runs = {
        "install": "python -m pip install -r requirements-quality.txt",
        "state": "python scripts/verify_release_provenance.py state",
        "provenance": "python scripts/verify_release_provenance.py plan",
        "download": "python scripts/verify_release_provenance.py download",
        "verify_staged": "python scripts/verify_release_provenance.py verify-staged",
        "metadata": "python scripts/verify_release_provenance.py metadata",
    }
    expected_env = {
        "state": {"GITHUB_TOKEN": "${{ github.token }}"},
        "provenance": {
            "ARTIFACT_BASE_URL": "${{ inputs.artifact_base_url }}",
            "TAG_EXISTS": "${{ steps.state.outputs.tag_exists }}",
        },
        "download": {"ARTIFACT_BASE_URL": "${{ inputs.artifact_base_url }}"},
    }
    for step_id in expected_ids:
        step = indexed[step_id]
        if set(step) != expected_keys[step_id]:
            errors.append(f"{step_id} step has unexpected or missing keys")
        if step_id in expected_uses and step.get("uses") != expected_uses[step_id]:
            errors.append(f"{step_id} step uses an unapproved action")
        if step_id in expected_runs and step.get("run") != expected_runs[step_id]:
            errors.append(f"{step_id} step must equal its canonical single command")
        if step_id in expected_env and step.get("env") != expected_env[step_id]:
            errors.append(f"{step_id} step env must match the exact allowlist")
    publish_condition = "steps.provenance.outputs.mode == 'publish'"
    guarded_ids = ("download", "verify_staged", "metadata", "publish")
    for step_id in guarded_ids:
        if indexed[step_id].get("if") != publish_condition:
            errors.append(f"{step_id} step must be guarded by publish mode")
    if indexed["checkout"].get("with") != {"fetch-depth": 0}:
        errors.append("checkout step inputs must match the exact allowlist")
    if indexed["setup_python"].get("with") != {"python-version": "3.13"}:
        errors.append("setup_python step inputs must match the exact allowlist")
    publish = indexed["publish"]
    publish_with = publish.get("with")
    if not isinstance(publish_with, dict):
        errors.append("publish step must define structured with inputs")
    elif publish_with != CANONICAL_PUBLISH_WITH:
        errors.append("publish with mapping must equal the complete canonical mapping")
    return errors


def check_target_triplet_consistency(root: Path, findings: list[Finding]) -> None:
    """Enforce that distribution/targets.json is the single source of truth
    for asset naming across release.yml, the update manifest and both
    installers. This is the concrete regression guard for issue #5's
    "tabela canonica de target triplets" acceptance criterion.
    """
    targets_path = root / "distribution/targets.json"
    if not targets_path.exists():
        findings.append(Finding("ERROR", "distribution/targets.json (canonical target-triplet table) is missing."))
        return

    table = load_json(targets_path)
    targets = table.get("targets", [])
    if not targets:
        findings.append(Finding("ERROR", "distribution/targets.json has no targets defined."))
        return

    release_yml = read_text(root / ".github/workflows/release.yml")
    install_ps1 = read_text(root / "install.ps1")
    install_sh = read_text(root / "install.sh")
    manifest = load_json(root / "simplicio-update-manifest.json")
    manifest_by_target = {a.get("target"): a for a in manifest.get("artifacts", [])}

    offenders: list[str] = []

    # Under the closed-world provenance release model, release.yml stages
    # whatever verify_release_provenance.py verifies-and-downloads by
    # publishing the whole dist/ directory (a generic glob), rather than
    # hard-coding a `cp asset dist/asset` line per target triplet. So the
    # per-asset name that matters lives in simplicio-update-manifest.json
    # (checked per-target below), not in release.yml's text; here we only
    # assert release.yml still publishes generically instead of silently
    # reintroducing a target-specific allowlist that could drift from this
    # table.
    if "dist/*" not in release_yml:
        offenders.append(
            "release.yml no longer publishes the generic dist/* glob "
            "(asset naming may have drifted from distribution/targets.json)"
        )

    for t in targets:
        target_id = t["id"]
        asset = t["asset"]
        installer = t.get("installer")
        manifest_target = t.get("manifest_target", target_id)

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
            Finding(
                "OK",
                "release.yml, installers and manifest all agree with "
                f"distribution/targets.json ({len(targets)} targets).",
            )
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


def run_audit(root: Path = ROOT, *, today: date | None = None) -> list[Finding]:
    today = today or date.today()
    findings: list[Finding] = []

    check_target_triplet_consistency(root, findings)

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

    artifacts = manifest.get("artifacts") or []
    signature_required = bool(manifest.get("security", {}).get("signature_required"))
    manifest_errors: list[str] = []
    for artifact in artifacts:
        name = str(artifact.get("artifact") or "")
        expected_url = (
            f"https://github.com/wesleysimplicio/simplicio/releases/download/"
            f"v{manifest_version}/{name}"
        )
        if not name or artifact.get("url") != expected_url:
            manifest_errors.append(f"manifest artifact URL is not version-bound: {name or 'missing-name'}")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(artifact.get("sha256") or "")):
            manifest_errors.append(f"manifest artifact has invalid SHA256: {name or 'missing-name'}")
        if signature_required and not str(artifact.get("signature") or "").startswith("ed25519:"):
            manifest_errors.append(f"manifest artifact lacks required Ed25519 signature: {name or 'missing-name'}")
    if not artifacts:
        manifest_errors.append("manifest contains no release artifacts")
    if manifest_errors:
        findings.extend(Finding("ERROR", message) for message in manifest_errors)
    else:
        findings.append(Finding("OK", "manifest artifact URLs, hashes, and signatures are version-bound."))

    wrappers = {
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

    release_errors = release_workflow_errors(read_text(root / ".github/workflows/release.yml"))
    if release_errors:
        findings.append(Finding("ERROR", "release workflow provenance is not fail-closed: " + ", ".join(release_errors)))
    else:
        findings.append(Finding("OK", "structured manual release supports idempotent state or verified staging publish."))

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

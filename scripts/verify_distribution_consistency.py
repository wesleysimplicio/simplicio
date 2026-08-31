#!/usr/bin/env python3
"""Fail-closed integrity audit for the public Simplicio distribution.

Covers verifiable packaging/distribution drift:
- canonical branch install URLs (`master` in this repo)
- release/version source-of-truth mismatches
- stale or contradictory public-beta claims
- the local publisher's ordered verification and immutable upload contract
- target-triplet naming drift between distribution/targets.json (the
  canonical table), the local publisher, the update manifest and the
  installers (issue #5)

Exit code:
- 0: no hard failures (warnings may still be printed, unless --strict)
- 1: at least one hard failure
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from textwrap import indent
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PUBLISHER = "scripts/publish_release_local.py"
PUBLIC_REPOSITORY = "wesleysimplicio/simplicio"
CANONICAL_BRANCH = "master"
MAIN_INSTALL_RE = re.compile(
    r"https://raw\.githubusercontent\.com/wesleysimplicio/simplicio/main/install\.(?:sh|ps1)"
)
BETA_NO_END_RE = re.compile(r"public beta with no end date", re.IGNORECASE)
ECOSYSTEM_VERSION_RE = re.compile(r"## Versão atual\s+([^\n]+)", re.MULTILINE)
CURRENT_VERSION_RE = re.compile(r"## Current Version:\s*v([^\s]+)")
# This is a source contract, not a publication receipt. Compare executable AST
# nodes instead of comments/strings, without importing or running the publisher.
# Helper implementations have their own executable tests; these ordered entry
# points prevent skipping their gates, broad uploads, or automatic overwrite.
LOCAL_CHECKS = '''verify_codex_hook_contract()
run([sys.executable, str(ROOT / "scripts/verify_distribution_consistency.py")])
run([sys.executable, "-m", "pytest", "-q",
     "tests/test_codex_integration_cli.py", "tests/test_release_local_contract.py"])
run([str(bundle / "simplicio-macos-arm64"), "version", "--json"])
if (ROOT / "scripts/verify_mcp_tools.py").is_file():
    run([sys.executable, str(ROOT / "scripts/verify_mcp_tools.py"),
         str(bundle / "simplicio-macos-arm64")])
'''
LOCAL_INSTALL_CHECK = '''terminal = run([
    sys.executable, str(ROOT / "scripts/release_install_smoke.py"),
    "--version", version, "--terminal", "--json"], timeout=900)
'''
LOCAL_PYPI_UPLOAD = '''run([sys.executable, "-m", "twine", "upload", "--non-interactive", str(wheel)], timeout=900)
'''
LOCAL_POST_CHECKS = '''pypi = wait_for_pypi(version)
package = run([sys.executable, str(ROOT / "scripts/release_install_smoke.py"),
               "--version", version, "--pypi", "--json"], timeout=1200)
remote = run([sys.executable, str(ROOT / "scripts/post_release_smoke.py"),
              "--repo", PUBLIC_REPOSITORY, "--version", tag, "--execute", "--json"], timeout=1200)
'''
LOCAL_ENTRY_CONTRACTS = {
    "publish": '''public_preflight(tag, version, require_clean=True)
bundle_receipt = verify_bundle(bundle, tag, version, source_commit)
changed = stage_bundle(bundle)
changed.extend(stage_codex_hooks(bundle))
changed.extend(update_public_metadata(tag, version, source_commit))
changed.extend(prepare_package(version))
''' + LOCAL_CHECKS + '''with tempfile.TemporaryDirectory(prefix="simplicio-public-wheel-") as raw:
    wheel = build_wheel(Path(raw), version)
    wheel_help_smoke(wheel)
    public_commit = commit_public(changed, tag, source_commit)
    create_public_release(tag, bundle)
''' + indent(LOCAL_INSTALL_CHECK + LOCAL_PYPI_UPLOAD + LOCAL_POST_CHECKS, "    "),
    "resume_publish": '''resume_state = resume_public_preflight(tag, version, source_commit)
bundle_receipt = verify_bundle(bundle, tag, version, source_commit)
verify_public_codex_hooks(bundle)
''' + LOCAL_CHECKS + '''with tempfile.TemporaryDirectory(prefix="simplicio-public-resume-wheel-") as raw:
    wheel = build_wheel(Path(raw), version)
    wheel_help_smoke(wheel)
''' + indent(LOCAL_INSTALL_CHECK + '''if not resume_state["already_published_to_pypi"]:
''' + indent(LOCAL_PYPI_UPLOAD, "    ") + LOCAL_POST_CHECKS, "    "),
    "required_release_assets": '''files = list(META_ASSETS)
for asset in ASSETS:
    files.extend((asset, asset + ".sig", asset + ".spdx.json", asset + ".provenance.json"))
return files
''',
    "create_public_release": '''run([
    "gh", "release", "create", tag,
    *[str(bundle / name) for name in required_release_assets()],
    "--repo", PUBLIC_REPOSITORY, "--verify-tag", "--title", "Simplicio Runtime " + tag,
    "--notes", "Signed public Runtime release %s built and verified locally." % tag,
], timeout=3600)
''',
}


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
        "pypi/simplicio/simplicio/__main__.py",
    )
    yield from (root / relative for relative in fixed)
    yield from sorted((root / "READMEs").glob("README*.md"))


def publisher_constant(document: ast.Module, name: str):
    values = [
        statement.value
        for statement in document.body
        if isinstance(statement, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in statement.targets)
    ]
    if len(values) != 1:
        raise ValueError(f"local publisher must define {name} exactly once")
    try:
        return ast.literal_eval(values[0])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"local publisher {name} must be literal data") from exc


def local_release_assets(root: Path) -> tuple[str, ...]:
    path = root / LOCAL_PUBLISHER
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{LOCAL_PUBLISHER} must be a regular local file")
    document = ast.parse(read_text(path))
    assets = publisher_constant(document, "ASSETS")
    if (
        not isinstance(assets, tuple)
        or not assets
        or any(not isinstance(asset, str) or re.fullmatch(r"[A-Za-z0-9._-]+", asset) is None for asset in assets)
        or len(set(assets)) != len(assets)
    ):
        raise ValueError("local publisher ASSETS must be unique safe filenames")
    return assets


def manual_release_errors(root: Path) -> list[str]:
    errors: list[str] = []
    workflow_root = root / ".github/workflows"
    if workflow_root.exists():
        workflows = sorted(path.relative_to(root).as_posix() for path in workflow_root.rglob("*") if path.is_file())
        if workflows:
            errors.append("public distribution must use local/manual publication, not workflow files: " + ", ".join(workflows))
    try:
        path = root / LOCAL_PUBLISHER
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{LOCAL_PUBLISHER} must be a regular local file")
        document = ast.parse(read_text(path))
        if publisher_constant(document, "PUBLIC_REPOSITORY") != PUBLIC_REPOSITORY:
            errors.append("local publisher must target the public distribution repository")
        if publisher_constant(document, "META_ASSETS") != ("SHA256SUMS", "simplicio-update-manifest.json"):
            errors.append("local publisher must include checksums and the signed manifest")
        local_release_assets(root)
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        return errors + [f"local publisher cannot be verified: {exc}"]

    functions = [node for node in document.body if isinstance(node, ast.FunctionDef)]
    names = [node.name for node in functions]
    if len(names) != len(set(names)):
        return errors + ["local publisher has duplicate function definitions"]
    indexed = {node.name: node for node in functions}
    for name, contract in LOCAL_ENTRY_CONTRACTS.items():
        function = indexed.get(name)
        if function is None:
            errors.append(f"local publisher is missing {name}")
            continue
        body = function.body
        if name in {"publish", "resume_publish"}:
            # Receipt serialization is not an effect gate. The entire sequence
            # before the final receipt must still equal the local contract.
            if not body or not isinstance(body[-1], ast.Return):
                errors.append(f"{name} must finish with a publication receipt")
                continue
            body = body[:-1]
        expected = ast.parse(contract).body
        if [ast.dump(node) for node in body] != [ast.dump(node) for node in expected]:
            errors.append(f"{name} must match the ordered local verification/publication contract")

    # No optional CI context, trigger, force-tag, or asset overwrite is an
    # alternative to the local gates. Inspect arguments, not comments.
    for node in ast.walk(document):
        if not isinstance(node, ast.Call) or not node.args or not isinstance(node.args[0], ast.List):
            continue
        arguments = node.args[0].elts
        literals = [item.value for item in arguments if isinstance(item, ast.Constant) and isinstance(item.value, str)]
        if literals[:2] in (["gh", "workflow"], ["gh", "run"]):
            errors.append("local publisher must not invoke remote workflows")
        if literals[:3] in (["gh", "release", "upload"], ["gh", "release", "delete"]):
            errors.append("local publisher must not overwrite or delete release assets")
        if literals[:2] in (["git", "tag"], ["git", "push"]) and any(
            flag in {"-f", "--force", "--force-with-lease", "--delete"} for flag in literals
        ):
            errors.append("local publisher must not move or delete published tags")
    return errors


def check_target_triplet_consistency(root: Path, findings: list[Finding]) -> None:
    """Enforce that distribution/targets.json is the single source of truth
    for asset naming across the local publisher, the update manifest and both
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

    install_ps1 = read_text(root / "install.ps1")
    install_sh = read_text(root / "install.sh")
    manifest = load_json(root / "simplicio-update-manifest.json")
    manifest_by_target = {a.get("target"): a for a in manifest.get("artifacts", [])}

    offenders: list[str] = []

    try:
        published_assets = set(local_release_assets(root))
        if published_assets != {target["asset"] for target in targets}:
            offenders.append("local publisher ASSETS differs from the canonical target table")
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        offenders.append(str(exc))

    expected_targets = {target.get("manifest_target", target["id"]) for target in targets}
    if set(manifest_by_target) != expected_targets or len(manifest_by_target) != len(manifest.get("artifacts", [])):
        offenders.append("manifest must contain each canonical target exactly once")

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
                "local publisher, installers and manifest all agree with "
                f"distribution/targets.json ({len(targets)} targets).",
            )
        )

    # Unsigned-but-checksummed artifacts are allowed as an interim step, but
    # must say so explicitly rather than silently claiming full verification.
    unsigned = [
        a["target"]
        for a in manifest.get("artifacts", [])
        if a.get("sha256")
        and not (
            a.get("signed", False)
            or str(a.get("signature") or "").startswith("ed25519:")
        )
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
    manifest_errors: list[str] = []
    security = manifest.get("security")
    if not isinstance(security, dict) or security.get("signature_required") is not True:
        manifest_errors.append("public release manifest must require Ed25519 signatures")
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
        if not str(artifact.get("signature") or "").startswith("ed25519:"):
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

    release_errors = manual_release_errors(root)
    if release_errors:
        findings.append(Finding("ERROR", "local release contract is not fail-closed: " + ", ".join(release_errors)))
    else:
        findings.append(Finding("OK", "local/manual publisher preserves ordered verification and explicit immutable release assets (source contract only)."))

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

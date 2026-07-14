"""Unit + regression tests for scripts/verify_distribution_consistency.py.

These are part of the CI quality gate (issue #10): every acceptance
criterion that says "regression test for a fixed bug" is anchored here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_distribution_consistency.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_distribution_consistency", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses.dataclass() looks the defining module up in sys.modules, so
    # it must be registered there before exec_module() runs the class body.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vdc = _load_module()


# ---------------------------------------------------------------------------
# Unit tests for the small parsing helpers.
# ---------------------------------------------------------------------------


def test_version_from_package_json(tmp_path):
    path = tmp_path / "package.json"
    path.write_text(json.dumps({"name": "x", "version": "9.9.9"}), encoding="utf-8")
    assert vdc.version_from_package_json(path) == "9.9.9"


def test_version_from_formula(tmp_path):
    path = tmp_path / "simplicio.rb"
    path.write_text('class Simplicio < Formula\n  version "9.9.9"\nend\n', encoding="utf-8")
    assert vdc.version_from_formula(path) == "9.9.9"


def test_version_from_formula_missing_raises(tmp_path):
    path = tmp_path / "simplicio.rb"
    path.write_text("class Simplicio < Formula\nend\n", encoding="utf-8")
    try:
        vdc.version_from_formula(path)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_version_from_pyproject(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\nversion = "9.9.9"\n', encoding="utf-8")
    assert vdc.version_from_pyproject(path) == "9.9.9"


def test_main_install_regex_flags_main_branch_reference():
    offending = "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh"
    assert vdc.MAIN_INSTALL_RE.search(offending) is not None


def test_main_install_regex_allows_master_branch_reference():
    ok = "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh"
    assert vdc.MAIN_INSTALL_RE.search(ok) is None


# ---------------------------------------------------------------------------
# Regression test: version.txt vs simplicio-update-manifest.json drift.
#
# The audit script previously reported (ERROR) that version.txt (3.0.2) and
# simplicio-update-manifest.json (3.5.2) disagreed on the release version.
# That is the exact class of "silent release drift" this quality gate exists
# to catch. version.txt has been synced to the manifest as part of turning
# this check into a blocking CI gate (see .github/workflows/quality-gate.yml)
# instead of a warning nobody reads. This test pins the fix so a future
# change can't silently reintroduce the drift.
# ---------------------------------------------------------------------------


def test_version_txt_matches_update_manifest_regression():
    version_txt = (REPO_ROOT / "version.txt").read_text(encoding="utf-8").strip()
    manifest = json.loads((REPO_ROOT / "simplicio-update-manifest.json").read_text(encoding="utf-8"))
    assert version_txt == manifest["version"], (
        "version.txt and simplicio-update-manifest.json drifted apart again; "
        "keep them in sync or update this test with a registered justification."
    )


def test_audit_script_exits_zero_on_this_repo_checkout():
    """End-to-end / integration-style check: running the real script against
    this checkout must not report any *new* hard (ERROR-level) failure.

    ``main()`` takes an explicit empty argv here (rather than the CLI
    default of reading ``sys.argv``) so this stays a library-level check
    and isn't polluted by pytest's own command-line arguments.

    The three ed25519-signature ERRORs below are a known, tracked interim
    gap (windows-x64/macos-x64/linux-x64 are checksum-verified but not yet
    signed; see simplicio-update-manifest.json's "signing_note" fields and
    issue #5) that predates and is unrelated to this audit script's release-
    workflow provenance work. This test still guards against any *other*
    ERROR being silently introduced.
    """
    findings = vdc.run_audit(vdc.ROOT)
    known_interim_errors = {
        "manifest artifact lacks required Ed25519 signature: simplicio-windows-x64.exe",
        "manifest artifact lacks required Ed25519 signature: simplicio-macos-x64",
        "manifest artifact lacks required Ed25519 signature: simplicio-linux-x64",
    }
    unexpected_errors = [
        item.message
        for item in findings
        if item.level == "ERROR" and item.message not in known_interim_errors
    ]
    assert unexpected_errors == []

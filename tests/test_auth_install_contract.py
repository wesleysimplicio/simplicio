"""Regression tests for the post-login installer contract.

The Runtime validation API historically returned the account email under
``user.email`` while older installers only inspected ``identity.email``.
These tests keep the shell installers defensive during staged upgrades.
"""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def installer_active(payload):
    identity = payload.get("identity") or {}
    entitlement = payload.get("entitlement") or {}
    identity_email = identity.get("email") or (payload.get("user") or {}).get("email")
    return (
        identity.get("enabled") is True
        and identity.get("login_enabled") is True
        and identity.get("status") not in {"disabled", "logged_out", "revoked"}
        and bool(identity_email)
        and entitlement.get("updates_allowed") is True
    )


def manifest_signature_present(payload):
    artifact = next(item for item in payload["artifacts"] if item["target"] == "windows-x64")
    return bool(artifact.get("signed")) or str(artifact.get("signature") or "").startswith("ed25519:")


def test_legacy_identity_shape_is_accepted_after_successful_login():
    payload = {
        "active": True,
        "user": {"email": "customer@example.com"},
        "identity": {
            "enabled": True,
            "login_enabled": True,
            "provider": "google_gmail",
            "status": "active",
        },
        "entitlement": {"active": True, "updates_allowed": True},
    }
    assert installer_active(payload)


def test_revoked_identity_is_still_rejected():
    payload = {
        "user": {"email": "customer@example.com"},
        "identity": {"enabled": True, "login_enabled": True, "status": "revoked"},
        "entitlement": {"active": True, "updates_allowed": True},
    }
    assert not installer_active(payload)


def test_both_published_installers_include_legacy_email_fallback():
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "$status.user.email" in powershell
    assert "payload.get(\"user\")" in shell


def test_manifest_signature_field_is_accepted_without_signed_boolean():
    payload = {
        "artifacts": [{
            "target": "windows-x64",
            "signature": "ed25519:valid-signature",
        }]
    }
    assert manifest_signature_present(payload)


def test_installers_use_ed25519_signature_when_signed_boolean_is_absent():
    powershell = (ROOT / "install.ps1").read_text(encoding="utf-8")
    shell = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert 'StartsWith("ed25519:")' in powershell
    assert "startswith('ed25519:')" in shell

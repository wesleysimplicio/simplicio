import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("verify_release_gate.py")
spec = importlib.util.spec_from_file_location("verify_release_gate", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _track(track_id, **extra):
    base = {
        "id": track_id,
        "status": "verified",
        "source": "installed",
        "evidence_ids": [f"{track_id}:receipt"],
        "redacted": True,
    }
    return {**base, **extra}


def valid_document():
    return {
        "schema": "simplicio.desktop.release-gate/v1",
        "source": "installed",
        "preview": False,
        "redacted": True,
        "tracks": [
            _track("install", all_platforms=True, native_install=True, runtime_digest=True,
                   signature=True, sbom=True, provenance=True, runtime_healthy=True),
            _track("oauth", all_platforms=True, clean_home=True, google_callback=True,
                   runtime_confirmed=True, host_unchanged=True, logout_relogin=True),
            _track("e2e", all_platforms=True, clean_home=True, scenario_matrix=True,
                   secrets_redacted=True),
            _track("usage", coverage="complete", unknown_providers=0,
                   usage_total_known=True, usage_total_tokens=185, renderer_recomputed=False),
            _track("cost", coverage="complete", pricing_unknown=False, cost_total_known=True,
                   cost_total_usd=0.02, renderer_recomputed=False),
            _track("privacy", paths_redacted=True, argv_redacted=True, prompts_absent=True,
                   secrets_redacted=True),
            _track("release", all_platforms=True, native_install=True, login_real=True,
                   runtime_digest=True, runtime_healthy=True),
        ],
        "dependencies": {
            issue: {
                "status": "verified",
                "source": "installed",
                "evidence_ids": [f"{issue}:receipt"],
                "redacted": True,
            }
            for issue in ("#282", "#283", "#286", "#287", "#288", "#289")
        },
    }


def test_ready_requires_every_installed_track_and_dependency():
    result = module.verify_gate(valid_document())
    assert result["status"] == "ready"
    assert result["verified_tracks"] == ["install", "oauth", "e2e", "usage", "cost", "privacy", "release"]
    assert result["blocking_reasons"] == []


@pytest.mark.parametrize("change", [
    lambda doc: doc["tracks"].__setitem__(3, _track(
        "usage", status="unavailable", coverage="complete", unknown_providers=0,
        usage_total_known=False, usage_total_tokens=0, renderer_recomputed=False)),
    lambda doc: doc["tracks"].__setitem__(4, _track(
        "cost", coverage="complete", pricing_unknown=True, cost_total_known=False,
        cost_total_usd=0, renderer_recomputed=False)),
])
def test_unknown_or_unavailable_evidence_blocks_gate(change):
    document = valid_document()
    change(document)
    result = module.verify_gate(document)
    assert result["status"] == "blocked"
    assert result["blocking_reasons"]


def test_zero_usage_requires_proof_and_sensitive_or_preview_data_is_rejected():
    zero = valid_document()
    zero["tracks"][3]["usage_total_tokens"] = 0
    result = module.verify_gate(zero)
    assert result["status"] == "blocked"
    assert "usage:zero_usage_proven=true" in result["blocking_reasons"]

    with pytest.raises(module.GateInputError, match="gate_preview_forbidden"):
        module.verify_gate({**valid_document(), "preview": True})
    with pytest.raises(module.GateInputError, match="gate_sensitive_field"):
        module.verify_gate({**valid_document(), "tracks": [
            *valid_document()["tracks"][:-1],
            {**valid_document()["tracks"][-1], "path": "/private/evidence"},
        ]})


def test_required_issue_set_cannot_be_skipped():
    document = valid_document()
    del document["dependencies"]["#289"]
    result = module.verify_gate(document)
    assert result["status"] == "blocked"
    assert "dependencies=exact_required_issues" in result["blocking_reasons"]

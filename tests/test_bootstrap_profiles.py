from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_public_bootstrap_contract_has_exactly_two_shared_profiles() -> None:
    contract = json.loads(
        (ROOT / "distribution" / "bootstrap-profiles.json").read_text(encoding="utf-8")
    )
    profiles = contract["download_options"]
    assert contract["schema"] == "simplicio.bootstrap-profiles/v1"
    assert [profile["id"] for profile in profiles] == [
        "recommended-desktop",
        "recommended-cli",
    ]
    assert len(profiles) == 2
    assert profiles[0]["recommended"] is True
    assert profiles[0]["component_lock"] == profiles[1]["component_lock"] == "shared"
    assert profiles[0]["shared_state_profile"] == profiles[1]["shared_state_profile"] == "recommended"
    assert "cli" in profiles[0]["includes"]
    assert "desktop-shell" in profiles[1]["excludes"]
    assert contract["invariants"]["exactly_two_download_options"] is True


def test_landing_surface_exposes_desktop_and_cli_only_once() -> None:
    landing = (ROOT / "landing.html").read_text(encoding="utf-8")
    assert landing.count('data-bootstrap-profile="recommended-desktop"') == 1
    assert landing.count('data-bootstrap-profile="recommended-cli"') == 1
    assert "Desktop · recomendado" in landing
    assert "CLI only" in landing

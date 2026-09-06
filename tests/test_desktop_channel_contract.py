from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
DMG_NAME = "Simplicio-3.8.47-arm64.dmg"
DMG_URL = "https://github.com/wesleysimplicio/simplicio/releases/download/v3.8.47/Simplicio-3.8.47-arm64.dmg"
DMG_SHA256 = "9c8b02e8b804ddcf992c26f5d156ab0261fe498bee30237727d74abbbc38d779"


def test_desktop_digest_is_separate_from_runtime_closed_world() -> None:
    desktop_sums = (ROOT / "DESKTOP-SHA256SUMS").read_text(encoding="ascii").splitlines()
    assert desktop_sums == [f"{DMG_SHA256} *{DMG_NAME}"]
    assert DMG_NAME not in (ROOT / "SHA256SUMS").read_text(encoding="ascii")
    manifest = json.loads((ROOT / "simplicio-update-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["artifacts"]) == 4
    assert all(record["artifact"] != DMG_NAME for record in manifest["artifacts"])


def test_public_desktop_links_and_windows_boundary_are_consistent() -> None:
    landing = (ROOT / "landing.html").read_text(encoding="utf-8")
    profile = json.loads((ROOT / "distribution" / "bootstrap-profiles.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release = (ROOT / "docs" / "desktop" / "RELEASE.md").read_text(encoding="utf-8")
    assert DMG_URL in landing
    assert profile["download_options"][0]["entrypoint"] == DMG_URL
    assert "Windows Desktop is not published." in readme
    assert DMG_URL in readme
    assert "Apple Developer ID signing" in readme
    assert "Gatekeeper acceptance is not claimed" in readme
    assert "Windows Desktop" in release
    assert "no GitHub Actions result is invented" in release

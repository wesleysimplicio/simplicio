"""Overlay releases retarget URLs without touching signed Runtime bytes."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_module():
    path = ROOT / "scripts/cut_public_overlay_release.py"
    spec = importlib.util.spec_from_file_location("cut_public_overlay_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rewrite_manifest_keeps_signatures_and_retargets_urls():
    module = load_module()
    original = {
        "schema": "simplicio.update-manifest/v1",
        "version": "3.8.47",
        "release_tag": "v3.8.47",
        "commit": "old",
        "source": {"version": "Cargo.toml", "tag": "v3.8.47", "commit": "old"},
        "security": {"signature_required": True},
        "artifacts": [
            {
                "target": "linux-x64",
                "artifact": "simplicio-linux-x64",
                "url": "https://github.com/wesleysimplicio/simplicio/releases/download/v3.8.47/simplicio-linux-x64",
                "sha256": "a" * 64,
                "signature": "ed25519:keep-me",
            }
        ],
    }
    rewritten = module.rewrite_manifest(
        original,
        version="3.8.49",
        runtime_from="v3.8.47",
        source_commit="abc123",
        generated_at="2026-09-09T00:00:00.000000Z",
    )
    assert rewritten["version"] == "3.8.49"
    assert rewritten["release_tag"] == "v3.8.49"
    assert rewritten["commit"] == "abc123"
    assert rewritten["runtime_binary"]["version"] == "3.8.47"
    assert rewritten["runtime_binary"]["bytes"] == "unchanged-signed"
    artifact = rewritten["artifacts"][0]
    assert artifact["sha256"] == "a" * 64
    assert artifact["signature"] == "ed25519:keep-me"
    assert artifact["url"].endswith("/v3.8.49/simplicio-linux-x64")
    assert original["artifacts"][0]["url"].endswith("/v3.8.47/simplicio-linux-x64")

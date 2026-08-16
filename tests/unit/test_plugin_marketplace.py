"""Contract tests for the public Simplicio marketplace bundle."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_marketplace_lists_existing_plugins() -> None:
    marketplace = _load_json(".claude-plugin/marketplace.json")
    assert marketplace["name"] == "simplicio"

    for entry in marketplace["plugins"]:
        source = ROOT / entry["source"]
        assert (source / ".claude-plugin/plugin.json").is_file()
        assert (source / "LICENSE").is_file()


def test_plugin_manifests_have_skill_sources() -> None:
    marketplace = _load_json(".claude-plugin/marketplace.json")

    for entry in marketplace["plugins"]:
        source = ROOT / entry["source"]
        manifest = _load_json(str(Path(entry["source"]) / ".claude-plugin/plugin.json"))
        skills = manifest["skills"]
        skill_paths = [skills] if isinstance(skills, str) else skills
        assert skill_paths
        for skill_path in skill_paths:
            skill_dir = source / skill_path.removeprefix("./")
            assert any(skill_dir.rglob("SKILL.md"))


def test_published_adapters_point_to_their_canonical_commands() -> None:
    prompt = _load_json("plugins/simplicio-prompt/.claude-plugin/plugin.json")
    assert prompt["name"] == "simplicio-prompt"
    assert (ROOT / "plugins/simplicio-prompt/commands/simplicio.md").is_file()
    assert (ROOT / "plugins/simplicio-prompt/hooks/plugin-runtime-adapter/adapter.mjs").is_file()

    sprint = _load_json("plugins/simplicio-sprint/.claude-plugin/plugin.json")
    assert sprint["name"] == "simplicio-sprint"
    skill = ROOT / "plugins/simplicio-sprint/skills/sendsprint/SKILL.md"
    assert "sendsprint run" in skill.read_text(encoding="utf-8")

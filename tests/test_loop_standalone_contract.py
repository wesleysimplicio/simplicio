from pathlib import Path


SKILL = Path(__file__).parents[1] / "plugin/skills/simplicio-loop/SKILL.md"


def test_loop_contract_allows_standalone_mode_without_runtime():
    text = SKILL.read_text(encoding="utf-8")
    assert "Runtime first when available" in text
    assert "continue through the standalone Loop operators" in text
    assert "runtime-integration=degraded" in text
    assert "never claim Runtime activation, Runtime authority" in text

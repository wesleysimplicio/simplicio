from pathlib import Path


SKILL = Path(__file__).parents[1] / "plugin/skills/simplicio-loop/SKILL.md"


def test_loop_contract_allows_standalone_mode_without_runtime():
    text = SKILL.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "Runtime first when available" in normalized
    assert "continue through the standalone Loop operators" in normalized
    assert "runtime-integration=degraded" in normalized
    assert "never claim Runtime activation, Runtime authority" in normalized

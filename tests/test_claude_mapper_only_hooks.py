from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[1]
HOOK = ROOT / "plugins" / "simplicio" / "hooks" / "mapper_context.py"


def _fake_mapper(path: Path, log: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json, os, pathlib, sys
log = pathlib.Path(os.environ["FAKE_MAPPER_LOG"])
log.open("a", encoding="utf-8").write(json.dumps({"argv": sys.argv[1:], "mode": os.environ.get("SIMPLICIO_RUNTIME_MODE")}) + "\\n")
if os.environ.get("FAKE_MAPPER_FAIL") == "1":
    raise SystemExit(23)
if sys.argv[1:] != ["map", "--repo", sys.argv[3], "--for-llm", "markdown"]:
    raise SystemExit(24)
print("# Mapper project map\\n\\ncomplete_map_tail")
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_hook(
    event: str,
    repo: Path,
    runtime: Path,
    *,
    session: str = "session",
    python_mapper: Path | None = None,
    path: str | None = None,
    extra_env: dict[str, str] | None = None,
    payload_extra: dict[str, object] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = {"hookEventName": event, "cwd": str(repo), "session_id": session}
    if payload_extra:
        payload.update(payload_extra)
    env = {
        **os.environ,
        "SIMPLICIO_BIN": str(runtime),
        "FAKE_MAPPER_LOG": str(runtime.with_name("mapper.log")),
    }
    if python_mapper is not None:
        env["SIMPLICIO_MAPPER_BIN"] = str(python_mapper)
    if path is not None:
        env["PATH"] = path
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=10,
    )


def _fake_python_mapper(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import os, pathlib, sys
log = pathlib.Path(os.environ["FAKE_PYTHON_MAPPER_LOG"])
log.open("a", encoding="utf-8").write(repr(sys.argv[1:]) + "\\n")
if sys.argv[1:] != ["map", "--root", os.environ["FAKE_PYTHON_ROOT"], "--out", ".simplicio", "--docs"]:
    raise SystemExit(31)
docs = pathlib.Path.cwd() / ".simplicio" / "docs"
docs.mkdir(parents=True, exist_ok=True)
(docs / "architecture.md").write_text("# Python fallback map\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Mapper Test"], check=True)
    (path / "src.py").write_text("print('one')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "src.py"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)


def test_claude_manifest_wires_only_the_mapper_hook() -> None:
    manifest = json.loads((ROOT / "plugins/simplicio/.claude-plugin/plugin.json").read_text())
    hooks = json.loads((ROOT / "plugins/simplicio/hooks/hooks.claude.json").read_text())
    assert manifest["hooks"] == "./hooks/hooks.claude.json"
    assert set(hooks["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStart"}
    hook_text = (ROOT / "plugins/simplicio/hooks/hooks.claude.json").read_text().lower()
    adapter_text = HOOK.read_text().lower()
    assert "simplicio-fast" not in hook_text + adapter_text
    assert "simplicio_context" not in hook_text + adapter_text
    loop_hooks = "\n".join(path.read_text().lower() for path in (ROOT / "plugin/hooks").glob("*") if path.is_file())
    assert "simplicio-fast" not in loop_hooks
    assert 'export simplicio_runtime_mode="mapper-only"' in (ROOT / "plugin/hooks/mcp-route.sh").read_text().lower()


def test_mapper_cache_is_reused_and_refreshed_after_project_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo)
    runtime = tmp_path / "simplicio"
    _fake_mapper(runtime, runtime.with_name("mapper.log"))

    first = _run_hook("SessionStart", repo, runtime)
    assert first.returncode == 0, first.stderr
    assert "complete_map_tail" in first.stdout
    cache = repo / ".simplicio/hook-context"
    receipt = json.loads((cache / "warm-receipt.json").read_text())
    assert receipt["mode"] == "mapper-only"
    first_payload = json.loads(first.stdout)
    assert (cache / "map.md").read_text() in first_payload["hookSpecificOutput"]["additionalContext"]

    second = _run_hook("UserPromptSubmit", repo, runtime)
    third = _run_hook("PreToolUse", repo, runtime)
    assert second.returncode == third.returncode == 0
    assert "additionalContext" not in json.loads(second.stdout)["hookSpecificOutput"]
    fresh_session = _run_hook("UserPromptSubmit", repo, runtime, session="new-session")
    assert "complete_map_tail" in fresh_session.stdout
    calls = [json.loads(line) for line in runtime.with_name("mapper.log").read_text().splitlines()]
    assert len(calls) == 1
    assert calls[0]["mode"] == "mapper-only"
    assert calls[0]["argv"] == ["map", "--repo", str(repo), "--for-llm", "markdown"]

    (repo / "src.py").write_text("print('two')\n", encoding="utf-8")
    refreshed = _run_hook("PostToolUse", repo, runtime)
    assert refreshed.returncode == 0, refreshed.stderr
    calls = [json.loads(line) for line in runtime.with_name("mapper.log").read_text().splitlines()]
    assert len(calls) == 2
    new_receipt = json.loads((cache / "warm-receipt.json").read_text())
    assert new_receipt["generation"] != receipt["generation"]


def test_mapper_failure_is_not_a_silent_native_bypass(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime = tmp_path / "simplicio"
    _fake_mapper(runtime, runtime.with_name("mapper.log"))
    result = _run_hook("PreToolUse", repo, runtime)
    # The fixture fails only when explicitly requested, so this first call proves setup.
    assert result.returncode == 0

    env = os.environ.copy()
    other = tmp_path / "other"
    other.mkdir()
    env.update({
        "SIMPLICIO_BIN": str(runtime),
        "FAKE_MAPPER_LOG": str(runtime.with_name("mapper.log")),
        "FAKE_MAPPER_FAIL": "1",
        "SIMPLICIO_MAPPER_BIN": str(runtime),
        "PATH": str(tmp_path / "empty-path"),
    })
    failed = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"hookEventName": "PreToolUse", "cwd": str(other)}),
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=10,
    )
    assert failed.returncode == 2
    payload = json.loads(failed.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Mapper obrigatório" in payload["hookSpecificOutput"]["permissionDecisionReason"]


def test_explicit_recovery_commands_get_static_guidance_without_bypass(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime = tmp_path / "simplicio"
    _fake_mapper(runtime, runtime.with_name("mapper.log"))
    result = _run_hook(
        "UserPromptSubmit",
        repo,
        runtime,
        payload_extra={"command": "repair"},
        extra_env={"FAKE_MAPPER_FAIL": "1", "PATH": str(tmp_path / "empty-path")},
    )
    assert result.returncode == 0
    hook_output = json.loads(result.stdout)["hookSpecificOutput"]
    assert "repair" in hook_output["additionalContext"]
    assert "permissionDecision" not in hook_output


def test_python_mapper_is_a_mapper_only_runtime_failover(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo)
    runtime = tmp_path / "simplicio"
    _fake_mapper(runtime, runtime.with_name("mapper.log"))
    python_mapper = tmp_path / "simplicio-mapper"
    _fake_python_mapper(python_mapper)

    fallback_env = {
        "FAKE_MAPPER_FAIL": "1",
        "FAKE_PYTHON_MAPPER_LOG": str(tmp_path / "python-mapper.log"),
        "FAKE_PYTHON_ROOT": str(repo),
    }
    result = _run_hook(
        "SessionStart", repo, runtime, python_mapper=python_mapper, extra_env=fallback_env
    )
    assert result.returncode == 0, result.stderr
    assert "Python fallback map" in result.stdout
    receipt = json.loads((repo / ".simplicio/hook-context/warm-receipt.json").read_text())
    assert receipt["mode"] == "mapper-only"
    assert receipt["mapper_backend"] == "python"
    assert len((tmp_path / "python-mapper.log").read_text().splitlines()) == 1

    reused = _run_hook(
        "PreToolUse", repo, runtime, python_mapper=python_mapper, extra_env=fallback_env
    )
    assert reused.returncode == 0
    assert len((tmp_path / "python-mapper.log").read_text().splitlines()) == 1


def test_hermes_manifest_and_adapter_remain_mapper_only() -> None:
    manifest = json.loads((ROOT / "plugins/simplicio-hermes/manifest.json").read_text())
    source = (ROOT / "plugins/simplicio-hermes/hermes_plugin.py").read_text().lower()
    assert manifest["modes"] == ["mapper-only"]
    assert manifest["runtime"]["mode"] == "mapper-only"
    assert "simplicio-fast" not in source
    assert "simplicio_exec" not in source

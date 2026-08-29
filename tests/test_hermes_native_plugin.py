from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "plugins" / "simplicio-hermes" / "hermes_plugin.py"


def load_adapter() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_simplicio_hermes_adapter", ADAPTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self) -> None:
        self.hooks = {}

    def register_hook(self, name, callback) -> None:
        self.hooks[name] = callback


class FakeBridge:
    def __init__(self) -> None:
        self.calls = []

    def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        if tool == "simplicio_prepare_model_call":
            return {"context_packet": {"summary": "bounded context", "digest": "abc123"}}
        return {"status": "recorded"}


def test_hermes_manifest_and_package_entrypoint_are_installable() -> None:
    package_manifest = (
        ROOT / "plugins" / "simplicio-hermes" / "plugin.yaml"
    ).read_text(encoding="utf-8")

    assert "name: simplicio-hermes" in package_manifest
    assert "  - pre_llm_call" in package_manifest
    assert "  - post_llm_call" in package_manifest
    assert (ROOT / "plugins" / "simplicio-hermes" / "__init__.py").is_file()


def test_hermes_pre_llm_hook_prepares_context_and_post_hook_records_receipt() -> None:
    adapter = load_adapter()
    bridge = FakeBridge()
    adapter._BRIDGE = bridge
    adapter._PREPARED.clear()
    context = FakeContext()
    adapter.register(context)

    assert set(context.hooks) == {
        "on_session_start",
        "pre_llm_call",
        "post_llm_call",
        "on_session_end",
    }

    result = context.hooks["pre_llm_call"](
        session_id="session-1",
        user_message="Map this repository",
        model="hermes-model",
        platform="openrouter",
        cwd=str(ROOT),
    )
    assert result is not None
    assert "bounded context" in result["context"]
    prepare_tool, prepare_args = bridge.calls[0]
    assert prepare_tool == "simplicio_prepare_model_call"
    assert prepare_args["host"] == "hermes"
    assert prepare_args["host_session_id"] == "session-1"
    assert prepare_args["task"] == "Map this repository"

    context.hooks["post_llm_call"](
        session_id="session-1",
        model="hermes-model",
        platform="openrouter",
        provider_request_id="provider-1",
    )
    record_tool, record_args = bridge.calls[1]
    assert record_tool == "simplicio_record_model_result"
    assert record_args["prepared_receipt"]["context_packet"]["digest"] == "abc123"
    assert record_args["provider_request_id"] == "provider-1"

    json.dumps(record_args)

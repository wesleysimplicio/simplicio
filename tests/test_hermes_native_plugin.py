from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import threading
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "plugins" / "simplicio-hermes" / "hermes_plugin.py"


def load_adapter() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_simplicio_hermes_adapter", ADAPTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mapper_receipt(arguments=None, content=None):
    arguments = arguments or {}
    content = content or json.dumps({
        "schema": "simplicio.mapper-prefix/v1",
        "project_map": {"files": ["module_á.py"] * 4000},
        "symbol_index": {"symbols": ["complete_map_tail"]},
    }, ensure_ascii=False, separators=(",", ":"))
    return {
        "status": "prepared", "protected": True,
        "api_request_id": arguments.get("api_request_id", "request"),
        "host_session_id": arguments.get("host_session_id", "session"),
        "provider_cache_status": "unknown",
        "context_packet": {
            "schema": "simplicio.context-packet/v1",
            "producer": "simplicio-native-mapper",
            "complete_map_artifacts": True,
            "content": content,
            "bytes": len(content.encode("utf-8")),
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        },
    }


class FakeContext:
    def __init__(self):
        self.hooks = {}
        self.middleware = {}

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_middleware(self, name, callback):
        self.middleware[name] = callback


class FakeBridge:
    def __init__(self):
        self.calls = []
        self.failure = None

    def call(self, tool, arguments):
        self.calls.append((tool, arguments))
        if self.failure:
            raise self.failure
        if tool == "simplicio_prepare_model_call":
            return mapper_receipt(arguments)
        return {"status": "recorded"}


def setup_plugin():
    adapter = load_adapter()
    bridge = FakeBridge()
    adapter._BRIDGE = bridge
    context = FakeContext()
    adapter.register(context)
    return adapter, bridge, context


def test_native_plugin_only_registers_mapper_context_and_telemetry():
    _, _, context = setup_plugin()
    assert set(context.middleware) == {"llm_request"}
    assert set(context.hooks) == {
        "on_session_start", "pre_llm_call", "post_llm_call", "on_session_end",
        "post_api_request", "api_request_error",
    }
    manifest = (ADAPTER.parent / "plugin.yaml").read_text()
    assert "name: simplicio-hermes" in manifest
    assert "post_api_request" in manifest


def test_full_mapper_prefix_is_stable_and_provider_options_are_preserved():
    _, bridge, context = setup_plugin()
    request = {
        "model": "model", "messages": [{"role": "system", "content": "native policy"},
                                     {"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "name": "native_edit"}],
        "stream": True, "temperature": 0.4,
        "cache_control": {"type": "ephemeral"},
    }
    original = json.loads(json.dumps(request))
    results = []
    for number in (1, 2):
        result = context.middleware["llm_request"](
            request=request, session_id=f"session-{number}", turn_id=f"turn-{number}",
            api_request_id=f"api-{number}", model="model", provider="provider",
            cwd=str(ROOT),
        )
        results.append(result["request"])
    assert results[0] == results[1]
    assert request == original
    assert len(results[0]["messages"][0]["content"].encode()) > 16384
    assert "complete_map_tail" in results[0]["messages"][0]["content"]
    assert results[0]["messages"][1:] == request["messages"]
    for field in ("model", "tools", "stream", "temperature", "cache_control"):
        assert results[0][field] == request[field]
    assert [call[0] for call in bridge.calls] == ["simplicio_prepare_model_call"] * 2


@pytest.mark.parametrize("field,value", [
    ("system", "native policy"),
    ("system", [{"type": "text", "text": "native policy", "cache_control": {"type": "ephemeral"}}]),
    ("instructions", "native policy"),
    ("input", [{"role": "user", "content": "hello"}]),
    ("input", "hello"),
])
def test_all_provider_request_shapes_receive_the_complete_map(field, value):
    _, _, context = setup_plugin()
    request = {field: value, "model": "model"}
    output = context.middleware["llm_request"](
        request=request, session_id="s", turn_id="t", api_request_id="r",
        provider="p", model="model", cwd=str(ROOT),
    )["request"]
    assert "complete_map_tail" in json.dumps(output[field])
    assert request[field] == value
    if field == "system" and isinstance(value, list):
        assert output[field][0] == value[0]


@pytest.mark.parametrize("receipt", [
    {"status": "login_required", "login_required": True},
    {"status": "degraded", "protected": False},
    {"status": "prepared", "context_packet": {"content": "old full-mode handle"}},
    mapper_receipt(content="tampered"),
])
def test_auth_errors_legacy_runtime_and_invalid_map_never_reach_provider(receipt):
    adapter, bridge, context = setup_plugin()
    if receipt.get("context_packet", {}).get("content") == "tampered":
        receipt["context_packet"]["content_sha256"] = "0" * 64
    bridge.call = lambda *_: receipt
    request = {"messages": [{"role": "user", "content": "native work"}]}
    with pytest.raises(adapter.SimplicioHermesError, match="mandatory"):
        context.middleware["llm_request"](
            request=request, session_id="s", model="model", provider="p", cwd=str(ROOT),
        )
    assert request["messages"][0]["content"] == "native work"
    assert not adapter._PREPARED


def test_runtime_outage_does_not_block_requests_or_leak_raw_errors(caplog):
    adapter, bridge, context = setup_plugin()
    bridge.failure = RuntimeError("secret-refresh-token")
    with pytest.raises(adapter.SimplicioHermesError, match="mandatory"):
        context.middleware["llm_request"](
            request={"messages": []}, session_id="s", model="model", cwd=str(ROOT),
        )
    assert "secret-refresh-token" not in caplog.text


def test_post_api_records_real_cache_usage_and_correlates_concurrent_requests():
    adapter, bridge, context = setup_plugin()
    for request in ("a", "b"):
        context.middleware["llm_request"](
            request={"messages": []}, session_id="s", turn_id="t", api_request_id=request,
            model="model", provider="p", cwd=str(ROOT),
        )
    context.hooks["post_api_request"](
        session_id="s", turn_id="t", api_request_id="a", model="model", provider="p",
        response={"body": {"id": "provider-a"}},
        usage={"input_tokens": 100, "output_tokens": 5, "cache_read_tokens": 80},
    )
    tool, args = bridge.calls[-1]
    assert tool == "simplicio_record_model_result"
    assert args["api_request_id"] == "a"
    assert args["provider_request_id"] == "provider-a"
    assert args["cache_read_input_tokens"] == 80
    assert args["input_tokens"] == 100 and args["output_tokens"] == 5
    assert "complete_map_tail" not in json.dumps(args)
    assert len(adapter._PREPARED) == 1
    context.hooks["post_api_request"](
        session_id="s", turn_id="t", api_request_id="b", model="model", provider="p",
    )
    assert "cache_read_input_tokens" not in bridge.calls[-1][1]
    assert "provider_request_id" not in bridge.calls[-1][1]
    assert not adapter._PREPARED


def test_pre_hook_maps_but_middleware_avoids_duplicate_spilled_context():
    _, bridge, context = setup_plugin()
    assert context.hooks["pre_llm_call"](
        session_id="s", turn_id="t", model="model", cwd=str(ROOT),
    ) is None
    assert bridge.calls[0][0] == "simplicio_prepare_model_call"


def test_session_start_warms_authenticated_mapper_without_waiting():
    _, bridge, context = setup_plugin()
    entered, release = threading.Event(), threading.Event()

    def slow_call(*args):
        entered.set()
        assert release.wait(2)
        return mapper_receipt()
    bridge.call = slow_call
    context.hooks["on_session_start"](session_id="s", cwd=str(ROOT))
    try:
        assert entered.wait(1)
    finally:
        release.set()


def test_legacy_host_still_gets_complete_context_without_requiring_middleware():
    adapter = load_adapter()
    adapter._BRIDGE = FakeBridge()
    hooks = {}
    class LegacyContext:
        def register_hook(self, name, callback):
            hooks[name] = callback
    adapter.register(LegacyContext())
    result = hooks["pre_llm_call"](session_id="s", model="model", cwd=str(ROOT))
    assert "complete_map_tail" in result["context"]
    assert len(result["context"].encode()) > 16384
    hooks["post_llm_call"](session_id="s")
    assert adapter._BRIDGE.calls[-1][0] == "simplicio_record_model_result"


def test_mcp_error_receipts_are_not_successful_context():
    adapter = load_adapter()
    with pytest.raises(adapter.SimplicioHermesError):
        adapter.RuntimeMcpBridge._content_payload({
            "isError": True, "content": [{"type": "text", "text": json.dumps(mapper_receipt())}],
        })


def test_mapper_process_is_scoped_and_checks_server_mode(monkeypatch):
    adapter = load_adapter()
    monkeypatch.setenv("SIMPLICIO_RUNTIME_MODE", "full")
    spawned = {}
    class Process:
        stdin = io.StringIO()
        def poll(self):
            return None
    def spawn(*args, **kwargs):
        spawned.update(kwargs)
        return Process()
    monkeypatch.setattr(adapter.subprocess, "Popen", spawn)
    bridge = adapter.RuntimeMcpBridge(binary=Path("/verified/simplicio"))
    requests = []
    def response(method, params):
        requests.append(method)
        if method == "initialize":
            return {"serverInfo": {"name": "simplicio"},
                    "x-simplicio": {"session_identity": {"mode": "mapper-only"}}}
        return {"tools": [{"name": name} for name in adapter._MAPPER_TOOLS]}
    monkeypatch.setattr(bridge, "_request", response)
    bridge._ensure_started()
    assert spawned["env"]["SIMPLICIO_RUNTIME_MODE"] == "mapper-only"
    assert adapter.os.environ["SIMPLICIO_RUNTIME_MODE"] == "full"
    assert requests == ["initialize", "tools/list"]


@pytest.mark.parametrize("mode,extra", [("full", None), ("mapper-only", "simplicio_exec")])
def test_incompatible_mcp_server_is_closed_before_any_tool_call(monkeypatch, mode, extra):
    adapter = load_adapter()
    class Process:
        stdin = io.StringIO()
        def poll(self):
            return None
    monkeypatch.setattr(adapter.subprocess, "Popen", lambda *a, **k: Process())
    bridge = adapter.RuntimeMcpBridge(binary=Path("/verified/simplicio"))
    closed = []
    monkeypatch.setattr(bridge, "close", lambda: closed.append(True))
    def response(method, params):
        if method == "initialize":
            return {"serverInfo": {"name": "simplicio"},
                    "x-simplicio": {"session_identity": {"mode": mode}}}
        names = list(adapter._MAPPER_TOOLS) + ([extra] if extra else [])
        return {"tools": [{"name": name} for name in names]}
    monkeypatch.setattr(bridge, "_request", response)
    with pytest.raises(adapter.SimplicioHermesError):
        bridge._ensure_started()
    assert closed


def test_disabled_modules_cannot_be_called_even_through_public_bridge(monkeypatch):
    adapter = load_adapter()
    bridge = adapter.RuntimeMcpBridge()
    started = []
    monkeypatch.setattr(bridge, "_ensure_started", lambda: started.append(True))
    with pytest.raises(adapter.SimplicioHermesError):
        bridge.call("simplicio_exec", {"command": "edit something"})
    assert not started


def test_canonical_hermes_usage_keeps_total_prompt_and_cache_buckets():
    adapter = load_adapter()
    assert adapter._token_usage({"usage": {
        "input_tokens": 20, "prompt_tokens": 100, "output_tokens": 4,
        "cache_read_tokens": 80,
    }}) == {"input_tokens": 100, "output_tokens": 4, "cache_read_input_tokens": 80}
    assert adapter._token_usage({"usage": {"input_tokens_details": {"cached_tokens": 0}}}) == {
        "cache_read_input_tokens": 0,
    }
    assert adapter._token_usage({"usage": {"cache_read_tokens": True}}) == {}


def test_stdio_transport_enforces_mode_and_rejects_login_errors(tmp_path, monkeypatch):
    import os
    import sys
    adapter = load_adapter()
    marker = tmp_path / "authenticated"
    program = tmp_path / "fake-runtime"
    receipt = mapper_receipt()
    script = (
        "#!" + sys.executable + "\n"
        "import json, os, pathlib, sys\n"
        "assert os.environ['SIMPLICIO_RUNTIME_MODE'] == 'mapper-only'\n"
        "tools = " + repr(sorted(adapter._MAPPER_TOOLS)) + "\n"
        "receipt = " + repr(receipt) + "\n"
        "marker = pathlib.Path(" + repr(str(marker)) + ")\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    if 'id' not in request: continue\n"
        "    method = request['method']\n"
        "    if method == 'initialize':\n"
        "        result = {'serverInfo': {'name': 'simplicio'}, 'x-simplicio': {'session_identity': {'mode': 'mapper-only'}}}\n"
        "    elif method == 'tools/list': result = {'tools': [{'name': name} for name in tools]}\n"
        "    else:\n"
        "        payload = receipt if marker.exists() else {'status': 'login_required'}\n"
        "        result = {'isError': not marker.exists(), 'content': [{'type': 'text', 'text': json.dumps(payload)}]}\n"
        "    print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}), flush=True)\n"
    )
    program.write_text(script, encoding="utf-8")
    program.chmod(0o755)
    if os.name == "nt":
        pytest.skip("POSIX test fixture executable")
    monkeypatch.setenv("SIMPLICIO_RUNTIME_MODE", "full")
    bridge = adapter.RuntimeMcpBridge(binary=program, timeout=2)
    try:
        with pytest.raises(adapter.SimplicioHermesError):
            bridge.call("simplicio_prepare_model_call", {"repo": str(tmp_path)})
        marker.touch()
        response = bridge.call("simplicio_prepare_model_call", {"repo": str(tmp_path)})
        assert "complete_map_tail" in adapter._mapper_context(response)
        assert os.environ["SIMPLICIO_RUNTIME_MODE"] == "full"
    finally:
        bridge.close()


def test_against_actual_hermes_request_middleware_when_source_is_available(monkeypatch):
    import os
    import sys
    source = os.getenv("HERMES_SOURCE")
    if not source:
        pytest.skip("set HERMES_SOURCE for installed-host contract verification")
    module_path = Path(source) / "hermes_cli" / "middleware.py"
    spec = importlib.util.spec_from_file_location("verified_hermes_middleware", module_path)
    assert spec and spec.loader
    host = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, host)
    spec.loader.exec_module(host)
    _, _, context = setup_plugin()
    monkeypatch.setattr(host, "_has_middleware", lambda kind: kind in context.middleware)
    monkeypatch.setattr(host, "_invoke_middleware",
                        lambda kind, **kwargs: [context.middleware[kind](**kwargs)])
    request = {"model": "model", "messages": [{"role": "user", "content": "hello"}],
               "tools": [{"name": "native_edit"}], "stream": True}
    result = host.apply_llm_request_middleware(
        request, session_id="s", turn_id="t", api_request_id="a", model="model",
        provider="p", cwd=str(ROOT),
    )
    assert result.changed is True
    assert result.original_payload == request
    assert "complete_map_tail" in result.payload["messages"][0]["content"]
    assert len(result.payload["messages"][0]["content"].encode()) > 32768
    assert result.payload["tools"] == request["tools"]
    assert result.payload["stream"] is True

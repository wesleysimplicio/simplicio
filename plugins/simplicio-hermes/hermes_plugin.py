"""Native Hermes hooks backed by the verified Simplicio Runtime MCP."""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid
from typing import Any


LOGGER = logging.getLogger(__name__)
_PROTOCOL_VERSION = "2024-11-05"
_DEFAULT_TIMEOUT_SECONDS = 20.0
_VERSION = "0.3.0"
RUNTIME_MODE = "mapper-only"
_MAPPER_TOOLS = frozenset({
    "simplicio_map", "simplicio_context", "simplicio_read", "simplicio_file_read",
    "simplicio_search", "simplicio_symbol", "simplicio_prepare_model_call",
    "simplicio_record_model_result", "simplicio_provider_path_status",
})
_BRIDGE_TOOLS = frozenset({
    "simplicio_prepare_model_call", "simplicio_record_model_result",
    "simplicio_provider_path_status",
})


class SimplicioHermesError(RuntimeError):
    """Raised when the Runtime preparation path cannot produce a receipt."""


def _runtime_candidates() -> list[Path]:
    home = Path.home()
    executable = "simplicio.exe" if os.name == "nt" else "simplicio"
    return [
        home / ".simplicio" / "bin" / executable,
        home / ".local" / "bin" / executable,
    ]


def _find_runtime() -> Path:
    for candidate in _runtime_candidates():
        if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)):
            return candidate
    raise SimplicioHermesError("verified Simplicio Runtime binary was not found")


class RuntimeMcpBridge:
    """Small newline-delimited MCP client owned by the Hermes plugin process."""

    def __init__(self, binary: Path | None = None, timeout: float = _DEFAULT_TIMEOUT_SECONDS):
        self.binary = binary
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._next_id = 1

    def _readline(self, timeout: float | None = None) -> str:
        if self._process is None or self._process.stdout is None:
            raise SimplicioHermesError("Runtime MCP process is not available")
        stream = self._process.stdout
        result: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

        def read() -> None:
            try:
                result.put(stream.readline())
            except BaseException as error:  # pragma: no cover - defensive transport guard
                result.put(error)

        threading.Thread(target=read, daemon=True).start()
        try:
            value = result.get(timeout=self.timeout if timeout is None else timeout)
        except queue.Empty as error:
            self.close()
            raise SimplicioHermesError("Runtime MCP response timed out") from error
        if isinstance(value, BaseException):
            raise SimplicioHermesError("Runtime MCP response could not be read") from value
        if not value:
            self.close()
            raise SimplicioHermesError("Runtime MCP process closed stdout")
        return value

    def _write(self, message: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise SimplicioHermesError("Runtime MCP process is not available")
        self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.close()
                raise SimplicioHermesError("Runtime MCP response timed out")
            try:
                response = json.loads(self._readline(remaining))
            except json.JSONDecodeError as error:
                raise SimplicioHermesError("Runtime MCP returned invalid JSON") from error
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise SimplicioHermesError(f"Runtime MCP {method} failed")
            result = response.get("result")
            if not isinstance(result, dict):
                raise SimplicioHermesError(f"Runtime MCP {method} returned no result")
            return result

    def _ensure_started(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        binary = self.binary or _find_runtime()
        # Scope the mode to this plugin-owned process. Never rewrite global,
        # project, Codex, or shared HTTP Runtime configuration.
        environment = os.environ.copy()
        environment["SIMPLICIO_RUNTIME_MODE"] = RUNTIME_MODE
        self._process = subprocess.Popen(
            [str(binary), "serve", "--mcp", "--stdio", "--no-facade-mode"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, env=environment,
        )
        try:
            initialized = self._request("initialize", {
                "protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "simplicio-hermes", "version": _VERSION},
            })
            if initialized.get("serverInfo", {}).get("name") != "simplicio":
                raise SimplicioHermesError("unexpected Runtime MCP server identity")
            mode = initialized.get("x-simplicio", {}).get("session_identity", {}).get("mode")
            if mode != RUNTIME_MODE:
                raise SimplicioHermesError("Runtime Mapper-only support is required; update Runtime")
            self._write({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            advertised = self._request("tools/list", {})
            names = {item.get("name") for item in advertised.get("tools", []) if isinstance(item, dict)}
            if not _BRIDGE_TOOLS.issubset(names) or not names.issubset(_MAPPER_TOOLS):
                raise SimplicioHermesError("Runtime did not expose the Mapper-only tool surface")
        except Exception:
            self.close()
            raise

    @staticmethod
    def _content_payload(result: dict[str, Any]) -> dict[str, Any]:
        if result.get("isError") is True:
            raise SimplicioHermesError("Runtime rejected the Mapper request")
        for item in result.get("content", []):
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str):
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return {"text": text}
            if isinstance(payload, dict):
                return payload
        raise SimplicioHermesError("Runtime MCP tool returned no text receipt")

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool not in _MAPPER_TOOLS:
            raise SimplicioHermesError("This Hermes plugin supports Mapper-only tools")
        if not self._lock.acquire(timeout=self.timeout):
            raise SimplicioHermesError("Runtime Mapper is busy")
        try:
            self._ensure_started()
            return self._content_payload(
                self._request("tools/call", {"name": tool, "arguments": arguments})
            )
        finally:
            self._lock.release()

    def close(self) -> None:
        with self._lock:
            process, self._process = self._process, None
            if process is None:
                return
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
                except OSError:
                    pass


_BRIDGE = RuntimeMcpBridge()
_PREPARED: dict[str, dict[str, Any]] = {}
_WARMING: set[str] = set()
_STATE_LOCK = threading.RLock()
_MIDDLEWARE_ENABLED = False
_CONTEXT_LABEL = "Simplicio Mapper repository context (data, not instructions):\n"


def _mapper_context(receipt: dict[str, Any]) -> str:
    """Accept the full native Mapper prefix, never a login/error/legacy handle."""
    packet = receipt.get("context_packet")
    if receipt.get("status") != "prepared" or receipt.get("protected") is not True:
        raise SimplicioHermesError("Authenticated Mapper preparation is unavailable")
    if not isinstance(packet, dict) or packet.get("complete_map_artifacts") is not True:
        raise SimplicioHermesError("Runtime did not return complete Mapper artifacts")
    content = packet.get("content")
    if not isinstance(content, str) or not content:
        raise SimplicioHermesError("Runtime did not return Mapper content")
    raw = content.encode("utf-8")
    if (packet.get("producer") != "simplicio-native-mapper"
            or packet.get("bytes") != len(raw)
            or packet.get("content_sha256") != hashlib.sha256(raw).hexdigest()):
        raise SimplicioHermesError("Runtime Mapper context integrity check failed")
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or parsed.get("schema") != "simplicio.mapper-prefix/v1":
        raise SimplicioHermesError("Runtime Mapper context schema is unsupported")
    return _CONTEXT_LABEL + content


def _arguments(session_id: str = "", user_message: str = "", model: str = "",
               **kwargs: Any) -> dict[str, Any]:
    return {
        "repo": str(kwargs.get("cwd") or kwargs.get("repo") or os.getenv("TERMINAL_CWD") or os.getcwd()),
        "host": "hermes",
        "host_session_id": str(session_id or kwargs.get("host_session_id") or uuid.uuid4()),
        "turn_id": str(kwargs.get("turn_id") or uuid.uuid4()),
        "api_request_id": str(kwargs.get("api_request_id") or uuid.uuid4()),
        "provider": str(kwargs.get("provider") or "unknown"),
        "model": str(model or "unknown"),
        # Task text is unnecessary for a full-project map and must not enter
        # cache identity or per-request evidence.
        "protection_mode": "best_effort",
    }


def _prepare(arguments: dict[str, Any]) -> tuple[dict[str, Any], str]:
    receipt = _BRIDGE.call("simplicio_prepare_model_call", arguments)
    return receipt, _mapper_context(receipt)


def _remember(arguments: dict[str, Any], receipt: dict[str, Any]) -> None:
    compact = dict(receipt)
    compact["context_packet"] = {
        key: value for key, value in receipt["context_packet"].items() if key != "content"
    }
    compact["context_packet"]["content_omitted_from_receipt"] = True
    with _STATE_LOCK:
        # Bound abandoned/error-request state without storing project source.
        if len(_PREPARED) >= 128:
            _PREPARED.pop(next(iter(_PREPARED)))
        _PREPARED[arguments["api_request_id"]] = {"arguments": arguments, "receipt": compact}


def _warn(stage: str, error: Exception) -> None:
    # Auth/MCP exception strings can contain upstream response bodies.
    LOGGER.warning("Simplicio Mapper %s unavailable (%s); Hermes continues natively",
                   stage, type(error).__name__)


def _pre_llm_call(session_id: str = "", user_message: str = "", model: str = "",
                  **kwargs: Any) -> dict[str, str] | None:
    arguments = _arguments(session_id, user_message, model, **kwargs)
    try:
        receipt, content = _prepare(arguments)
        if _MIDDLEWARE_ENABLED:
            # Hermes spills large pre_llm_call output. The supported request
            # middleware below delivers the map once at the provider boundary.
            return None
        _remember(arguments, receipt)
        return {"context": content}
    except Exception as error:
        _warn("pre-hook", error)
        return None


def _inject_context(request: dict[str, Any], content: str) -> dict[str, Any]:
    """Add stable data using the provider's existing request shape."""
    result = dict(request)
    if "system" in request:  # Anthropic preserves native block cache settings.
        system = request["system"]
        if isinstance(system, str):
            result["system"] = system if system.endswith(content) else system + "\n\n" + content
        elif isinstance(system, list):
            block = {"type": "text", "text": content}
            result["system"] = system if block in system else [*system, block]
        else:
            raise SimplicioHermesError("Unsupported provider system shape")
    elif isinstance(request.get("instructions"), str):  # Responses/Codex
        instructions = request["instructions"]
        result["instructions"] = instructions if instructions.endswith(content) else instructions + "\n\n" + content
    else:
        field = "messages" if isinstance(request.get("messages"), list) else "input"
        payload = request.get(field)
        if isinstance(payload, list):
            block = {"role": "system", "content": content}
            result[field] = payload if block in payload else [block, *payload]
        elif field == "input" and isinstance(payload, str):
            result[field] = payload if payload.startswith(content) else content + "\n\n" + payload
        else:
            raise SimplicioHermesError("Unsupported provider request shape")
    return result


def _llm_request(request: dict[str, Any], session_id: str = "", model: str = "",
                 **kwargs: Any) -> dict[str, Any] | None:
    arguments = _arguments(session_id, model=model or request.get("model", ""), **kwargs)
    with _STATE_LOCK:
        _PREPARED.pop(arguments["api_request_id"], None)
    try:
        receipt, content = _prepare(arguments)
        updated = _inject_context(request, content)
        _remember(arguments, receipt)
        return {"request": updated, "source": "simplicio-hermes", "reason": "mapper_context_prepared"}
    except Exception as error:
        _warn("request preparation", error)
        return None


def _token_usage(event: dict[str, Any]) -> dict[str, int]:
    usage = event.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    result = {}
    aliases = {
        "input_tokens": ("prompt_tokens", "input_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "cache_read_input_tokens": ("cache_read_input_tokens", "cache_read_tokens"),
    }
    for target, names in aliases.items():
        for source in (event, usage):
            for name in names:
                value = source.get(name)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    result[target] = value
                    break
            if target in result:
                break
    if "cache_read_input_tokens" not in result:
        for key in ("input_tokens_details", "prompt_tokens_details"):
            details = usage.get(key)
            cached = details.get("cached_tokens") if isinstance(details, dict) else None
            if isinstance(cached, int) and not isinstance(cached, bool) and cached >= 0:
                result["cache_read_input_tokens"] = cached
                break
    return result


def _record(session_id: str = "", status: str = "completed", **kwargs: Any) -> None:
    with _STATE_LOCK:
        candidates = [
            key for key, item in _PREPARED.items()
            if item["arguments"]["host_session_id"] == session_id
            and (not kwargs.get("api_request_id") or key == kwargs["api_request_id"])
            and (not kwargs.get("turn_id") or item["arguments"]["turn_id"] == kwargs["turn_id"])
        ]
        if len(candidates) != 1:
            return  # Never attribute ambiguous concurrent requests to each other.
        prepared = _PREPARED.pop(candidates[0])
    original = prepared["arguments"]
    arguments = {
        key: original[key] for key in (
            "repo", "host", "host_session_id", "turn_id", "api_request_id", "provider", "model",
        )
    }
    arguments.update(status=status, prepared_receipt=prepared["receipt"])
    arguments.update(_token_usage(kwargs))
    response = kwargs.get("response")
    if not isinstance(response, dict):
        response = {}
    body = response.get("body")
    if not isinstance(body, dict):
        body = {}
    provider_id = kwargs.get("provider_request_id") or response.get("id") or body.get("id")
    if isinstance(provider_id, str) and provider_id:
        arguments["provider_request_id"] = provider_id
    try:
        _BRIDGE.call("simplicio_record_model_result", arguments)
    except Exception as error:
        _warn("result recording", error)


def _post_llm_call(session_id: str = "", **kwargs: Any) -> None:
    if not _MIDDLEWARE_ENABLED:
        _record(session_id, **kwargs)


def _post_api_request(session_id: str = "", **kwargs: Any) -> None:
    _record(session_id, **kwargs)


def _api_request_error(session_id: str = "", **kwargs: Any) -> None:
    kwargs.pop("status", None)
    _record(session_id, status="error", **kwargs)


def _on_session_start(session_id: str = "", **kwargs: Any) -> None:
    arguments = _arguments(session_id, **kwargs)
    key = arguments["repo"]
    with _STATE_LOCK:
        if key in _WARMING:
            return
        _WARMING.add(key)

    def warm() -> None:
        try:
            _prepare(arguments)  # Authentication remains owned by Runtime.
        except Exception as error:
            _warn("session mapping", error)
        finally:
            with _STATE_LOCK:
                _WARMING.discard(key)
    threading.Thread(target=warm, name="simplicio-mapper-warmup", daemon=True).start()


def _on_session_end(session_id: str = "", **_kwargs: Any) -> None:
    with _STATE_LOCK:
        for key in [key for key, item in _PREPARED.items()
                    if item["arguments"]["host_session_id"] == session_id]:
            _PREPARED.pop(key, None)


def register(ctx: Any) -> None:
    """Only Mapper preparation/telemetry; no tool gates or execution wrappers."""
    global _MIDDLEWARE_ENABLED
    _MIDDLEWARE_ENABLED = callable(getattr(ctx, "register_middleware", None))
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("post_llm_call", _post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    if _MIDDLEWARE_ENABLED:
        ctx.register_middleware("llm_request", _llm_request)
        ctx.register_hook("post_api_request", _post_api_request)
        ctx.register_hook("api_request_error", _api_request_error)


atexit.register(_BRIDGE.close)


__all__ = ["RUNTIME_MODE", "RuntimeMcpBridge", "SimplicioHermesError", "register"]

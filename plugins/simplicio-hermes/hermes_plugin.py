"""Native Hermes hooks backed by the verified Simplicio Runtime MCP."""

from __future__ import annotations

import atexit
import json
import logging
import os
from pathlib import Path
import queue
import subprocess
import threading
import uuid
from typing import Any


LOGGER = logging.getLogger(__name__)
_PROTOCOL_VERSION = "2024-11-05"
_DEFAULT_TIMEOUT_SECONDS = 20.0
_MAX_CONTEXT_BYTES = 16_384


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

    def _readline(self) -> str:
        if self._process is None or self._process.stdout is None:
            raise SimplicioHermesError("Runtime MCP process is not available")
        result: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

        def read() -> None:
            try:
                result.put(self._process.stdout.readline())
            except BaseException as error:  # pragma: no cover - defensive transport guard
                result.put(error)

        threading.Thread(target=read, daemon=True).start()
        try:
            value = result.get(timeout=self.timeout)
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
        while True:
            try:
                response = json.loads(self._readline())
            except json.JSONDecodeError as error:
                raise SimplicioHermesError("Runtime MCP returned invalid JSON") from error
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise SimplicioHermesError(f"Runtime MCP {method} failed: {response['error']}")
            result = response.get("result")
            if not isinstance(result, dict):
                raise SimplicioHermesError(f"Runtime MCP {method} returned no result")
            return result

    def _ensure_started(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        binary = self.binary or _find_runtime()
        self._process = subprocess.Popen(
            [str(binary), "serve", "--mcp", "--stdio", "--no-facade-mode"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        initialized = self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "simplicio-hermes", "version": "0.2.0"},
            },
        )
        server_info = initialized.get("serverInfo", {})
        if server_info.get("name") != "simplicio":
            self.close()
            raise SimplicioHermesError("unexpected Runtime MCP server identity")
        self._write({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    @staticmethod
    def _content_payload(result: dict[str, Any]) -> dict[str, Any]:
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
        with self._lock:
            self._ensure_started()
            return self._content_payload(
                self._request("tools/call", {"name": tool, "arguments": arguments})
            )

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
                process.terminate()


_BRIDGE = RuntimeMcpBridge()
_PREPARED: dict[str, dict[str, Any]] = {}
_STATE_LOCK = threading.RLock()


def _bounded_context(receipt: dict[str, Any]) -> str:
    packet = receipt.get("context_packet") or receipt.get("context") or receipt
    encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    raw = encoded.encode("utf-8")
    if len(raw) > _MAX_CONTEXT_BYTES:
        encoded = raw[:_MAX_CONTEXT_BYTES].decode("utf-8", errors="ignore")
    return "Simplicio Runtime context (verified pre_llm_call receipt):\n" + encoded


def _pre_llm_call(
    session_id: str = "",
    user_message: str = "",
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> dict[str, str] | None:
    host_session_id = session_id or str(uuid.uuid4())
    turn_id = str(kwargs.get("turn_id") or uuid.uuid4())
    api_request_id = str(kwargs.get("api_request_id") or uuid.uuid4())
    provider = str(kwargs.get("provider") or platform or "unknown")
    selected_model = str(model or kwargs.get("model") or "unknown")
    arguments = {
        "repo": str(kwargs.get("cwd") or os.getcwd()),
        "host": "hermes",
        "host_session_id": host_session_id,
        "turn_id": turn_id,
        "api_request_id": api_request_id,
        "provider": provider,
        "model": selected_model,
        "task": str(user_message),
        "protection_mode": "best_effort",
    }
    try:
        receipt = _BRIDGE.call("simplicio_prepare_model_call", arguments)
    except Exception as error:  # Hermes pre_llm_call is context-only and fail-open by contract.
        LOGGER.warning("Simplicio pre_llm_call preparation failed: %s", error)
        return None
    with _STATE_LOCK:
        _PREPARED[host_session_id] = {"arguments": arguments, "receipt": receipt}
    return {"context": _bounded_context(receipt)}


def _post_llm_call(
    session_id: str = "",
    model: str = "",
    platform: str = "",
    **kwargs: Any,
) -> None:
    with _STATE_LOCK:
        prepared = _PREPARED.get(session_id)
    if prepared is None:
        return
    original = prepared["arguments"]
    arguments = {
        "repo": original["repo"],
        "host": "hermes",
        "host_session_id": original["host_session_id"],
        "turn_id": original["turn_id"],
        "api_request_id": original["api_request_id"],
        "provider": str(kwargs.get("provider") or platform or original["provider"]),
        "model": str(model or kwargs.get("model") or original["model"]),
        "provider_request_id": str(kwargs.get("provider_request_id") or original["api_request_id"]),
        "status": "completed",
        "prepared_receipt": prepared["receipt"],
    }
    try:
        _BRIDGE.call("simplicio_record_model_result", arguments)
    except Exception as error:
        LOGGER.warning("Simplicio post_llm_call receipt failed: %s", error)


def _on_session_start(**_kwargs: Any) -> None:
    return None


def _on_session_end(session_id: str = "", **_kwargs: Any) -> None:
    with _STATE_LOCK:
        _PREPARED.pop(session_id, None)


def register(ctx: Any) -> None:
    """Register the native Hermes lifecycle hooks."""
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("post_llm_call", _post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)


atexit.register(_BRIDGE.close)


__all__ = ["RuntimeMcpBridge", "SimplicioHermesError", "register"]

"""Native Hermes hooks backed by the verified Simplicio Runtime MCP."""

from __future__ import annotations

import atexit
from collections import deque
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Any


LOGGER = logging.getLogger(__name__)
_PROTOCOL_VERSION = "2024-11-05"
_DEFAULT_TIMEOUT_SECONDS = 20.0
_VERSION = "0.4.0"
RUNTIME_MODE = "mapper-only"
_PYTHON_MAPPER_ENV = "SIMPLICIO_MAPPER_BIN"
_PYTHON_MAPPER_ROOT_ENV = "SIMPLICIO_MAPPER_ROOT"
_PYTHON_MAPPER_MANIFEST_ENV = "SIMPLICIO_MAPPER_MANIFEST"
_MAPPER_CACHE = Path(".simplicio") / "hook-context"
_MAPPER_SCHEMA = "simplicio.mapper-prefix/v1"
_MAPPER_PROTOCOL = "simplicio.mapper/v1"
_MAX_CORRELATION_RECEIPTS = 128
_MAX_TRACKED_RESULTS = 128
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


class MapperResolution:
    def __init__(self, command: tuple[str, ...], environment: dict[str, str], version: str,
                 protocol: str, schema: str, capabilities: tuple[str, ...], digest: str,
                 compatibility: dict[str, str], resolution_source: str):
        self.command = command
        self.environment = environment
        self.version = version
        self.protocol = protocol
        self.schema = schema
        self.capabilities = capabilities
        self.digest = digest
        self.compatibility = compatibility
        self.resolution_source = resolution_source


_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = _SEMVER.match(value)
    if not match:
        raise SimplicioHermesError("mapper_version_invalid")
    return tuple(int(part) for part in match.groups())


def _first_string(*values: Any) -> str | None:
    return next((value for value in values if isinstance(value, str) and value), None)


def _minimal_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Keep subprocesses away from tokens, cookies and unrelated host state."""
    allowed = {
        "HOME", "USERPROFILE", "PATH", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV",
        "SystemRoot", "WINDIR", "PATHEXT",
        "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL",
    }
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment["SIMPLICIO_RUNTIME_MODE"] = RUNTIME_MODE
    if extra:
        environment.update(extra)
    return environment


def _process_group_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


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


def _manifest_candidates(candidate: Path) -> list[Path]:
    if candidate.is_dir():
        return [
            candidate / "simplicio-mapper-manifest.json",
            candidate / "manifest.json",
            candidate / ".simplicio-mapper" / "manifest.json",
        ]
    return [candidate.with_name("simplicio-mapper-manifest.json"), candidate.with_suffix(".manifest.json")]


def _load_mapper_manifest(candidate: Path, *, required: bool) -> dict[str, Any]:
    configured = os.environ.get(_PYTHON_MAPPER_MANIFEST_ENV)
    paths = [Path(configured).expanduser()] if configured else _manifest_candidates(candidate)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    if required:
        raise SimplicioHermesError("mapper_manifest_missing")
    return {}


def _json_field(payload: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value
    return None


def _compatibility_range(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, str]:
    values: dict[str, Any] = {}
    for source in (manifest.get("compatibility"), payload.get("compatibility"), manifest, payload):
        if isinstance(source, dict):
            for key in ("min_version", "minimum", "max_version", "maximum"):
                if key not in values and isinstance(source.get(key), str):
                    values[key] = source[key]
    if "min_version" not in values or "max_version" not in values:
        raise SimplicioHermesError("mapper_compatibility_range_missing")
    minimum = _version_tuple(values["min_version"])
    maximum = _version_tuple(values["max_version"])
    if minimum > maximum:
        raise SimplicioHermesError("mapper_compatibility_range_invalid")
    return {"min_version": values["min_version"], "max_version": values["max_version"]}


def _mapper_digest(command: tuple[str, ...], manifest: dict[str, Any], payload: dict[str, Any]) -> str:
    digest = _first_string(
        _json_field(payload, "sha256", "digest", "binary_sha256"),
        _json_field(manifest, "sha256", "digest", "binary_sha256"),
    )
    executable = Path(command[0]) if command and command[0] != sys.executable else None
    actual = None
    if executable is not None and executable.is_file():
        hasher = hashlib.sha256()
        try:
            with executable.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            actual = hasher.hexdigest()
        except OSError as error:
            raise SimplicioHermesError("mapper_digest_unreadable") from error
    if not digest or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise SimplicioHermesError("mapper_digest_missing")
    digest = digest.lower()
    if actual and actual != digest:
        raise SimplicioHermesError("mapper_digest_mismatch")
    manifest_digest = _first_string(_json_field(manifest, "sha256", "digest", "binary_sha256"))
    if manifest_digest and manifest_digest.lower() != digest:
        raise SimplicioHermesError("mapper_manifest_digest_mismatch")
    return digest


def _resolve_python_mapper() -> MapperResolution:
    """Resolve and attest a Mapper before any map command is allowed."""
    configured_binary = os.environ.get(_PYTHON_MAPPER_ENV)
    configured_root = os.environ.get(_PYTHON_MAPPER_ROOT_ENV)
    source = ""
    candidate: Path
    extra: dict[str, str] = {}

    if configured_binary:
        candidate = Path(configured_binary).expanduser()
        if not candidate.is_file():
            resolved = shutil.which(configured_binary)
            if resolved:
                candidate = Path(resolved)
        if not candidate.is_file() or (os.name != "nt" and not os.access(candidate, os.X_OK)):
            raise SimplicioHermesError("configured_mapper_invalid")
        command = (str(candidate.resolve()),)
        source = "env:SIMPLICIO_MAPPER_BIN"
        manifest = _load_mapper_manifest(candidate, required=False)
    elif configured_root:
        candidate = Path(configured_root).expanduser().resolve()
        if not (candidate / "simplicio_mapper").is_dir():
            raise SimplicioHermesError("configured_mapper_root_invalid")
        command = (sys.executable, "-B", "-m", "simplicio_mapper.cli")
        source = "env:SIMPLICIO_MAPPER_ROOT"
        current = os.environ.get("PYTHONPATH", "")
        extra["PYTHONPATH"] = os.pathsep.join([str(candidate), current]) if current else str(candidate)
        manifest = _load_mapper_manifest(candidate, required=False)
    else:
        managed_root = next((path for path in (
            Path.home() / ".simplicio" / "mapper",
            Path.home() / ".simplicio" / "src" / "simplicio-mapper",
        ) if (path / "simplicio_mapper").is_dir()), None)
        if managed_root:
            candidate = managed_root
            command = (sys.executable, "-B", "-m", "simplicio_mapper.cli")
            source = "installer-managed-manifest"
            current = os.environ.get("PYTHONPATH", "")
            extra["PYTHONPATH"] = os.pathsep.join([str(candidate), current]) if current else str(candidate)
            manifest = _load_mapper_manifest(candidate, required=True)
        else:
            executable = shutil.which("simplicio-mapper")
            if executable:
                candidate = Path(executable).resolve()
                command = (str(candidate),)
                source = "installer-managed-path"
                manifest = _load_mapper_manifest(candidate, required=True)
            else:
                raise SimplicioHermesError("mapper_resolution_missing")

    environment = _minimal_environment(extra)
    try:
        result = subprocess.run(
            [*command, "version", "--json"], cwd=str(candidate if candidate.is_dir() else candidate.parent),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", timeout=_DEFAULT_TIMEOUT_SECONDS, check=False,
            env=environment, **_process_group_options(),
        )
    except subprocess.TimeoutExpired as error:
        raise SimplicioHermesError("mapper_version_timeout") from error
    if result.returncode != 0:
        raise SimplicioHermesError("mapper_version_failed")
    try:
        payload = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise SimplicioHermesError("mapper_version_not_json") from error
    if not isinstance(payload, dict):
        raise SimplicioHermesError("mapper_version_invalid")
    nested = payload.get("mapper")
    if isinstance(nested, dict):
        payload = {**payload, **nested}
    version = _first_string(_json_field(payload, "version", "mapper_version"))
    protocol = _first_string(_json_field(payload, "protocol", "protocol_version"))
    schema = _first_string(_json_field(payload, "schema", "schema_version", "schema_range"))
    producer = _first_string(_json_field(payload, "producer", "name"))
    if not version or not protocol or not schema or producer != "simplicio-mapper":
        raise SimplicioHermesError("mapper_version_contract_invalid")
    version_value = _version_tuple(version)
    compatibility = _compatibility_range(payload, manifest)
    if not (_version_tuple(compatibility["min_version"]) <= version_value <= _version_tuple(compatibility["max_version"])):
        raise SimplicioHermesError("mapper_version_out_of_range")
    if protocol != _MAPPER_PROTOCOL or schema != _MAPPER_SCHEMA:
        raise SimplicioHermesError("mapper_protocol_or_schema_incompatible")
    raw_capabilities = _json_field(payload, "capabilities")
    if isinstance(raw_capabilities, dict):
        capabilities = tuple(sorted(key for key, value in raw_capabilities.items() if value is True))
    elif isinstance(raw_capabilities, list):
        capabilities = tuple(sorted(value for value in raw_capabilities if isinstance(value, str)))
    else:
        raise SimplicioHermesError("mapper_capabilities_missing")
    if "map" not in capabilities:
        raise SimplicioHermesError("mapper_map_capability_missing")
    digest = _mapper_digest(command, manifest, payload)
    return MapperResolution(
        command=command, environment=environment, version=version, protocol=protocol,
        schema=schema, capabilities=capabilities, digest=digest,
        compatibility=compatibility, resolution_source=source,
    )


def _find_python_mapper() -> tuple[list[str], dict[str, str]]:
    resolution = _resolve_python_mapper()
    return list(resolution.command), dict(resolution.environment)


def _project_generation(root: Path) -> str:
    """Hash effective project bytes so equal git status cannot hide edits."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise SimplicioHermesError("project_root_invalid")
    digest = hashlib.sha256()
    try:
        for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            directory_path = Path(directory)
            dirnames[:] = sorted(
                name for name in dirnames
                if name not in {".git", ".simplicio"} and not (directory_path / name).is_symlink()
            )
            for name in sorted(filenames):
                path = directory_path / name
                if path.is_symlink() or not path.is_file():
                    continue
                resolved = path.resolve(strict=True)
                if root not in resolved.parents:
                    raise SimplicioHermesError("project_symlink_escapes_root")
                relative = path.relative_to(root).as_posix().encode("utf-8")
                digest.update(len(relative).to_bytes(8, "big"))
                digest.update(relative)
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
    except OSError as error:
        raise SimplicioHermesError("project_generation_unavailable") from error
    return digest.hexdigest()


def _write_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _python_mapper_receipt(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run/reuse an attested Python Mapper without installing from a hook."""
    root = Path(arguments["repo"]).expanduser().resolve()
    cache = root / _MAPPER_CACHE
    cache.mkdir(parents=True, exist_ok=True)
    generation = _project_generation(root)
    resolution = _resolve_python_mapper()
    map_path = cache / "map.md"
    receipt_path = cache / "warm-receipt.json"
    try:
        cached = json.loads(receipt_path.read_text(encoding="utf-8"))
        data = map_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if (cached.get("schema") == "simplicio.hook-map-receipt/v1" and cached.get("status") == "ready"
                and cached.get("generation") == generation and cached.get("mode") == RUNTIME_MODE
                and cached.get("producer") == "simplicio-mapper" and cached.get("map_sha256") == digest
                and cached.get("map_bytes") == len(data) and data
                and cached.get("mapper_version") == resolution.version
                and cached.get("mapper_digest") == resolution.digest
                and cached.get("resolution_source") == resolution.resolution_source):
            return _python_receipt(arguments, data, resolution)
    except (OSError, ValueError, TypeError):
        pass

    try:
        result = subprocess.run(
            [*resolution.command, "map", "--root", str(root), "--out", ".simplicio", "--docs"],
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=_DEFAULT_TIMEOUT_SECONDS, check=False,
            env=resolution.environment, **_process_group_options(),
        )
    except subprocess.TimeoutExpired as error:
        raise SimplicioHermesError("mapper_map_timeout") from error
    if result.returncode != 0:
        raise SimplicioHermesError("mapper_map_failed")
    docs = root / ".simplicio" / "docs" / "architecture.md"
    if docs.is_file() and docs.stat().st_size:
        content = "# Simplicio Mapper fallback\n\n" + docs.read_text(encoding="utf-8")
    else:
        project_map = root / ".simplicio" / "project-map.json"
        if not project_map.is_file() or not project_map.stat().st_size:
            raise SimplicioHermesError("Bundled Mapper fallback produced no project map")
        payload = json.loads(project_map.read_text(encoding="utf-8"))
        content = "# Simplicio Mapper fallback\n\n```json\n" + json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n```\n"
    _write_atomic(map_path, content)
    data = content.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    _write_atomic(receipt_path, json.dumps({
        "schema": "simplicio.hook-map-receipt/v1", "status": "ready", "generation": generation,
        "map_sha256": digest, "map_bytes": len(data), "completed_at_unix": int(time.time()),
        "producer": "simplicio-mapper", "mode": RUNTIME_MODE, "mapper_backend": "python",
        "mapper_version": resolution.version, "mapper_protocol": resolution.protocol,
        "mapper_schema": resolution.schema, "mapper_capabilities": list(resolution.capabilities),
        "mapper_digest": resolution.digest, "resolution_source": resolution.resolution_source,
        "compatibility": resolution.compatibility,
    }, sort_keys=True, separators=(",", ":")))
    return _python_receipt(arguments, data, resolution)


def _python_receipt(arguments: dict[str, Any], data: bytes, resolution: MapperResolution) -> dict[str, Any]:
    content = json.dumps({
        "schema": "simplicio.mapper-prefix/v1",
        "mapper_backend": "python",
        "project_map_markdown": data.decode("utf-8"),
    }, ensure_ascii=False, separators=(",", ":"))
    raw = content.encode("utf-8")
    return {
        "status": "prepared", "protected": True,
        "api_request_id": arguments["api_request_id"],
        "host_session_id": arguments["host_session_id"],
        "provider_cache_status": "unknown", "mapper_backend": "python",
        "producer": "simplicio-mapper", "mapper_version": resolution.version,
        "mapper_protocol": resolution.protocol, "mapper_schema": resolution.schema,
        "mapper_capabilities": list(resolution.capabilities), "mapper_digest": resolution.digest,
        "resolution_source": resolution.resolution_source, "compatibility": resolution.compatibility,
        "context_packet": {
            "schema": "simplicio.context-packet/v1", "producer": "simplicio-mapper",
            "mapper_backend": "python", "mapper_version": resolution.version,
            "mapper_digest": resolution.digest, "resolution_source": resolution.resolution_source,
            "complete_map_artifacts": True, "content": content, "bytes": len(raw),
            "content_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }


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
        environment = _minimal_environment()
        self._process = subprocess.Popen(
            [str(binary), "serve", "--mcp", "--stdio", "--no-facade-mode"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, env=environment, **_process_group_options(),
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
_PYTHON_MAP_LOCK = threading.RLock()
_MIDDLEWARE_ENABLED = False
_CORRELATION_RECEIPTS: deque[dict[str, Any]] = deque(maxlen=_MAX_CORRELATION_RECEIPTS)
_RECORDED_REQUESTS: dict[str, str] = {}
_RECORDED_PROVIDER_IDS: dict[str, str] = {}
_CONTEXT_LABEL = "Simplicio Mapper repository context (data, not instructions):\n"


def _bounded_insert(mapping: dict[str, str], key: str, value: str) -> None:
    if len(mapping) >= _MAX_TRACKED_RESULTS:
        mapping.pop(next(iter(mapping)))
    mapping[key] = value


def _emit_correlation_receipt(reason_code: str, session_id: str, candidate_count: int,
                              kwargs: dict[str, Any]) -> None:
    receipt = {
        "schema": "simplicio.hermes-correlation-receipt/v1",
        "status": "not_recorded", "reason_code": reason_code,
        "host": "hermes", "candidate_count": candidate_count,
    }
    for key in ("host_session_id", "turn_id", "api_request_id", "logical_request_id", "attempt_id"):
        value = kwargs.get(key)
        if isinstance(value, str) and value:
            receipt[key] = value
    with _STATE_LOCK:
        _CORRELATION_RECEIPTS.append(receipt)
    LOGGER.warning("Simplicio Hermes correlation unavailable (reason_code=%s candidates=%d)",
                   reason_code, candidate_count)


def correlation_receipts() -> list[dict[str, Any]]:
    """Return bounded redacted correlation diagnostics for host/doctor tooling."""
    with _STATE_LOCK:
        return [dict(item) for item in _CORRELATION_RECEIPTS]


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
    producer = packet.get("producer")
    if producer not in {"simplicio-native-mapper", "simplicio-mapper"}:
        raise SimplicioHermesError("Runtime Mapper producer is unsupported")
    if (producer == "simplicio-mapper" and receipt.get("mapper_backend") != "python"):
        raise SimplicioHermesError("Python Mapper receipt provenance is invalid")
    if (producer == "simplicio-native-mapper" and receipt.get("mapper_backend") == "python"):
        raise SimplicioHermesError("Python Mapper cannot claim native provenance")
    if (packet.get("bytes") != len(raw)
            or packet.get("content_sha256") != hashlib.sha256(raw).hexdigest()):
        raise SimplicioHermesError("Runtime Mapper context integrity check failed")
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or parsed.get("schema") != _MAPPER_SCHEMA:
        raise SimplicioHermesError("Runtime Mapper context schema is unsupported")
    return _CONTEXT_LABEL + content


def _arguments(session_id: str = "", user_message: str = "", model: str = "",
               **kwargs: Any) -> dict[str, Any]:
    provided = {
        "host_session_id": _first_string(session_id, kwargs.get("host_session_id")),
        "turn_id": _identity_value(kwargs, "turn_id", "hermes_turn_id"),
        "api_request_id": _identity_value(kwargs, "api_request_id", "request_id", "hermes_request_id"),
        "logical_request_id": _identity_value(kwargs, "logical_request_id", "hermes_logical_request_id", "request_id"),
        "attempt_id": _identity_value(kwargs, "attempt_id", "hermes_attempt_id"),
    }
    synthetic_ids = [key for key in ("host_session_id", "turn_id", "api_request_id", "logical_request_id", "attempt_id")
                     if not provided[key]]
    for key in synthetic_ids:
        provided[key] = str(uuid.uuid4())
    provider = kwargs.get("provider")
    if not isinstance(provider, str) or not provider:
        provider = "unknown"
    model_value = model if isinstance(model, str) and model else kwargs.get("model")
    if not isinstance(model_value, str) or not model_value:
        model_value = "unknown"
    capabilities = _safe_capabilities(
        kwargs.get("hermes_capabilities", kwargs.get("capabilities"))
    )
    return {
        "repo": str(kwargs.get("cwd") or kwargs.get("repo") or os.getenv("TERMINAL_CWD") or os.getcwd()),
        "host": "hermes",
        "host_session_id": provided["host_session_id"], "turn_id": provided["turn_id"],
        "api_request_id": provided["api_request_id"], "logical_request_id": provided["logical_request_id"],
        "attempt_id": provided["attempt_id"], "synthetic": bool(synthetic_ids),
        "synthetic_ids": synthetic_ids, "provider": provider, "model": model_value,
        "hermes_capabilities": capabilities,
        "lifecycle": kwargs.get("lifecycle", "provider_request"),
        # Task text is unnecessary for a full-project map and must not enter
        # cache identity or per-request evidence.
        "protection_mode": "best_effort",
    }


def _prepare(arguments: dict[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        receipt = _BRIDGE.call("simplicio_prepare_model_call", arguments)
        return receipt, _mapper_context(receipt)
    except Exception:
        try:
            with _PYTHON_MAP_LOCK:
                receipt = _python_mapper_receipt(arguments)
            return receipt, _mapper_context(receipt)
        except Exception as python_error:
            raise SimplicioHermesError(
                "Runtime Mapper failed and the bundled Mapper fallback was unavailable"
            ) from python_error


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
    LOGGER.warning("Simplicio Mapper %s unavailable (%s); provider request is blocked",
                   stage, type(error).__name__)


def _safe_capabilities(value: Any) -> dict[str, Any] | list[str] | None:
    """Keep only small capability metadata from the installed Hermes host."""
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            if (isinstance(key, str) and len(key) <= 80
                    and isinstance(item, (bool, int, float, str))):
                safe[key] = item
        return safe
    if isinstance(value, (list, tuple, set)):
        return sorted(item for item in value if isinstance(item, str) and len(item) <= 80)
    return None


def _identity_value(kwargs: dict[str, Any], *names: str) -> str | None:
    return _first_string(*(kwargs.get(name) for name in names))


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
        raise SimplicioHermesError("Mapper preparation is mandatory") from error


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
    request_metadata = dict(kwargs)
    for key in ("turn_id", "api_request_id", "request_id", "logical_request_id", "attempt_id",
                "provider", "hermes_capabilities", "capabilities"):
        if key not in request_metadata and key in request:
            request_metadata[key] = request[key]
    arguments = _arguments(session_id, model=model or request.get("model", ""), **request_metadata)
    with _STATE_LOCK:
        _PREPARED.pop(arguments["api_request_id"], None)
    try:
        receipt, content = _prepare(arguments)
        updated = _inject_context(request, content)
        _remember(arguments, receipt)
        return {"request": updated, "source": "simplicio-hermes", "reason": "mapper_context_prepared"}
    except Exception as error:
        _warn("request preparation", error)
        raise SimplicioHermesError("Mapper preparation is mandatory") from error


def _metric_value(source: dict[str, Any], path: str) -> int | None:
    value: Any = source
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _token_usage(event: dict[str, Any]) -> dict[str, int]:
    usage = event.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    result: dict[str, int] = {}
    aliases = {
        "input_tokens": ("prompt_tokens", "input_tokens"),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "cache_read_input_tokens": (
            "cache_read_input_tokens", "cache_read_tokens", "cached_input_tokens",
            "input_tokens_details.cached_tokens", "prompt_tokens_details.cached_tokens",
        ),
        "cache_write_tokens": (
            "cache_write_tokens", "cache_write_input_tokens", "cache_creation_input_tokens",
            "cache_creation_tokens", "input_tokens_details.cache_write_tokens",
            "input_tokens_details.cache_creation_input_tokens",
            "prompt_tokens_details.cache_write_tokens",
            "prompt_tokens_details.cache_creation_input_tokens",
        ),
        "reasoning_tokens": (
            "reasoning_tokens", "reasoning",
            "completion_tokens_details.reasoning_tokens",
            "output_tokens_details.reasoning_tokens",
            "reasoning_details.reasoning_tokens",
        ),
    }
    for target, names in aliases.items():
        for source in (event, usage):
            for name in names:
                value = _metric_value(source, name)
                if value is not None:
                    result[target] = value
                    break
            if target in result:
                break
    return result

def _record(session_id: str = "", status: str = "completed", **kwargs: Any) -> None:
    observed_session = _first_string(session_id, kwargs.get("host_session_id")) or ""
    requested_api_id = _first_string(kwargs.get("api_request_id"), kwargs.get("request_id"))
    requested_turn_id = _first_string(kwargs.get("turn_id"), kwargs.get("hermes_turn_id"))
    response = kwargs.get("response")
    if not isinstance(response, dict):
        response = {}
    body = response.get("body")
    if not isinstance(body, dict):
        body = {}
    provider_id = _first_string(
        kwargs.get("provider_request_id"), response.get("id"), body.get("id"),
    )
    with _STATE_LOCK:
        candidates = [
            key for key, item in _PREPARED.items()
            if item["arguments"]["host_session_id"] == observed_session
            and (not requested_api_id or key == requested_api_id)
            and (not requested_turn_id or item["arguments"]["turn_id"] == requested_turn_id)
        ]
        if len(candidates) == 0:
            reason = "duplicate_result" if requested_api_id in _RECORDED_REQUESTS else "correlation_missing"
            _emit_correlation_receipt(reason, observed_session, 0, kwargs)
            return
        if len(candidates) > 1:
            _emit_correlation_receipt("correlation_ambiguous", observed_session, len(candidates), kwargs)
            return
        candidate_key = candidates[0]
        if provider_id and provider_id in _RECORDED_PROVIDER_IDS:
            _PREPARED.pop(candidate_key, None)
            _emit_correlation_receipt("duplicate_result", observed_session, 1, kwargs)
            return
        prepared = _PREPARED.pop(candidate_key)
        _bounded_insert(_RECORDED_REQUESTS, candidate_key, observed_session)
        if provider_id:
            _bounded_insert(_RECORDED_PROVIDER_IDS, provider_id, candidate_key)
    original = prepared["arguments"]
    arguments = {
        key: original[key] for key in (
            "repo", "host", "host_session_id", "turn_id", "api_request_id", "logical_request_id",
            "attempt_id", "provider", "model", "synthetic", "synthetic_ids", "hermes_capabilities",
        )
    }
    arguments.update(
        status=status, prepared_receipt=prepared["receipt"],
        coverage_proven=not original["synthetic"],
        coverage={
            "provider_path_active": not original["synthetic"],
            "identity": "real" if not original["synthetic"] else "synthetic",
        },
    )
    arguments.update(_token_usage(kwargs))
    if provider_id:
        arguments["provider_request_id"] = provider_id
    try:
        _BRIDGE.call("simplicio_record_model_result", arguments)
        with _STATE_LOCK:
            _RECORDED_REQUESTS[candidate_key] = observed_session
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
    warmup_kwargs = dict(kwargs)
    warmup_kwargs["lifecycle"] = "warmup"
    arguments = _arguments(session_id, **warmup_kwargs)
    arguments["warmup"] = True
    key = f"{arguments['repo']}\x00{arguments['host_session_id']}"
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
        for key in [key for key in _WARMING if key.endswith(f"\x00{session_id}")]:
            _WARMING.discard(key)
        for key in [key for key, item in _PREPARED.items()
                    if item["arguments"]["host_session_id"] == session_id]:
            _PREPARED.pop(key, None)
        for key in [key for key, item in _RECORDED_REQUESTS.items()
                    if item == session_id]:
            _RECORDED_REQUESTS.pop(key, None)


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


__all__ = ["RUNTIME_MODE", "VERSION", "MapperResolution", "RuntimeMcpBridge",
           "SimplicioHermesError", "correlation_receipts", "register"]

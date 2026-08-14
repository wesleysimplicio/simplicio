#!/usr/bin/env python3
"""Portable identity contract for agents claiming shared Simplicio work.

The identity is deliberately transport-neutral: a queue (local JSONL, shared
filesystem, or a future API) can persist it without knowing whether the caller
is Codex, Claude, or another runtime.  ``device_id`` is a privacy-preserving
host fingerprint; callers may override it for stable CI/container identities.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import socket
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

SCHEMA = "simplicio.agent-identity/v1"
PROTOCOL = "simplicio-distributed/v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _device_id() -> str:
    override = (os.environ.get("SIMPLICIO_DEVICE_ID") or "").strip()
    if override:
        return override
    raw = "%s|%s|%s" % (socket.gethostname(), getpass.getuser(), platform.system())
    return "device-%s" % hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def identity_path(path: Optional[str] = None) -> Path:
    return Path(path or os.environ.get("SIMPLICIO_IDENTITY_FILE") or
                os.path.join(".simplicio/orchestrator", "agent-identity.json"))


def _read(path: Path) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get("schema") == SCHEMA else None


def ensure_identity(*, path: Optional[str] = None, runtime: Optional[str] = None,
                    session_id: Optional[str] = None,
                    agent_id: Optional[str] = None,
                    device_id: Optional[str] = None,
                    capabilities: Optional[list[str]] = None) -> dict[str, Any]:
    """Load or atomically create a stable identity for this agent process."""
    target = identity_path(path)
    existing = _read(target)
    if existing:
        # Runtime/session are intentionally refreshed per invocation while the
        # identity and device remain stable across reconnects.
        existing["runtime"] = (runtime or os.environ.get("SIMPLICIO_RUNTIME") or
                                existing.get("runtime") or "unknown")
        existing["session_id"] = (session_id or os.environ.get("SIMPLICIO_SESSION_ID") or
                                   existing.get("session_id") or uuid.uuid4().hex)
        if capabilities is not None:
            existing["capabilities"] = list(capabilities)
        _validate(existing)
        return existing
    value = {
        "schema": SCHEMA,
        "protocol": PROTOCOL,
        "agent_id": (agent_id or os.environ.get("SIMPLICIO_AGENT_ID") or
                      "agent-%s" % uuid.uuid4().hex),
        "runtime": runtime or os.environ.get("SIMPLICIO_RUNTIME") or "unknown",
        "device_id": device_id or _device_id(),
        "session_id": session_id or os.environ.get("SIMPLICIO_SESSION_ID") or uuid.uuid4().hex,
        "capabilities": list(capabilities or ["claim", "heartbeat", "fencing", "receipts"]),
        "issued_at": _now(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".agent-identity-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    _validate(value)
    return value


def _validate(value: dict[str, Any]) -> None:
    """Reject malformed or duplicate capability identities before persistence."""
    capabilities = value.get("capabilities") or []
    if len(capabilities) != len(set(capabilities)):
        raise ValueError("duplicate capabilities are not allowed")
    if any(not isinstance(capability, str) or not capability.strip() for capability in capabilities):
        raise ValueError("capabilities must contain non-empty strings")


def lease_identity(identity: Mapping[str, Any]) -> dict[str, str]:
    """Return only claim-safe identity fields to persist in a lease."""
    return {name: str(identity.get(name) or "") for name in
            ("agent_id", "runtime", "device_id", "session_id")}


def identity_matches(lease_identity_value: Mapping[str, Any], identity: Mapping[str, Any]) -> bool:
    if not isinstance(lease_identity_value, Mapping):
        return False
    return all(str(lease_identity_value.get(name) or "") == str(identity.get(name) or "")
               for name in ("agent_id", "runtime", "device_id", "session_id"))

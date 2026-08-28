"""Bounded, transactional host integration orchestration.

The Runtime remains the authority for live MCP handshakes.  This module owns
the installer-side mechanics that are safe to exercise without starting a
host: selecting a documented scope, merging the portable MCP entry, keeping
unrelated configuration byte-for-byte equivalent, and emitting evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .host_integrations import HOSTS, HostSpec, detect_hosts


SCHEMA = "simplicio.host-adapters/v1"
MANAGED_SERVER = "simplicio"
TRUTHY = frozenset(("1", "true", "yes", "on"))


@dataclass(frozen=True)
class IntegrationResult:
    host_id: str
    status: str
    scope: str
    config: str | None
    capability: str
    verification: str
    reason_code: str
    changed: bool = False
    backup: str | None = None


def _is_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in TRUTHY


def _safe_binary(binary: str | os.PathLike[str]) -> str:
    path = Path(binary).expanduser()
    if not path.is_absolute() or not path.name:
        raise ValueError("binary must be an absolute executable path")
    return str(path)


def _entry(binary: str) -> dict[str, Any]:
    return {
        "command": binary,
        "args": ["serve", "--mcp", "--stdio"],
    }


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _scope_path(spec: HostSpec, *, scope: str, home: Path, cwd: Path) -> Path | None:
    if scope not in spec.scopes:
        return None
    candidates = spec.config_paths
    if scope == "user":
        candidates = tuple(item for item in candidates if item.startswith("~/"))
    elif scope == "workspace":
        candidates = tuple(item for item in candidates if not item.startswith("~/"))
    elif scope == "remote":
        candidates = tuple(item for item in candidates if not item.startswith("~/"))
    for raw in candidates:
        if raw.startswith("~/"):
            return home / raw[2:]
        return cwd / raw
    return None


def _load_json(path: Path) -> tuple[dict[str, Any], bytes, str | None]:
    if not path.exists():
        return {}, b"", None
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, raw, "malformed_config"
    if not isinstance(value, dict):
        return {}, raw, "malformed_config"
    return value, raw, None


def _merge_mcp(document: dict[str, Any], binary: str) -> tuple[dict[str, Any], str]:
    result = json.loads(json.dumps(document, ensure_ascii=False))
    key = "mcpServers" if isinstance(result.get("mcpServers"), dict) else "servers"
    servers = result.setdefault(key, {})
    if not isinstance(servers, dict):
        raise ValueError("MCP server collection must be an object")
    servers[MANAGED_SERVER] = _entry(binary)
    return result, key


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_one(spec: HostSpec, path: Path, binary: str, *, dry_run: bool) -> IntegrationResult:
    document, before, error = _load_json(path)
    if error:
        return IntegrationResult(spec.host_id, "failed", "", str(path), spec.capability, "none", error)
    try:
        merged, _ = _merge_mcp(document, binary)
        encoded = (json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    except (TypeError, ValueError):
        return IntegrationResult(spec.host_id, "failed", "", str(path), spec.capability, "none", "invalid_mcp_document")
    changed = encoded != before
    backup: str | None = None
    if changed and not dry_run:
        try:
            if path.exists():
                backup_path = path.with_name(path.name + ".simplicio.bak")
                shutil.copy2(path, backup_path)
                backup = str(backup_path)
            _atomic_write(path, encoded)
            round_trip, _, round_trip_error = _load_json(path)
            servers = round_trip.get("mcpServers", round_trip.get("servers", {}))
            if round_trip_error or not isinstance(servers, dict) or servers.get(MANAGED_SERVER) != _entry(binary):
                raise OSError("managed entry did not survive the atomic write")
        except (OSError, ValueError):
            if backup and Path(backup).exists():
                shutil.copy2(backup, path)
            return IntegrationResult(spec.host_id, "failed", "", str(path), spec.capability, "none", "write_or_verify_failed")
    return IntegrationResult(
        spec.host_id,
        "planned" if dry_run else "registered",
        "",
        str(path),
        spec.capability,
        "config_roundtrip" if not dry_run else "dry_run",
        "already_registered" if not changed else "registered",
        changed=changed,
        backup=backup,
    )


def install_detected_hosts(
    binary: str | os.PathLike[str],
    *,
    home: Path | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    scope: str | None = None,
    dry_run: bool = False,
    specs: Iterable[HostSpec] = HOSTS,
) -> dict[str, Any]:
    """Install every detected supported integration and isolate failures."""

    binary_path = _safe_binary(binary)
    environment = dict(os.environ if env is None else env)
    resolved_home = (home or Path.home()).expanduser().resolve()
    resolved_cwd = (cwd or Path.cwd()).resolve()
    chosen_scope = scope or environment.get("SIMPLICIO_HOST_SCOPE", "user")
    if chosen_scope not in {"user", "workspace", "remote"}:
        raise ValueError("scope must be user, workspace, or remote")
    detections = {str(item["id"]): item for item in detect_hosts(resolved_home, environment, specs)}
    results: list[IntegrationResult] = []
    for spec in specs:
        observed = detections[spec.host_id]
        status = str(observed["status"])
        if status in {"absent", "skipped", "unsupported"}:
            results.append(IntegrationResult(spec.host_id, status, chosen_scope, None, spec.capability, "none", status))
            continue
        if spec.contract == "unverified":
            results.append(IntegrationResult(spec.host_id, "unsupported", chosen_scope, None, spec.capability, "none", "contract_unverified"))
            continue
        if spec.capability == "portable-cli":
            results.append(IntegrationResult(spec.host_id, "detected", chosen_scope, None, spec.capability, "portable_cli", "manual_host_verification"))
            continue
        path = _scope_path(spec, scope=chosen_scope, home=resolved_home, cwd=resolved_cwd)
        if path is None:
            results.append(IntegrationResult(spec.host_id, "failed", chosen_scope, None, spec.capability, "none", "scope_unsupported"))
            continue
        item = _write_one(spec, path, binary_path, dry_run=dry_run)
        results.append(
            IntegrationResult(
                item.host_id,
                item.status,
                chosen_scope,
                item.config,
                item.capability,
                item.verification,
                item.reason_code,
                item.changed,
                item.backup,
            )
        )
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "schema": SCHEMA,
        "binary": binary_path,
        "scope": chosen_scope,
        "dry_run": dry_run,
        "runtime_installation": "one_binary",
        "results": [asdict(result) for result in results],
        "counts": counts,
        "failed_hosts": [result.host_id for result in results if result.status == "failed"],
        "verification": "config_roundtrip_only; live_handshake_remains_runtime_owned",
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Install detected Simplicio host integrations transactionally.")
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--scope", choices=("user", "workspace", "remote"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = install_detected_hosts(args.binary, home=args.home, cwd=args.cwd, scope=args.scope, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) if args.json else "\n".join(
        f"{item['host_id']}: {item['status']} ({item['reason_code']})" for item in result["results"]
    ))
    return int(bool(result["failed_hosts"]))


if __name__ == "__main__":
    raise SystemExit(main())

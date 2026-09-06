"""Deterministic host discovery and Runtime-registration receipts.

The public installer owns distribution of one Runtime binary.  It must not
reimplement every editor's MCP writer or silently guess a third-party CLI.
This module therefore keeps the host matrix in one place, performs exact
non-invasive probes, and records the Runtime's registration result alongside
the detected hosts.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA = "simplicio.host-integration/v1"
TRUTHY = frozenset(("1", "true", "yes", "on"))


@dataclass(frozen=True)
class HostSpec:
    """A host entry with only evidence-safe detection metadata."""

    host_id: str
    name: str
    executable_names: Tuple[str, ...] = ()
    app_paths: Tuple[str, ...] = ()
    config_paths: Tuple[str, ...] = ()
    capability: str = "unsupported"
    contract: str = "unknown"
    minimum_version: str = "unknown"
    verification_command: Tuple[str, ...] = ()
    scopes: Tuple[str, ...] = ("user",)
    default_scope: str = "user"
    mcp_environment: Tuple[Tuple[str, str], ...] = ()
    documentation: str = ""
    reason: str = ""


def _runtime_mcp(
    host_id: str,
    name: str,
    executable_names: Sequence[str],
    config_paths: Sequence[str],
    documentation: str,
    minimum_version: str = "not-pinned",
    scopes: Sequence[str] = ("user",),
    default_scope: str = "user",
    mcp_environment: Sequence[Tuple[str, str]] = (),
) -> HostSpec:
    return HostSpec(
        host_id=host_id,
        name=name,
        executable_names=tuple(executable_names),
        config_paths=tuple(config_paths),
        capability="runtime-mcp",
        contract="delegated-to-runtime",
        minimum_version=minimum_version,
        verification_command=(
            "simplicio",
            "mcp",
            "register",
            "--binary",
            "<absolute-path>",
            "--json",
        ),
        scopes=tuple(scopes),
        default_scope=default_scope,
        mcp_environment=tuple(mcp_environment),
        documentation=documentation,
        reason="The Runtime owns the atomic MCP/native-hook registration.",
    )


def _unverified(host_id: str, name: str, documentation: str, reason: str) -> HostSpec:
    # No executable is intentionally listed until the upstream product contract
    # is verified.  An empty probe is safer than a false positive from a
    # similarly named command.
    return HostSpec(
        host_id=host_id,
        name=name,
        capability="unsupported",
        contract="unverified",
        verification_command=(),
        documentation=documentation,
        reason=reason,
    )


HOSTS: Tuple[HostSpec, ...] = (
    _runtime_mcp(
        "claude-code",
        "Claude Code",
        ("claude",),
        ("~/.claude/settings.json", "~/.claude/.mcp.json"),
        "https://docs.anthropic.com/claude/docs/claude-code",
        mcp_environment=(("SIMPLICIO_RUNTIME_MODE", "mapper-only"),),
    ),
    _runtime_mcp(
        "cursor",
        "Cursor",
        ("cursor",),
        ("~/.cursor/mcp.json", ".cursor/mcp.json"),
        "https://cursor.com/cli",
        scopes=("user", "workspace"),
        default_scope="user",
    ),
    _unverified(
        "deepseek-harness",
        "DeepSeek Harness",
        "",
        "The canonical harness executable and plugin/MCP contract are not verified.",
    ),
    _runtime_mcp(
        "opencode",
        "OpenCode",
        ("opencode",),
        ("~/.config/opencode/opencode.json", "opencode.json"),
        "https://opencode.ai/docs/cli/",
    ),
    _runtime_mcp(
        "vscode",
        "Visual Studio Code",
        ("code", "code-insiders"),
        ("~/.vscode/mcp.json", ".vscode/mcp.json"),
        "https://code.visualstudio.com/docs/copilot/chat/mcp-servers",
        scopes=("user", "workspace", "remote"),
        default_scope="user",
    ),
    _unverified(
        "antigravity",
        "Google Antigravity",
        "https://antigravity.google/docs/cli-overview",
        "The canonical executable and public extension/MCP contract are not verified.",
    ),
    _runtime_mcp(
        "kiro",
        "Kiro",
        ("kiro-cli",),
        ("~/.kiro/settings/mcp.json", ".kiro/settings/mcp.json"),
        "https://kiro.dev/docs/cli/",
    ),
    _runtime_mcp(
        "pi",
        "Pi",
        ("pi",),
        ("~/.pi/agent/mcp.json",),
        "https://pi.dev/",
    ),
    _runtime_mcp(
        "oh-my-pi",
        "oh-my-pi",
        ("omp",),
        ("~/.omp/mcp.json",),
        "https://omp.sh/",
    ),
    HostSpec(
        host_id="orca",
        name="OrcaDev / Orca ADE",
        executable_names=("orca",),
        capability="portable-cli",
        contract="documented-cli",
        minimum_version="not-pinned",
        verification_command=("orca", "status", "--json"),
        documentation="https://www.onorca.dev/docs/cli/overview",
        reason="Use the documented Orca skills/MCP path; do not alter worktrees.",
    ),
    _unverified(
        "command-code",
        "Command Code",
        "https://commandcode.ai/docs/quickstart",
        "The canonical executable and official integration contract are not verified.",
    ),
)


REMAINING_HOSTS: Tuple[Tuple[str, str, str], ...] = (
    ("grok", "Grok", "https://github.com/wesleysimplicio/simplicio"),
    ("github-copilot", "GitHub Copilot", "https://github.com/features/copilot"),
    ("mimo-code", "MiMo Code", "https://github.com/wesleysimplicio/simplicio"),
    ("amp", "Amp", "https://github.com/wesleysimplicio/simplicio"),
    ("openclaude", "OpenClaude", "https://github.com/wesleysimplicio/simplicio"),
    ("hermes-agent", "Hermes Agent", "https://github.com/wesleysimplicio/simplicio"),
    ("devin", "Devin", "https://github.com/wesleysimplicio/simplicio"),
    ("goose", "Goose", "https://github.com/block/goose"),
    ("auggie", "Auggie", "https://github.com/wesleysimplicio/simplicio"),
    ("autohand-code", "Autohand Code", "https://github.com/wesleysimplicio/simplicio"),
    ("charm-crush", "Charm/Crush", "https://github.com/charmbracelet/crush"),
    ("cline", "Cline", "https://github.com/cline/cline"),
    ("codebuff", "Codebuff", "https://github.com/wesleysimplicio/simplicio"),
    ("continue", "Continue", "https://github.com/continuedev/continue"),
    ("droid", "Droid", "https://github.com/wesleysimplicio/simplicio"),
    ("kilocode", "Kilocode", "https://github.com/Kilo-Org/kilocode"),
    ("kimi", "Kimi", "https://github.com/wesleysimplicio/simplicio"),
    ("mistral-vibe", "Mistral Vibe", "https://github.com/mistralai"),
    ("qwen-code", "Qwen Code", "https://github.com/QwenLM/Qwen-Code"),
    ("rovo-dev", "Rovo Dev", "https://www.atlassian.com/software/rovo"),
)

# Names requested by the compatibility-matrix issue.  Entries that already
# have a dedicated adapter (currently oh-my-pi) remain represented by that
# adapter; every other row is explicit and fail-closed until verified.
COMPATIBILITY_MATRIX_HOST_IDS = frozenset(
    {
        "grok",
        "github-copilot",
        "mimo-code",
        "amp",
        "openclaude",
        "oh-my-pi",
        "hermes-agent",
        "devin",
        "goose",
        "auggie",
        "autohand-code",
        "charm-crush",
        "cline",
        "codebuff",
        "command-code",
        "continue",
        "droid",
        "kilocode",
        "kimi",
        "mistral-vibe",
        "qwen-code",
        "rovo-dev",
    }
)

HOSTS = HOSTS + tuple(
    _unverified(host_id, name, docs, "The public contract is not verified; automatic detection is disabled.")
    for host_id, name, docs in REMAINING_HOSTS
)


def compatibility_matrix() -> Tuple[Dict[str, object], ...]:
    """Expose the complete, redacted host contract table for UIs and CI."""

    return tuple(
        {
            "id": spec.host_id,
            "name": spec.name,
            "capability": spec.capability,
            "contract": spec.contract,
            "executable_names": list(spec.executable_names),
            "scopes": list(spec.scopes),
            "verification": list(spec.verification_command),
            "documentation": spec.documentation,
        }
        for spec in HOSTS
    )


def _home_path(value: str, home: Path) -> Path:
    if value.startswith("~/"):
        return home / value[2:]
    return Path(value)


def _is_truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in TRUTHY


def _skip_hosts(env: Mapping[str, str]) -> frozenset:
    raw = env.get("SIMPLICIO_SKIP_HOSTS", "")
    return frozenset(item.strip().lower() for item in raw.split(",") if item.strip())


def _is_skipped(spec: HostSpec, env: Mapping[str, str], skipped: frozenset) -> bool:
    env_name = "SIMPLICIO_SKIP_" + spec.host_id.upper().replace("-", "_")
    return spec.host_id.lower() in skipped or _is_truthy(env.get(env_name))


def _exact_executables(spec: HostSpec, env: Mapping[str, str]) -> List[str]:
    path = env.get("PATH")
    found: List[str] = []
    for name in spec.executable_names:
        resolved = shutil.which(name, path=path)
        if resolved and Path(resolved).name == name:
            found.append(str(Path(resolved).resolve()))
    return found


def detect_hosts(
    home: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
    specs: Iterable[HostSpec] = HOSTS,
) -> List[Dict[str, object]]:
    """Return an evidence-only snapshot without launching any host process."""

    resolved_home = (home or Path.home()).expanduser().resolve()
    environ = dict(os.environ if env is None else env)
    skipped = _skip_hosts(environ)
    result: List[Dict[str, object]] = []
    for spec in specs:
        executable_paths = _exact_executables(spec, environ)
        app_paths = [
            str(path)
            for path in (_home_path(item, resolved_home) for item in spec.app_paths)
            if path.exists()
        ]
        config_paths = [
            str(path)
            for path in (_home_path(item, resolved_home) for item in spec.config_paths)
            if path.exists()
        ]
        present = bool(executable_paths or app_paths)
        skipped_host = _is_skipped(spec, environ, skipped)
        if skipped_host:
            status = "skipped"
        elif not present and spec.contract == "unverified":
            status = "unsupported"
        elif not present:
            status = "absent"
        elif spec.contract == "unverified":
            status = "unsupported"
        else:
            status = "detected"
        result.append(
            {
                "id": spec.host_id,
                "name": spec.name,
                "status": status,
                "capability": spec.capability,
                "contract": spec.contract,
                "minimum_version": spec.minimum_version,
                "verification": list(spec.verification_command),
                "scopes": list(spec.scopes),
                "default_scope": spec.default_scope,
                "executable": executable_paths[0] if executable_paths else None,
                "app": app_paths[0] if app_paths else None,
                "config": config_paths[0] if config_paths else None,
                "documentation": spec.documentation,
                "reason": spec.reason,
            }
        )
    return result


def build_summary(
    runtime_report: Optional[Mapping[str, object]] = None,
    home: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, object]:
    hosts = detect_hosts(home=home, env=env)
    report = dict(runtime_report or {})
    runtime_status = report.get("status") if report else "not-run"
    registered = report.get("registered")
    failed = report.get("failed")
    if isinstance(registered, list):
        registered_ids = {str(item) for item in registered}
        for host in hosts:
            if host["status"] == "detected" and host["id"] in registered_ids:
                host["status"] = "registered"
    if isinstance(failed, list):
        failed_ids = {str(item) for item in failed}
        for host in hosts:
            if host["id"] in failed_ids:
                host["status"] = "failed"
    counts: Dict[str, int] = {}
    for host in hosts:
        status = str(host["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "schema": SCHEMA,
        "runtime": "single-binary",
        "runtime_registration": {"status": runtime_status},
        "hosts": hosts,
        "counts": counts,
    }


def write_summary(path: Path, summary: Mapping[str, object]) -> None:
    """Write a redacted, recoverable receipt with restrictive permissions."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    temporary = Path(raw_path)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.chmod(0o600)
        os.replace(str(temporary), str(path))
        replaced = True
    finally:
        if not replaced:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect Simplicio host integration detection.")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = build_summary(home=args.home)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for host in summary["hosts"]:
            print("{name}: {status}".format(**host))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

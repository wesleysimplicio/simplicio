#!/usr/bin/env python3
"""Generate an evidence-backed Simplicio capability inventory.

The scanner is intentionally conservative: it observes packaging/source surfaces,
marks inferred contracts, and leaves semantic details for capability-overrides.json.
It never executes a discovered command unless --probe-help is explicitly passed.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


GENERATOR_VERSION = "1.0.0"
SKIP_PARTS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "target",
    "dist", "build", "__pycache__", ".mypy_cache", ".pytest_cache",
}
KNOWN_CONFIG_NAMES = {
    "pyproject.toml", "setup.cfg", "setup.py", "Cargo.toml", "Cargo.lock",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "uv.lock", "poetry.lock", "Pipfile", "Pipfile.lock", ".env.example",
    "docker-compose.yml", "docker-compose.yaml", "Makefile", "justfile",
}
MCP_DECORATOR_RE = re.compile(r"@(?:[\w.]+\.)?(?:tool|resource|prompt)\b")
MCP_REGISTER_RE = re.compile(r"(?:\.tool|\.resource|\.prompt)\(\s*[\"']([^\"']+)")
ARGPARSE_PARSER_RE = re.compile(r"\.add_parser\(\s*[\"']([^\"']+)[\"'](?P<tail>[^)]*)\)")
HELP_SUBCOMMAND_RE = re.compile(r"\{([^}\n]+)\}")
RUST_ITEM_RE = re.compile(
    r"\bpub\s+(?:(?:async|unsafe|const)\s+)?"
    r"(?P<kind>fn|struct|enum|trait|type|const|static)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
RUST_FN_RE = re.compile(
    r"\bpub\s+(?:(?:async|unsafe|const)\s+)?fn\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<args>[^)]*)\)"
    r"(?:\s*->\s*(?P<return>[^\{]+))?"
)
SIGNAL_PATTERNS = {
    "filesystem-write": re.compile(r"\b(?:write_text|write_bytes|mkdir|makedirs|unlink|rename|replace)\b|open\([^\n]{0,160}[\"']w"),
    "subprocess": re.compile(r"\b(?:subprocess|Popen|Command::new|os\.system)\b"),
    "network": re.compile(r"\b(?:httpx|requests|urllib|socket|aiohttp|grpc)\b"),
    "database": re.compile(r"\b(?:sqlite|sqlalchemy|psycopg|redis|diskcache)\b"),
    "process-exit": re.compile(r"\b(?:sys\.exit|exit\(|panic!|abort)\b"),
}
FALLBACK_RE = re.compile(r"\b(?:fallback|degraded|retry|backoff|without\s+runtime|compatib(?:le|ility))\b", re.I)


def read_text(path: Path, limit: int = 1_500_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def run_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def load_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(read_text(path))
    except (ValueError, OSError):
        return {}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def files_under(root: Path, suffixes: tuple[str, ...] | None = None, limit: int = 20_000) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(result) >= limit or not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if suffixes and path.suffix not in suffixes:
            continue
        result.append(path)
    return result


def base_capability(cap_id: str, kind: str, name: str, source: str, *, status: str = "observed") -> dict[str, Any]:
    return {
        "id": cap_id,
        "kind": kind,
        "name": name,
        "status": status,
        "source": [source],
        "interfaces": {"cli": [], "mcp": [], "python_api": [], "rust_api": [], "config": []},
        "inputs": [],
        "outputs": [],
        "effects": {"observed_signals": [], "confidence": "requires_review"},
        "errors": [],
        "fallbacks": [],
        "cost": {"estimated_class": "unknown", "tokens": None, "latency": None, "measurement": "unmeasured"},
        "dependencies": [],
        "version": {},
        "compatibility": {},
        "evidence": [source],
    }


def python_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], str | None]:
    args = [arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
    returns = ast.unparse(node.returns) if node.returns else None
    return args, returns


def python_caps(path: Path, root: Path, signals: set[str], errors: set[str], fallbacks: set[str]) -> list[dict[str, Any]]:
    text = read_text(path)
    for name, pattern in SIGNAL_PATTERNS.items():
        if pattern.search(text):
            signals.add(name)
    for match in FALLBACK_RE.finditer(text):
        fallbacks.add(match.group(0).lower())
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    result: list[dict[str, Any]] = []
    source = rel(path, root)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name.startswith("_"):
            continue
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        cap = base_capability(f"repo.python_api.{node.name}", "python_api", node.name, source, status="inferred")
        cap["interfaces"]["python_api"] = [{"module": source.removesuffix(".py").replace("/", "."), "symbol": node.name, "kind": kind}]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args, returns = python_signature(node)
            cap["inputs"] = [{"name": name, "type": "unknown"} for name in args]
            cap["outputs"] = [{"type": returns or "unknown", "source": "return-annotation" if returns else "inferred"}]
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                exc = child.exc.func if isinstance(child.exc, ast.Call) else child.exc
                if isinstance(exc, ast.Name):
                    errors.add(exc.id)
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [ast.unparse(dec) for dec in child.decorator_list]
                for decorator in decorators:
                    if MCP_DECORATOR_RE.search("@" + decorator):
                        mcp = base_capability(f"repo.mcp.{child.name}", "mcp", child.name, source, status="observed")
                        mcp["interfaces"]["mcp"] = [{"name": child.name, "decorator": decorator, "schema": "requires_probe"}]
                        mcp["inputs"] = [{"name": name, "type": "unknown"} for name in python_signature(child)[0]]
                        mcp["outputs"] = [{"type": python_signature(child)[1] or "unknown"}]
                        result.append(mcp)
        result.append(cap)
    return result


def rust_caps(path: Path, root: Path, signals: set[str], errors: set[str], fallbacks: set[str]) -> list[dict[str, Any]]:
    text = read_text(path)
    for name, pattern in SIGNAL_PATTERNS.items():
        if pattern.search(text):
            signals.add(name)
    if "Result<" in text or "thiserror" in text or "anyhow" in text:
        errors.add("Result/error-type")
    for match in FALLBACK_RE.finditer(text):
        fallbacks.add(match.group(0).lower())
    result: list[dict[str, Any]] = []
    source = rel(path, root)
    for match in RUST_ITEM_RE.finditer(text):
        name, kind = match.group("name"), match.group("kind")
        cap = base_capability(f"repo.rust_api.{name}", "rust_api", name, source, status="observed")
        cap["interfaces"]["rust_api"] = [{"module": source, "symbol": name, "kind": kind}]
        cap["inputs"] = [{"signature": match.group(0)}]
        cap["outputs"] = [{"type": "unknown"}]
        if kind == "fn":
            fn = RUST_FN_RE.search(text, max(0, match.start() - 20))
            if fn and fn.group("return"):
                cap["outputs"] = [{"type": fn.group("return").strip()}]
        result.append(cap)
    return result


def cli_source_caps(path: Path, root: Path) -> list[dict[str, Any]]:
    """Observe argparse subcommands and checked-in CLI help without executing code."""
    text = read_text(path)
    source = rel(path, root)
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    if path.suffix == ".py":
        names.update(match.group(1) for match in ARGPARSE_PARSER_RE.finditer(text))
    if path.name == "_top.txt" or "cli_help" in path.parts:
        for line in text.splitlines():
            if "usage:" not in line and "positional arguments" not in line:
                continue
            for group in HELP_SUBCOMMAND_RE.findall(line):
                names.update(item.strip() for item in group.split(",") if re.fullmatch(r"[a-z][a-z0-9-]*", item.strip()))
    for name in sorted(names):
        cap = base_capability(f"repo.cli.subcommand.{name}", "cli", name, source, status="observed")
        cap["interfaces"]["cli"] = [{"command": name, "source_type": "argparse-or-help", "help_probe": "not-run"}]
        cap["inputs"] = [{"name": "argv", "type": "command-line"}]
        cap["outputs"] = [{"name": "stdout"}, {"name": "stderr"}, {"name": "exit_status"}]
        cap["evidence"].append(source)
        result.append(cap)
    return result


def mcp_source_caps(path: Path, root: Path) -> list[dict[str, Any]]:
    """Observe common MCP registrations in Python/JS/TS source."""
    text = read_text(path)
    source = rel(path, root)
    result: list[dict[str, Any]] = []
    names = {match.group(1) for match in MCP_REGISTER_RE.finditer(text)}
    for name in sorted(names):
        cap = base_capability(f"repo.mcp.{name}", "mcp", name, source, status="observed")
        cap["interfaces"]["mcp"] = [{"name": name, "schema": "requires-probe", "source_type": "registration"}]
        cap["inputs"] = [{"name": "arguments", "type": "MCP-schema-required"}]
        cap["outputs"] = [{"name": "result", "type": "MCP-schema-required"}]
        result.append(cap)
    return result


def cost_class(kind: str, signals: set[str]) -> str:
    if "network" in signals or "subprocess" in signals:
        return "external-or-process-dependent"
    if "filesystem-write" in signals or "database" in signals:
        return "local-state-dependent"
    return "read-only-low" if kind in {"python_api", "rust_api", "mcp"} else "metadata-low"


def enrich(cap: dict[str, Any], signals: set[str], errors: set[str], fallbacks: set[str], package: dict[str, Any], compatibility: dict[str, Any]) -> None:
    cap["effects"]["observed_signals"] = sorted(signals)
    cap["effects"]["confidence"] = "inferred" if signals else "requires_review"
    cap["errors"] = [{"name": value, "status": "observed-signal"} for value in sorted(errors)]
    cap["fallbacks"] = [{"name": value, "status": "observed-signal"} for value in sorted(fallbacks)]
    cap["cost"]["estimated_class"] = cost_class(cap["kind"], signals)
    cap["dependencies"] = package.get("dependencies", [])
    cap["version"] = {"package": package.get("version"), "generator": GENERATOR_VERSION}
    cap["compatibility"] = compatibility


def discover(root: Path, probe_help: bool, max_files: int) -> dict[str, Any]:
    root = root.resolve()
    signals: set[str] = set()
    errors: set[str] = set()
    fallbacks: set[str] = set()
    package: dict[str, Any] = {"name": root.name, "version": None, "dependencies": []}
    primary_packaging = False
    compatibility: dict[str, Any] = {"python": None, "rust": None, "node": None, "os": "unknown"}
    capabilities: list[dict[str, Any]] = []
    evidence: list[str] = []

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = load_toml(pyproject)
        project = data.get("project", {})
        primary_packaging = bool(project)
        package.update({"name": project.get("name", package["name"]), "version": project.get("version"), "dependencies": project.get("dependencies", [])})
        compatibility["python"] = project.get("requires-python")
        scripts = project.get("scripts", {})
        for name, target in scripts.items():
            cap = base_capability(f"repo.cli.{name}", "cli", name, "pyproject.toml")
            cap["interfaces"]["cli"] = [{"command": name, "entrypoint": target, "help_probe": "not-run"}]
            cap["inputs"] = [{"name": "argv", "type": "command-line"}]
            cap["outputs"] = [{"name": "stdout"}, {"name": "stderr"}, {"name": "exit_status"}]
            capabilities.append(cap)
        evidence.append("pyproject.toml")

    cargo_files = list(root.rglob("Cargo.toml"))
    for cargo in cargo_files:
        data = load_toml(cargo)
        cargo_pkg = data.get("package", {})
        if cargo_pkg:
            package.setdefault("rust", {})
            package["rust"].update({"name": cargo_pkg.get("name"), "version": cargo_pkg.get("version")})
            compatibility["rust"] = cargo_pkg.get("rust-version") or cargo_pkg.get("edition")
            package["dependencies"] = sorted(set(package.get("dependencies", []) + list(data.get("dependencies", {}).keys())))
        for item in data.get("bin", []):
            name = item.get("name")
            if not name:
                continue
            cap = base_capability(f"repo.cli.{name}", "cli", name, rel(cargo, root))
            cap["interfaces"]["cli"] = [{"command": name, "path": item.get("path"), "help_probe": "not-run"}]
            cap["inputs"] = [{"name": "argv", "type": "command-line"}]
            cap["outputs"] = [{"name": "stdout"}, {"name": "stderr"}, {"name": "exit_status"}]
            capabilities.append(cap)
        if cargo.is_file():
            evidence.append(rel(cargo, root))

    package_json = root / "package.json"
    if package_json.is_file():
        data = load_json(package_json)
        if not primary_packaging and (not package.get("name") or package.get("name") == root.name):
            package["name"] = data.get("name", package["name"])
        if not primary_packaging and not package.get("version"):
            package["version"] = data.get("version")
        package["dependencies"] = sorted(set(package.get("dependencies", []) + list(data.get("dependencies", {}).keys())))
        compatibility["node"] = data.get("engines", {}).get("node")
        bins = data.get("bin", {})
        bins = {data.get("name", root.name): bins} if isinstance(bins, str) else bins
        for name, target in bins.items():
            cap = base_capability(f"repo.cli.{name}", "cli", name, "package.json")
            cap["interfaces"]["cli"] = [{"command": name, "entrypoint": target, "help_probe": "not-run"}]
            cap["inputs"] = [{"name": "argv", "type": "command-line"}]
            cap["outputs"] = [{"name": "stdout"}, {"name": "stderr"}, {"name": "exit_status"}]
            capabilities.append(cap)
        evidence.append("package.json")

    config_paths = []
    for path in files_under(root, limit=max_files):
        if path.name in KNOWN_CONFIG_NAMES or path.name.startswith(".env") or path.suffix in {".toml", ".ini", ".cfg"}:
            config_paths.append(rel(path, root))
    for config in sorted(set(config_paths)):
        cap = base_capability(f"repo.config.{config}", "config", config, config, status="observed")
        cap["interfaces"]["config"] = [{"path": config, "format": Path(config).suffix or "plain"}]
        cap["outputs"] = [{"name": "configuration-values"}]
        capabilities.append(cap)
        evidence.append(config)

    for path in files_under(root, (".py",), limit=max_files):
        capabilities.extend(python_caps(path, root, signals, errors, fallbacks))
        capabilities.extend(cli_source_caps(path, root))
        capabilities.extend(mcp_source_caps(path, root))
    for path in files_under(root, (".js", ".ts", ".jsx", ".tsx"), limit=max_files):
        capabilities.extend(mcp_source_caps(path, root))
        capabilities.extend(cli_source_caps(path, root))
    for path in files_under(root, (".rs",), limit=max_files):
        capabilities.extend(rust_caps(path, root, signals, errors, fallbacks))

    for path in files_under(root, (".txt", ".md"), limit=max_files):
        if path.name == "_top.txt" or "cli_help" in path.parts:
            capabilities.extend(cli_source_caps(path, root))

    # The same capability can be visible through packaging metadata, source,
    # and help fixtures. Keep the strongest observed record once per ID.
    unique: dict[str, dict[str, Any]] = {}
    for cap in capabilities:
        current = unique.get(cap["id"])
        if current is None:
            unique[cap["id"]] = cap
            continue
        current["status"] = "observed" if "observed" in {current["status"], cap["status"]} else current["status"]
        current["source"] = sorted(set(current["source"] + cap["source"]))
        current["evidence"] = sorted(set(current["evidence"] + cap["evidence"]))
        for surface in current["interfaces"]:
            current["interfaces"][surface].extend(cap["interfaces"].get(surface, []))
    capabilities = list(unique.values())

    for cap in capabilities:
        enrich(cap, signals, errors, fallbacks, package, compatibility)
        if cap["kind"] == "cli" and probe_help:
            command = cap["name"]
            executable = shutil.which(command)
            if executable:
                try:
                    result = subprocess.run([executable, "--help"], capture_output=True, text=True, timeout=3, check=False)
                    cap["interfaces"]["cli"][0]["help_probe"] = {
                        "executable": executable,
                        "exit_status": result.returncode,
                        "text": (result.stdout or result.stderr)[:20_000],
                    }
                except (OSError, subprocess.TimeoutExpired) as exc:
                    cap["interfaces"]["cli"][0]["help_probe"] = {"error": type(exc).__name__}
            else:
                cap["interfaces"]["cli"][0]["help_probe"] = {"status": "not-installed"}

    overrides = load_json(root / "capability-overrides.json")
    for cap in capabilities:
        override = overrides.get(cap["id"], {}) if isinstance(overrides, dict) else {}
        if isinstance(override, dict):
            for key, value in override.items():
                cap[key] = value
            cap.setdefault("evidence", []).append("capability-overrides.json")

    return {
        "schema_version": "simplicio.capability-inventory/v1",
        "generator": {"name": "generate_capability_inventory.py", "version": GENERATOR_VERSION},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(root),
        "revision": {
            "git_sha": run_git(root, "rev-parse", "HEAD"),
            "git_branch": run_git(root, "branch", "--show-current"),
            "dirty": bool(run_git(root, "status", "--porcelain")),
        },
        "package": package,
        "compatibility": compatibility,
        "observed_signals": {"effects": sorted(signals), "errors": sorted(errors), "fallbacks": sorted(fallbacks)},
        "capabilities": capabilities,
        "evidence": sorted(set(evidence)),
        "review": {"required_for": ["semantic inputs/outputs", "measured cost", "side-effect certainty", "complete MCP schemas"]},
    }


REQUIRED_FIELDS = {
    "id", "kind", "name", "status", "source", "interfaces", "inputs", "outputs",
    "effects", "errors", "fallbacks", "cost", "dependencies", "version", "compatibility", "evidence",
}


def validate_inventory(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "simplicio.capability-inventory/v1":
        errors.append("schema_version must be simplicio.capability-inventory/v1")
    if not isinstance(data.get("capabilities"), list):
        return errors + ["capabilities must be a list"]
    seen: set[str] = set()
    for index, cap in enumerate(data["capabilities"]):
        missing = sorted(REQUIRED_FIELDS - set(cap)) if isinstance(cap, dict) else sorted(REQUIRED_FIELDS)
        if missing:
            errors.append(f"capabilities[{index}] missing: {', '.join(missing)}")
        if isinstance(cap, dict) and cap.get("id") in seen:
            errors.append(f"duplicate capability id: {cap.get('id')}")
        if isinstance(cap, dict):
            seen.add(cap.get("id"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, default=Path("capability-inventory.json"))
    parser.add_argument("--probe-help", action="store_true", help="run --help only for discovered installed CLI commands")
    parser.add_argument("--max-files", type=int, default=20_000)
    parser.add_argument("--validate", type=Path, help="validate an existing inventory instead of generating one")
    args = parser.parse_args()
    if args.validate:
        try:
            data = json.loads(args.validate.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"invalid inventory: {exc}", file=sys.stderr)
            return 2
        problems = validate_inventory(data)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"valid inventory: {len(data.get('capabilities', []))} capabilities")
        return 0
    if not args.repository:
        parser.error("repository is required unless --validate is used")
    if not args.repository.is_dir():
        parser.error(f"repository is not a directory: {args.repository}")
    inventory = discover(args.repository, args.probe_help, max(1, args.max_files))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"generated {len(inventory['capabilities'])} capabilities at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

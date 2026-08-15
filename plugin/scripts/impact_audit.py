#!/usr/bin/env python3
"""simplicio-loop — task impact audit.

Builds a local dependency/impact map for the files a task plans to touch. This is the mechanical
check behind "reflect on scope before editing": if a planned change has reverse dependencies or
related tests outside the declared task surface, the plan is incomplete until those files are at
least reviewed.

Usage:
    python3 scripts/impact_audit.py audit . --file app/service.py --cover app/service.py
    python3 scripts/impact_audit.py audit . --file app/service.py --cover app/service.py --cover tests/test_service.py --json
    python3 scripts/impact_audit.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SEVERITY_ORDER = {"info": 0, "medium": 1, "high": 2}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".simplicio/orchestrator",
    ".playwright-cli",
    ".playwright-mcp",
    ".pytest_cache",
    ".serena",
    ".simplicio",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "venv",
    ".venv",
}

CODE_EXTS = {
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}

PY_FROM_RE = re.compile(r"^\s*from\s+([.\w]+)\s+import\s+", re.M)
PY_IMPORT_RE = re.compile(r"^\s*import\s+([.\w,\s]+)", re.M)
JS_IMPORT_RE = re.compile(r"\bimport\s+(?:[^;]*?\s+from\s+)?[\"'`]([^\"'`]+)[\"'`]", re.M)
JS_EXPORT_FROM_RE = re.compile(r"\bexport\s+[^;]*?\s+from\s+[\"'`]([^\"'`]+)[\"'`]", re.M)
JS_REQUIRE_RE = re.compile(r"\brequire\s*\(\s*[\"'`]([^\"'`]+)[\"'`]\s*\)")
JS_DYNAMIC_IMPORT_RE = re.compile(r"\bimport\s*\(\s*[\"'`]([^\"'`]+)[\"'`]\s*\)")


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    seed: str
    file: str


def relpath(path: Path, root: Path) -> str:
    return os.path.relpath(str(path), str(root)).replace(os.sep, "/")


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        cur = Path(current)
        for name in names:
            path = cur / name
            if path.suffix.lower() in CODE_EXTS and path.stat().st_size <= 1_000_000:
                yield path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def is_test_file(rel: str) -> bool:
    parts = rel.lower().split("/")
    base = os.path.basename(rel).lower()
    return "tests" in parts or "__tests__" in parts or base.startswith("test_") or base.endswith(".test.ts") or base.endswith(".spec.ts") or base.endswith(".test.js") or base.endswith(".spec.js")


def resolve_python_spec(rel: str, spec: str, root: Path) -> list[str]:
    file_path = root / rel
    out: list[str] = []
    level = len(spec) - len(spec.lstrip("."))
    name = spec.lstrip(".")
    parts = [p for p in name.split(".") if p]
    if level:
        base_dir = file_path.parent
        for _ in range(max(level - 1, 0)):
            base_dir = base_dir.parent
        candidates = []
        if parts:
            candidates.append(base_dir.joinpath(*parts).with_suffix(".py"))
            candidates.append(base_dir.joinpath(*parts, "__init__.py"))
        else:
            candidates.append(base_dir / "__init__.py")
    else:
        candidates = [
            root.joinpath(*parts).with_suffix(".py"),
            root.joinpath(*parts, "__init__.py"),
        ] if parts else []
    for cand in candidates:
        if cand.exists():
            out.append(relpath(cand, root))
    return out


def resolve_python_import_spec(spec: str, root: Path) -> list[str]:
    parts = [p for p in spec.split(".") if p]
    if not parts:
        return []
    out: list[str] = []
    for cand in (
        root.joinpath(*parts).with_suffix(".py"),
        root.joinpath(*parts, "__init__.py"),
    ):
        if cand.exists():
            out.append(relpath(cand, root))
    return out


def resolve_python_from_ast(rel: str, module: str | None, level: int, names: list[str], root: Path) -> set[str]:
    file_path = root / rel
    base_dir = file_path.parent
    for _ in range(max(level - 1, 0)):
        base_dir = base_dir.parent
    module_parts = [p for p in (module or "").split(".") if p]
    module_base = base_dir.joinpath(*module_parts) if level else root.joinpath(*module_parts)
    out: set[str] = set()
    for cand in (
        module_base.with_suffix(".py"),
        module_base / "__init__.py",
    ):
        if module_parts and cand.exists():
            out.add(relpath(cand, root))
    for name in names:
        if name == "*":
            continue
        name_parts = [p for p in name.split(".") if p]
        if not name_parts:
            continue
        for cand in (
            module_base.joinpath(*name_parts).with_suffix(".py"),
            module_base.joinpath(*name_parts, "__init__.py"),
        ):
            if cand.exists():
                out.add(relpath(cand, root))
    if not out and level == 0 and module:
        out.update(resolve_python_import_spec(module, root))
    return out


def resolve_js_spec(rel: str, spec: str, root: Path) -> list[str]:
    if not spec.startswith("."):
        return []
    base = (root / rel).parent / spec
    candidates = []
    if base.suffix:
        candidates.append(base)
    else:
        for ext in (".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"):
            candidates.append(base.with_suffix(ext))
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            candidates.append(base / ("index" + ext))
    out = []
    for cand in candidates:
        if cand.exists():
            out.append(relpath(cand, root))
    return out


def extract_python_imports(rel: str, text: str, root: Path) -> set[str]:
    imports: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        for spec in PY_FROM_RE.findall(text):
            imports.update(resolve_python_spec(rel, spec, root))
        for group in PY_IMPORT_RE.findall(text):
            for spec in [x.strip() for x in group.split(",") if x.strip()]:
                imports.update(resolve_python_spec(rel, spec.split(" as ", 1)[0], root))
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.update(resolve_python_import_spec(alias.name, root))
        elif isinstance(node, ast.ImportFrom):
            imports.update(
                resolve_python_from_ast(
                    rel,
                    node.module,
                    node.level,
                    [alias.name for alias in node.names],
                    root,
                )
            )
    return imports


def extract_imports(rel: str, text: str, root: Path) -> set[str]:
    imports: set[str] = set()
    if rel.endswith(".py"):
        imports.update(extract_python_imports(rel, text, root))
    else:
        specs = []
        specs.extend(JS_IMPORT_RE.findall(text))
        specs.extend(JS_EXPORT_FROM_RE.findall(text))
        specs.extend(JS_REQUIRE_RE.findall(text))
        specs.extend(JS_DYNAMIC_IMPORT_RE.findall(text))
        for spec in specs:
            imports.update(resolve_js_spec(rel, spec, root))
    imports.discard(rel)
    return imports


def build_graph(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    imports_by_file: dict[str, set[str]] = {}
    reverse_by_file: dict[str, set[str]] = {}
    texts: dict[str, str] = {}
    for path in iter_files(root):
        rel = relpath(path, root)
        text = read_text(path)
        texts[rel] = text
        imports = extract_imports(rel, text, root)
        imports_by_file[rel] = imports
        for dep in imports:
            reverse_by_file.setdefault(dep, set()).add(rel)
    return imports_by_file, reverse_by_file, texts


def walk_graph(graph: dict[str, set[str]], starts: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(starts)
    while stack:
        node = stack.pop()
        for nxt in graph.get(node, set()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def related_tests(seed: str, reverse_closure: set[str], texts: dict[str, str]) -> set[str]:
    hits = {rel for rel in reverse_closure if is_test_file(rel)}
    stem = Path(seed).stem.lower()
    for rel in texts:
        if not is_test_file(rel):
            continue
        text_l = texts.get(rel, "").lower()
        if stem and stem in text_l:
            hits.add(rel)
    return hits


def audit(root: Path, seeds: list[str], cover: list[str]) -> dict:
    root = root.resolve()
    imports_by_file, reverse_by_file, texts = build_graph(root)
    norm_cover = {c.replace(os.sep, "/") for c in cover}
    issues: list[Issue] = []
    seed_reports = []
    impacted_union: set[str] = set()

    for seed in seeds:
        seed_rel = seed.replace(os.sep, "/")
        direct_imports = sorted(imports_by_file.get(seed_rel, set()))
        all_imports = walk_graph(imports_by_file, [seed_rel])
        all_imports.discard(seed_rel)
        direct_imports_set = set(direct_imports)
        transitive_imports = sorted(all_imports - direct_imports_set)

        direct_imported_by = sorted(reverse_by_file.get(seed_rel, set()))
        all_imported_by = walk_graph(reverse_by_file, [seed_rel])
        all_imported_by.discard(seed_rel)
        direct_imported_by_set = set(direct_imported_by)
        transitive_imported_by = sorted(all_imported_by - direct_imported_by_set)

        tests = sorted(related_tests(seed_rel, all_imported_by, texts))
        impacted = sorted(set(all_imports) | set(all_imported_by) | set(tests) | {seed_rel})
        impacted_union.update(impacted)

        for file in sorted(all_imported_by):
            if file not in norm_cover:
                issues.append(Issue(
                    severity="high",
                    code="uncovered_reverse_dependency",
                    message="A file imports or depends on the changed file but is outside the declared review/edit surface.",
                    seed=seed_rel,
                    file=file,
                ))
        for file in tests:
            if file not in norm_cover and file not in all_imported_by:
                issues.append(Issue(
                    severity="medium",
                    code="uncovered_related_test",
                    message="A related test exists but is outside the declared review/edit surface.",
                    seed=seed_rel,
                    file=file,
                ))
        for file in sorted(all_imports):
            if file not in norm_cover:
                issues.append(Issue(
                    severity="medium",
                    code="uncovered_local_dependency",
                    message="A local dependency of the changed file is outside the declared review/edit surface.",
                    seed=seed_rel,
                    file=file,
                ))

        seed_reports.append({
            "seed": seed_rel,
            "imports": direct_imports,
            "transitive_imports": transitive_imports,
            "imported_by": direct_imported_by,
            "transitive_imported_by": transitive_imported_by,
            "related_tests": tests,
            "impacted": impacted,
        })

    result = {
        "schema": "simplicio.impact-audit/v1",
        "root": str(root),
        "seeds": seeds,
        "cover": sorted(norm_cover),
        "counts": {
            "seed_files": len(seeds),
            "covered_files": len(norm_cover),
            "impacted_files": len(impacted_union),
            "issues": len(issues),
            "high_issues": sum(1 for i in issues if i.severity == "high"),
            "medium_issues": sum(1 for i in issues if i.severity == "medium"),
        },
        "reports": seed_reports,
        "issues": [asdict(i) for i in sorted(issues, key=lambda i: (-SEVERITY_ORDER[i.severity], i.seed, i.file, i.code))],
    }
    return result


def print_human(result: dict, fail_on: str) -> None:
    c = result["counts"]
    failed = failing_issues(result, fail_on)
    print("impact-audit: %s" % ("PASS" if not failed else "FAIL"))
    print("  seeds=%d covered=%d impacted=%d issues=%d high=%d medium=%d" % (
        c["seed_files"], c["covered_files"], c["impacted_files"], c["issues"], c["high_issues"], c["medium_issues"]
    ))
    for report in result["reports"]:
        print("  seed %s" % report["seed"])
        if report["imports"]:
            print("    imports: %s" % ", ".join(report["imports"]))
        if report["transitive_imports"]:
            print("    transitive_imports: %s" % ", ".join(report["transitive_imports"]))
        if report["imported_by"]:
            print("    imported_by: %s" % ", ".join(report["imported_by"]))
        if report["transitive_imported_by"]:
            print("    transitive_imported_by: %s" % ", ".join(report["transitive_imported_by"]))
        if report["related_tests"]:
            print("    tests: %s" % ", ".join(report["related_tests"]))
    for issue in result["issues"][:50]:
        print("  [%s] %s seed=%s file=%s — %s" % (
            issue["severity"], issue["code"], issue["seed"], issue["file"], issue["message"]
        ))


def failing_issues(result: dict, fail_on: str) -> list[dict]:
    threshold = SEVERITY_ORDER[fail_on]
    return [i for i in result["issues"] if SEVERITY_ORDER[i["severity"]] >= threshold]


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "app").mkdir()
        (root / "ui").mkdir()
        (root / "tests").mkdir()
        (root / "app" / "service.py").write_text(
            "from .util import helper\n\ndef compute():\n    return helper()\n",
            encoding="utf-8",
        )
        (root / "app" / "util.py").write_text(
            "def helper():\n    return 1\n",
            encoding="utf-8",
        )
        (root / "app" / "controller.py").write_text(
            "from app.service import compute\n\nprint(compute())\n",
            encoding="utf-8",
        )
        (root / "ui" / "screen.py").write_text(
            "from app.controller import compute\n\nprint(compute())\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_service.py").write_text(
            "from app.service import compute\n\ndef test_compute():\n    assert compute() == 1\n",
            encoding="utf-8",
        )
        fail = audit(root, ["app/service.py"], ["app/service.py"])
        codes = {i["code"] for i in fail["issues"]}
        assert "uncovered_reverse_dependency" in codes, fail
        assert "tests/test_service.py" in fail["reports"][0]["related_tests"], fail
        assert "ui/screen.py" in {i["file"] for i in fail["issues"] if i["code"] == "uncovered_reverse_dependency"}, fail
        ok = audit(
            root,
            ["app/service.py"],
            ["app/service.py", "app/util.py", "app/controller.py", "ui/screen.py", "tests/test_service.py"],
        )
        assert ok["counts"]["issues"] == 0, ok
    print("impact_audit selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit task scope against file dependencies.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    audit_p = sub.add_parser("audit")
    audit_p.add_argument("root", nargs="?", default=".")
    audit_p.add_argument("--file", action="append", default=[], help="Seed file the task plans to touch.")
    audit_p.add_argument("--cover", action="append", default=[], help="File explicitly in scope for read/edit/test review.")
    audit_p.add_argument("--json", action="store_true")
    audit_p.add_argument("--fail-on", choices=["high", "medium", "info"], default="high")
    sub.add_parser("selftest")
    args = parser.parse_args()

    if args.cmd == "selftest":
        return selftest()
    if not args.file:
        print("impact-audit: BLOCKED — pass at least one --file seed.", flush=True)
        return 2
    cover = list(dict.fromkeys(args.cover + args.file))
    result = audit(Path(args.root), [f.replace(os.sep, "/") for f in args.file], cover)
    failed = failing_issues(result, args.fail_on)
    result["fail_on"] = args.fail_on
    result["blocking_issues"] = failed
    result["counts"]["blocking_issues"] = len(failed)
    result["ok"] = not failed
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result, args.fail_on)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

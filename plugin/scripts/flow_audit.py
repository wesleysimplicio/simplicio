#!/usr/bin/env python3
"""simplicio-loop — full-stack flow audit.

Builds a static, deterministic map of UI actions, frontend HTTP calls, backend endpoints, and
backend service calls. It is intentionally heuristic, but fail-closed on the gaps that are almost
always real integration defects:

  * a frontend API call whose path has no backend endpoint anywhere in the scanned tree
  * a backend endpoint that is still a stub / TODO / 501 / NotImplemented path

Medium findings are surfaced for human/agent review but do not fail the default gate unless
`--fail-on medium` is requested. This keeps ordinary local UI buttons from becoming false P0s while
still making the loose ends visible.

Usage:
    python3 scripts/flow_audit.py audit . --fail-on high
    python3 scripts/flow_audit.py audit . --json
    python3 scripts/flow_audit.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

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
    "scripts",
    "target",
    "test",
    "tests",
    "__tests__",
    "venv",
    ".venv",
}

TEXT_EXTS = {
    ".cs",
    ".go",
    ".html",
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

FRONT_HINTS = (
    "/frontend/",
    "/front/",
    "/client/",
    "/clients/",
    "/web/",
    "/ui/",
    "/pages/",
    "/components/",
    "/views/",
    "/screens/",
    "/app/",
)

BACK_HINTS = (
    "/backend/",
    "/back/",
    "/server/",
    "/api/",
    "/apis/",
    "/controller",
    "/controllers/",
    "/route",
    "/routes/",
    "/handler",
    "/handlers/",
    "/service",
    "/services/",
)

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}

ENDPOINT_PATTERNS = [
    # Express/Fastify/Koa-ish: app.get("/x"), router.post("/x")
    re.compile(r"(?<!@)\b(?:app|api|router|routes|server)\.(get|post|put|patch|delete|options|head)\s*\(\s*[\"'`]([^\"'`]+)[\"'`]", re.I),
    # Decorator frameworks: @app.get("/x"), @router.post("/x")
    re.compile(r"@\w+\.(get|post|put|patch|delete|options|head)\s*\(\s*[\"'`]([^\"'`]+)[\"'`]", re.I),
    # Gin/Echo-ish: router.GET("/x")
    re.compile(r"\b(?:r|router|group|api)\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s*\(\s*[\"'`]([^\"'`]+)[\"'`]"),
]

FLASK_ROUTE_RE = re.compile(
    r"@\w+\.route\s*\(\s*[\"'`]([^\"'`]+)[\"'`](?P<tail>[^)]*)\)", re.I | re.S
)
SPRING_ROUTE_RE = re.compile(
    r"@(Get|Post|Put|Patch|Delete|Request)Mapping\s*(?:\(\s*)?(?:value\s*=\s*)?[\"'`]([^\"'`]*)[\"'`]",
    re.I,
)
ASPNET_ROUTE_RE = re.compile(r"\[Http(Get|Post|Put|Patch|Delete)(?:\s*\(\s*\"([^\"]*)\")?\]", re.I)
DJANGO_PATH_RE = re.compile(r"\b(?:path|re_path)\s*\(\s*[\"'`]([^\"'`]+)[\"'`]", re.I)
GO_HANDLE_RE = re.compile(r"\bhttp\.HandleFunc\s*\(\s*[\"'`]([^\"'`]+)[\"'`]", re.I)

FETCH_RE = re.compile(r"\bfetch\s*\(\s*([\"'`])([^\"'`]+)\1", re.I)
AXIOS_METHOD_RE = re.compile(
    r"\b(?:axios|api|client|http|httpClient)\.(get|post|put|patch|delete)\s*\(\s*([\"'`])([^\"'`]+)\2",
    re.I,
)
AXIOS_DIRECT_RE = re.compile(r"\baxios\s*\(\s*([\"'`])([^\"'`]+)\1", re.I)
REQUESTS_RE = re.compile(
    r"\b(?:requests|httpx|client|session)\.(get|post|put|patch|delete)\s*\(\s*([\"'`])([^\"'`]+)\2",
    re.I,
)
RUBY_NET_RE = re.compile(r"\bNet::HTTP::(Get|Post|Put|Patch|Delete)\b.*?([\"'`])([^\"'`]+)\2", re.I | re.S)

UI_ACTION_RE = re.compile(
    r"(<(?:button|a|form|input|select|textarea)\b[^>]*(?:onClick|onSubmit|@click|v-on:click|onclick|onsubmit)[^>]*>)"
    r"|(\b(?:onClick|onSubmit|addEventListener)\s*[=:/(])",
    re.I,
)

STUB_RE = re.compile(
    r"\b(TODO|FIXME|NotImplemented|NotImplementedError|UnsupportedOperationException|unimplemented!|todo!|pass\b|return\s+501|status\s*\(\s*501|throw\s+new\s+Error\s*\(\s*[\"'`][^\"'`]*(?:todo|not implemented|stub))",
    re.I,
)

# The persistence layer (#79): flow_audit previously stopped at the HTTP boundary — an endpoint
# that never reaches its repository/ORM/SQL, a dead DB call, a service method that swallows the
# write, was invisible. These patterns cover raw SQL plus the common ORM/driver call shapes across
# languages; intentionally broad (a persistence check is inherently heuristic, same spirit as the
# endpoint/call regexes above) rather than an exhaustive per-ORM grammar.
DB_PATTERNS = [
    re.compile(r"\b(?:SELECT\s+.+?\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b", re.I),
    re.compile(r"\bprisma\.\w+\.(?:findMany|findUnique|findFirst|create|update|delete|upsert|count)\s*\("),
    re.compile(r"\b(?:sequelize|Model|\w+Model)\.(?:findAll|findOne|findByPk|create|update|destroy|bulkCreate)\s*\("),
    re.compile(r"\bgetRepository\s*\(|@Entity\b|@Repository\b|\.createQueryBuilder\s*\("),
    re.compile(r"\bDB::table\s*\(|::class\)\s*->|Model::(?:find|create|where|all)\s*\(|->save\s*\(\s*\)"),
    re.compile(r"\bsession\.query\s*\(|db\.session\.(?:add|commit|query)\s*\("),
    re.compile(r"\.objects\.(?:filter|all|get|create|update|get_or_create)\s*\("),
    re.compile(r"\bmongoose\.model\s*\(|\.findOne\s*\(|\.insertOne\s*\(|\.updateOne\s*\(|\.deleteOne\s*\("),
    re.compile(r"\b(?:psycopg2|pymysql|sqlite3)\.connect\s*\(|mongoose\.connect\s*\(|createConnection\s*\("),
    re.compile(r"\bcursor\.execute\s*\(|\.query\s*\(\s*[\"'`]|\brepository\.\w+\s*\("),
]


@dataclass
class Ref:
    method: str
    path: str
    file: str
    line: int
    source: str
    raw: str


@dataclass
class UiAction:
    file: str
    line: int
    snippet: str
    has_nearby_call: bool


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    file: str
    line: int
    path: str = ""
    method: str = ""


def relpath(path: Path, root: Path) -> str:
    return os.path.relpath(str(path), str(root)).replace(os.sep, "/")


def iter_files(root: Path) -> Iterable[Path]:
    for current, dirs, names in os.walk(root):
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS
            and not d.startswith(".cache")
            and not d.startswith(".pytest-")
        ]
        cur = Path(current)
        for name in names:
            path = cur / name
            if path.suffix.lower() in TEXT_EXTS and path.stat().st_size <= 1_000_000:
                yield path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def line_for(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def line_window(text: str, line: int, radius: int = 12) -> str:
    lines = text.splitlines()
    start = max(0, line - radius - 1)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start:end])


def classify_file(rel: str, text: str, endpoints_found: bool) -> str:
    rel_l = "/" + rel.lower()
    if endpoints_found or any(h in rel_l for h in BACK_HINTS):
        return "backend"
    if any(h in rel_l for h in FRONT_HINTS) or Path(rel).suffix.lower() in {".jsx", ".tsx", ".vue", ".svelte", ".html"}:
        return "frontend"
    if "react" in text[:2000].lower() or "onclick" in text.lower() or "onsubmit" in text.lower():
        return "frontend"
    return "unknown"


def extract_method_from_tail(tail: str, default: str = "GET") -> str:
    m = re.search(r"\bmethod\s*:\s*([\"'`])([A-Z]+)\1", tail or "", re.I)
    if m:
        return m.group(2).upper()
    return default


def route_methods_from_flask_tail(tail: str) -> list[str]:
    m = re.search(r"methods\s*=\s*\[([^\]]+)\]", tail or "", re.I)
    if not m:
        return ["GET"]
    methods = re.findall(r"[\"'`]([A-Z]+)[\"'`]", m.group(1), re.I)
    return [x.upper() for x in methods] or ["GET"]


def normalize_path(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    parsed = urlparse(raw)
    path = parsed.path if parsed.scheme and parsed.netloc else raw
    path = path.split("?", 1)[0].split("#", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", ":param", path)
    path = re.sub(r"\{[^}/]+\}", ":param", path)
    path = re.sub(r"<[^>/]+>", ":param", path)
    path = re.sub(r"\[[^]/]+\]", ":param", path)
    path = re.sub(r":\w+", ":param", path)
    path = re.sub(r"/+", "/", path)
    if not path.startswith("/"):
        return None
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def path_variants(path: str) -> set[str]:
    variants = {path}
    for prefix in ("/api/v1", "/api", "/v1"):
        if path == prefix:
            variants.add("/")
        elif path.startswith(prefix + "/"):
            variants.add(path[len(prefix):] or "/")
    return variants


def paths_match(a: str, b: str) -> bool:
    return bool(path_variants(a) & path_variants(b))


def methods_match(client_method: str, endpoint_method: str) -> bool:
    return client_method in {"ANY", endpoint_method} or endpoint_method == "ANY"


def add_ref(refs: list[Ref], method: str, raw_path: str, file: str, line: int, source: str) -> None:
    path = normalize_path(raw_path)
    if not path:
        return
    refs.append(Ref(method=method.upper(), path=path, file=file, line=line, source=source, raw=raw_path))


def extract_endpoints(text: str, rel: str) -> list[Ref]:
    refs: list[Ref] = []
    for rx in ENDPOINT_PATTERNS:
        for m in rx.finditer(text):
            add_ref(refs, m.group(1), m.group(2), rel, line_for(text, m.start()), "endpoint")
    for m in FLASK_ROUTE_RE.finditer(text):
        for method in route_methods_from_flask_tail(m.group("tail")):
            add_ref(refs, method, m.group(1), rel, line_for(text, m.start()), "endpoint")
    for m in SPRING_ROUTE_RE.finditer(text):
        method = "ANY" if m.group(1).lower() == "request" else m.group(1).replace("Mapping", "").upper()
        add_ref(refs, method, m.group(2) or "/", rel, line_for(text, m.start()), "endpoint")
    for m in ASPNET_ROUTE_RE.finditer(text):
        add_ref(refs, m.group(1), "/" + (m.group(2) or ""), rel, line_for(text, m.start()), "endpoint")
    for m in DJANGO_PATH_RE.finditer(text):
        add_ref(refs, "ANY", "/" + m.group(1), rel, line_for(text, m.start()), "endpoint")
    for m in GO_HANDLE_RE.finditer(text):
        add_ref(refs, "ANY", m.group(1), rel, line_for(text, m.start()), "endpoint")
    return refs


def extract_http_calls(text: str, rel: str, source: str) -> list[Ref]:
    refs: list[Ref] = []
    for m in FETCH_RE.finditer(text):
        tail = text[m.end():m.end() + 260]
        add_ref(refs, extract_method_from_tail(tail), m.group(2), rel, line_for(text, m.start()), source)
    for m in AXIOS_DIRECT_RE.finditer(text):
        tail = text[m.end():m.end() + 260]
        add_ref(refs, extract_method_from_tail(tail, default="ANY"), m.group(2), rel, line_for(text, m.start()), source)
    for m in AXIOS_METHOD_RE.finditer(text):
        add_ref(refs, m.group(1), m.group(3), rel, line_for(text, m.start()), source)
    for m in REQUESTS_RE.finditer(text):
        add_ref(refs, m.group(1), m.group(3), rel, line_for(text, m.start()), source)
    for m in RUBY_NET_RE.finditer(text):
        add_ref(refs, m.group(1), m.group(3), rel, line_for(text, m.start()), source)
    return refs


def extract_ui_actions(text: str, rel: str, frontend_calls: list[Ref]) -> list[UiAction]:
    actions: list[UiAction] = []
    for m in UI_ACTION_RE.finditer(text):
        line = line_for(text, m.start())
        local_handler = line_window(text, line, radius=0)
        nearby = bool(FETCH_RE.search(local_handler) or AXIOS_METHOD_RE.search(local_handler) or AXIOS_DIRECT_RE.search(local_handler))
        snippet = (m.group(0) or "").strip().replace("\n", " ")
        actions.append(UiAction(file=rel, line=line, snippet=snippet[:180], has_nearby_call=nearby))
    return actions


def endpoint_has_stub(text: str, line: int) -> bool:
    lines = text.splitlines()
    window = "\n".join(lines[max(0, line - 1): min(len(lines), line + 8)])
    return bool(STUB_RE.search(window))


def endpoint_has_persistence(text: str, line: int, radius: int = 30, next_endpoint_line: int | None = None) -> bool:
    """A wider window than the stub check: the persistence call is often deeper in the handler
    body, or delegated to a same-file service/repository function a few lines below.

    Bounded by `next_endpoint_line` (the next endpoint's start line in the SAME file, if any) so
    the window never leaks into a neighboring handler's body — two closely-defined endpoints would
    otherwise let one handler's real DB call falsely "cover" its stub-free-but-DB-free neighbor.
    """
    lines = text.splitlines()
    end = min(len(lines), line + radius)
    if next_endpoint_line is not None:
        end = min(end, next_endpoint_line - 1)
    window = "\n".join(lines[max(0, line - 1): max(line, end)])
    return any(rx.search(window) for rx in DB_PATTERNS)


def has_matching_endpoint(call: Ref, endpoints: list[Ref]) -> bool:
    return any(paths_match(call.path, ep.path) and methods_match(call.method, ep.method) for ep in endpoints)


def audit(root: Path) -> dict:
    root = root.resolve()
    endpoints: list[Ref] = []
    frontend_calls: list[Ref] = []
    backend_calls: list[Ref] = []
    ui_actions: list[UiAction] = []
    file_kinds: dict[str, str] = {}
    texts: dict[str, str] = {}

    for path in iter_files(root):
        rel = relpath(path, root)
        text = read_text(path)
        texts[rel] = text
        file_endpoints = extract_endpoints(text, rel)
        kind = classify_file(rel, text, bool(file_endpoints))
        file_kinds[rel] = kind
        endpoints.extend(file_endpoints)
        calls = extract_http_calls(text, rel, "frontend_call" if kind == "frontend" else "backend_call")
        if kind == "frontend":
            frontend_calls.extend(calls)
            ui_actions.extend(extract_ui_actions(text, rel, calls))
        elif kind == "backend":
            backend_calls.extend(calls)

    issues: list[Issue] = []
    for call in frontend_calls:
        if not has_matching_endpoint(call, endpoints):
            issues.append(Issue(
                severity="high",
                code="frontend_call_without_backend_endpoint",
                message="Frontend HTTP call has no matching backend endpoint in the scanned workspace.",
                file=call.file,
                line=call.line,
                path=call.path,
                method=call.method,
            ))

    endpoint_lines_by_file: dict[str, list[int]] = {}
    for ep in endpoints:
        endpoint_lines_by_file.setdefault(ep.file, []).append(ep.line)
    for lines_ in endpoint_lines_by_file.values():
        lines_.sort()

    def _next_endpoint_line(ep: Ref) -> int | None:
        siblings = endpoint_lines_by_file.get(ep.file, [])
        later = [ln for ln in siblings if ln > ep.line]
        return min(later) if later else None

    for ep in endpoints:
        if endpoint_has_stub(texts.get(ep.file, ""), ep.line):
            issues.append(Issue(
                severity="high",
                code="backend_endpoint_stub",
                message="Backend endpoint appears to be incomplete or stubbed.",
                file=ep.file,
                line=ep.line,
                path=ep.path,
                method=ep.method,
            ))
        elif ep.method.upper() != "GET" and not endpoint_has_persistence(
                texts.get(ep.file, ""), ep.line, next_endpoint_line=_next_endpoint_line(ep)):
            # #79: the persistence-layer link of the flow (endpoint -> repository/ORM/SQL) is
            # otherwise invisible. Scoped to non-GET (write) endpoints only — a read-only GET with
            # no observed DB call is common and not inherently suspicious (cache, proxy, static/
            # health-check response); a mutating endpoint with no observed persistence call is the
            # "dead write" defect this closes. Medium, not high: heuristic, same as the other
            # loose-end findings below — a genuine defect needs human/agent confirmation, not an
            # automatic hard fail.
            issues.append(Issue(
                severity="medium",
                code="backend_endpoint_without_persistence_call",
                message="Backend endpoint has no observed repository/ORM/SQL call nearby; verify "
                        "whether the write actually persists or the call is delegated elsewhere.",
                file=ep.file,
                line=ep.line,
                path=ep.path,
                method=ep.method,
            ))

    for action in ui_actions:
        if not action.has_nearby_call:
            issues.append(Issue(
                severity="medium",
                code="ui_action_without_observed_backend_call",
                message="Interactive UI action has no nearby observed backend call; verify whether it is local-only or a missing integration.",
                file=action.file,
                line=action.line,
            ))

    for ep in endpoints:
        if not any(paths_match(ep.path, call.path) and methods_match(call.method, ep.method) for call in frontend_calls):
            issues.append(Issue(
                severity="medium",
                code="backend_endpoint_without_frontend_call",
                message="Backend endpoint has no observed frontend caller; verify whether it is internal, external-only, or orphaned.",
                file=ep.file,
                line=ep.line,
                path=ep.path,
                method=ep.method,
            ))

    for call in backend_calls:
        if call.path.startswith("/") and not has_matching_endpoint(call, endpoints):
            issues.append(Issue(
                severity="medium",
                code="backend_service_call_without_local_endpoint",
                message="Backend/service call points to a local-looking path with no matching endpoint in the scanned workspace.",
                file=call.file,
                line=call.line,
                path=call.path,
                method=call.method,
            ))

    counts = {
        "files": len(file_kinds),
        "frontend_files": sum(1 for k in file_kinds.values() if k == "frontend"),
        "backend_files": sum(1 for k in file_kinds.values() if k == "backend"),
        "endpoints": len(endpoints),
        "frontend_calls": len(frontend_calls),
        "backend_service_calls": len(backend_calls),
        "ui_actions": len(ui_actions),
        "issues": len(issues),
        "high_issues": sum(1 for i in issues if i.severity == "high"),
        "medium_issues": sum(1 for i in issues if i.severity == "medium"),
        "persistence_gaps": sum(1 for i in issues if i.code == "backend_endpoint_without_persistence_call"),
    }
    return {
        "schema": "simplicio.flow-audit/v1",
        "root": str(root),
        "ok": counts["high_issues"] == 0,
        "counts": counts,
        "endpoints": [asdict(x) for x in endpoints],
        "frontend_calls": [asdict(x) for x in frontend_calls],
        "backend_service_calls": [asdict(x) for x in backend_calls],
        "ui_actions": [asdict(x) for x in ui_actions],
        "issues": [asdict(x) for x in sorted(issues, key=lambda i: (-SEVERITY_ORDER[i.severity], i.file, i.line, i.code))],
    }


def print_human(result: dict, fail_on: str) -> None:
    c = result["counts"]
    print("flow-audit: %s" % ("PASS" if not _failing_issues(result, fail_on) else "FAIL"))
    print(
        "  files=%d frontend=%d backend=%d endpoints=%d frontend_calls=%d service_calls=%d ui_actions=%d"
        % (
            c["files"],
            c["frontend_files"],
            c["backend_files"],
            c["endpoints"],
            c["frontend_calls"],
            c["backend_service_calls"],
            c["ui_actions"],
        )
    )
    if not result["issues"]:
        print("  issues=0")
        return
    print("  issues=%d high=%d medium=%d" % (c["issues"], c["high_issues"], c["medium_issues"]))
    for issue in result["issues"][:50]:
        loc = "%s:%s" % (issue["file"], issue["line"])
        target = (" %s %s" % (issue.get("method") or "", issue.get("path") or "")).rstrip()
        print("  [%s] %s %s%s — %s" % (issue["severity"], issue["code"], loc, target, issue["message"]))
    if len(result["issues"]) > 50:
        print("  ... %d more issues omitted; rerun with --json" % (len(result["issues"]) - 50))


def _failing_issues(result: dict, fail_on: str) -> list[dict]:
    threshold = SEVERITY_ORDER[fail_on]
    return [i for i in result["issues"] if SEVERITY_ORDER[i["severity"]] >= threshold]


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "frontend").mkdir()
        (root / "backend").mkdir()
        (root / "frontend" / "Login.tsx").write_text(
            """
export function Login() {
  return <div>
    <button onClick={() => fetch("/api/login", { method: "POST" })}>Login</button>
    <button onClick={() => fetch("/api/missing")}>Missing</button>
    <button onClick={() => setOpen(true)}>Local only</button>
  </div>
}
""".strip(),
            encoding="utf-8",
        )
        (root / "backend" / "routes.py").write_text(
            """
@app.post("/api/login")
def login():
    raise NotImplementedError("TODO wire auth")

@app.get("/api/users")
def users():
    return []

@app.post("/api/orders")
def create_order():
    order = Order(item=request.json["item"])
    return {"ok": True}

@app.post("/api/orders2")
def create_order_persisted():
    order = Order(item=request.json["item"])
    db.session.add(order)
    db.session.commit()
    return {"ok": True}
""".strip(),
            encoding="utf-8",
        )
        result = audit(root)
        codes = {i["code"] for i in result["issues"]}
        assert "frontend_call_without_backend_endpoint" in codes, result
        assert "backend_endpoint_stub" in codes, result
        assert "ui_action_without_observed_backend_call" in codes, result
        assert "backend_endpoint_without_persistence_call" in codes, result
        assert result["counts"]["endpoints"] == 4, result
        assert result["counts"]["persistence_gaps"] == 1, result
        persistence_issues = [i for i in result["issues"]
                              if i["code"] == "backend_endpoint_without_persistence_call"]
        assert len(persistence_issues) == 1 and persistence_issues[0]["path"] == "/api/orders", result
        assert result["counts"]["frontend_calls"] == 2, result
    print("flow_audit selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit full-stack flow coverage.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    audit_p = sub.add_parser("audit")
    audit_p.add_argument("root", nargs="?", default=".")
    audit_p.add_argument("--json", action="store_true")
    audit_p.add_argument("--fail-on", choices=["high", "medium", "info"], default="high")
    self_p = sub.add_parser("selftest")
    _ = self_p
    args = parser.parse_args()
    if args.cmd == "selftest":
        return selftest()
    result = audit(Path(args.root))
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result, args.fail_on)
    return 1 if _failing_issues(result, args.fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())

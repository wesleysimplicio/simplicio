#!/usr/bin/env python3
"""pr_dod_review.py — mechanical DoD + ACs verdict for open PRs.

When all issues are claimed (DEFER_ACTIVE_CLAIM), a session with no work to
claim reviews OPEN PRs against the 7-dimension Definition of Done (CLAUDE.md)
and the frozen acceptance criteria of the underlying issue, commenting what
remains for the claiming agent.

Subcommands:
  check   Print a verdict JSON to stdout (PR body + referenced issue body).
  --post  Publish the verdict as a PR comment via `gh` (requires `gh` auth).
  selftest Run 13 embedded assertions, exit non-zero on any failure.

Stdlib only. Deterministic. No network except in --post mode (gh).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Dict, List, Tuple

# The 7 Definition-of-Done dimensions (CLAUDE.md / SKILL.md).
DOD_DIMENSIONS: List[str] = [
    "implementation",
    "unit_tests",
    "integration_tests",
    "system_tests",
    "regression_tests",
    "perf_benchmark",
    "min_coverage",
]

# Keywords that, when present in a PR body, indicate a dimension is addressed.
DOD_SIGNALS: Dict[str, List[str]] = {
    "implementation": ["## implementação", "implementacao", "the change itself", "## what was implemented"],
    "unit_tests": ["unit", "pytest", "test_", "unittest", "coverage of the new"],
    "integration_tests": ["integration", "against its real collaborators", "no mocks"],
    "system_tests": ["system test", "end-to-end", "end to end", "e2e", "cli/api surface"],
    "regression_tests": ["regression", "existing suite still green", "no prior behavior"],
    "perf_benchmark": ["benchmark", "latency", "throughput", "measured number", "perf "],
    "min_coverage": ["coverage", "85%", "branch coverage", "line/branch"],
}

# Compatibility vocabulary used by the structured ``review`` API.  These stable Portuguese
# identifiers match the seven dimensions named in the loop contract while accepting the English
# evidence commonly found in PR descriptions.
REVIEW_DIMENSIONS: List[Tuple[str, List[str]]] = [
    ("implementacao", ["## summary", "## implementação", "## implementacao", "implemented"]),
    ("testes_unitarios", DOD_SIGNALS["unit_tests"]),
    ("testes_integracao", DOD_SIGNALS["integration_tests"]),
    ("testes_sistema", DOD_SIGNALS["system_tests"]),
    ("testes_regressao", DOD_SIGNALS["regression_tests"]),
    ("performance_benchmark", DOD_SIGNALS["perf_benchmark"]),
    ("cobertura_minima", DOD_SIGNALS["min_coverage"]),
]

REVIEW_NA_SIGNALS: Dict[str, List[str]] = {
    "testes_unitarios": ["no new logic"],
    "testes_integracao": ["no cross-service seam", "no integration seam"],
    "testes_sistema": ["no full run flow", "no end-to-end flow"],
    "testes_regressao": ["nothing that could regress", "no behavior change"],
    "performance_benchmark": ["no hot path", "no performance impact"],
    "cobertura_minima": ["nothing to measure", "no executable code"],
}

NEGATIVE_EVIDENCE = re.compile(
    r"\b(?:fail(?:ed|s|ure|ing)?|broken|red|missing|pending|todo|blocked|unknown|"
    r"attempted|incomplete|revert(?:ed|s|ing)?|roll(?:ed)?\s+back|rollback|unavailable|"
    r"no\s+longer\s+(?:pass(?:es|ed|ing)?|improve(?:s|d|ing)?|work(?:s|ed|ing)?)|"
    r"nothing\s+(?:was\s+)?implemented|no\s+(?:implementation|change|code|tests?|evidence|coverage|benchmark)|"
    r"unverified|uncovered|skipped|regress(?:ed|es|ing)|worsen(?:ed|s|ing)?|"
    r"not\s+(?:run|executed|verified|tested|available|pass(?:ed|ing)?|green|improved|"
    r"successful|complete(?:d)?|implemented|covered)|"
    r"(?:did|does|do|is|are|was|were|has|have|had|can|could|should|would|will)\s+not\s+"
    r"(?:pass(?:ed|ing)?|run|execute(?:d)?|verif(?:y|ied)|test(?:ed)?|succeed(?:ed)?|"
    r"complete(?:d)?|implement(?:ed)?|cover(?:ed)?|improve(?:d)?|work(?:ing)?)|"
    r"(?:is|are|has|have|had|did|was|were|does|do|can|could|should|would|will)n't|won't|"
    r"below\s+(?:the\s+)?(?:threshold|minimum))",
    re.IGNORECASE,
)
FUTURE_OR_HISTORICAL_EVIDENCE = re.compile(
    r"\b(?:should|would|could|will|planned|expected|future|tomorrow|later|eventually|"
    r"previous|previously|older|historically|yesterday)\b|"
    r"\bbefore(?:\s+(?:these|this|the))?\b|"
    r"\blast\s+(?:week|month|release|version|run|build)\b|"
    r"\bprior\s+(?:commit|release|version|run|build)\b|"
    r"\bafter\s+(?:the\s+)?(?:planned|future|proposed)\s+(?:fix|change|work)\b",
    re.IGNORECASE,
)
POSITIVE_EVIDENCE = re.compile(
    r"\b(?:pass(?:ed|es|ing)?|green|verified|successful(?:ly)?|executed|ran|runs?|"
    r"cover(?:ed|s)?|hit|measured|improved)\b",
    re.IGNORECASE,
)
AC_POSITIVE_EVIDENCE = re.compile(
    r"\b(?:pass(?:ed|es|ing)?|green|verified|successful(?:ly)?|"
    r"covered\s+by|tested\s+by|proof\s*[:=]|evidence\s*[:=])\b",
    re.IGNORECASE,
)
PERCENTAGE = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*%")
COVERAGE_MEASUREMENT = re.compile(
    r"\bcoverage\s*(?:(?:is|at)\s+|[=:]\s*)?(\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
CURRENT_COVERAGE_MEASUREMENT = re.compile(
    r"\b(?:current|currently|now|final|actual)\s+coverage\s*"
    r"(?:(?:is|at)\s+|[=:]\s*)?(\d{1,3}(?:\.\d+)?)\s*%|"
    r"\bcoverage\s*(?:is\s+)?(?:currently|now|final|actual)\s*"
    r"(?:at\s+|[=:]\s*)?(\d{1,3}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
COVERAGE_NONCURRENT = re.compile(
    r"\b(?:historical|history|previous|prior|before|baseline|target|goal|aim|planned|"
    r"plan|aspirational|expected|would|could|should|was|used\s+to)\b",
    re.IGNORECASE,
)
PERF_MEASUREMENT = re.compile(
    r"(?<![\w.])(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>ns|us|µs|ms|s|ops/s|req/s|requests?/s|mb/s|gb/s)\b",
    re.IGNORECASE,
)
IMPLEMENTATION_ACTION = re.compile(
    r"\b(?:implemented|changed|added|fixed|removed|updated|refactored|documented|"
    r"wrote|created|migrated|hardened)\b",
    re.IGNORECASE,
)

TEST_DIMENSIONS = {
    "testes_unitarios", "testes_integracao", "testes_sistema", "testes_regressao",
}
TEST_LANE_TERM = r"(?:unit|integration|system|end[- ]to[- ]end|e2e|regression)"
TEST_SUBJECT_LIST = re.compile(
    r"\b(?P<lanes>" + TEST_LANE_TERM
    + r"(?:(?:\s*,\s*(?:and\s+)?|\s+(?:and|&)\s+)"
    + TEST_LANE_TERM + r")*)\s+tests?\b",
)
TEST_LANE_NAME = re.compile(TEST_LANE_TERM)
TEST_CONTEXT_LABELS = (
    ("testes_unitarios", "unit"),
    ("testes_integracao", "integration"),
    ("testes_sistema", "system"),
    ("testes_regressao", "regression"),
)


def _named_test_subjects(segment: str) -> set:
    """Return lanes named in noun phrases that directly govern ``test(s)``."""
    dimensions = set()
    for subject_list in TEST_SUBJECT_LIST.finditer(segment):
        for lane in TEST_LANE_NAME.findall(subject_list.group("lanes")):
            if lane == "unit":
                dimensions.add("testes_unitarios")
            elif lane == "integration":
                dimensions.add("testes_integracao")
            elif lane in {"system", "end-to-end", "end to end", "e2e"}:
                dimensions.add("testes_sistema")
            elif lane == "regression":
                dimensions.add("testes_regressao")
    return dimensions


def _mentioned_test_lanes(segment: str) -> set:
    """Return bare lane names in a bounded current-state clause."""
    dimensions = set()
    for lane in TEST_LANE_NAME.findall(segment):
        if lane == "unit":
            dimensions.add("testes_unitarios")
        elif lane == "integration":
            dimensions.add("testes_integracao")
        elif lane in {"system", "end-to-end", "end to end", "e2e"}:
            dimensions.add("testes_sistema")
        elif lane == "regression":
            dimensions.add("testes_regressao")
    return dimensions


def _normalized_perf_measurements(segment: str):
    """Return performance values normalized within comparable unit families."""
    normalized = []
    time_scale = {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1.0}
    byte_scale = {"mb/s": 1e6, "gb/s": 1e9}
    operation_units = {"ops/s", "req/s", "request/s", "requests/s"}
    for measurement in PERF_MEASUREMENT.finditer(segment):
        value = float(measurement.group("value"))
        unit = measurement.group("unit").lower()
        if unit in time_scale:
            normalized.append((value * time_scale[unit], "time"))
        elif unit in byte_scale:
            normalized.append((value * byte_scale[unit], "bytes_per_second"))
        elif unit in operation_units:
            normalized.append((value, "operations_per_second"))
    return normalized


def _norm(text: str) -> str:
    return (text or "").lower()


def _segments(text: str) -> List[str]:
    """Return bounded evidence statements instead of one keyword soup."""
    segments: List[str] = []
    # A contrast changes the current state.  Preserve coordinated test lanes
    # structurally so an elided ``They fail`` retains every named lane rather
    # than whichever textual regex happened to match last.
    scalar_subject = re.compile(
        r"\b(?:coverage|benchmark|performance|implementation|implemented)\b",
    )
    context_lanes = set()
    context_scalar = ""

    def current_context() -> str:
        if context_lanes:
            labels = [label for dimension, label in TEST_CONTEXT_LABELS if dimension in context_lanes]
            return " and ".join(labels) + " tests"
        return context_scalar

    def explicit_context(clause: str):
        lanes = _named_test_subjects(clause)
        if not lanes and (POSITIVE_EVIDENCE.search(clause) or NEGATIVE_EVIDENCE.search(clause)):
            lanes = _mentioned_test_lanes(clause)
        if lanes:
            return lanes, ""
        found = scalar_subject.findall(clause)
        if found:
            return set(), " ".join(found)
        if re.search(r"\btests?\b", clause):
            return set(), "tests"
        return set(), ""

    def split_state_commas(clause: str) -> List[str]:
        """Split comma-separated state clauses, never coordinated subject lists."""
        pieces: List[str] = []
        start = 0
        for comma in re.finditer(r",", clause):
            left = clause[start:comma.start()].strip()
            right = clause[comma.end():].strip()
            left_has_state = has_state(left)
            if not left_has_state:
                continue
            current_transition = bool(re.match(r"^(?:right\s+)?now\b", right))
            subject_candidate = re.sub(
                r"^(?:(?:right\s+)?now\s+)?(?:only\s+)?", "", right,
            )
            lane_state = bool(
                is_lane_state_clause(subject_candidate)
            )
            coverage_transition = is_coverage_transition(left, right)
            if current_transition or lane_state or coverage_transition:
                pieces.append(left)
                start = comma.end()
        pieces.append(clause[start:].strip())
        return [piece for piece in pieces if piece]

    def has_state(clause: str) -> bool:
        return bool(
            POSITIVE_EVIDENCE.search(clause)
            or NEGATIVE_EVIDENCE.search(clause)
            or re.search(r"\bn/a\b", clause)
            or ("coverage" in clause and PERCENTAGE.search(clause))
        )

    def is_lane_state_clause(clause: str) -> bool:
        return bool(
            has_state(clause)
            and (TEST_SUBJECT_LIST.match(clause) or _mentioned_test_lanes(clause))
        )

    def is_coverage_transition(left: str, right: str) -> bool:
        return bool(
            "coverage" in left
            and PERCENTAGE.search(left)
            and PERCENTAGE.search(right)
            and re.search(r"\b(?:current|currently|now)\b", right)
        )

    def split_state_ands(clause: str) -> List[str]:
        """Split independent lane/coverage predicates joined by plain ``and``."""
        pieces: List[str] = []
        start = 0
        for conjunction in re.finditer(r"\band\b", clause):
            left = clause[start:conjunction.start()].strip()
            right = clause[conjunction.end():].strip()
            subject_candidate = re.sub(r"^(?:only\s+)?", "", right)
            independent_lanes = bool(
                _named_test_subjects(left)
                and has_state(left)
                and is_lane_state_clause(subject_candidate)
            )
            coverage_transition = is_coverage_transition(left, right)
            if independent_lanes or coverage_transition:
                pieces.append(left)
                start = conjunction.end()
        pieces.append(clause[start:].strip())
        return [piece for piece in pieces if piece]

    for statement in re.split(r"(?:\r?\n)+|;\s*|(?<=[.!?])\s+", _norm(text)):
        statement = re.sub(
            r"^(?:however|but|yet|although|though|nevertheless|mas|por[ée]m)\s*,?\s*",
            "", statement,
        )
        contrast_clauses = [clause.strip() for clause in re.split(
            r"(?:\s+\b(?:but|however|yet|although|though|mas|por[ée]m)\b\s+|"
            r"(?:\s*,\s*|\s+)and\s+now\s+)", statement,
        ) if clause.strip()]
        clauses = [
            clause
            for contrast_clause in contrast_clauses
            for state_clause in split_state_ands(contrast_clause)
            for clause in split_state_commas(state_clause)
        ]
        if not clauses:
            continue
        # Carry the most recent explicit subject only into an anaphoric next
        # sentence.  This recognizes "They fail now" / "It is unavailable"
        # without making an unrelated bare failure revoke the wrong dimension.
        if (
            current_context()
            and re.match(r"^(?:(?:right\s+)?now\s+)?(?:it|they|this|these|those)\b", clauses[0])
            and explicit_context(clauses[0]) == (set(), "")
        ):
            clauses[0] = current_context() + " " + clauses[0]
        for index, clause in enumerate(clauses):
            previous_lanes = set(context_lanes)
            if index and current_context() and explicit_context(clause) == (set(), ""):
                clause = current_context() + " " + clause
            segments.append(clause)
            found_lanes, found_scalar = explicit_context(clause)
            if (
                previous_lanes
                and found_lanes
                and re.search(r"\bonly\b", clause)
                and POSITIVE_EVIDENCE.search(clause)
            ):
                for excluded in previous_lanes - found_lanes:
                    label = next(
                        label for dimension, label in TEST_CONTEXT_LABELS if dimension == excluded
                    )
                    segments.append(label + " tests not pass now")
            if found_lanes or found_scalar:
                context_lanes = found_lanes
                context_scalar = found_scalar
    return segments


def _dimension_evidence(normalized: str, dimension: str, signals: List[str]) -> str:
    """Return positive, dimension-local evidence or an empty string.

    A bare keyword is never proof.  Failure/negation in the same statement wins, coverage must
    meet the documented 85% floor, and performance evidence must contain a measured number.
    """
    segments = _segments(normalized)
    if dimension == "cobertura_minima":
        evidence = ""
        for segment in segments:
            if "coverage" not in segment:
                continue
            if FUTURE_OR_HISTORICAL_EVIDENCE.search(segment):
                continue
            if NEGATIVE_EVIDENCE.search(segment):
                evidence = ""
                continue
            current = list(CURRENT_COVERAGE_MEASUREMENT.finditer(segment))
            direct = list(COVERAGE_MEASUREMENT.finditer(segment))
            measurement = (current or direct)[-1] if (current or direct) else None
            if measurement and not (not current and COVERAGE_NONCURRENT.search(segment)):
                raw_value = next(group for group in measurement.groups() if group is not None)
                value = float(raw_value)
                evidence = "%g%%" % value if 85.0 <= value <= 100.0 else ""
        return evidence

    evidence = ""
    for segment in segments:
        hits = [signal for signal in signals if signal in segment]
        negative = bool(NEGATIVE_EVIDENCE.search(segment))
        named_test_subjects = _named_test_subjects(segment)
        # A named failing lane only revokes that lane.  An unqualified
        # ``tests fail`` remains deliberately conservative and revokes every
        # test lane because there is no safe basis for choosing just one.
        if (
            dimension in TEST_DIMENSIONS
            and negative
            and named_test_subjects
            and dimension not in named_test_subjects
        ):
            continue
        generic_test_failure = (
            dimension in TEST_DIMENSIONS
            and bool(re.search(r"\btests?\b", segment))
            and negative
        )
        if not hits and not generic_test_failure:
            continue
        # Evidence is stateful: the latest relevant statement wins.  A current failure or
        # regression therefore revokes an earlier PASS instead of being skipped.
        if FUTURE_OR_HISTORICAL_EVIDENCE.search(segment):
            continue
        if NEGATIVE_EVIDENCE.search(segment):
            evidence = ""
            continue
        if dimension == "performance_benchmark":
            measurements = _normalized_perf_measurements(segment)
            if len(measurements) >= 2:
                families = {family for _value, family in measurements}
                if len(families) != 1:
                    evidence = ""
                    continue
                family = next(iter(families))
                latency_metric = re.search(
                    r"\b(?:latency|duration|elapsed|response\s+time)\b", segment,
                )
                throughput_metric = re.search(
                    r"\b(?:throughput|ops/s|req/s|requests?/s|mb/s|gb/s)\b", segment,
                )
                if ((latency_metric and family != "time")
                        or (throughput_metric and family == "time")):
                    evidence = ""
                    continue
                first, last = measurements[0][0], measurements[-1][0]
                improved = last < first if family == "time" else last > first
                evidence = hits[0] if improved else ""
                continue
            if POSITIVE_EVIDENCE.search(segment) and measurements:
                evidence = hits[0]
            else:
                evidence = ""
            continue
        if POSITIVE_EVIDENCE.search(segment):
            evidence = hits[0]
        else:
            evidence = ""
    return evidence


def _implementation_evidence(normalized: str) -> str:
    """Require an explicit, current implementation action."""
    evidence = ""
    for segment in _segments(normalized):
        if segment in {"## summary", "## implementação", "## implementacao"}:
            continue
        relevant = bool(
            IMPLEMENTATION_ACTION.search(segment)
            or re.search(r"\bimplement(?:ation|ed|ing)?\b", segment)
            or re.search(r"\b(?:revert(?:ed|s|ing)?|roll(?:ed)?\s+back|rollback)\b", segment)
        )
        if not relevant:
            continue
        if FUTURE_OR_HISTORICAL_EVIDENCE.search(segment):
            continue
        if NEGATIVE_EVIDENCE.search(segment):
            evidence = ""
            continue
        if IMPLEMENTATION_ACTION.search(segment):
            evidence = "implementation statement"
    return evidence


def _na_evidence(normalized: str, dimension: str, signals: List[str]) -> str:
    """Accept N/A only when its concrete reason is in the same statement."""
    candidate = ""
    negative_seen = False
    for segment in _segments(normalized):
        explicit_na = "not applicable" in segment or re.search(r"\bn/a\b", segment)
        if not explicit_na and FUTURE_OR_HISTORICAL_EVIDENCE.search(segment):
            continue
        relevant = any(signal in segment for signal in signals)
        if dimension in TEST_DIMENSIONS and re.search(r"\btests?\b", segment):
            named_test_subjects = _named_test_subjects(segment)
            relevant = not named_test_subjects or dimension in named_test_subjects
        if relevant and NEGATIVE_EVIDENCE.search(segment):
            negative_seen = True
            candidate = ""
        if not explicit_na:
            continue
        for signal in REVIEW_NA_SIGNALS.get(dimension, []):
            if signal in segment:
                candidate = signal
    return "" if negative_seen else candidate


def verdict_dod(pr_body: str, issue_body: str) -> Dict[str, Dict[str, object]]:
    """Return per-dimension status: addressed / missing + evidence snippet."""
    pr = _norm(pr_body)
    del issue_body  # requirements in an issue are not evidence that a PR executed them
    legacy_dimensions = {
        "implementation": "implementacao",
        "unit_tests": "testes_unitarios",
        "integration_tests": "testes_integracao",
        "system_tests": "testes_sistema",
        "regression_tests": "testes_regressao",
        "perf_benchmark": "performance_benchmark",
        "min_coverage": "cobertura_minima",
    }
    out: Dict[str, Dict[str, object]] = {}
    for dim in DOD_DIMENSIONS:
        signals = DOD_SIGNALS.get(dim, [])
        if dim == "implementation":
            evidence = _implementation_evidence(pr)
        else:
            evidence = _dimension_evidence(pr, legacy_dimensions[dim], signals)
        addressed = bool(evidence)
        out[dim] = {
            "addressed": addressed,
            "evidence": evidence or "(none)",
        }
    return out


def unresolved_acs(issue_body: str) -> List[str]:
    """Return issue acceptance-criteria checklist lines still unfilled (- [ ])."""
    lines = (issue_body or "").splitlines()
    open_items: List[str] = []
    for ln in lines:
        m = re.match(r"\s*[-*]\s*\[\s*\]\s*(.*)", ln)
        if m:
            open_items.append(m.group(1).strip())
    return open_items


def extract_ac_items(issue_body: str) -> List[Dict[str, object]]:
    """Parse checked and unchecked Markdown acceptance-criteria items.

    This is the public counterpart to ``unresolved_acs``: consumers that need to preserve the
    issue's checked state must not have to reverse-engineer the lossy unresolved-only result.
    """
    items: List[Dict[str, object]] = []
    for line in (issue_body or "").splitlines():
        match = re.match(r"\s*[-*]\s*\[\s*([xX]?)\s*\]\s*(.*)", line)
        if match:
            items.append({"text": match.group(2).strip(), "checked": bool(match.group(1))})
    return items


def _nearby_ac_evidence(pr_body: str, ac_text: str) -> bool:
    """True only for an exact AC citation with positive evidence in the same statement."""
    needle = _norm(ac_text).strip()
    if not needle:
        return False
    escaped = re.escape(needle)
    short_item = len(needle) < 4 or len(re.findall(r"\w+", needle)) < 2
    if short_item:
        mention = re.compile(
            r"(?:^|\n)\s*(?:[-*]\s*)?(?:ac|acceptance criterion|crit[eé]rio)"
            r"(?:\s*#?\d+)?\s*[:=-]\s*`?" + escaped + r"`?(?=\s|[-—:;,.]|$)",
            re.IGNORECASE,
        )
    else:
        mention = re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)
    resolved = False
    mentioned = False
    for segment in _segments(pr_body):
        if not mention.search(segment):
            continue
        mentioned = True
        if (NEGATIVE_EVIDENCE.search(segment)
                or FUTURE_OR_HISTORICAL_EVIDENCE.search(segment)):
            resolved = False
        else:
            evidence_text = mention.sub(" ", segment)
            resolved = bool(AC_POSITIVE_EVIDENCE.search(evidence_text))
    return mentioned and resolved


def review(pr_body: str, issue_body: str = "") -> Dict[str, object]:
    """Return the structured, evidence-aware DoD/AC review contract.

    A dimension is satisfied by an explicit evidence signal.  A non-implementation dimension
    can instead be skipped only when the PR says it is not applicable *and* gives that
    dimension's concrete reason.  Unchecked ACs remain unresolved unless the PR cites the AC
    text next to a test/proof/pass signal.
    """
    normalized = _norm(pr_body)
    dod: List[Dict[str, object]] = []
    missing: List[str] = []
    for dimension, signals in REVIEW_DIMENSIONS:
        evidence = _dimension_evidence(normalized, dimension, signals)
        if dimension == "implementacao":
            evidence = _implementation_evidence(normalized)
        na_evidence = _na_evidence(normalized, dimension, signals)
        skipped = bool(na_evidence)
        addressed = bool(evidence) or skipped
        if not addressed:
            missing.append(dimension)
        dod.append({
            "dimension": dimension,
            "status": "SKIPPED_WITH_REASON" if skipped else ("PRESENT" if evidence else "MISSING"),
            "addressed": addressed,
            "skipped_with_reason": skipped,
            "evidence": na_evidence or evidence or "(none)",
        })

    ac_items = extract_ac_items(issue_body)
    unresolved = [
        str(item["text"])
        for item in ac_items
        if not item["checked"] and not _nearby_ac_evidence(pr_body, str(item["text"]))
    ]
    verdict = "COMPLIANT" if not missing and not unresolved else "GAPS_FOUND"
    return {
        "schema": "simplicio.pr-dod-review/v1",
        "verdict": verdict,
        "dod": dod,
        "missing_dod": missing,
        "ac_items_total": len(ac_items),
        "unresolved_acs": unresolved,
    }


def build_verdict(pr_body: str, issue_body: str, pr_url: str = "", issue_no: str = "") -> Dict[str, object]:
    # Keep this compatibility response shape, but derive it from the same conservative evidence
    # analysis as ``review`` so callers cannot merge on a negated assertion or an unchecked AC.
    structured = review(pr_body, issue_body)
    legacy_dimensions = {
        "implementation": "implementacao",
        "unit_tests": "testes_unitarios",
        "integration_tests": "testes_integracao",
        "system_tests": "testes_sistema",
        "regression_tests": "testes_regressao",
        "perf_benchmark": "performance_benchmark",
        "min_coverage": "cobertura_minima",
    }
    structured_dod = {
        str(item["dimension"]): item for item in structured["dod"]  # type: ignore[index]
    }
    dod = {
        dimension: {
            "addressed": structured_dod[legacy_dimensions[dimension]]["addressed"],
            "evidence": structured_dod[legacy_dimensions[dimension]]["evidence"],
        }
        for dimension in DOD_DIMENSIONS
    }
    acs = list(structured["unresolved_acs"])  # type: ignore[index]
    addressed = sum(1 for d in dod.values() if d["addressed"])
    total = len(dod)
    verdict = {
        "schema": "simplicio.pr-dod-review/v1",
        "pr_url": pr_url,
        "issue": issue_no,
        "dod_addressed": f"{addressed}/{total}",
        "dod": dod,
        "unresolved_acceptance_criteria": acs,
        "ready_to_merge": (addressed == total and not acs),
    }
    return verdict


def render_comment(
    v: Dict[str, object], pr_number: object = None, issue_number: object = None,
) -> str:
    if "verdict" in v:
        return _render_structured_comment(v, pr_number=pr_number, issue_number=issue_number)
    dod = v["dod"]  # type: ignore[index]
    lines = ["## PR DoD + ACs Review (mechanical)", ""]
    lines.append(f"DoD addressed: **{v['dod_addressed']}**")
    lines.append("")
    lines.append("| Dimension | Status | Evidence |")
    lines.append("|---|---|---|")
    for dim, d in dod.items():  # type: ignore[union-attr]
        status = "✅" if d["addressed"] else "❌"  # type: ignore[index]
        lines.append(f"| {dim} | {status} | {d['evidence']} |")  # type: ignore[index]
    acs = v["unresolved_acceptance_criteria"]  # type: ignore[index]
    lines.append("")
    if acs:
        lines.append("**Unresolved acceptance criteria:**")
        for a in acs:
            lines.append(f"- [ ] {a}")
    else:
        lines.append("**All acceptance criteria resolved.** ✅")
    lines.append("")
    lines.append("> Generated by `scripts/pr_dod_review.py` — mechanical verdict, not a substitute for human review.")
    return "\n".join(lines)


def _render_structured_comment(
    result: Dict[str, object], pr_number: object = None, issue_number: object = None,
) -> str:
    heading = "## PR DoD + ACs Review (mechanical)"
    if pr_number is not None:
        heading += " — PR #%s" % pr_number
    if issue_number is not None:
        heading += " · issue #%s" % issue_number
    lines = [heading, "", "Verdict: **%s**" % result["verdict"], ""]
    lines.extend(["| Dimension | Status | Evidence |", "|---|---|---|"])
    for dimension in result["dod"]:  # type: ignore[union-attr]
        lines.append(
            "| %s | %s | %s |" % (
                dimension["dimension"], dimension["status"], dimension["evidence"],
            )
        )
    missing = result["missing_dod"]  # type: ignore[index]
    unresolved = result["unresolved_acs"]  # type: ignore[index]
    lines.append("")
    if missing or unresolved:
        if missing:
            lines.append("**MISSING DoD:** %s" % ", ".join(missing))  # type: ignore[arg-type]
        if unresolved:
            lines.append("**Unresolved acceptance criteria:**")
            lines.extend("- [ ] %s" % item for item in unresolved)  # type: ignore[union-attr]
    else:
        lines.append("**No mechanical gaps found.**")
    lines.extend([
        "",
        "> Generated by `scripts/pr_dod_review.py` — mechanical verdict, not a substitute for human review.",
    ])
    return "\n".join(lines)


def _post_comment(pr_url: str, body: str) -> Tuple[bool, str]:
    if not pr_url:
        return False, "no PR url provided"
    # Extract owner/repo/number from url like https://github.com/o/r/pull/123
    m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        return False, f"cannot parse PR url: {pr_url}"
    owner, repo, num = m.group(1), m.group(2), m.group(3)
    try:
        res = subprocess.run(
            ["gh", "pr", "comment", num, "--repo", f"{owner}/{repo}", "--body", body],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if res.returncode != 0:
            return False, res.stderr.strip() or "gh failed"
        return True, res.stdout.strip()
    except FileNotFoundError:
        return False, "gh not installed"
    except subprocess.TimeoutExpired:
        return False, "gh timed out after 30 seconds"


def _load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Mechanical DoD+ACs review for open PRs")
    p.add_argument("--pr-body", help="PR body text or path (prefix @ to read a file)")
    p.add_argument("--issue-body", help="Referenced issue body text or path (@file)")
    p.add_argument("--pr-url", default="", help="PR url (for --post)")
    p.add_argument("--issue-no", default="", help="Issue number (for context)")
    p.add_argument("--post", action="store_true", help="Publish verdict as a PR comment via gh")
    p.add_argument("subcommand", nargs="?", default="check", help="check | selftest")
    args = p.parse_args(argv)

    if args.subcommand == "selftest":
        return _selftest()

    pr_body = args.pr_body or ""
    issue_body = args.issue_body or ""
    if pr_body.startswith("@"):
        pr_body = _load(pr_body[1:])
    if issue_body.startswith("@"):
        issue_body = _load(issue_body[1:])

    # The CLI is the production consumer of the evidence-aware API.  Keep build_verdict()
    # available for callers that need its historical response shape, but never use its legacy
    # shape to decide whether a live PR is compliant.
    verdict = review(pr_body, issue_body)
    if args.pr_url:
        verdict["pr_url"] = args.pr_url
    if args.issue_no:
        verdict["issue"] = args.issue_no
    if args.post:
        ok, msg = _post_comment(
            args.pr_url,
            render_comment(verdict, issue_number=args.issue_no or None),
        )
        print(json.dumps({"posted": ok, "detail": msg, "verdict": verdict}, indent=2))
        return 0 if ok else 1
    print(json.dumps(verdict, indent=2))
    return 0


def _selftest() -> int:
    """13 embedded assertions. Exit 1 on any failure."""
    failures: List[str] = []
    pr = (
        "## Implementação\nImplemented the change. Unit tests passed via pytest. Integration tests passed with no mocks. "
        "System e2e passed. Regression: existing suite green. "
        "Benchmark latency improved from 12ms to 4ms. Coverage 90%."
    )
    issue = "## Acceptance Criteria\n- [x] done one\n- [ ] pending two\n- [ ] pending three"

    # 1-7: each DoD dimension detected
    v = build_verdict(pr, issue)
    for i, dim in enumerate(DOD_DIMENSIONS, start=1):
        if not v["dod"][dim]["addressed"]:  # type: ignore[index]
            failures.append(f"{i}: dimension {dim} not detected as addressed")

    # 8-9: unresolved ACs extraction
    acs = v["unresolved_acceptance_criteria"]  # type: ignore[index]
    if len(acs) != 2:
        failures.append(f"8-9: expected 2 unresolved ACs, got {len(acs)}")
    if "pending two" not in acs:
        failures.append("8: missing 'pending two'")
    if "pending three" not in acs:
        failures.append("9: missing 'pending three'")

    # 10: resolved AC not counted
    if "[x] done one" in acs:
        failures.append("10: resolved AC wrongly counted")

    # 11: ready_to_merge false when ACs open
    if v["ready_to_merge"]:  # type: ignore[index]
        failures.append("11: ready_to_merge should be False with open ACs")

    # 12: fully-addressed PR with no open ACs => ready
    full_pr = pr
    full_issue = "## AC\n- [x] a\n- [x] b"
    v2 = build_verdict(full_pr, full_issue)
    if v2["dod_addressed"] != "7/7":  # type: ignore[index]
        failures.append("12: expected 7/7 addressed")
    if not v2["ready_to_merge"]:  # type: ignore[index]
        failures.append("12b: should be ready when all addressed + no open ACs")

    # 13: render_comment contains table + unresolved list
    cm = render_comment(v)
    if "| Dimension |" not in cm:
        failures.append("13: comment missing DoD table")
    if "- [ ] pending two" not in cm:
        failures.append("13b: comment missing unresolved AC")

    if failures:
        print("SELFTEST FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("selftest: 13/13 passed")
    return 0


def cmd_selftest(_args: object = None) -> int:
    """Compatibility command hook used by selftest registries."""
    return _selftest()


if __name__ == "__main__":
    sys.exit(main())

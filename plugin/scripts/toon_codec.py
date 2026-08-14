#!/usr/bin/env python3
"""simplicio-loop — TOON (Token-Oriented Object Notation) codec.

Reference spec: https://github.com/toon-format/toon. TOON losslessly represents any JSON value in
fewer tokens than JSON — YAML-style indentation for objects, an inline list for a scalar array, and
a CSV-style tabular block for an array of UNIFORM objects (same keys, scalar-only values), which is
where most of the token savings come from (~40% fewer tokens than JSON on typical uniform arrays,
per the toon-format benchmark). Anything that can't be represented tabularly — an empty array, a
non-uniform array (differing keys / mixed types / nested arrays-or-objects per element) — falls back
to compact JSON for that value, so the format is ALWAYS lossless, never lossy-compact.

This module is a plain encoder/decoder (`encode_toon` / `decode_toon`), model-free and dependency-
free (stdlib only). It is a rendering choice for LLM-prompt-facing payloads — it never changes what
gets written to disk. Durable state (journal.jsonl, anchor.json, receipts, ...) stays JSON; only a
value about to be dropped into a prompt is a candidate for `encode_toon`.

Grammar (the subset this codec implements):
  object            "key: value" lines, one per key. A nested object under "key" is
                    "key:" followed by its body indented two spaces further.
  empty object      "key: {}" (JSON fallback — unambiguous, no indented body to confuse with null).
  scalar array      "key[N]: v1,v2,v3" — N item count, comma-separated scalars on one line.
  uniform array     "key[N]{f1,f2,f3}:" header, then N rows of "v1,v2,v3" indented two spaces
  of objects        further, one row per element, values in the SAME field order as the header.
  empty / non-      "key: <compact-json>" — any array that is empty, has elements with differing
  uniform array     keys, mixed scalar types, or nested arrays/objects per element.
  scalars           numbers/bools/null unquoted; strings quoted (JSON-style) only when they contain
                    a comma, colon, newline, leading/trailing whitespace, or would otherwise parse
                    as a number/bool/null.
  root              an object or array follows the SAME rules with no enclosing "key:" — a root
                    array is "[N]{...}:" / "[N]: ..." with no key prefix.

Two known, deliberate simplifications documented so a future reader doesn't "fix" them into a
subtler bug:
  - array/object field NAMES are joined raw in a tabular header (no quoting) — fine for the
    ordinary identifier-shaped JSON keys this repo's payloads use; a field name containing a comma
    would need the general JSON fallback instead (not attempted here).
  - an UNQUOTED string scalar that happens to look like bracket/brace JSON syntax with no comma
    inside (e.g. the literal string "[1]") is ambiguous with the array/object JSON-fallback form and
    decodes as that structure instead of the original string. The spec's quoting rule doesn't cover
    this case either; avoid it in payloads (or quote it explicitly) rather than relying on this
    codec to disambiguate it.

Usage:
    python3 scripts/toon_codec.py encode <FILE|- >   # reads JSON, prints TOON
    python3 scripts/toon_codec.py decode <FILE|- >   # reads TOON, prints JSON
    python3 scripts/toon_codec.py selftest
"""
import json
import re
import sys

_NUM_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
_INT_RE = re.compile(r"^-?\d+$")

# a "key" or a root-array header line: KEY[N]{f1,f2}: val  /  KEY[N]: val  /  KEY: val
_KEY_LINE_RE = re.compile(
    r'^(?P<key>"(?:[^"\\]|\\.)*"|[^:\[]+?)'
    r"(?:\[(?P<n>\d+)\](?:\{(?P<fields>[^}]*)\})?)?"
    r":(?P<val>.*)$"
)
# root array header with no key: [N]{f1,f2}: val  /  [N]: val
_ROOT_ARRAY_RE = re.compile(
    r"^\[(?P<n>\d+)\](?:\{(?P<fields>[^}]*)\})?:(?P<val>.*)$"
)


# ----------------------------------------------------------------------------------------------
# scalar formatting / quoting
# ----------------------------------------------------------------------------------------------

def _looks_like_number_bool_null(s):
    if s in ("true", "false", "null"):
        return True
    return bool(_NUM_RE.match(s))


def _needs_quote(s):
    if s == "":
        return True
    if s != s.strip():
        return True
    if any(ch in s for ch in (",", ":", "\n")):
        return True
    return _looks_like_number_bool_null(s)


def _quote(s):
    return json.dumps(s, ensure_ascii=False)


def _fmt_scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return json.dumps(v)
    if isinstance(v, str):
        return _quote(v) if _needs_quote(v) else v
    # a scalar of some other JSON-representable type — round-trip it as a quoted JSON string
    return _quote(json.dumps(v, ensure_ascii=False))


def _key_needs_quote(k):
    if k == "":
        return True
    if k != k.strip():
        return True
    if any(ch in k for ch in (",", ":", "\n", "[", "]", "{", "}")):
        return True
    return _looks_like_number_bool_null(k)


def _fmt_key(key):
    k = str(key)
    return _quote(k) if _key_needs_quote(k) else k


def _split_csv(s):
    """Split a comma-separated row, treating a JSON-quoted span as one field (commas inside
    quotes don't split)."""
    tokens = []
    cur = []
    in_quotes = False
    i = 0
    while i < len(s):
        c = s[i]
        if in_quotes:
            cur.append(c)
            if c == "\\" and i + 1 < len(s):
                cur.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_quotes = False
            i += 1
            continue
        if c == '"':
            in_quotes = True
            cur.append(c)
            i += 1
            continue
        if c == ",":
            tokens.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    tokens.append("".join(cur))
    return tokens


def _parse_scalar(tok):
    tok = tok.strip()
    if tok == "":
        return ""
    if tok.startswith('"'):
        try:
            return json.loads(tok)
        except ValueError:
            return tok.strip('"')
    if tok == "true":
        return True
    if tok == "false":
        return False
    if tok == "null":
        return None
    if _INT_RE.match(tok):
        return int(tok)
    if _NUM_RE.match(tok):
        return float(tok)
    return tok


def _parse_scalar_or_json(val):
    if val.startswith("{") or val.startswith("["):
        try:
            return json.loads(val)
        except ValueError:
            pass
    return _parse_scalar(val)


def _parse_key(raw):
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw.strip()


# ----------------------------------------------------------------------------------------------
# array classification
# ----------------------------------------------------------------------------------------------

def _is_scalar(v):
    return not isinstance(v, (dict, list))


def _is_uniform_array_of_objects(arr):
    if not arr or not all(isinstance(x, dict) for x in arr):
        return False
    first_keys = list(arr[0].keys())
    if not first_keys:
        return False  # array of empty objects — nothing to tabulate, fall back
    for x in arr:
        if list(x.keys()) != first_keys:
            return False
        if not all(_is_scalar(v) for v in x.values()):
            return False
    return True


def _is_scalar_array(arr):
    return bool(arr) and all(_is_scalar(v) for v in arr)


# ----------------------------------------------------------------------------------------------
# encode
# ----------------------------------------------------------------------------------------------

def _encode_array_lines(key_text, arr, indent):
    """key_text is the already-formatted 'key' for a keyed array, or '' for a root array (no key
    prefix — used both for a root-level array value and recursively has no other caller)."""
    n = len(arr)
    if n == 0:
        return [indent + ("%s: []" % key_text if key_text else "[]")]
    if _is_uniform_array_of_objects(arr):
        fields = list(arr[0].keys())
        field_list = ",".join(str(f) for f in fields)
        header = ("%s[%d]{%s}:" % (key_text, n, field_list) if key_text
                  else "[%d]{%s}:" % (n, field_list))
        lines = [indent + header]
        for row in arr:
            vals = [_fmt_scalar(row[f]) for f in fields]
            lines.append(indent + "  " + ",".join(vals))
        return lines
    if _is_scalar_array(arr):
        vals = ",".join(_fmt_scalar(v) for v in arr)
        header = "%s[%d]: %s" % (key_text, n, vals) if key_text else "[%d]: %s" % (n, vals)
        return [indent + header]
    # non-uniform / mixed-type / nested-per-element -> compact JSON fallback (never lossy)
    blob = json.dumps(arr, separators=(",", ":"), ensure_ascii=False)
    return [indent + ("%s: %s" % (key_text, blob) if key_text else blob)]


def _encode_object_body(d, indent):
    lines = []
    for k, v in d.items():
        key_text = _fmt_key(k)
        if isinstance(v, dict):
            if not v:
                lines.append(indent + "%s: {}" % key_text)
            else:
                lines.append(indent + "%s:" % key_text)
                lines.extend(_encode_object_body(v, indent + "  "))
        elif isinstance(v, list):
            lines.extend(_encode_array_lines(key_text, v, indent))
        else:
            lines.append(indent + "%s: %s" % (key_text, _fmt_scalar(v)))
    return lines


def encode_toon(value):
    """Encode any JSON-representable Python value (dict/list/scalar) as a TOON string."""
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "\n".join(_encode_object_body(value, ""))
    if isinstance(value, list):
        if not value:
            return "[]"
        return "\n".join(_encode_array_lines("", value, ""))
    return _fmt_scalar(value)


# ----------------------------------------------------------------------------------------------
# decode
# ----------------------------------------------------------------------------------------------

def _tokenize(text):
    lines = []
    for raw in text.split("\n"):
        if raw.strip() == "":
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))
    return lines


class _Parser:
    def __init__(self, lines):
        self.lines = lines
        self.pos = 0

    def _peek(self):
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def parse_object(self, indent):
        obj = {}
        while True:
            item = self._peek()
            if item is None or item[0] != indent:
                break
            _, content = item
            m = _KEY_LINE_RE.match(content)
            if not m:
                break
            self.pos += 1
            key = _parse_key(m.group("key"))
            n, fields, val = m.group("n"), m.group("fields"), m.group("val")
            if n is not None:
                obj[key] = self._parse_array_value(indent, int(n), fields, val)
            else:
                val_stripped = val.strip()
                if val_stripped == "":
                    obj[key] = self.parse_object(indent + 2)
                else:
                    obj[key] = _parse_scalar_or_json(val_stripped)
        return obj

    def _parse_array_value(self, indent, n, fields, val):
        if fields is not None:
            field_list = [f.strip() for f in fields.split(",")] if fields else []
            rows = []
            for _ in range(n):
                item = self._peek()
                if item is None or item[0] != indent + 2:
                    break
                _, content = item
                self.pos += 1
                vals = [_parse_scalar(tok) for tok in _split_csv(content)]
                rows.append(dict(zip(field_list, vals)))
            return rows
        vals_str = val.strip()
        return [_parse_scalar(tok) for tok in _split_csv(vals_str)] if vals_str else []


def _parse_root_array(lines, m):
    n = int(m.group("n"))
    fields, val = m.group("fields"), m.group("val")
    if fields is not None:
        field_list = [f.strip() for f in fields.split(",")] if fields else []
        rows = []
        idx = 1
        for _ in range(n):
            if idx >= len(lines):
                break
            indent, content = lines[idx]
            if indent != 2:
                break
            vals = [_parse_scalar(tok) for tok in _split_csv(content)]
            rows.append(dict(zip(field_list, vals)))
            idx += 1
        return rows
    vals_str = val.strip()
    return [_parse_scalar(tok) for tok in _split_csv(vals_str)] if vals_str else []


def decode_toon(text):
    """Decode a TOON string back into a Python value. Inverse of `encode_toon`."""
    if text is None:
        return None
    text = text.rstrip("\n")
    if text.strip() == "":
        return None
    lines = _tokenize(text)
    if not lines:
        return None
    first_indent, first_content = lines[0]
    if first_indent == 0:
        m = _ROOT_ARRAY_RE.match(first_content)
        if m:
            return _parse_root_array(lines, m)
    parser = _Parser(lines)
    obj = parser.parse_object(0)
    if parser.pos == len(lines) and parser.pos > 0:
        return obj
    # not an object (or nothing consumed) -> compact-JSON fallback, else a bare scalar
    whole = text.strip()
    try:
        return json.loads(whole)
    except ValueError:
        pass
    if len(lines) == 1:
        return _parse_scalar(first_content)
    return whole


# ----------------------------------------------------------------------------------------------
# CLI + selftest
# ----------------------------------------------------------------------------------------------

def _read_source(spec):
    if spec is None or spec == "-":
        return sys.stdin.read()
    with open(spec, encoding="utf-8", errors="replace") as f:
        return f.read()


def cmd_encode(argv):
    src = argv[0] if argv else "-"
    value = json.loads(_read_source(src))
    print(encode_toon(value))


def cmd_decode(argv):
    src = argv[0] if argv else "-"
    value = decode_toon(_read_source(src))
    print(json.dumps(value, ensure_ascii=False))


def cmd_selftest(_argv):
    checks = []

    def chk(name, got, want):
        ok = got == want
        checks.append(ok)
        print("  [%s] %-32s got=%r want=%r" % ("ok" if ok else "XX", name, got, want))

    def round_trip(name, value):
        toon = encode_toon(value)
        back = decode_toon(toon)
        ok = back == value
        checks.append(ok)
        print("  [%s] roundtrip.%-24s %r" % ("ok" if ok else "XX", name, toon.splitlines()[0][:60]
              if toon else toon))
        if not ok:
            print("        toon=%r" % toon)
            print("        got =%r" % back)
            print("        want=%r" % value)

    # nested objects
    round_trip("nested_object", {
        "user": {"id": 1, "name": "Alice", "address": {"city": "Lisbon", "zip": "1000-001"}},
        "active": True,
    })

    # uniform array of objects — the tabular case (main token-saving path)
    round_trip("uniform_array", {
        "items": [
            {"id": 1, "name": "Alice", "role": "admin"},
            {"id": 2, "name": "Bob", "role": "user"},
            {"id": 3, "name": "Carol, PhD", "role": "user"},  # comma in a field forces quoting
        ]
    })

    # non-uniform array fallback (differing keys per element)
    round_trip("non_uniform_array", {
        "events": [{"type": "login", "user": "a"}, {"type": "click", "x": 1, "y": 2}]
    })

    # mixed-type array fallback
    round_trip("mixed_type_array", {"mixed": [1, "two", True, None]})

    # array containing a nested object per element -> fallback (not tabular)
    round_trip("nested_in_array", {"rows": [{"id": 1, "meta": {"a": 1}}, {"id": 2, "meta": {"b": 2}}]})

    # empty array / empty object
    round_trip("empty_array", {"tags": []})
    round_trip("empty_object", {"config": {}})
    round_trip("root_empty_array", [])
    round_trip("root_empty_object", {})

    # scalars needing quoting: comma, colon, leading/trailing space, number-looking string
    round_trip("quoting", {
        "a": "has,comma", "b": "has:colon", "c": " leading space", "d": "42", "e": "true",
        "f": "", "g": "plain string", "h": 3, "i": 3.5, "j": None, "k": False,
    })

    # root-level uniform array of objects (no enclosing key)
    round_trip("root_uniform_array", [
        {"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"},
    ])

    # root-level scalar array
    round_trip("root_scalar_array", [1, 2, 3, "four"])

    # a realistic multi-level payload (drift-verdict-shaped, the wired use case)
    round_trip("drift_verdict_shaped", {
        "verdict": "INCOMPLETE",
        "reason": "2/3 criteria verified — 1 still open",
        "pending": ["AC3"],
        "coverage": "2/3",
    })

    # spot-check the actual rendered shape for the tabular case (not just round-trip)
    toon = encode_toon({"items": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]})
    chk("tabular.header", toon.splitlines()[0], "items[2]{id,name}:")
    chk("tabular.row0", toon.splitlines()[1], "  1,Alice")

    # spot-check scalar array shape
    toon2 = encode_toon({"tags": ["a", "b", "c"]})
    chk("scalar_array.shape", toon2, "tags[3]: a,b,c")

    # spot-check non-uniform fallback shape (compact JSON on the value)
    toon3 = encode_toon({"events": [{"a": 1}, {"b": 2}]})
    chk("fallback.is_compact_json", toon3, 'events: [{"a":1},{"b":2}]')

    ok = all(checks)
    print("selftest: %s (%d/%d)" % ("PASS" if ok else "FAIL", sum(checks), len(checks)))
    sys.exit(0 if ok else 1)


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        sys.exit(2)
    sub, rest = argv[0], argv[1:]
    {"encode": cmd_encode, "decode": cmd_decode, "selftest": cmd_selftest}.get(
        sub, lambda _a: (print("unknown command %r. choices: encode decode selftest" % sub),
                         sys.exit(2)))(rest)


if __name__ == "__main__":
    main()

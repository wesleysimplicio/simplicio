#!/usr/bin/env python3
"""simplicio-orient — command clamp wrapper (rtk core, portable).

Run a dev command and return its output REDUCED before it reaches the model context:
  success-collapse · dedup-with-counts · signal-tiered caps · tee-cache on failure.

Usage:
    python3 hooks/orient_clamp.py -- <command> [args...]
    python3 hooks/orient_clamp.py --json -- <command> [args...]   # machine summary

Works on Windows/macOS/Linux (pure Python, no shell-specific syntax). Safe and
fail-open: on ANY internal error it prints the raw output and propagates the REAL
exit code — it can never turn "task works" into "task dead".

Config (optional): .simplicio/orchestrator/orient.toml
    [tee]   mode = "failures" | "always" | "never"   (default failures)
    [hooks] exclude_commands = ["curl", "wget", "playwright", "ssh", "vim", "less"]
Excluded commands run RAW (streaming/interactive/binary must not be filtered).
"""
import os
import re
import subprocess
import sys
import time

try:  # Windows consoles default to cp1252 — force UTF-8 so arbitrary output never crashes.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CAP_ERRORS = 20
CAP_WARNINGS = 10
CAP_LIST = 20
TEE_DIR = os.path.join(".simplicio/orchestrator", "tee")
CONFIG = os.path.join(".simplicio/orchestrator", "orient.toml")
DEFAULT_EXCLUDES = ["curl", "wget", "playwright", "ssh", "vim", "less", "top", "htop"]

ERR_RE = re.compile(r"\b(error|fail(ed|ure)?|panic|exception|fatal|traceback)\b", re.I)
WARN_RE = re.compile(r"\bwarn(ing)?\b", re.I)
CLEAN_RE = re.compile(
    r"^(ok|done|success|up.to.date|no changes|nothing to commit|pass(ed|ing)?)", re.I
)


def load_config():
    mode, excludes = "failures", list(DEFAULT_EXCLUDES)
    try:
        if os.path.exists(CONFIG):
            txt = open(CONFIG, encoding="utf-8").read()
            m = re.search(r'mode\s*=\s*"(\w+)"', txt)
            if m:
                mode = m.group(1)
            m = re.search(r"exclude_commands\s*=\s*\[(.*?)\]", txt, re.S)
            if m:
                excludes = re.findall(r'"([^"]+)"', m.group(1)) or excludes
    except Exception:
        pass
    return mode, excludes


def is_excluded(cmd, excludes):
    joined = " ".join(cmd).lower()
    return any(joined.startswith(x.lower()) or (" " + x.lower() + " ") in (" " + joined + " ")
               for x in excludes)


def tee_write(cmd, raw):
    try:
        os.makedirs(TEE_DIR, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "_", " ".join(cmd).lower())[:40].strip("_")
        path = os.path.join(TEE_DIR, "%d_%s.log" % (int(time.time()), slug or "cmd"))
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write(raw)
        return path
    except Exception:
        return None


def dedup_counts(lines):
    out, prev, n = [], None, 0
    for ln in lines:
        if ln == prev:
            n += 1
        else:
            if prev is not None:
                out.append(prev if n == 1 else "%s  x%d" % (prev, n))
            prev, n = ln, 1
    if prev is not None:
        out.append(prev if n == 1 else "%s  ×%d" % (prev, n))
    return out


def clamp(raw, exit_code):
    lines = raw.splitlines()
    err = [l for l in lines if ERR_RE.search(l)]
    warn = [l for l in lines if WARN_RE.search(l) and l not in err]
    # success-collapse: clean exit, no error/warning → one line
    if exit_code == 0 and not err and not warn:
        first = next((l for l in lines if l.strip()), "")
        if not lines or CLEAN_RE.search(first.strip()) or len(lines) <= 1:
            return (first.strip() or "ok"), False
        kept = dedup_counts([l for l in lines if l.strip()])[:CAP_LIST]
        clipped = len(kept) < len([l for l in lines if l.strip()])
        return "\n".join(kept), clipped
    # has errors/warnings → keep signal, dedup
    body = dedup_counts(err)[:CAP_ERRORS] + dedup_counts(warn)[:CAP_WARNINGS]
    clipped = len(err) > CAP_ERRORS or len(warn) > CAP_WARNINGS
    if not body:  # underflow-safe: fall back to a tail of raw
        body = [l for l in lines if l.strip()][-CAP_ERRORS:]
        clipped = clipped or len(lines) > CAP_ERRORS
    return "\n".join(body), clipped


def main():
    argv = sys.argv[1:]
    as_json = False
    if argv and argv[0] == "--json":
        as_json, argv = True, argv[1:]
    if not argv or argv[0] != "--" or len(argv) < 2:
        sys.stderr.write("usage: orient_clamp.py [--json] -- <command> [args...]\n")
        sys.exit(2)
    cmd = argv[1:]
    mode, excludes = load_config()

    # Excluded → run raw, stream through unchanged.
    if is_excluded(cmd, excludes):
        try:
            return sys.exit(subprocess.call(cmd))
        except Exception as e:
            sys.stderr.write("orient_clamp passthrough error: %s\n" % e)
            sys.exit(1)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        raw = (proc.stdout or "") + (proc.stderr or "")
        code = proc.returncode
    except FileNotFoundError:
        sys.stderr.write("orient_clamp: command not found: %s\n" % cmd[0])
        sys.exit(127)
    except Exception:
        # fail-open: re-run inheriting stdio so the user still gets the real result
        try:
            sys.exit(subprocess.call(cmd))
        except Exception:
            sys.exit(1)

    reduced, clipped = clamp(raw, code)
    tee_path = None
    if mode == "always" or (mode == "failures" and (code != 0 or (clipped and code != 0))):
        tee_path = tee_write(cmd, raw)

    if as_json:
        import json
        print(json.dumps({
            "exit": code, "reduced": reduced, "tee": tee_path,
            "raw_chars": len(raw), "reduced_chars": len(reduced),
        }))
    else:
        print(reduced)
        if tee_path:
            print("[full output: %s]" % tee_path)
    sys.exit(code)  # propagate the REAL exit code


if __name__ == "__main__":
    main()

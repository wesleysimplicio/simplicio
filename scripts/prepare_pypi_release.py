#!/usr/bin/env python3
"""Prepare or verify the public PyPI launcher for one signed release manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_ROOT = ROOT / "pypi" / "simplicio"
DEFAULT_MANIFEST = ROOT / "simplicio-update-manifest.json"
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.-]*)?$")


class PreparationError(RuntimeError):
    """The public package cannot be bound safely to the requested release."""


def normalize_version(value: str) -> str:
    version = str(value or "").strip().lstrip("v")
    if not VERSION_PATTERN.fullmatch(version):
        raise PreparationError("invalid release version: %s" % (value or "<empty>"))
    return version


def replace_one(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise PreparationError("could not update exactly one %s" % label)
    return updated


def bind_manifest_digest(text: str, version: str, digest: str) -> str:
    block_pattern = re.compile(
        r"(TRUSTED_MANIFEST_SHA256\s*=\s*\{\n)(.*?)(^\})",
        re.MULTILINE | re.DOTALL,
    )
    match = block_pattern.search(text)
    if match is None:
        raise PreparationError("TRUSTED_MANIFEST_SHA256 mapping was not found")
    body = match.group(2)
    entry_pattern = re.compile(
        r'(?m)^[ \t]*"' + re.escape(version) + r'"[ \t]*:[ \t]*"[0-9a-fA-F]{64}",[ \t]*$'
    )
    desired_entry = '    "%s": "%s",' % (version, digest)
    if entry_pattern.search(body):
        body = entry_pattern.sub(desired_entry, body, count=1)
    else:
        body = body + desired_entry + "\n"
    return text[: match.start()] + match.group(1) + body + match.group(3) + text[match.end() :]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=str(path.parent),
        prefix=".%s." % path.name,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare(
    package_root: Path,
    manifest_path: Path,
    requested_version: str,
    *,
    check: bool = False,
) -> dict:
    package_root = Path(package_root)
    manifest_path = Path(manifest_path)
    version = normalize_version(requested_version)
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise PreparationError("could not read release manifest: %s" % exc) from exc
    manifest_version = normalize_version(str(manifest.get("version") or ""))
    if manifest_version != version:
        raise PreparationError(
            "requested version %s does not match manifest %s" % (version, manifest_version)
        )
    digest = hashlib.sha256(manifest_bytes).hexdigest()

    paths = {
        "pyproject.toml": package_root / "pyproject.toml",
        "simplicio/__init__.py": package_root / "simplicio" / "__init__.py",
        "simplicio/__main__.py": package_root / "simplicio" / "__main__.py",
    }
    try:
        current = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    except OSError as exc:
        raise PreparationError("could not read public package: %s" % exc) from exc
    if 'name = "simplicio-installer"' not in current["pyproject.toml"]:
        raise PreparationError("package is not simplicio-installer")

    desired = dict(current)
    desired["pyproject.toml"] = replace_one(
        current["pyproject.toml"],
        r'^version = "[^"]+"$',
        'version = "%s"' % version,
        "pyproject version",
    )
    desired["simplicio/__init__.py"] = replace_one(
        current["simplicio/__init__.py"],
        r'^__version__ = "[^"]+"$',
        '__version__ = "%s"' % version,
        "package version",
    )
    desired["simplicio/__main__.py"] = bind_manifest_digest(
        current["simplicio/__main__.py"], version, digest
    )
    changed = [name for name in paths if desired[name] != current[name]]
    if check and changed:
        raise PreparationError(
            "public package is not prepared for %s: %s" % (version, ", ".join(changed))
        )
    if not check:
        for name in changed:
            atomic_write(paths[name], desired[name])
    return {
        "schema": "simplicio.pypi-release-preparation/v1",
        "version": version,
        "manifest_sha256": digest,
        "changed_files": changed,
        "mode": "check" if check else "prepare",
        "ok": not (check and changed),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        receipt = prepare(
            args.package_root,
            args.manifest,
            args.version,
            check=args.check,
        )
    except PreparationError as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print("prepare-pypi-release: %s" % exc)
        return 1
    if args.json:
        print(json.dumps(receipt, sort_keys=True))
    else:
        print(
            "prepared simplicio-installer %s (manifest sha256:%s)"
            % (receipt["version"], receipt["manifest_sha256"])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

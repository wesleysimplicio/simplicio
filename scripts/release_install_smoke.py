#!/usr/bin/env python3
"""Run both public installation paths against one immutable release.

This is intentionally an end-to-end smoke: it uses the checked-out terminal
installer and a clean virtual environment that installs simplicio-installer
from PyPI. Both paths then download the same signed GitHub Release into an
isolated HOME and verify the installed Runtime JSON envelope.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "simplicio-update-manifest.json"
DEFAULT_PYPI_INDEX = "https://pypi.org/simple"


class SmokeError(RuntimeError):
    """An actionable release-install smoke failure."""


def _tail(value: str, limit: int = 800) -> str:
    return value[-limit:].strip()


def run_checked(command: list[str], env: dict[str, str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SmokeError("command could not complete: %s" % " ".join(command)) from exc
    if result.returncode != 0:
        detail = _tail(result.stderr or result.stdout)
        raise SmokeError("command failed (%s): %s" % (" ".join(command), detail))
    return result


def release_version(requested: str | None = None) -> str:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    version = str(manifest.get("version") or "").lstrip("v")
    if not version:
        raise SmokeError("simplicio-update-manifest.json has no version")
    if requested and requested.lstrip("v") != version:
        raise SmokeError("requested version %s does not match manifest %s" % (requested, version))
    return version


def current_target() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    mapping = {
        ("Darwin", "arm64"): "macos-arm64",
        ("Darwin", "aarch64"): "macos-arm64",
        ("Darwin", "x86_64"): "macos-x64",
        ("Linux", "x86_64"): "linux-x64",
        ("Linux", "amd64"): "linux-x64",
        ("Windows", "amd64"): "windows-x64",
        ("Windows", "x86_64"): "windows-x64",
    }
    try:
        return mapping[(system, machine)]
    except KeyError as exc:
        raise SmokeError("unsupported smoke host: %s/%s" % (system, machine)) from exc


def isolated_env(home: Path, bundle: Path, bin_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in ("SIMPLICIO_BIN_DIR", "SIMPLICIO_BUNDLE_DIR", "SIMPLICIO_VERSION"):
        env.pop(key, None)
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "SIMPLICIO_BUNDLE_DIR": str(bundle),
            "SIMPLICIO_BIN_DIR": str(bin_dir),
        }
    )
    return env


def installed_binary(bin_dir: Path) -> Path:
    return bin_dir / ("simplicio.exe" if os.name == "nt" else "simplicio")


def verify_runtime(binary: Path, env: dict[str, str], expected: str) -> dict:
    if not binary.is_file():
        raise SmokeError("installer did not create %s" % binary)
    payload = json.loads(run_checked([str(binary), "version", "--json"], env).stdout)
    runtime = payload.get("runtime") or {}
    actual = str(runtime.get("version") or payload.get("version") or "").lstrip("v")
    if actual != expected:
        raise SmokeError("installed Runtime version %s does not match %s" % (actual or "missing", expected))
    return {"binary": str(binary), "runtime_version": actual}


def terminal_install(version: str, root: Path) -> dict:
    home = root / "terminal-home"
    bundle = home / ".simplicio"
    bin_dir = root / "terminal-bin"
    home.mkdir(parents=True)
    env = isolated_env(home, bundle, bin_dir)
    env["SIMPLICIO_VERSION"] = version
    if os.name == "nt":
        shell = shutil.which("pwsh") or "pwsh"
        command = [shell, "-NoProfile", "-File", str(ROOT / "install.ps1"), "-Version", version]
    else:
        command = ["sh", str(ROOT / "install.sh")]
    result = run_checked(command, env)
    evidence = verify_runtime(installed_binary(bin_dir), env, version)
    evidence.update({"method": "terminal", "target": current_target(), "stdout_tail": _tail(result.stdout)})
    return evidence


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def venv_launcher(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "simplicio.exe"
    return venv / "bin" / "simplicio"


def pypi_install(version: str, root: Path, index_url: str) -> dict:
    venv = root / "pypi-venv"
    run_checked([sys.executable, "-m", "venv", str(venv)], dict(os.environ))
    python = venv_python(venv)
    install_command = [
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-cache-dir",
        "--no-deps",
        "--index-url",
        index_url,
        "simplicio-installer==" + version,
    ]
    last_error: SmokeError | None = None
    for _attempt in range(3):
        try:
            run_checked(install_command, dict(os.environ), timeout=180)
            last_error = None
            break
        except SmokeError as exc:
            last_error = exc
            time.sleep(5)
    if last_error is not None:
        raise last_error

    home = root / "pypi-home"
    bundle = home / ".simplicio"
    bin_dir = home / ".local" / "bin"
    home.mkdir(parents=True)
    env = isolated_env(home, bundle, bin_dir)
    result = run_checked([str(venv_launcher(venv)), "install"], env, timeout=300)
    evidence = verify_runtime(installed_binary(bin_dir), env, version)
    evidence.update({"method": "pypi", "index_url": index_url, "stdout_tail": _tail(result.stdout)})
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version")
    parser.add_argument("--terminal", action="store_true")
    parser.add_argument("--pypi", action="store_true")
    parser.add_argument("--pypi-index-url", default=os.environ.get("PYPI_INDEX_URL", DEFAULT_PYPI_INDEX))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    version = release_version(args.version)
    if not (args.terminal or args.pypi):
        args.terminal = args.pypi = True
    report = {"version": version, "target": current_target(), "checks": []}
    with tempfile.TemporaryDirectory(prefix="simplicio-release-install-") as temporary:
        root = Path(temporary)
        if args.terminal:
            report["checks"].append(terminal_install(version, root))
        if args.pypi:
            report["checks"].append(pypi_install(version, root, args.pypi_index_url))
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print("RELEASE INSTALL SMOKE PASS " + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

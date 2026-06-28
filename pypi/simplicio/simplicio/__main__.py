#!/usr/bin/env python3
"""Simplicio CLI entry point.

'pip install simplicio && simplicio install' downloads and installs the real binary.
All other commands are delegated to the binary.
"""

from __future__ import annotations

import subprocess
import sys
import os
import platform
import shutil

# Canonical install location (matches install.sh / install.ps1).
INSTALL_DIR = os.path.expanduser("~/.local/bin")
BINARY_NAME = "simplicio" + (".exe" if platform.system() == "Windows" else "")
BINARY_PATH = os.path.join(INSTALL_DIR, BINARY_NAME)

def _resolve_binary():
    """Find the installed real binary: canonical dir first, then PATH."""
    if os.path.exists(BINARY_PATH):
        return BINARY_PATH
    found = shutil.which("simplicio")
    # Avoid recursing into this very wrapper if it shadows the real binary.
    if found and os.path.realpath(found) != os.path.realpath(sys.argv[0]):
        return found
    return None

def do_install() -> None:
    """Install the real Simplicio binary via the canonical platform installer.

    Single source of truth: the shell/powershell installers handle release
    asset-name resolution, PATH, and the centralized ~/.local/bin location.
    """
    print("Installing Simplicio...")
    system = platform.system()
    if system in ("Darwin", "Linux"):
        subprocess.run(
            "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh",
            shell=True, check=True,
        )
    elif system == "Windows":
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.ps1 | iex"],
            check=True,
        )
    else:
        print(f"Unsupported platform: {system}")
        sys.exit(1)

def main():
    args = sys.argv[1:]
    
    if not args or args[0] == "install":
        do_install()
        return
    
    # If the real binary is installed, delegate to it.
    binary = _resolve_binary()
    if binary:
        try:
            subprocess.run([binary] + args, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)
    else:
        print("Simplicio is not installed. Run 'simplicio install' first.")
        sys.exit(1)

if __name__ == "__main__":
    main()

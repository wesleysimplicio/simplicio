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
import urllib.request
import json
import tarfile
import io
import shutil

INSTALL_DIR = os.path.expanduser("~/.simplicio/bin")
BINARY_NAME = "simplicio" + (".exe" if platform.system() == "Windows" else "")
BINARY_PATH = os.path.join(INSTALL_DIR, BINARY_NAME)

def do_install() -> None:
    """Download and install the Simplicio binary."""
    print("⚡ Installing Simplicio...")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    
    # Detect arch
    arch_map = {"x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}
    machine = platform.machine().lower()
    arch = arch_map.get(machine, machine)
    
    sys_map = {"Darwin": "apple-darwin", "Linux": "unknown-linux-gnu"}
    os_name = sys_map.get(platform.system(), platform.system().lower())
    
    url = f"https://github.com/wesleysimplicio/simplicio/releases/latest/download/simplicio-{arch}-{os_name}.tar.gz"
    
    print(f"  Downloading {url}...")
    try:
        resp = urllib.request.urlopen(url)
        data = resp.read()
    except Exception as e:
        print(f"  Download failed: {e}")
        print("  Falling back to install.sh...")
        subprocess.run(
            "curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/main/install.sh | sh",
            shell=True, check=True
        )
        return
    
    # Extract binary
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for member in tar.getmembers():
            if member.name.endswith("/simplicio") or member.name == "simplicio":
                tar.extract(member, INSTALL_DIR)
                extracted = os.path.join(INSTALL_DIR, member.name)
                if extracted != BINARY_PATH:
                    shutil.move(extracted, BINARY_PATH)
                break
    
    os.chmod(BINARY_PATH, 0o755)
    print(f"✅ Installed at {BINARY_PATH}")
    print("   Run 'simplicio --help' to get started.")

def main():
    args = sys.argv[1:]
    
    if not args or args[0] == "install":
        do_install()
        return
    
    # If binary exists, delegate
    if os.path.exists(BINARY_PATH):
        try:
            subprocess.run([BINARY_PATH] + args, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)
    else:
        print("Simplicio is not installed. Run 'simplicio install' first.")
        sys.exit(1)

if __name__ == "__main__":
    main()

# Optional modules (v3.8.49)

Zig-cross optional binaries for the Simplicio Runtime. They are GitHub
Release assets, not signed `simplicio-{os}-{arch}` Runtime executables.

- Release: https://github.com/wesleysimplicio/simplicio/releases/tag/v3.8.49
- Zip: `simplicio-modules-3.8.49.zip`
- Manifest: `manifest.json` (sha256 + PE/Mach-O/ELF magic)

Signed Runtime remains **v3.8.47**. `install.sh` / `install.ps1` and host
plugins pin that version. Do not promote v3.8.49 to latest until a signed
official-runtime binary exists for every target in `targets.json`.

Modules: browser, computer, voice, n8n, skills, image, comms.
Targets: linux-x64, macos-arm64, macos-x64, windows-x64.

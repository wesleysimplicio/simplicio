# Optional modules (v3.8.49)

Zig-cross optional binaries. GitHub Release assets.

- Latest public release: https://github.com/wesleysimplicio/simplicio/releases/tag/v3.8.49
- Zip: `simplicio-modules-3.8.49.zip`
- Manifest: `manifest.json` (sha256 + PE/Mach-O/ELF magic)

Signed `simplicio-{os}-{arch}` installer assets on v3.8.49 are the **v3.8.47
bytes** (Ed25519 unchanged). See `runtime_binary` in
`simplicio-update-manifest.json`. The kernel still reports 3.8.47 until a new
official-runtime is signed.

Future overlay cuts: `python3.11 scripts/cut_public_overlay_release.py`.

Modules: browser, computer, voice, n8n, skills, image, comms.
Targets: linux-x64, macos-arm64, macos-x64, windows-x64.

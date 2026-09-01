# Desktop v3.8.41 native release preflight

Date: 2026-09-01  
Status: **blocked; local preflight only; no public release**

This record captures the evidence produced on the Apple Silicon host. It is not a release declaration and does not close issues #282 or #283.

## Inputs

- Desktop source baseline: `origin/master` at `96c7447dc3877d40846729b105b13b1d6a62835e`
- Desktop candidate: `3.8.41`
- Runtime sidecar: public Runtime `v3.8.40`, macOS ARM64
- Runtime sidecar SHA-256: `f8404218d89bb6599d2f83335d3419f86fe9f81730a53b9690639c0f9fee9a8e`
- Target: `aarch64-apple-darwin`

## Local evidence

- `npm --prefix apps/desktop test`: 50 test files, 337 tests passed.
- `npm --prefix apps/desktop run build`: passed.
- Packaged sidecar smoke: 1 passed, 0 failed.
- Tauri CLI: `2.11.4`.
- Tauri bundle: `Simplicio.app`, `Simplicio-3.8.41-arm64.dmg`, and `Simplicio-3.8.41-arm64.zip`.
- SHA-256 of local ZIP: `5ff980aba7d62868fffa62d08b88dc76d24e4fa8d4b4be0cbf0d1eb72ea47d47`.
- SHA-256 of local DMG: `ae58107de0e361da45b0b7762e15de1db52093d85a4d1e30e9f05d7039be6fcc`.
- The sidecar inside the app, ZIP extraction, and mounted DMG all match the Runtime digest above.
- `codesign --verify --deep --strict`: passed after local ad-hoc signing.

## Blocking gates

- `security find-identity -v -p codesigning`: 0 valid identities. The package is ad-hoc signed, with no Developer ID identity.
- `spctl --assess --type execute`: rejected. Apple notarization/Gatekeeper acceptance is not proven.
- This host has Command Line Tools but no full Xcode; the required multi-platform native build/sign sequence was not completed.
- Windows x64, Linux x64, and macOS Intel installers were not built or smoke-tested.
- No clean native installation with a real Google OAuth grant, callback, logout, or redacted screenshots was performed. The UI control executable required for that manual evidence was unavailable in this session.
- Desktop ZIP/DMG Ed25519 signatures, SBOM, and provenance were not generated. The Runtime sidecar's own signed manifest does not substitute for signatures/provenance of the Desktop containers.

## Release decision

Do not tag, publish, or close #282/#283 from this preflight. The next release attempt must add the missing platform builds, platform signing/notarization, Desktop-container attestations, served-byte re-download checks, and the manual clean-HOME Google OAuth evidence.

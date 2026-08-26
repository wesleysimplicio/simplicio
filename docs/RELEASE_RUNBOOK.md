# Public Runtime release runbook

This repository is the public distribution surface for Simplicio Runtime. It
does not build source from sibling `simplicio-*` repositories during install.
The release files committed here and attached to the GitHub Release must be
the four signed Runtime binaries plus the Desktop artifacts listed for the release.

## Required release files

For each release `vX.Y.Z`, publish:

- `simplicio-macos-arm64` and `.sig`;
- `simplicio-macos-x64` and `.sig`;
- `simplicio-linux-x64` and `.sig`;
- `simplicio-windows-x64.exe` and `.sig`;
- `SHA256SUMS`;
- `simplicio-update-manifest.json`;
- matching `version.txt` and `VERSION.md`;
- `Simplicio-X.Y.Z-arm64.dmg` and `.zip` when the Desktop build is published;
- SHA-256 and signing/notarization status for each Desktop artifact.

The manifest must use the immutable `vX.Y.Z` download URLs, require Ed25519,
refuse unsigned artifacts, match the checksums and sidecars byte-for-byte, and
publish the root `signing_pubkey` exactly as
`2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok=`.
Do not publish a new release from a checkout where `version.txt` and the
manifest disagree.

## Desktop release assets

Desktop artifacts are published as assets of the public GitHub Release. They
are not part of the signed Runtime update manifest because they are consumed
by the Desktop distribution path. The release record must include their exact
filename, SHA-256, size, and platform signing/notarization status.

For `v3.8.24`:

- `Simplicio-3.8.24-arm64.dmg` — 135,726,628 bytes —
  `c4d8b2164f1bf6239ecd993f8b7cb6de2ef36b7413f6566611f265e4f17d0d54`;
- `Simplicio-3.8.24-arm64.zip` — 134,909,582 bytes —
  `4148e1402a61ec4635279beea0c712ce0c5a1c7710374f89d6239c19dce056e9`;
- Apple Developer ID signing and notarization: unavailable for this build.

Both files must be attached to the public `v3.8.24` GitHub Release.

## Signature payload contract

The compiled Runtime command `update sign <sha256>` signs this exact UTF-8
payload, including the domain prefix and the lowercase hexadecimal digest:

```text
simplicio-release-v1:<lowercase-sha256>
```

The `.sig` sidecar and the manifest `signature` field must contain the same
`ed25519:<base64>` value. The bootstrap verifier used by both `install.ps1`
and `install.sh` validates this domain-separated payload and is pinned by its
SHA-256 in the installers. A raw 32-byte SHA-256 digest is not a valid release
signature payload. Missing or divergent `signing_pubkey` values are fatal. The
publication gate also verifies every signature before a release can be staged;
`SIMPLICIO_ALLOW_UNVERIFIED=1` never bypasses a stable release failure and is
only permitted for an explicitly selected unofficial channel.

## Manual publication order

1. Build and sign the artifacts from the intended `simplicio-runtime` main
   commit.
2. Commit the Runtime metadata and release record into a release branch;
   keep oversized Desktop artifacts in staging for GitHub Release upload.
3. Run `python3 scripts/verify_distribution_consistency.py`,
   `python3 -m unittest discover -s tests -p 'test_verify_ed25519.py'`, and
   the release provenance tests.
4. Open and merge a PR into `master`.
5. Create the immutable `vX.Y.Z` tag at that merge commit.
6. Upload the exact files from the merged tree with `gh release create`.
7. Run the mandatory post-release smoke on the published GitHub Release:
   `VERSION=vX.Y.Z; python3 scripts/post_release_smoke.py --version "$VERSION" --execute --json`.
   Run it once on each native host in the support matrix; this re-downloads
   the release and checks every artifact, sidecar, SBOM, provenance record,
   version, clean-home login gate, and MCP login gate.

The release is not ready for users if any check is skipped or unverified. Do
not force-move a published tag; use a new patch release if published bytes
need correction.

The post-release receipt is part of the release evidence. It must contain a
successful result for all four targets from static verification and a
successful native result for macOS arm64, macOS x64, Linux x64, and Windows
x64. A green pre-publish build does not replace this test: the test validates
the bytes and metadata actually served to users.

The installer target ID and the build target in provenance are separate
namespaces. Their approved aliases are maintained in
`distribution/targets.json`; the smoke test accepts only those explicit
aliases, never an arbitrary target string.

## Installer smoke for every release

Depois de publicar o GitHub Release e o pacote PyPI da mesma versão, execute o
smoke multiplataforma. Ele cria `HOME` e virtualenvs temporários, instala pelo
script de terminal e por `pip`, baixa a release assinada, e verifica o binário
instalado sem reutilizar estado do mantenedor:

```bash
python3 scripts/release_install_smoke.py --version vX.Y.Z --json
```

O workflow `publish-pypi.yml` executa esse mesmo comando em Linux, Windows,
macOS Intel e macOS Apple Silicon depois do job de publicação. Uma nova release
não deve ser considerada pronta se qualquer um dos dois métodos falhar.

## Latest-only installation

The PyPI bootstrap installs the launcher and then resolves the signed Runtime
release required by that package version:

```bash
python3 -m pip install --upgrade simplicio-installer
simplicio install
```

After installation, login is mandatory:

```bash
simplicio auth login
simplicio auth status --json
simplicio ecosystem verify --json
```

See the Runtime repository's
[manual release runbook](https://github.com/wesleysimplicio/simplicio-runtime/blob/main/docs/PUBLIC_RELEASE_RUNBOOK.md)
for signing-key handling and the full maintainer commands.

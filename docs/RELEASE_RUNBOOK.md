# Public Runtime release runbook

This repository is the public distribution surface for Simplicio Runtime. It
does not build source from sibling `simplicio-*` repositories during install.
The release files committed here and attached to the GitHub Release must be
the same four signed binaries.

## Required release files

For each release `vX.Y.Z`, publish:

- `simplicio-macos-arm64` and `.sig`;
- `simplicio-macos-x64` and `.sig`;
- `simplicio-linux-x64` and `.sig`;
- `simplicio-windows-x64.exe` and `.sig`;
- `SHA256SUMS`;
- `simplicio-update-manifest.json`;
- matching `version.txt` and `VERSION.md`.

The manifest must use the immutable `vX.Y.Z` download URLs, require Ed25519,
refuse unsigned artifacts, and match the checksums and sidecars byte-for-byte.
Do not publish a new release from a checkout where `version.txt` and the
manifest disagree.

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
signature payload. The publication gate also verifies every signature before a
release can be staged; never bypass it with `SIMPLICIO_ALLOW_UNVERIFIED=1`.

## Manual publication order

1. Build and sign the artifacts from the intended `simplicio-runtime` main
   commit.
2. Copy only the required public files into a release branch.
3. Run `python3 scripts/verify_distribution_consistency.py`,
   `python3 -m unittest discover -s tests -p 'test_verify_ed25519.py'`, and
   the release provenance tests.
4. Open and merge a PR into `master`.
5. Create the immutable `vX.Y.Z` tag at that merge commit.
6. Upload the exact files from the merged tree with `gh release create`.
7. Re-download every asset, verify SHA-256 and Ed25519, and test both
   installers plus `simplicio ecosystem verify --json`.

The release is not ready for users if any check is skipped or unverified. Do
not force-move a published tag; use a new patch release if published bytes
need correction.

## Latest-only installation

Installers intentionally resolve the GitHub `latest` release instead of a
hard-coded version:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
powershell -c "irm https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.ps1 | iex"
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

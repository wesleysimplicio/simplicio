# Public Runtime release runbook

This repository is the public distribution surface for Simplicio Runtime. It
does not build source from sibling `simplicio-*` repositories during install.
Release metadata, signatures, SBOMs, provenance, checksums, manifests, and hooks
are committed here. Runtime and Desktop executables are staged locally and
attached to the GitHub Release; the source-tree policy intentionally refuses to
track executable build products.

Publication is local/manual through `scripts/publish_release_local.py`. This
public repository must not contain remote workflow definitions. The distribution
audit checks the actual Python publisher's ordered gates and explicit asset
set without importing or executing it. Passing this source contract is not a
build, signature, upload, or installed-platform receipt.

## Required release files

For each release `vX.Y.Z`, publish:

- `simplicio-macos-arm64` and `.sig`;
- `simplicio-macos-x64` and `.sig`;
- `simplicio-linux-x64` and `.sig`;
- `simplicio-windows-x64.exe` and `.sig`;
- a `.spdx.json` SBOM and `.provenance.json` record for each of the four Runtime
  executables, in addition to its matching `.sig`;
- `SHA256SUMS`;
- `simplicio-update-manifest.json`;
- matching `version.txt` and `VERSION.md`;
- `codex/mcp-route.sh` and `codex/mcp-route.ps1`, copied from the same Runtime
  source commit and committed in the immutable tag;
- `Simplicio-X.Y.Z-arm64.dmg` and `.zip` when the Desktop build is published;
- SHA-256 and signing/notarization status for each Desktop artifact.

The manifest must use the immutable `vX.Y.Z` download URLs, require Ed25519,
refuse unsigned artifacts, match the checksums and sidecars byte-for-byte, and
publish the root `signing_pubkey` exactly as
`2RoVWAoqA/DtDkT5PZdzQYIP82zFskQqJx4S1w06Wok=`.
Do not publish a new release from a checkout where `version.txt` and the
manifest disagree.

The Codex hooks are versioned tag files rather than GitHub Release assets.
Before tagging, execute `bash tests/test_codex_hooks.sh` and require every
allow-unchanged case to exit zero with empty stdout. A bare
`permissionDecision: "allow"` without `updatedInput` is release-blocking.

## Desktop release assets

Desktop artifacts are published as assets of the public GitHub Release. They
are not part of the signed Runtime update manifest because they are consumed
by the Desktop distribution path. The release record must include their exact
filename, SHA-256, size, and platform signing/notarization status.

### Published Desktop v3.8.39

The Desktop assets were added manually to the existing public `v3.8.39`
release after [PR #263](https://github.com/wesleysimplicio/simplicio/pull/263)
merged. Their source commit is `dd7dd0665630fcdd6c9a76d07956d840f80fc0a9`;
the already published Runtime tag was not moved and no existing asset was
overwritten.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `Simplicio-3.8.39-arm64.dmg` | 33754359 | `5b2c6380d9f5b52ee0371cb3937a4279a806e22dd88f5a80e121e48e7de96735` |
| `Simplicio-3.8.39-arm64.zip` | 32030285 | `38c73a9c7d6a80a2e370b3ce59d4299fae9f760e440dd406a9d453c6394ca290` |

Both packages and their `.sig`, `.spdx.json`, and `.provenance.json` sidecars
were downloaded again from GitHub. All eight assets matched the verified
local files byte-for-byte; Ed25519 signatures, SBOM digests, provenance sizes,
version, and source commit were checked against the downloaded files.

The bundled `simplicio` must preserve the exact digest of the official
`simplicio-macos-arm64` release asset:
`c6dca7c384aaedb0226f6ea93a0dbe259a175f999c070e6c8ef609af519e5130`.
When repairing the local ad-hoc app signature, sign the outer bundle only.
Do not use `codesign --force --deep --sign -`: it rewrites the Runtime
sidecar signature and changes its digest. `--deep` is appropriate for the
subsequent verification, not for this signing step. Verify the sidecar hash
before and after signing, then package, hash, and sign the final archives.

Verified locally on macOS ARM64:

- DMG mount, ZIP extraction, and installed app report Desktop `3.8.39`;
- the bundled Runtime hash matches the official asset in all three locations;
- `codesign --verify --deep --strict` passes in all three locations;
- the installed app opens with Runtime `3.8.39`, active account, and working
  navigation; frontend tests/build, Rust tests, and repository validation pass.

Still open, and not implied by successful publication:

- Apple Developer ID signing and notarization are unavailable. The signature
  is ad-hoc and `spctl`/Gatekeeper rejects the app. Ed25519 distribution
  authentication does not replace Apple platform trust.
- Ambient/Workspace/Agent action contracts are incomplete in the installed
  path. Today reports `ambient.today_projection_unavailable`; disabled
  actions are not counted as working workflows.
- Native installed smoke for Windows, Linux, and macOS Intel, plus composed
  Loop/Agent/Code N/N-1 release-train gates, are not proven by this host's run.
- Desktop provenance truthfully records
  `optimization_profile_receipt_not_supplied`; no optimization result is
  inferred from a successful build.

### Historical Desktop v3.8.24

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
   commit: Windows first, then both macOS targets, then Linux. Assemble an
   external local bundle containing all required Runtime files and Codex hooks.
   Keep Desktop packages separate; the Runtime publisher's explicit asset set
   does not upload them. Never force-add executable products to the source tree.
2. Start from an updated, clean public `master`. Use an authenticated local `gh`
   session and a Python environment with `requirements-quality.txt`, `build`,
   and `twine` installed; `pwsh` is mandatory for the Windows hook test. Supply
   PyPI credentials through the environment/credential manager, never command
   arguments, source files, or release notes.
3. Run the local source and regression gates before publishing:

   ```bash
   python3 scripts/verify_distribution_consistency.py
   python3 -m pytest -q tests/test_distribution_consistency.py tests/test_release_provenance.py tests/test_verify_ed25519.py tests/test_release_local_contract.py tests/test_plugin_release_policy.py
   ```

4. Inspect the local preflight using the exact intended version, bundle path,
   and full 40-character Runtime source commit (replace the placeholders):

   ```bash
   python3 scripts/publish_release_local.py --bundle /absolute/path/to/verified-bundle --version vX.Y.Z --source-commit RUNTIME_COMMIT_40_HEX --check-only
   ```

   `--check-only` checks repository/authentication/publication state. It does
   **not** validate bundle contents or prove signatures, builds, or installation;
   its `ready` result must not be reported as a verified release.
5. Invoke the same local command with `--publish` in place of `--check-only`.
   This is the explicit mutating step: it verifies the signed bundle, stages
   metadata/hooks, runs the local gates, builds and smoke-tests the wheel,
   opens and merges the release PR into `master`, compares the merged files,
   tags that commit, and creates the public release with `--verify-tag` and an
   explicit list of assets. It then checks terminal installation, uploads the
   wheel to PyPI, and verifies package installation and the downloaded release.
   Do not separately create the tag or upload assets before this command.

   The publisher also stages the plugin bootstrap target, its immutable public
   installer commit, and SHA-256 hashes of the original Git blob bytes. From
   Runtime 3.8.40 onward, the plugin requires the persistent-login capability
   floor; later patch releases update the bootstrap target without forcing an
   upgrade from a compatible installed Runtime. A policy change increments the
   plugin patch version consistently in its Codex, Claude, and portable manifests.
   The publisher verifies both downloaded installer scripts and runs the real
   bootstrap tests before tagging, including when resuming an interrupted release.
   Do not update a plugin's target to an unpublished Runtime version in advance.
6. If publication partially fails, inspect the receipts and remote state before
   choosing any recovery. `--resume` requires the matching existing tag, final
   release and exact Runtime asset set; it rechecks the bundle/hooks and skips
   the PyPI upload only when that version already exists. It does not recreate
   a release, fix incomplete assets, or authorize overwriting them. Desktop
   assets already attached to that release are outside this resume contract.
7. Run the mandatory post-release smoke on the published GitHub Release:
   `python3 scripts/post_release_smoke.py --version vX.Y.Z --execute --json`.
   Run it once on each native host in the support matrix; this re-downloads
   the release and checks every artifact, sidecar, SBOM, provenance record,
   version, clean-home login gate, and MCP login gate.

The release is not ready for users if any check is skipped or unverified. Do
not force-move a published tag; use a new patch release if published bytes
need correction.

`scripts/verify_release_provenance.py` remains a separate local verification
tool for remote/tag identity and immutable staging: its `state`, `plan`,
`download`, `verify-staged`, and `metadata` commands do not publish anything.
Its artifact-only staging set is not the Runtime publisher's complete bundle
with signature, SBOM, provenance, and hook files. Do not substitute one for
the other or treat either source check as proof of a completed publication.

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

O publicador local/manual verifica o wheel local antes da publicação. Depois
de criar o GitHub Release, executa o smoke com `--terminal`; após publicar o
PyPI, executa-o com `--pypi`, seguido de `post_release_smoke.py --execute`.
Os recibos nativos de Linux, Windows, macOS Intel e macOS Apple Silicon são
registrados por host, sem delegar build ou publicação a workflows remotos. Uma
nova release não deve ser considerada pronta se qualquer um dos dois métodos falhar.

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

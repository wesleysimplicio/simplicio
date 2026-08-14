# Simplicio Runtime

Simplicio Runtime is distributed as one native `simplicio` binary. It is the
Simplicio MCP server: install the binary, register it in an MCP-compatible
client, and let the client start it over stdio.

This repository is intentionally an installation and quick-start guide. It
does not try to promote every Simplicio component or document every runtime
capability.

## Scope

- **Runtime binary:** `simplicio`
- **MCP entry point:** `simplicio serve --mcp --stdio`
- **No local LLM:** the runtime does not include, download, or require local
  model weights.
- **Official distribution:** use the release binary or the official installer.
- **Release page:** [github.com/wesleysimplicio/simplicio/releases](https://github.com/wesleysimplicio/simplicio/releases)

There is no PyPI installation step for the Runtime binary.

## Install the latest release

### macOS and Linux

The official installer detects the platform, downloads the latest release,
verifies the published SHA-256 checksum, and installs `simplicio`:

```sh
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

To install a specific release instead of the latest one:

```sh
export SIMPLICIO_VERSION=v3.8.11
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

The installer normally places the binary in `~/.local/bin`. If the shell
cannot find `simplicio`, add that directory to `PATH` and open a new terminal.

### Direct binary download

Use the release asset that matches the operating system and CPU architecture.
For the currently published targets:

```sh
# Linux x64
mkdir -p "$HOME/.local/bin"
curl -fL https://github.com/wesleysimplicio/simplicio/releases/latest/download/simplicio-linux-x64 \
  -o "$HOME/.local/bin/simplicio"
chmod +x "$HOME/.local/bin/simplicio"
```

For macOS Apple Silicon, use `simplicio-macos-arm64` in the download URL.
Checksums are published as `SHA256SUMS` and in
`simplicio-update-manifest.json`.

If a target is not present in the selected release, do not use an unrelated
asset; check the [release assets](https://github.com/wesleysimplicio/simplicio/releases/latest).

## Verify the installation

```sh
simplicio version
simplicio doctor
```

## Configure the MCP server

The product is referred to as **Simplicio MCP**. The current Runtime command
that exposes it over stdio is:

```sh
simplicio serve --mcp --stdio
```

An MCP client configuration normally looks like this:

```json
{
  "mcpServers": {
    "simplicio": {
      "command": "simplicio",
      "args": ["serve", "--mcp", "--stdio"]
    }
  }
}
```

If `simplicio` is not on the client's `PATH`, replace `command` with the
absolute path to the installed binary. The exact configuration file depends
on the MCP client.

## Update

```sh
simplicio update check
simplicio update apply
```

## Troubleshooting

- `command not found`: add `~/.local/bin` to `PATH` and restart the terminal.
- Checksum failure: download again from the official release page and do not
  bypass verification casually.
- Unsupported platform or architecture: confirm that a matching asset exists
  in the selected release.

## License

Proprietary. See [LICENSE](LICENSE).

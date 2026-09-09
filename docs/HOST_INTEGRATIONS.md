# Host integration registry

The public installers distribute one verified Runtime and invoke:

```text
simplicio mcp register --binary <absolute-path> --json
```

Runtime owns the transactional configuration changes. The PyPI launcher records
the redacted result beside the binary in `simplicio-host-integrations.json`.
The [29-host README matrix](../README.md#host-integrations) and
[installer paths and upstream contracts](INSTALLER_HOSTS.md) describe the
expanded adapters and their release boundary. Immutable v3.8.47 downloads do
not gain adapters merely because the public metadata changed.

## Detection and registration evidence

Detection does not launch a client. It checks exact executable names (including
Windows executable suffixes), documented application paths and existing
configuration files. These are detection signals, not proof of an active MCP
connection. Native adapters use initialized user configuration directories.

A host becomes `registered` only when an applied Runtime receipt reports the
corresponding successful write. The launcher understands native `writes`
entries and legacy `registered` arrays. Dry-run plans never count as applied.
Malformed or custom configuration produces a reasoned skipped result.

Pi uses a bundled extension discovered from
`~/.pi/agent/extensions/simplicio.ts`; oh-my-pi uses its independent
`~/.omp/agent/mcp.json` registry. A generic Pi `mcp.json` is not sufficient.
Goose, Vibe, Continue, Amp and OpenCode-family clients have distinct schemas;
the Python generic JSON helper defers those writes to Runtime.

Devin requires setup in the environment where Devin executes. Codebuff requires
a project/SDK bridge. Neither is reported as automatically configured by a local
user registry. DeepSeek Harness remains unverified; a model name alone does
not identify a compatible host executable.

## Opt-out

```text
SIMPLICIO_SKIP_HOSTS=amp,pi
SIMPLICIO_SKIP_AMP=1
```

The new native adapters honor their opt-outs without removing existing files.
The detection report also honors these controls. Support in older installed
Runtime versions is version-specific; inspect the native dry-run receipt.
Explicit disabled settings and client trust/permission prompts remain owned
by the client.

## Receipt and live verification

The `simplicio.host-integration/v1` receipt contains per-host detection evidence,
capability, status and an upstream documentation reference. It omits credentials
and is written atomically with mode `0600`.

After registration, restart or reload the client, inspect its tools list and
make a harmless `simplicio_map` call in a test repository. Configuration
round-trip tests do not establish live acceptance in every third-party host.

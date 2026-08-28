# Desktop provider contract

## Status semantics

| Status | Required evidence | User action |
| --- | --- | --- |
| `connected` | executable or host found, supported version, valid registration and successful Runtime handshake | inspect or disconnect |
| `detected` | host or CLI found, but registration/handshake is absent or not yet checked | connect |
| `needs_attention` | an intended connection exists and a specific validation failed | repair |
| `not_installed` | no supported installation found in bounded platform locations | install instructions |

Detection alone must never produce a green state. A registration file alone is
also insufficient: the current binary identity and a live or fixture-backed
handshake must agree.

## Initial coverage

The first-class matrix starts with Codex and Claude Code, followed by Cursor,
VS Code/Cline, Windsurf, Kiro, JetBrains and Zed as their registration and
handshake fixtures become available. OpenCode, Grok, Hermes and Gemini CLI
start as compatible adapters and graduate only after cross-platform fixtures
and clean-machine tests pass.

This host registry is intentionally separate from the model-provider registry.
Finding an OpenAI, Anthropic, xAI or Bedrock model credential does not prove
that Codex, Claude Code, Grok or another host is connected to Simplicio.

Every adapter implements the same Runtime-owned interface:

```text
detect -> inspect registration -> validate version -> handshake -> explain -> propose repair
```

The snapshot returns redacted state and account labels only. Secrets, complete
configuration files, raw command output and provider transcripts never cross
the Desktop bridge.

## Host-path caveat

Packaged apps do not inherit the same `PATH` as an interactive shell. Detection
must cover version managers and known installation roots without sourcing user
shell startup files. The result records where it looked and why a host is still
unknown, but exposes only a bounded explanation to the UI.

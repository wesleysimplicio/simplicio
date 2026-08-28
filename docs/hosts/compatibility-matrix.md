# Compatibility matrix

The installer exposes this matrix through `compatibility_matrix()` and keeps
every row explicit. Detection is exact and non-invasive; `unsupported` rows
have no guessed executable and no automatic configuration writer.

| Host | Capability | Contract | Probe |
| --- | --- | --- | --- |
| Claude Code | runtime-mcp | delegated-to-runtime | `claude` |
| Cursor | runtime-mcp | delegated-to-runtime | `cursor` |
| DeepSeek Harness | unsupported | unverified | — |
| OpenCode | runtime-mcp | delegated-to-runtime | `opencode` |
| Visual Studio Code | runtime-mcp | delegated-to-runtime | `code`, `code-insiders` |
| Google Antigravity | unsupported | unverified | — |
| Kiro | runtime-mcp | delegated-to-runtime | `kiro-cli` |
| Pi | runtime-mcp | delegated-to-runtime | `pi` |
| oh-my-pi | runtime-mcp | delegated-to-runtime | `omp` |
| OrcaDev / Orca ADE | portable-cli | documented-cli | `orca status --json` |
| Command Code | unsupported | unverified | — |
| Grok | unsupported | unverified | — |
| GitHub Copilot | unsupported | unverified | — |
| MiMo Code | unsupported | unverified | — |
| Amp | unsupported | unverified | — |
| OpenClaude | unsupported | unverified | — |
| Hermes Agent | unsupported | unverified | — |
| Devin | unsupported | unverified | — |
| Goose | unsupported | unverified | — |
| Auggie | unsupported | unverified | — |
| Autohand Code | unsupported | unverified | — |
| Charm/Crush | unsupported | unverified | — |
| Cline | unsupported | unverified | — |
| Codebuff | unsupported | unverified | — |
| Continue | unsupported | unverified | — |
| Droid | unsupported | unverified | — |
| Kilocode | unsupported | unverified | — |
| Kimi | unsupported | unverified | — |
| Mistral Vibe | unsupported | unverified | — |
| Qwen Code | unsupported | unverified | — |
| Rovo Dev | unsupported | unverified | — |

The returned matrix contains only public contract metadata. It never includes
credentials, prompt bodies, configuration bodies, or host process output.

---
description: Install the simplicio-prompt runtime contract into the current repository's agent rules files (CLAUDE.md, AGENTS.md, .cursorrules, .github/copilot-instructions.md, etc.).
argument-hint: "[target: claude-code|codex|hermes|opencode|cursor|copilot|cline|aider|gemini|all]"
allowed-tools: Bash
---

Install the simplicio-prompt runtime contract into the repository. The target
argument selects which agent rule files to write:

- `claude-code` → `CLAUDE.md`
- `codex` → `AGENTS.md`
- `hermes` → `AGENTS.md`
- `opencode` → `AGENTS.md`
- `cursor` → `.cursor/rules/simplicio-prompt.mdc` (+ legacy `.cursorrules`)
- `copilot` → `.github/copilot-instructions.md`
- `cline` → `.clinerules/simplicio-prompt.md`
- `aider` → `CONVENTIONS.md`
- `gemini` → `GEMINI.md`
- `all` → every file above

Default target if `$ARGUMENTS` is empty: `claude-code`.

Run:

```bash
npx simplicio-prompt --target ${ARGUMENTS:-claude-code}
```

Report which files were created or updated. The CLI wraps content in
`<!-- simplicio-prompt:start -->` / `<!-- simplicio-prompt:end -->` markers so
reinstalling updates in place instead of duplicating.

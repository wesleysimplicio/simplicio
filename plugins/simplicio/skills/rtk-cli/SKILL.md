---
name: rtk-cli
description: usar RTK CLI para reduzir tokens em exploração de repositório, git, grep/find e comandos shell verbosos, preservando o sinal técnico relevante
source: https://github.com/rtk-ai/rtk
---

# Skill: `rtk-cli`

Use RTK quando o gargalo for **ruído de terminal**. A ideia: comprimir output verboso antes de ele virar contexto de agent.

> RTK é opcional. Se não estiver instalado, continua com o comando normal.

---

## Trigger

- Quando o usuário pedir para economizar tokens.
- Quando a task envolver muito `git status`, `git diff`, `git log`, `grep`, `find`, `ls`, `npm test`, `cargo test`, `gh ...`.
- Quando a exploração for shell-heavy e o output normal do terminal tende a desperdiçar contexto.
- Quando o pedido mencionar explicitamente `rtk`, `RTK CLI`, `Rust Token Killer`.

Não ativar para:

- comandos interativos;
- browser/UI automation;
- output que precisa ser preservado verbatim como evidência principal.

---

## Steps

1. Verifique se `rtk` existe no ambiente: `command -v rtk`.
2. Se existir, prefira `rtk read`, `rtk grep`, `rtk find`, `rtk git ...` e `rtk <comando-verbooso>` nas etapas de inspeção/validação.
3. Se não existir, siga normalmente e não bloqueie a task só por isso.
4. Quando um comando exigir a saída crua como evidência, rode sem RTK.
5. Se precisar explicar o padrão ao usuário/time, registre que RTK é um acelerador opcional para reduzir tokens, não uma dependência obrigatória do projeto.

---

## Padrões

- Prefira:
  - `rtk read AGENTS.md`
  - `rtk grep "pattern" src/`
  - `rtk find "*.ts" .`
  - `rtk git status`
  - `rtk git diff`
  - `rtk git log -n 10`
  - `rtk npm test`
- Evite RTK em:
  - `curl`
  - `playwright`
  - comandos com prompt interativo
  - comandos em que cada linha completa do output importa para auditoria
- Se houver configuração local de RTK, use exclusões para comandos como `curl` e `playwright`.
- Trate RTK como otimização de I/O textual, não como substituto de leitura criteriosa.

---

## Definition of Done

- [ ] `rtk` foi usado quando disponível em comandos shell-heavy relevantes.
- [ ] Comandos que precisavam output bruto ficaram fora do RTK.
- [ ] A task não ficou bloqueada na ausência de RTK.
- [ ] O padrão de uso ficou documentado no repo para sessões futuras.

---

## Exemplos

```bash
command -v rtk >/dev/null 2>&1 && rtk git status || git status
command -v rtk >/dev/null 2>&1 && rtk grep "TODO" . || rg "TODO" .
command -v rtk >/dev/null 2>&1 && rtk npm test || npm test
```

---

## Notas

- Docs oficiais: `rtk init --codex`, `rtk init -g`, `rtk gain`, `rtk --version`.
- Fonte primária: `rtk-ai/rtk`.
- Integração com Codex é por instrução/prompt-level; não depende de hook nativo no Codex.

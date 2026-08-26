# Registro de erros dos instaladores

Registro versionado dos incidentes observados nos instaladores públicos e dos
sentinelas de regressão que devem continuar sendo executados. O registro cobre
Windows PowerShell e o caminho comum macOS/Linux; falhas de contrato ainda não
resolvidas permanecem como `open`.

A fonte legível por máquina é
[`tests/install_error_registry.json`](../tests/install_error_registry.json). Cada
entrada aponta para pelo menos um teste executável. O teste do registro valida
também os caminhos públicos, o fallback de autenticação e a limpeza de staging.

## Status

- `fixed`: correção já publicada.
- `guarded`: o caminho de erro está tratado e protegido por teste.
- `open`: falha conhecida ainda pendente; o teste permanece como sentinela.

## Incidentes

| ID | Plataforma | Status | Sintoma resumido |
|---|---|---|---|
| WIN-PS-PARSE-001 | Windows | fixed | PowerShell falhava no parse de `$LASTEXITCODE:` antes do fetch. |
| WIN-FETCH-002 | Windows | guarded | Falha de helper/binário precisava de diagnóstico e limpeza. |
| UNIX-FETCH-003 | macOS/Linux | fixed | Fetch do binário saía pelo `set -e` sem tratamento explícito. |
| AUTH-SHAPE-004 | Todas | fixed | Login válido em `user.email` era rejeitado. |
| DOC-INSTALL-005 | Todas | fixed | Docs apontavam para installers/canais inconsistentes em vez do bootstrap PyPI. |
| MCP-BOOT-006 | Todas | open | Testes ainda esperam o contrato antigo de login/MCP. |
| CODEX-HOOK-007 | Todas | open | Política do hook versionado diverge do teste. |
| UNINSTALL-008 | Todas | open | Contrato de uninstall/rollback diverge dos scripts atuais. |
| MACOS-X64-009 | macOS Intel | open | Teste ainda exige alias `macos-x86_64`; tabela/manifest usam `macos-x64`. |
| BENCH-010 | CI | open | Auditoria de timing/relatório não está determinística no ambiente atual. |
| PYPI-MANIFEST-011 | Packaging | open | Pin padrão do instalador PyPI diverge do checkout versionado. |

## Regras para novos incidentes

1. Registrar o sintoma reproduzível e a plataforma antes de alterar o instalador.
2. Apontar causa provável, proteção esperada e teste de regressão.
3. Marcar `open` quando o contrato ainda exigir decisão; não transformar falha em
   skip silencioso.
4. Quando corrigido, atualizar o status e registrar o commit de resolução.
5. Executar o teste específico e a validação progressiva antes de publicar.

Última auditoria: o registro também cobre o contrato público do bootstrap PyPI.
O caso UNIX-FETCH-003 permanece coberto pelo mesmo patch.

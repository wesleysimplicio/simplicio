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
| MCP-BOOT-006 | Todas | fixed | Handshake MCP agora depende de login ativo e não testa staging. |
| CODEX-HOOK-007 | Todas | fixed | Codex é opt-in e exige hook versionado explícito. |
| UNINSTALL-008 | Todas | fixed | Keep-data, purge confirmado e rollback estão explícitos nos instaladores. |
| MACOS-X64-009 | macOS Intel | fixed | Teste e instalador usam o alvo canônico `macos-x64`. |
| BENCH-010 | CI | fixed | Wrappers npm e manifesto estão alinhados em 3.8.25. |
| PYPI-MANIFEST-011 | Packaging | fixed | Pin PyPI 3.8.25 confere com o manifest público. |

## Regras para novos incidentes

1. Registrar o sintoma reproduzível e a plataforma antes de alterar o instalador.
2. Apontar causa provável, proteção esperada e teste de regressão.
3. Marcar `open` quando o contrato ainda exigir decisão; não transformar falha em
   skip silencioso.
4. Quando corrigido, atualizar o status e registrar o commit de resolução.
5. Executar o teste específico e a validação progressiva antes de publicar.

Última auditoria: o registro também cobre o contrato público do bootstrap PyPI.
O caso UNIX-FETCH-003 permanece coberto pelo mesmo patch.

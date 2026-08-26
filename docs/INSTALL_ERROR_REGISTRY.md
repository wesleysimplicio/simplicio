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
| RELEASE-TAG-012 | Todas | fixed | Pin `3.8.25` montava URL sem o prefixo `v` no GitHub Release. |
| SWAP-ACTIVATION-013 | macOS/Linux | fixed | Linha duplicada podia impedir o binário staged de virar o ativo. |
| PYPI-PUBLIC-014 | Todas | fixed | O smoke público detectou pacote ausente no PyPI e passou a bloquear releases sem publicação. |
| MCP-TOML-PATH-015 | Todas | fixed | TOML do MCP usava barras invertidas do Windows ou `~`, gerando escape inválido/caminho não absoluto. |
| LOCAL-RELEASE-016 | Release | fixed | A publicação dependia de automação hospedada, embora a operação oficial seja local e manual. |
| POST-SMOKE-CLI-017 | Release | fixed | O publicador chamava o smoke final com a opção inexistente `--repository`. |
| PYPI-MANIFEST-011 | Packaging | fixed | Pin PyPI 3.8.25 confere com o manifest público. |

## Regras para novos incidentes

1. Registrar o sintoma reproduzível e a plataforma antes de alterar o instalador.
2. Apontar causa provável, proteção esperada e teste de regressão.
3. Marcar `open` quando o contrato ainda exigir decisão; não transformar falha em
   skip silencioso.
4. Quando corrigido, atualizar o status e registrar o commit de resolução.
5. Executar o teste específico e a validação progressiva antes de publicar.

Última auditoria local: 196 testes Pytest + 30 subtestes, 69 testes do runner Python e 15 testes Node passaram antes da v3.8.30.
O registro cobre os contratos públicos de bootstrap PyPI, MCP, Codex, uninstall, rollback, publicação local e alvos macOS.

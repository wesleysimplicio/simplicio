# simplicio no Ecossistema Simplicio

## Quem depende deste repo
Consumidores finais via release do Runtime e, opcionalmente, via `npx @wesleysimplicio/simplicio`.

## De quem este repo depende
- [simplicio-runtime](https://github.com/wesleysimplicio/simplicio-runtime) — fonte do binário compilado e do bundle nativo incluído no release

## Regra de distribuição

O Runtime binário é a fronteira de instalação. Cada release compatível deve
conter e verificar estas seis superfícies nativas:

- Mapper
- Dev CLI
- Loop
- Fast
- Prompt
- Sprint projection

O instalador chama apenas `simplicio ecosystem verify --json`. Ele não instala
pacotes Python, não clona os repositórios `simplicio-*` e não substitui o
Runtime por um checkout local. Adapters legados podem ser acionados somente por
um fluxo explícito fora do instalador.

Validação local:

```bash
simplicio ecosystem verify --json
```

O resultado deve listar a versão real, commit de proveniência, modo de
implementação e compatibilidade de cada componente.

## Estado do manifest público

O manifest atualmente publicado neste repositório ainda é o `3.6.7`, um
release legado de transição. A próxima publicação do Runtime precisa substituir
seus artefatos pelos binários que passam na verificação do bundle acima; esta
documentação não declara que o asset legado já contém os seis componentes.

## Versão mínima esperada pelos dependentes
Nenhuma — repo é ponto de entrada para usuários finais.

---

_Last updated: 2026-08-14_

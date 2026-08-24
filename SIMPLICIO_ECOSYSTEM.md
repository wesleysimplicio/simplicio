# simplicio no Ecossistema Simplicio

## Quem depende deste repo
Consumidores finais via release do Runtime e, opcionalmente, via `npx @wesleysimplicio/simplicio`.

## De quem este repo depende
- [simplicio-runtime](https://github.com/wesleysimplicio/simplicio-runtime) — fonte do binário compilado e do bundle Python que a próxima release compatível deve incluir

## Versão atual

3.8.24 (release pública assinada; quatro alvos)

## Regra de distribuição

O Runtime binário é a fronteira de instalação. Cada release compatível deve
conter e verificar as fontes Python reais destas seis superfícies, sem
reescrevê-las como Rust nativo:

- Mapper
- Dev CLI
- Loop
- Fast
- Prompt
- Sprint

O instalador deve validar `simplicio version --json` e
`simplicio ecosystem doctor --json`. Ele não instala pacotes Python, não clona
os repositórios `simplicio-*` e não substitui o Runtime por um checkout local.
Adapters legados podem ser acionados somente por um fluxo explícito fora do
instalador.

Validação local:

```bash
simplicio version --json
simplicio ecosystem doctor --json
```

O resultado deve listar a versão real, commit de proveniência, contrato de
segurança, estado de login e compatibilidade dos componentes. A ausência de
`source_code_distributed=true`, login ativo ou chave pública é um bloqueio de
release, não uma advertência ignorável.

## Estado do manifest público

O manifest atualmente publicado neste repositório é o `3.8.20`. Esta release
publica os quatro alvos canônicos (macOS Apple Silicon, macOS Intel, Linux x64
e Windows x64), cada um com SHA256 e sidecar Ed25519. O binário informa
`source_code_distributed=true`, `identity.enabled/login_enabled=true` e
`security.signature_required/public_key_configured=true`. O instalador continua
fail-closed: exige bundle Python embutido, login Google ativo e manifest
assinado.

## Versão mínima esperada pelos dependentes
Nenhuma — repo é ponto de entrada para usuários finais.

---

_Last updated: 2026-08-20_

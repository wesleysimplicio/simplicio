# 🌌 Integração Asolaria — Binary/Host-8 Distribution

> **Documento de Arquitetura e Implementação**
> _Simplicio Public Distribution Repository — simplicio_
>
> **Nota de alinhamento público (v3.8.16):** este documento contém arquitetura,
> histórico e roadmap Host-8/Asolaria. Para instalar o produto atual, prevalecem
> INSTALL.md, MCP-CONNECT.md, distribution/targets.json e
> simplicio-update-manifest.json. A release pública é um binário único por
> target; o instalador verifica SHA256 + Ed25519 e registra automaticamente os
> clientes MCP detectados. O login Google continua obrigatório ao usar recursos
> protegidos do Runtime, mas não bloqueia a configuração inicial.

---

## Sumário

1. [Contexto e Fundamentos](#1-contexto-e-fundamentos)
2. [Host-8 Binary Distribution Format (P0)](#2-host-8-binary-distribution-format-p0)
3. [Cipher Doctrine — Assinatura de Binários (P0)](#3-cipher-doctrine--assinatura-de-binários-p0)
4. [Binary/Hash/Hex/Crypto Tuple (P1)](#4-binaryhashhexcrypto-tuple-p1)
5. [Process Scoreboard (P1)](#5-process-scoreboard-p1)
6. [Rust Host-8 Migration Path (P2)](#6-rust-host-8-migration-path-p2)
7. [Fabric-First Verify Pipeline (P2)](#7-fabric-first-verify-pipeline-p2)
8. [Scoreboard Atual](#8-scoreboard-atual)
9. [Roadmap e Métricas de Sucesso](#9-roadmap-e-métricas-de-sucesso)
10. [Referências](#10-referências)

---

## 1. Contexto e Fundamentos

### 1.1 O que é Asolaria?

**Asolaria** (JesseBrown1980) é um ecossistema conceitual e técnico que define substratos de quarta geração para computação distribuída, verificação de proveniência e formatos de comunicação compactos. Dois conceitos são críticos para o **simplicio** enquanto repositório público de distribuição de binários:

### 1.2 HYPER-BECHS — The Third Set

O [HYPER-BECHS — the third set](https://github.com/JesseBrown1980/HYPER-BECHS--the-third-set) define a 4ª geração do substrato Asolaria, com ênfase em:

| Conceito | Definição | Aplicação no Simplicio |
|----------|-----------|------------------------|
| **Rust Host-8 Migration** | json=0, pixels-first, binary compacto, 8-byte host | Formato de distribuição binária compacta |
| **Binary/Hash/Hex/Crypto Tuple** | Todo artefato representado nos 4 formatos | Manifesto de atualização estendido |
| **Process Scoreboard** | Rastreamento de processos/daemons no HYPER-BECHS | Scoreboard de binários do runtime |

### 1.3 Asolaria Cipher Doctrine

A [Fabric-First Cipher Doctrine](https://github.com/JesseBrown1980/HYPER-BECHS--the-third-set/blob/acer/system-interpretations-2026-06-26/FABRIC-FIRST-CIPHER-ASOLARIA-AGENT-DOCTRINE-2026-06-27.md) define:

- **Fabric-First**: O tecido (fabric) é o dado bruto. O cipher é a camada de verificação em cima do fabric.
- **Integridade de Binário**: SHA256SUMS não é suficiente — precisa de assinatura + cadeia de proveniência.
- **Cadeia Completa**: build → sign → publish → verify. Rejeitar binário se qualquer elo falhar.

### 1.4 Estado Atual do Simplicio

O repositório **simplicio** (`wesleysimplicio/simplicio`) distribui binários compilados do runtime Rust para macOS (ARM64/x86_64), Linux (x86_64) e Windows (x86_64). O pipeline atual inclui:

- **SHA256SUMS** — checksums SHA256 de todos os artefatos de distribuição
- **`simplicio-update-manifest.json`** — manifesto de atualização com schema v1
- **install.sh / install.ps1** — instaladores que baixam binários do GitHub Releases
- **`scripts/verify_distribution_consistency.py`** — auditoria de consistência da distribuição

A integração Asolaria evolui este pipeline para ser **mais seguro, mais compacto e totalmente verificável**.

---

## 2. Host-8 Binary Distribution Format (P0)

### 2.1 Definição do Formato

O formato **Host-8** é um encapsulamento binário compacto com header de 8 bytes + body comprimido (zstd), seguindo o princípio **json=0** e **pixels-first** do HYPER-BECHS.

```
┌────────────────────────────────────────────────┐
│              HOST-8 HEADER (8 bytes)             │
├──────────┬────────┬──────┬───────┬──────────────┤
│ Magic (2) │ Ver (2)│ Arch(1)│ Flags(1)│ Reserved(2)│
│ 0x484D    │ 0x0001 │ 0x01  │ 0x00   │ 0x0000      │
├──────────┴────────┴──────┴───────┴──────────────┤
│                                                   │
│           ZSTD-COMPRESSED BINARY BODY             │
│                                                   │
└────────────────────────────────────────────────┘
```

**Campos do Header:**

| Offset | Tamanho | Campo | Descrição |
|--------|---------|-------|-----------|
| 0      | 2 bytes | **Magic Number** | `0x484D` ("HM" — Host Manifest) |
| 2      | 2 bytes | **Version** | `0x0001` (versão 1 do formato) |
| 4      | 1 byte  | **Architecture** | `0x00`=arm64, `0x01`=x86_64, `0x02`=aarch64 |
| 5      | 1 byte  | **Flags** | Bit 0: signed (1) / unsigned (0); Bits 1-7: reservado |
| 6      | 2 bytes | **Reserved** | Zero-filled, para expansão futura |

### 2.2 Implementação

#### CLI: Detecção e Extração

```bash
# Detectar se um binário está no formato Host-8
simplicio --host8 detect ./simplicio

# Extrair binário do formato Host-8
simplicio --host8 extract ./simplicio.h8 -o ./simplicio

# Empacotar binário no formato Host-8
simplicio --host8 pack ./simplicio -o ./simplicio.h8
```

**Flags de arquitetura:**

| Flag | Significado |
|------|-------------|
| `--host8` | Ativa modo Host-8 (detecta formato automaticamente) |
| `--host8-always-pack` | Sempre empacota saída em Host-8 |
| `--host8-no-verify` | Pula verificação de assinatura ao extrair |

#### Formatos de Artefato Publicados

O pipeline de release passará a publicar **dois formatos** por plataforma:

```
simplicio                                 # Binário raw (existente)
simplicio.h8                              # Host-8 empacotado (NOVO)
simplicio-windows-x64.exe                 # Binário raw Windows (existente)
simplicio-windows-x64.h8                  # Host-8 Windows (NOVO)
simplicio-linux-x64                       # Binário raw Linux (existente)
simplicio-linux-x64.h8                    # Host-8 Linux (NOVO)
simplicio-darwin-arm64                    # Binário raw macOS ARM (existente)
simplicio-darwin-arm64.h8                 # Host-8 macOS ARM (NOVO)
```

### 2.3 Integração com Instaladores

O `install.sh` e `install.ps1` ganham suporte a Host-8 via variável de ambiente:

```bash
# Instalação tradicional (binário raw)
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh

# Instalação via Host-8 (formato compacto)
SIMPLICIO_HOST8=1 curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```

O instalador com `SIMPLICIO_HOST8=1`:
1. Baixa o artefato `.h8` em vez do raw
2. Verifica o magic number `0x484D`
3. Extrai o binário (zstd decompression)
4. Verifica assinatura (se signed flag estiver setada)
5. Instala o binário extraído

### 2.4 Vantagens

| Aspecto | Binário Raw | Host-8 |
|---------|------------|--------|
| Tamanho | ~26 MB (Windows) | ~8-10 MB (com zstd) |
| Verificação embutida | ❌ (separada em SHA256SUMS) | ✅ (flags + assinatura no header) |
| Auto-descritivo | ❌ | ✅ (arquitetura + versão no header) |
| Compatibilidade retroativa | ✅ | ✅ (instalador detecta automaticamente) |

---

## 3. Cipher Doctrine — Assinatura de Binários (P0)

### 3.1 Princípio Fabric-First

A Cipher Doctrine estabelece que **SHA256SUMS não é suficiente**. Todo binário distribuído deve ter:

1. **SHA256** do binário (fabric hash — já existe)
2. **Assinatura Ed25519** do SHA256 (cipher signature — NOVO)
3. **Fingerprint** da chave pública que assinou
4. **Cadeia de proveniência** documentada: _quem construiu → quem assinou → como foi publicado_

### 3.2 Schema Estendido do Manifesto

O `simplicio-update-manifest.json` atual já possui campos de `signature` (vazios). O schema evolui para v2:

```json
{
  "schema": "simplicio.update-manifest/v2",
  "version": "1.6.4",
  "channel": "stable",
  "security": {
    "checksum_algorithm": "SHA256",
    "signature_algorithm": "ed25519",
    "signature_required": true,
    "refuse_unsigned": true,
    "signing_key_fingerprint": "SHA256:abc123...",
    "signing_key_url": "https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/docs/signing-public-key.pem",
    "provenance_chain": [
      {"step": "build", "actor": "simplicio-runtime CI", "verified_by": "sha256( source_tree )"},
      {"step": "sign",  "actor": "release-bot",           "verified_by": "ed25519( sha256( binary ) )"},
      {"step": "publish","actor": "github-releases",       "verified_by": "signature on manifest"}
    ]
  },
  "artifacts": [
    {
      "target": "windows-x86_64",
      "artifact": "simplicio-windows-x86_64.exe",
      "sha256": "93860620f29344251823ebb22e65702e904d39a987108c0a12874d5ea289dba0",
      "hex": "93860620f29344251823ebb22e65702e904d39a987108c0a12874d5ea289dba0",
      "signature": "MC0CFQ...base64-ed25519-signature...",
      "signature_algorithm": "ed25519",
      "signing_key_fingerprint": "SHA256:abc123..."
    }
  ]
}
```

**Mudanças do v1 para v2:**

| Campo | v1 | v2 |
|-------|----|----|
| `schema` | `simplicio.update-manifest/v1` | `simplicio.update-manifest/v2` |
| `security.signing_key_fingerprint` | ❌ | ✅ |
| `security.signing_key_url` | ❌ | ✅ |
| `security.provenance_chain` | ❌ | ✅ |
| `artifacts[].signature` | `""` (vazio) | assinatura Ed25519 real |
| `artifacts[].hex` | ❌ | ✅ (SHA256 em hex) |
| `artifacts[].signing_key_fingerprint` | ❌ | ✅ |

### 3.3 Geração de Chaves e Processo de Assinatura

```bash
# 1. Gerar par de chaves Ed25519 para distribuição
simplicio crypto generate-key -o ./keys/simplicio-signing-key
#   → ./keys/simplicio-signing-key (privada, NUNCA comitar)
#   → ./keys/simplicio-signing-key.pub (pública, comitar)

# 2. Assinar um binário
simplicio crypto sign --key ./keys/simplicio-signing-key \
  --binary ./simplicio \
  --output ./simplicio.sig

# 3. Verificar assinatura
simplicio crypto verify --key ./keys/simplicio-signing-key.pub \
  --binary ./simplicio \
  --signature ./simplicio.sig

# 4. Verificar binário instalado
simplicio verify --signature
```

### 3.4 Chave Pública e Distribuição

A chave pública de assinatura é versionada e commitada no repositório:

```
docs/
├── signing-public-key.pem               # Chave pública atual
├── signing-public-key.v1.pem            # Versão anterior (rotação)
└── signing-key-changelog.md             # Histórico de rotação de chaves
```

O fingerprint da chave pública é incluído no manifesto e verificado pelo instalador.

### 3.5 Verificação no Instalador

O `install.sh` ganha o passo opcional de verificação de assinatura:

```bash
# Atual: baixa e instala
# Novo: baixa, baixa assinatura, baixa chave pública, verifica, instala

if [ "${SIMPLICIO_VERIFY_SIGNATURE:-}" = "1" ]; then
  info "verifying Ed25519 signature..."
  PUBLIC_KEY_URL="$RAW/docs/signing-public-key.pem"
  SIGNATURE_URL="$GITHUB/releases/download/$VERSION/$ASSET.sig"
  curl -sSfL "$PUBLIC_KEY_URL" -o "$TMP_DIR/public-key.pem"
  curl -sSfL "$SIGNATURE_URL" -o "$TMP_DIR/binary.sig"
  if "$BINARY_SRC" crypto verify \
    --key "$TMP_DIR/public-key.pem" \
    --binary "$BINARY_SRC" \
    --signature "$TMP_DIR/binary.sig" 2>/dev/null; then
    ok "signature verified"
  else
    err "signature verification FAILED — binary may be tampered"
  fi
fi
```

---

## 4. Binary/Hash/Hex/Crypto Tuple (P1)

### 4.1 Definição do Tuple

Seguindo o substrato HYPER-BECHS, todo artefato de distribuição é representado em 4 formatos:

| Formato | Descrição | Exemplo |
|---------|-----------|---------|
| **Binary** | URL do binário hospedado | `https://github.com/.../simplicio-darwin-arm64` |
| **Hash** | SHA256 do binário (bytes) | `50affbf647d9...` |
| **Hex** | Representação hex do hash | `50affbf647d9...` (idêntico ao hash, mas semanticamente distinto) |
| **Crypto** | Assinatura Ed25519 em base64 | `MC0CFQ...` |

### 4.2 Manifesto Estendido com Tuple

```json
{
  "artifacts": [
    {
      "target": "macos-arm64",
      "binary_url": "https://github.com/wesleysimplicio/simplicio/releases/download/v1.6.4/simplicio-macos-arm64",
      "binary_url_host8": "https://github.com/wesleysimplicio/simplicio/releases/download/v1.6.4/simplicio-macos-arm64.h8",
      "hash": {
        "algorithm": "SHA256",
        "value": "50affbf647d9bb032049d7be86ce8f700b28ccec6df016d0c58cdcfd2d84db4c"
      },
      "hex": "50affbf647d9bb032049d7be86ce8f700b28ccec6df016d0c58cdcfd2d84db4c",
      "crypto": {
        "algorithm": "Ed25519",
        "signature": "MC0CFQ...",
        "key_fingerprint": "SHA256:abc123..."
      }
    }
  ]
}
```

### 4.3 Verificação Cruzada

O comando `simplicio verify --tuple` verifica a integridade dos 4 formatos:

```bash
simplicio verify --tuple --manifest simplicio-update-manifest.json

# Output esperado:
# ✓ Binary: accessible at URL
# ✓ Hash: sha256 matches downloaded binary
# ✓ Hex: matches hash value
# ✓ Crypto: ed25519 signature verified
# → Tuple: INTEGRITY PASSED
```

---

## 5. Process Scoreboard (P1)

### 5.1 Definição

O **Process Scoreboard** é um rastreamento formal de todos os binários e processos no ecossistema Simplicio, modelado a partir do scoreboard do HYPER-BECHS (acer/liris colonies). Cada entrada documenta: role, arquivo, plataforma, status e elegibilidade para Host-8.

### 5.2 Formato do Scoreboard

O scoreboard é publicado como `SCOREBOARD.md` na raiz do repositório e inclui:

| Role | Arquivo | Plataforma | Status | Host-8 Ready | Notas |
|------|---------|------------|--------|--------------|-------|
| **Runtime** | `simplicio` | macOS ARM64 | ✅ stable | ✅ yes | Binário principal Rust |
| **Runtime** | `simplicio` | macOS x86_64 | ✅ stable | ✅ yes | Binário principal Rust |
| **Runtime** | `simplicio` | Linux x86_64 | ✅ stable | ✅ yes | Binário principal Rust |
| **Runtime** | `simplicio.exe` | Windows x86_64 | ✅ stable | ✅ yes | Binário principal Rust |
| **Update Manifest** | `simplicio-update-manifest.json` | Cross-platform | ✅ stable | 🔄 in-progress | Schema v2 com tuple |
| **Package (npm)** | `npm/simplicio/package.json` | Cross-platform | ✅ stable | ⬜ n/a | Wrapper npm |
| **Package (PyPI)** | `pypi/simplicio/pyproject.toml` | Cross-platform | ✅ stable | ⬜ n/a | Wrapper PyPI |
| **Installer (sh)** | `install.sh` | macOS/Linux | ✅ stable | 🔄 in-progress | Com suporte Host-8 |
| **Installer (ps1)** | `install.ps1` | Windows | ✅ stable | 🔄 in-progress | Com suporte Host-8 |
| **Badge vsix** | `simplicio-badge.vsix` | Cross-platform | ✅ stable | ⬜ n/a | VS Code badge |
| **CI/CD** | `.github/workflows/release.yml` | Cross-platform | ✅ stable | 🔄 in-progress | Fabric-first verify |
| **Audit Script** | `scripts/verify_distribution_consistency.py` | Cross-platform | ✅ stable | ⬜ n/a | Auditoria de distribuição |

### 5.3 Status Definitions

| Status | Significado |
|--------|-------------|
| ✅ **stable** | Em produção, completamente funcional |
| 🔄 **in-progress** | Migração ativa para Host-8 ou Cipher Doctrine |
| ⚠️ **beta** | Em teste, pode ter alterações |
| ❌ **deprecated** | Substituído, manter apenas para compatibilidade retroativa |

---

## 6. Rust Host-8 Migration Path (P2)

### 6.1 Motivação

O ecossistema Simplicio inclui adaptadores e gateways (Discord, Telegram, Slack, WhatsApp) que atualmente são implementados como processos Node.js. A migração para **Rust Host-8** significa:

1. Reescrever cada daemon Node.js como um processo Rust
2. Adotar o protocolo Host-8 (8-byte header, binary frames)
3. Eliminar dependência de Node.js runtime
4. Reduzir consumo de memória e latência

### 6.2 Mapeamento de Daemons

| Daemon | Linguagem Atual | Host-8 Candidate? | Prioridade | Estimativa |
|--------|----------------|-------------------|------------|------------|
| Discord Adapter | Node.js | ✅ yes | Alta | ~2 semanas |
| Telegram Gateway | Node.js | ✅ yes | Alta | ~2 semanas |
| Slack Adapter | Node.js | ✅ yes | Média | ~3 semanas |
| WhatsApp Gateway | Node.js | ✅ yes | Média | ~3 semanas |
| Gateway Guardian | Node.js | ✅ yes | Baixa | ~4 semanas |
| MCP Adapter | Rust (já) | ✅ yes | Concluído | — |
| ACP Adapter | Rust (já) | ✅ yes | Concluído | — |

### 6.3 Scoreboard de Migração

O scoreboard será mantido no `SCOREBOARD.md` e atualizado a cada release:

```markdown
## Host-8 Migration Scoreboard

| Daemon | Source | Status | Host-8? | Target Release |
|--------|--------|--------|---------|----------------|
| Discord Adapter | `gateways/discord/` | ⬜ planned | yes | v2.0 |
| Telegram Gateway | `gateways/telegram/` | ⬜ planned | yes | v2.0 |
| Slack Adapter | `gateways/slack/` | ⬜ backlog | yes | v2.1 |
| WhatsApp Gateway | `gateways/whatsapp/` | ⬜ backlog | yes | v2.1 |
| Gateway Guardian | `guardian/` | ⬜ backlog | yes | v2.2 |
| MCP Adapter | `mcp/` | ✅ done | yes | v1.6 |
| ACP Adapter | `acp/` | ✅ done | yes | v1.6 |
```

---

## 7. Fabric-First Verify Pipeline (P2)

### 7.1 O Princípio

**Fabric-First** significa que a verificação começa pelo dado bruto (fabric) antes de qualquer camada de cipher. No pipeline de CI/CD:

1. **Build** produz o binário
2. **Fabric Check**: verifica que o binário foi construído a partir do source tree correto (SHA256 do source == esperado)
3. **Sign**: assina o binário com Ed25519
4. **Publish**: publica apenas se fabric check + signature passarem
5. **Verify**: pós-publicação, verifica que o binário publicado corresponde ao fabric

### 7.2 Script de Verificação

```bash
#!/usr/bin/env bash
# scripts/verify-fabric.sh — Fabric-First verification
# Verifies that a built binary corresponds to the correct source tree.

set -euo pipefail

VERSION="${1:-}"
BINARY="${2:-./simplicio}"
SOURCE_ROOT="${3:-.}"

echo "=== Fabric-First Verify ==="

# 1. Compute source tree checksum
echo "[fabric] computing source tree checksum..."
SOURCE_HASH=$(find "$SOURCE_ROOT" -type f \
  -not -path '*/.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/target/*' \
  -not -name '*.png' -not -name '*.svg' \
  -not -name 'simplicio*' \
  | sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
echo "[fabric] source tree hash: $SOURCE_HASH"

# 2. Compute binary hash
echo "[fabric] computing binary checksum..."
BINARY_HASH=$(shasum -a 256 "$BINARY" | cut -d' ' -f1)
echo "[fabric] binary hash: $BINARY_HASH"

# 3. Check that binary was built from this source
# In CI, we compare against expected hash from the build manifest
if [ -n "$VERSION" ]; then
  EXPECTED_HASH=$(python3 -c "
import json
m = json.load(open('simplicio-update-manifest.json'))
for a in m.get('artifacts', []):
    print(a.get('sha256', ''))
" 2>/dev/null | grep . || echo "")
  if [ -n "$EXPECTED_HASH" ] && [ "$BINARY_HASH" != "$EXPECTED_HASH" ]; then
    echo "[fabric] FAIL: binary hash $BINARY_HASH does not match manifest $EXPECTED_HASH"
    exit 1
  fi
fi

# 4. Sign (if signing key available)
if [ -f "./keys/simplicio-signing-key" ]; then
  echo "[cipher] signing binary with Ed25519..."
  ./simplicio crypto sign \
    --key ./keys/simplicio-signing-key \
    --binary "$BINARY" \
    --output "$BINARY.sig"
  echo "[cipher] signature: $(cat "$BINARY.sig" | head -c 40)..."
fi

echo "=== Fabric-First PASSED ==="
```

### 7.3 Integração com dod.yml / CI

O script `verify-fabric.sh` é integrado ao pipeline de release:

```yaml
# .github/workflows/release.yml (trecho)
jobs:
  verify-fabric:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify Fabric
        run: |
          bash scripts/verify-fabric.sh \
            "${GITHUB_REF_NAME}" \
            "./simplicio-linux-x64" \
            "."
  publish:
    needs: [verify-fabric, build]
    steps:
      - name: Publish only if fabric check passed
        run: |
          echo "Fabric verification passed — publishing..."
```

---

## 8. Scoreboard Atual

### 8.1 Artefatos de Distribuição

| Artefato | Formato | SHA256 | Assinatura | Host-8 |
|----------|---------|--------|------------|--------|
| `simplicio` (macOS ARM64) | Raw binary | `50affb...` | ⬜ vazio | 🔄 planned |
| `simplicio-darwin-x64` | Raw binary | `931975...` | ⬜ vazio | 🔄 planned |
| `simplicio-linux-x64` | Raw binary | `78337e...` | ⬜ vazio | 🔄 planned |
| `simplicio-windows-x64.exe` | Raw binary | `938606...` | ⬜ vazio | 🔄 planned |
| `simplicio-windows-x64.zip` | Zip archive | `1eedc9...` | ⬜ vazio | 🔄 planned |
| `simplicio-package-manager-manifests.zip` | Zip archive | `b3836c...` | ⬜ vazio | 🔄 planned |
| `simplicio-update-manifest.json` | JSON (v1) | — | — | 🔄 planned (v2) |

### 8.2 Processos do Ecossistema

| Processo | Runtime | Status | Notas |
|----------|---------|--------|-------|
| Simplicio CLI (Rust) | Rust | ✅ stable | Binário principal |
| `verify_distribution_consistency.py` | Python | ✅ stable | Auditoria de distribuição |
| install.sh | Shell | ✅ stable | Instalador Unix |
| install.ps1 | PowerShell | ✅ stable | Instalador Windows |
| Discord Gateway | Node.js | 🔄 migrating to Rust | Prioridade alta |
| Telegram Gateway | Node.js | 🔄 planned | — |
| Slack Adapter | Node.js | ⬜ backlog | — |
| WhatsApp Gateway | Node.js | ⬜ backlog | — |
| GitHub Actions CI | YAML/CI | ✅ stable | Release pipeline |

---

## 9. Roadmap e Métricas de Sucesso

### 9.1 Fases

| Fase | Prioridade | Itens | Release Alvo |
|------|-----------|-------|--------------|
| **🔴 P0** | Crítica | Host-8 format, Ed25519 signatures, manifesto v2 | v1.7.0 |
| **🟡 P1** | Alta | Binary/Hash/Hex/Crypto tuple, Process Scoreboard | v1.8.0 |
| **🔵 P2** | Média | Rust migration, Fabric-First verify pipeline | v2.0.0 |

### 9.2 Métricas de Sucesso

- [ ] **P0.1** Host-8 binary format implementado e distribuível (`simplicio --host8 pack/extract/detect`)
- [ ] **P0.2** Ed25519 signature pipeline funcional (sign + verify no CI)
- [ ] **P0.3** `simplicio-update-manifest.json` atualizado para schema v2 com signatures reais
- [ ] **P0.4** `install.sh` com suporte a verificação de assinatura (`SIMPLICIO_VERIFY_SIGNATURE=1`)
- [ ] **P1.1** Binary/Hash/Hex/Crypto tuple completo no manifesto
- [ ] **P1.2** `SCOREBOARD.md` publicado com scoreboard completo
- [ ] **P1.3** `simplicio verify --tuple` implementado
- [ ] **P2.1** `scripts/verify-fabric.sh` integrado ao CI
- [ ] **P2.2** Scoreboard de migração Host-8 atualizado a cada release

### 9.3 Dependências

| Item | Depende de | Bloqueia |
|------|-----------|----------|
| Host-8 format | — | P1.1, P2.2 |
| Ed25519 signing keys | — | P0.2, P0.3, P0.4 |
| Manifesto v2 | P0.2 | P1.1 |
| Scoreboard | P1.1 | P2.2 |
| Fabric-First verify | — | P2.1 |

---

## 10. Referências

### 10.1 Documentos Asolaria

| Documento | Link |
|-----------|------|
| HYPER-BECHS — The Third Set | https://github.com/JesseBrown1980/HYPER-BECHS--the-third-set |
| Fabric-First Cipher Doctrine | https://github.com/JesseBrown1980/HYPER-BECHS--the-third-set/blob/acer/system-interpretations-2026-06-26/FABRIC-FIRST-CIPHER-ASOLARIA-AGENT-DOCTRINE-2026-06-27.md |
| Rust Host-8 Migration | https://github.com/JesseBrown1980/HYPER-BECHS--the-third-set (acer/liris colonies) |

### 10.2 Documentos Simplicio

| Documento | Descrição |
|-----------|-----------|
| `VERSION.md` | Estrutura do repositório (README primeiro) |
| `SIMPLICIO_ECOSYSTEM.md` | Dependências do ecossistema |
| `simplicio-update-manifest.json` | Manifesto de atualização (schema v1 atual) |
| `SHA256SUMS` | Checksums atuais dos binários |
| `scripts/verify_distribution_consistency.py` | Auditoria de consistência |
| `INSTALL.md` | Guia de instalação |
| `install.sh` | Instalador Unix |
| `install.ps1` | Instalador Windows |

### 10.3 Padrões Criptográficos

| Algoritmo | Propósito | Especificação |
|-----------|-----------|---------------|
| SHA-256 | Fabric hash (integridade do binário) | FIPS 180-4 |
| Ed25519 | Cipher signature (proveniência) | RFC 8032 |
| Zstandard (zstd) | Compressão do body Host-8 | RFC 8878 |

---

> **Status deste documento:** Rascunho inicial — documenta a arquitetura e o plano de implementação para a Integração Asolaria.
> **Última atualização:** 2026-07-03
> **Issue de referência:** [#3 — 🌌 Integração Asolaria: Binary/Host-8 Distribution](https://github.com/wesleysimplicio/simplicio/issues/3)

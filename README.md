# Simplicio Runtime

Este repositório é a porta de entrada do Simplicio. Clone o repositório e use
os instaladores versionados aqui para instalar o Runtime e os componentes CLI
do ecossistema. Não é necessário acessar um site externo.

O Runtime é distribuído como o binário nativo `simplicio` e expõe o Simplicio
MCP pelo comando `simplicio serve --mcp --stdio`.

## O que é instalado

Os instaladores baixam os assets oficiais das releases no GitHub:

| Componente | Distribuição instalada |
|---|---|
| Runtime / MCP | Binário nativo `simplicio` |
| Mapper | `simplicio-mapper` |
| Dev CLI | `simplicio-dev-cli` |
| Fast | `simplicio-fast` |
| Loop | `simplicio-loop` |
| Prompt | `simplicio-prompt` |
| Sprint | `simplicio-sprint` |

Mapper, Dev CLI, Fast, Loop, Prompt e Sprint são publicados como wheels Python
que fornecem seus executáveis CLI. O instalador usa uma virtualenv própria em
`~/.simplicio/components-venv` e não instala extras de inferência nem pesos de
LLM local.

## Instalação pelo repositório Git

### macOS Apple Silicon e Linux

Requer Python 3.11 ou superior, `curl` e `git`:

```sh
git clone https://github.com/wesleysimplicio/simplicio.git
cd simplicio
sh install.sh
```

O `install.sh`:

1. consulta as releases do Runtime em ordem decrescente;
2. escolhe o asset mais recente compatível com o sistema e a arquitetura;
3. recua para releases anteriores até encontrar Windows, macOS ou Linux quando
   a release mais recente não tiver aquele asset;
4. instala as wheels mais recentes disponíveis dos seis componentes;
5. verifica SHA-256 quando o asset publica digest no GitHub.

Para fixar uma release específica do Runtime:

```sh
SIMPLICIO_VERSION=v3.8.11 sh install.sh
```

### Windows

Requer Git, PowerShell 5.1+ e Python 3.11 ou superior:

```powershell
git clone https://github.com/wesleysimplicio/simplicio.git
Set-Location simplicio
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

O `install.ps1` aplica a mesma seleção por release. Na publicação atual, o
Runtime encontra os assets publicados para macOS Apple Silicon e Linux em
`v3.8.11` e o executável Windows na release anterior compatível. O instalador
não assume que todas as plataformas estejam na mesma tag.

Para fixar a release do Runtime no Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Version v3.8.10
```

## Releases e assets

As releases oficiais e seus assets ficam nos repositórios GitHub:

- [Runtime](https://github.com/wesleysimplicio/simplicio/releases)
- [Mapper](https://github.com/wesleysimplicio/simplicio-mapper/releases)
- [Dev CLI](https://github.com/wesleysimplicio/simplicio-dev-cli/releases)
- [Fast](https://github.com/wesleysimplicio/simplicio-fast/releases)
- [Loop](https://github.com/wesleysimplicio/simplicio-loop/releases)
- [Prompt](https://github.com/wesleysimplicio/simplicio-prompt/releases)
- [Sprint](https://github.com/wesleysimplicio/simplicio-sprint/releases)

O instalador não usa o site de marketing, PyPI como fonte dos componentes ou
modelos locais. Ele usa o GitHub para localizar as releases e instala as
wheels oficiais encontradas nelas; as dependências Python normais são
resolvidas pela virtualenv.

## Verificação

```sh
simplicio version
simplicio doctor
simplicio-mapper --help
simplicio-dev-cli --help
simplicio-fast --help
simplicio-loop --help
sendsprint --help
```

O Prompt fornece, entre outros, os comandos `simplicio-subagents`,
`simplicio-tui`, `simplicio-acp-adapter`, `simplicio-plugins` e
`simplicio-skills`.

## Configurar o Simplicio MCP

O comando do servidor MCP é:

```sh
simplicio serve --mcp --stdio
```

Exemplo de configuração para um cliente MCP:

```json
{
  "mcpServers": {
    "simplicio": {
      "command": "simplicio",
      "args": ["serve", "--mcp", "--stdio"]
    }
  }
}
```

Se o cliente não encontrar o executável, use o caminho absoluto instalado em
`~/.local/bin/simplicio` ou em `%USERPROFILE%\.local\bin\simplicio.exe`.

## Atualizar ou remover

Execute novamente o instalador para atualizar o Runtime e os componentes. Os
instaladores são idempotentes e mantêm a virtualenv sob `~/.simplicio`.

```sh
sh install.sh --doctor
sh install.sh --uninstall
```

No Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Doctor
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
```

## Licença

Proprietária. Consulte [LICENSE](LICENSE).

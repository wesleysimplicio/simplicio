# Conectando ao MCP do Simplicio Agent

O Simplicio Agent expõe **10 ferramentas MCP** que qualquer cliente compatível (Claude, Cursor, VS Code, Cline, Continue, etc.) pode consumir.

## Conexão via STDIO (recomendada)

Adicione no arquivo de configuração MCP do seu cliente:

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

### Onde colocar

| Cliente | Arquivo | Localização |
|---|---|---|
| **Claude Code** | `~/.claude/settings.json` | `mcpServers.simplicio` |
| **Cursor** | `~/.cursor/mcp.json` | `mcpServers.simplicio` |
| **VS Code** | `.vscode/mcp.json` | `mcpServers.simplicio` |
| **Cline** | `~/.config/cline/mcp_settings.json` | `mcpServers.simplicio` |
| **Continue** | `~/.continue/config.json` | `experimental.mcpServers.simplicio` |

## Conexão via HTTP

Se preferir HTTP em vez de STDIO:

```json
{
  "mcpServers": {
    "simplicio": {
      "url": "http://localhost:6119",
      "headers": {
        "Authorization": "Bearer seu-token-aqui"
      }
    }
  }
}
```

## Ferramentas expostas

| Ferramenta | Descrição |
|---|---|
| `simplicio_map` | Orientação estrutural do repositório |
| `simplicio_memory` | Recall da memória neural (FTS + vector) |
| `simplicio_edit` | Edição determinística de arquivos |
| `simplicio_gate` | Gate de missão |
| `simplicio_validate` | Validação contratual |
| `simplicio_run` | Execução completa de tarefas |
| `simplicio_symbol` | Navegação de símbolos |
| `simplicio_search` | Busca semântica |
| `simplicio_read` | Leitura otimizada de arquivos |
| `simplicio_exec` | Execução shell compactada |

## Verificando se está funcionando

```bash
# Teste rápido
simplicio runtime map --repo . --for-llm markdown

# Ver conexão
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | simplicio serve --mcp --stdio
```

## Instalação automática

O instalador único já configura o MCP automaticamente:

```bash
curl -fsSL https://raw.githubusercontent.com/wesleysimplicio/simplicio/master/install.sh | sh
```
